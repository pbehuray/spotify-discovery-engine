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
from supabase import create_client

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


# Reuse the classification taxonomy from classify.py
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

# Production classifier model (slower but more accurate)
GROQ_MODEL = "llama-3.3-70b-versatile"
# Fallback model used silently when the production model hits rate limits
GROQ_FALLBACK_MODEL = "llama-3.1-8b-instant"


def _get_groq_client():
    """Initialize Groq client from st.secrets or env."""
    api_key = _get_secret("GROQ_API_KEY")
    if not api_key:
        raise ValueError("GROQ_API_KEY not found in st.secrets or environment")
    return Groq(api_key=api_key, timeout=30)


def _get_supabase_client():
    """Initialize Supabase client from st.secrets or env."""
    url = _get_secret("SUPABASE_URL")
    key = _get_secret("SUPABASE_KEY")
    if not url or not key:
        raise ValueError("SUPABASE_URL and SUPABASE_KEY must be set in st.secrets or environment")
    return create_client(url, key)


def _classify_with_model(text, model, groq_client):
    """
    Internal helper: classify a review with a specific Groq model.

    Returns:
        (classification_dict, error_str) tuple
    """
    prompt = f"{TAXONOMY}\n\nReview text:\n{text}\n\nClassification:"

    for attempt in range(MAX_RETRIES):
        try:
            response = groq_client.chat.completions.create(
                model=model,
                messages=[
                    {
                        "role": "system",
                        "content": "You are a helpful assistant that classifies Spotify reviews according to a fixed taxonomy. Return ONLY valid JSON.",
                    },
                    {"role": "user", "content": prompt},
                ],
                temperature=0,
                max_tokens=300,
                timeout=30,
            )

            result_text = response.choices[0].message.content

            # Strip JSON fences if present
            result_text = re.sub(r"^```json\s*", "", result_text)
            result_text = re.sub(r"^```\s*", "", result_text)
            result_text = re.sub(r"\s*```$", "", result_text)

            return json.loads(result_text), None

        except Exception as e:
            error_str = str(e)

            if "rate_limit_exceeded" in error_str and "tokens" in error_str:
                # Don't wait; signal caller to try fallback model
                return None, error_str

            if "429" in error_str and attempt < MAX_RETRIES - 1:
                time.sleep(RETRY_BACKOFF)
                continue

            return None, error_str

    return None, "max retries exceeded"


def classify_single_review(text):
    """
    Classify a single raw review text using Groq.
    Tries the production model first; silently falls back to a faster model
    if Groq rate limits are hit.

    Args:
        text: Raw review text

    Returns:
        Classification dict, or None if classification failed
    """
    groq_client = _get_groq_client()

    # Try production model first
    result, error = _classify_with_model(text, GROQ_MODEL, groq_client)
    if result is not None:
        print(f"Classified with {GROQ_MODEL}")
        return result

    # If rate limited, silently fall back to the fast model
    if error and "rate_limit_exceeded" in error:
        print(f"Rate limit on {GROQ_MODEL}, falling back to {GROQ_FALLBACK_MODEL}")
        result, _ = _classify_with_model(text, GROQ_FALLBACK_MODEL, groq_client)
        if result is not None:
            print(f"Classified with {GROQ_FALLBACK_MODEL}")
        return result

    print(f"Classification error: {error}")
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
    return list(run_live_demo(n=n))


def run_live_demo(n=5):
    """
    Generator that scrapes the most recent Play Store reviews and classifies
    them one by one, yielding a result dict after each successful classification.

    Args:
        n: Maximum number of most recent reviews to classify

    Yields:
        Dict with review_text, rating, segment, frustration_type,
        discovery_related, sentiment
    """
    print("Starting live demo ingestion...")

    # Scrape only US for a fast demo, stop after 10 reviews
    raw_reviews = scrape_play_store_reviews(app_id="com.spotify.music", days=7, countries=["us"], max_reviews=10)
    if not raw_reviews:
        print("No reviews scraped.")
        return

    # Sort by review date descending and take the n most recent
    raw_reviews = sorted(raw_reviews, key=lambda r: r["at"], reverse=True)[:n]
    normalized = [normalize_review(r) for r in raw_reviews]
    print(f"Normalized {len(normalized)} most recent reviews")

    # Optionally upsert raw reviews to Supabase
    try:
        upsert_reviews_to_supabase(normalized)
    except Exception as e:
        print(f"Upsert raw reviews failed: {e}")

    for review in normalized:
        classification = classify_single_review(review["text"])
        if not classification:
            continue

        # Upsert classified tag to Supabase
        try:
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
            supabase.table("tagged_reviews").upsert(tagged, on_conflict="id").execute()
        except Exception as e:
            print(f"Upsert tagged review failed: {e}")

        yield {
            "review_text": review["text"],
            "rating": review["rating"],
            "segment": classification.get("segment"),
            "frustration_type": classification.get("frustration_type"),
            "discovery_related": classification.get("discovery_related"),
            "sentiment": classification.get("sentiment"),
        }

        time.sleep(SLEEP_BETWEEN_REQUESTS)

    print(f"Live demo complete")


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


def trigger_full_pipeline():
    """
    Trigger the GitHub Actions workflow_dispatch for pipeline.yml.
    Alias for trigger_github_actions().
    """
    return trigger_github_actions()


def _parse_repo():
    """Parse owner/repo from st.secrets or env GITHUB_REPO."""
    repo = _get_secret("GITHUB_REPO")
    if not repo:
        raise ValueError("GITHUB_REPO not found in st.secrets or environment")
    return repo.strip()


def load_insights():
    """
    Load insights.json from project root.

    Returns:
        Full insights dict
    """
    project_root = os.path.dirname(os.path.abspath(__file__))
    insights_path = os.path.join(project_root, "insights.json")
    with open(insights_path, "r", encoding="utf-8") as f:
        return json.load(f)


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
