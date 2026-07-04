"""
Streamlit backend — pure functions for the Spotify Discovery dashboard.
No UI here; imported by the Streamlit frontend.
"""

import os
import json
import time
import re
import requests
import streamlit as st
from dotenv import load_dotenv
from groq import Groq
from supabase import create_client, Client

from ingestion.play_store import (
    scrape_play_store_reviews,
    normalize_review,
    upsert_reviews_to_supabase,
)

load_dotenv()


def _get_secret(key):
    """Read from st.secrets first, then fall back to environment variables."""
    try:
        value = st.secrets.get(key)
        if value:
            return value
    except Exception:
        pass
    return os.getenv(key)

# Reuse the classification taxonomy
TAXONOMY = """
You are classifying Spotify user reviews about music discovery. Classify each review according to this taxonomy:

frustration_type (must be one of):
- stale_recommendations: Same songs/artists repeated in recommendations
- filter_bubble_lock_in: Trapped in familiar content, unable to discover new music
- discovery_friction: Difficulty finding new music, poor discovery features
- algorithmic_sameness: All recommendations feel the same, predictable
- poor_new_release_surfacing: New releases not surfaced well
- context_blindness: Recommendations ignore context (time, mood, activity)
- over_personalization: Too personalized, no variety or exploration
- control_loss: User has no control over what's recommended
- none: Not related to discovery frustration

segment (must be one of):
- lapsed_explorer: Used to discover new music but stopped
- active_explorer: Still actively seeking new music
- passive_listener: Background listening, not seeking discovery
- genre_loyalist: Stays within specific genres
- mood_listener: Listens based on mood/context
- podcast_first: Primarily listens to podcasts
- unknown: Cannot determine segment

desired_behavior (must be one of):
- find_new_artists: Wants to discover new artists
- break_routine: Wants variety from usual listening
- match_mood_or_context: Wants music matching situation/mood
- deep_dive_genre: Wants to explore a specific genre deeply
- social_discovery: Wants music shared by friends/social
- rediscover_back_catalog: Wants to find old/forgotten music
- none: No specific desired behavior

Additional fields:
- root_cause: Brief explanation in 12 words or fewer
- unmet_need: Brief explanation in 12 words or fewer
- discovery_related: true if the review is about music discovery/recommendations, false otherwise
- sentiment: positive, neutral, or negative

Return ONLY valid JSON with these exact keys:
{
  "frustration_type": "...",
  "segment": "...",
  "desired_behavior": "...",
  "root_cause": "...",
  "unmet_need": "...",
  "discovery_related": true/false,
  "sentiment": "positive/neutral/negative"
}
"""

MAX_RETRIES = 3
SLEEP_BETWEEN_REQUESTS = 0.5
RETRY_BACKOFF = 2


def _get_groq_client():
    """Initialize Groq client from st.secrets or env."""
    api_key = _get_secret("GROQ_API_KEY")
    if not api_key:
        raise ValueError("GROQ_API_KEY not found in st.secrets or environment")
    return Groq(api_key=api_key)


def _get_supabase_client():
    """Initialize Supabase client from st.secrets or env."""
    url = _get_secret("SUPABASE_URL")
    key = _get_secret("SUPABASE_KEY")
    if not url or not key:
        raise ValueError("SUPABASE_URL and SUPABASE_KEY must be set in st.secrets or environment")
    return create_client(url, key)


def classify_single_review(text):
    """
    Classify a single raw review text using Groq.

    Args:
        text: Raw review text

    Returns:
        Classification dict, or None if classification failed
    """
    groq_client = _get_groq_client()
    prompt = f"{TAXONOMY}\n\nReview text:\n{text}\n\nClassification:"

    for attempt in range(MAX_RETRIES):
        try:
            response = groq_client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[
                    {
                        "role": "system",
                        "content": "You are a helpful assistant that classifies Spotify reviews according to a fixed taxonomy. Return ONLY valid JSON.",
                    },
                    {"role": "user", "content": prompt},
                ],
                temperature=0,
                response_format={"type": "json_object"},
            )

            result_text = response.choices[0].message.content

            # Strip JSON fences if present
            result_text = re.sub(r"^```json\s*", "", result_text)
            result_text = re.sub(r"^```\s*", "", result_text)
            result_text = re.sub(r"\s*```$", "", result_text)

            return json.loads(result_text)

        except Exception as e:
            error_str = str(e)

            if "rate_limit_exceeded" in error_str and "tokens" in error_str:
                time_match = re.search(r"Please try again in (\d+m)?(\d+\.?\d*)s?", error_str)
                if time_match:
                    minutes = int(time_match.group(1)[:-1]) if time_match.group(1) else 0
                    seconds = float(time_match.group(2))
                    wait_time = minutes * 60 + seconds
                    time.sleep(wait_time)
                    continue

            if "429" in error_str and attempt < MAX_RETRIES - 1:
                time.sleep(RETRY_BACKOFF)
                continue

            print(f"Classification error: {e}")
            return None

    return None


def run_live_ingestion(n=10):
    """
    Scrape latest Play Store reviews (7 days), classify them, and upsert to DB.

    Args:
        n: Maximum number of newly scraped reviews to classify and return

    Returns:
        List of dicts with review_text, rating, segment, frustration_type,
        discovery_related, sentiment
    """
    print("Starting live ingestion...")

    # 1. Scrape (7 days only for fast demo)
    raw_reviews = scrape_play_store_reviews(
        app_id="com.spotify.music", days=7, lang="en", countries=["us"]
    )
    if not raw_reviews:
        print("No reviews scraped.")
        return []

    # 2. Normalize
    normalized = [normalize_review(r) for r in raw_reviews]
    print(f"Normalized {len(normalized)} reviews")

    # 3. Upsert raw reviews to Supabase
    upsert_reviews_to_supabase(normalized)

    # 4. Classify up to n reviews
    results = []
    for review in normalized[:n]:
        classification = classify_single_review(review["text"])
        if not classification:
            continue

        # Upsert classification
        supabase = _get_supabase_client()
        tagged = {
            "id": review["id"],
            "frustration_type": classification.get("frustration_type"),
            "segment": classification.get("segment"),
            "desired_behavior": classification.get("desired_behavior"),
            "root_cause": classification.get("root_cause"),
            "unmet_need": classification.get("unmet_need"),
            "discovery_related": classification.get("discovery_related"),
            "sentiment": classification.get("sentiment"),
        }
        try:
            supabase.table("tagged_reviews").upsert(tagged, on_conflict="id").execute()
        except Exception as e:
            print(f"Upsert tagged review failed: {e}")
            continue

        results.append(
            {
                "review_text": review["text"],
                "rating": review["rating"],
                "segment": classification.get("segment"),
                "frustration_type": classification.get("frustration_type"),
                "discovery_related": classification.get("discovery_related"),
                "sentiment": classification.get("sentiment"),
            }
        )

        time.sleep(SLEEP_BETWEEN_REQUESTS)

    print(f"Live ingestion complete: {len(results)} reviews classified")
    return results


def load_insights():
    """
    Load insights.json from project root.

    Returns:
        Full insights dict
    """
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    insights_path = os.path.join(project_root, "insights.json")
    with open(insights_path, "r", encoding="utf-8") as f:
        return json.load(f)


def _parse_repo():
    """Parse owner/repo from st.secrets or env GITHUB_REPO."""
    repo = _get_secret("GITHUB_REPO")
    if not repo:
        raise ValueError("GITHUB_REPO not found in st.secrets or environment")
    return repo.strip()


def trigger_github_actions():
    """
    Trigger the GitHub Actions workflow_dispatch for pipeline.yml.

    Returns:
        True if triggered successfully, False otherwise
    """
    token = _get_secret("GITHUB_TOKEN")
    repo = _parse_repo()

    if not token:
        raise ValueError("GITHUB_TOKEN not found in st.secrets or environment")

    url = f"https://api.github.com/repos/{repo}/actions/workflows/pipeline.yml/dispatches"
    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github.v3+json",
    }
    payload = {"ref": "main"}

    try:
        response = requests.post(url, headers=headers, json=payload, timeout=30)
        return response.status_code in (204, 200)
    except Exception as e:
        print(f"Failed to trigger GitHub Actions: {e}")
        return False


def get_pipeline_run_status():
    """
    Get the latest workflow run status for pipeline.yml.

    Returns:
        Status string: "queued", "in_progress", "completed", or "failed"
    """
    token = _get_secret("GITHUB_TOKEN")
    repo = _parse_repo()

    if not token:
        raise ValueError("GITHUB_TOKEN not found in st.secrets or environment")

    url = f"https://api.github.com/repos/{repo}/actions/workflows/pipeline.yml/runs?per_page=1"
    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github.v3+json",
    }

    try:
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()
        data = response.json()
        runs = data.get("workflow_runs", [])
        if not runs:
            return "unknown"

        latest = runs[0]
        status = latest.get("status")
        conclusion = latest.get("conclusion")

        if status == "queued":
            return "queued"
        if status == "in_progress":
            return "in_progress"
        if status == "completed":
            return conclusion if conclusion else "completed"
        return status

    except Exception as e:
        print(f"Failed to get pipeline status: {e}")
        return "unknown"
