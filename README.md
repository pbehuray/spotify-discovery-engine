# Spotify Discovery Review Analysis Engine

An AI classification pipeline that ingests Spotify user reviews from multiple sources, tags each one against a fixed **discovery taxonomy** using an LLM, and produces **verifiable frequency counts and crosstabs** — not summaries.

## Headline finding (from `insights.md`)

Across 456 classified reviews, **159 (34.9%) were discovery-related.** Among those:

- **Top frustration:** stale recommendations (65), then control loss (37)
- **Dominant segment:** active explorers (113) — users actively seeking new music
- **Top desired behavior:** find new artists (88)
- **Top unmet need:** "new music" (36)
- **Key finding:** stale recommendations + loss of control account for 64% of all discovery frustrations

> **In one line:** Active explorers want new music but face stale recommendations and have no control to steer toward fresher results.

---

## What this is (and isn't)

This is a **classification engine**, not a retrieval/RAG system. Every review is tagged against a fixed taxonomy so the output is *countable and verifiable* (e.g. "52 reviews mention stale recommendations"), rather than an LLM-generated summary. This makes the insights defensible.

## Architecture

```
Data Sources ──▶ Supabase (Postgres) ──▶ Groq LLM Classifier ──▶ Aggregation ──▶ insights.json / insights.md
  • Play Store      • raw_reviews          (llama-3.3-70b)        (counts +
  • App Store       • tagged_reviews                              crosstabs)
  • Reddit/Forum/Social
```

**Tech stack:** Python · Supabase (Postgres) · Groq (`llama-3.3-70b-versatile`)

## Data sources — what is live vs hand-collected

| Source | Method | Notes |
|---|---|---|
| **Play Store** | **Live scrape** via `google-play-scraper` (`play_store.py`) | Fetches fresh reviews from Google at runtime. Re-running pulls newer reviews. This is the statistical backbone (~12k reviews). |
| App Store | Scraper attempted (`app_store.py`), hand-collected in practice | Apple's review feed is JS-rendered and access-limited, so the live scraper is unreliable; these reviews were hand-collected from public pages into `paste_sources.txt`. |
| Reddit | Scraper attempted (`reddit_public.py`), hand-collected in practice | Reddit's public endpoint rate-limits aggressively; reviews were hand-collected from public threads into `paste_sources.txt`. |
| Forum / Social | Hand-collected | No reliable scraper (per-site parsing / blocked APIs); collected from public pages into `paste_sources.txt`. |

All sources flow through the **same normalization and the same classifier**, so they're analyzed identically. `app_store.py` and `reddit_public.py` are retained to show the attempted live-scraping paths; where a source could not be reliably scraped, it was hand-collected and loaded via `paste_importer.py`.

## Project structure

```
spotify-discovery-engine/
  docs/
    problemStatement.md      # What and why (source of truth)
    architecture.md          # System design
  ingestion/
    play_store.py            # Live Google Play scraper (Phase 2) — primary source
    app_store.py             # App Store scraper attempt (unreliable; source hand-collected)
    reddit_public.py         # Reddit public-endpoint scraper attempt (rate-limited; hand-collected)
    paste_importer.py        # Imports hand-collected reviews from paste_sources.txt
  paste_sources.txt          # Hand-collected App Store / Reddit / forum / social reviews
  classify.py                # LLM classifier (Phase 3)
  aggregate.py               # Aggregation + insights generation (Phase 4)
  test_db.py                 # Phase 1 DB connection test
  init_db.sql                # Creates raw_reviews + tagged_reviews tables
  insights.json              # Generated output (machine-readable)
  insights.md                # Generated output (human-readable)
  requirements.txt
  .env                       # API keys (gitignored — not in repo)
```

---

## How to run the full pipeline

### Setup

```bash
# 1. Virtual environment
python -m venv venv
venv\Scripts\activate            # Windows
# source venv/bin/activate       # Mac/Linux

# 2. Dependencies
pip install -r requirements.txt

# 3. Environment variables — create a .env file with:
#    SUPABASE_URL=your-project-url
#    SUPABASE_KEY=your-service-role-key   (sb_secret_... format)
#    GROQ_API_KEY=your-groq-key           (from console.groq.com/keys)

# 4. Initialize the database
#    Open your Supabase project → SQL Editor → run the contents of init_db.sql
```

### Verify the connection (Phase 1)

```bash
python test_db.py
# Expect: "✓ All tests passed! Database connection is working."
```

### Run the pipeline (Phases 2–4)

```bash
# Phase 2 — ingest reviews
python ingestion/play_store.py        # live scrape from Google Play
python ingestion/paste_importer.py    # load hand-collected reviews

# Phase 3 — classify with Groq
python classify.py

# Phase 4 — aggregate into insights
python aggregate.py
```

After Phase 4, see `insights.md` and `insights.json` for the results.

---

## Notes for evaluators

- **Live scraping:** `play_store.py` fetches fresh reviews from Google Play at runtime — re-running pulls reviews posted since the last run. The pipeline is idempotent (safe to re-run; no duplicates, keyed on review ID).
- **Sampling:** Classification runs on all hand-collected reviews plus a random sample of Play Store reviews (configurable at the top of `classify.py`). A random sample yields the same percentages as classifying everything, at a fraction of the cost.
- **Groq free tier:** The free tier caps at 100k tokens/day. The classifier batches with rate-limit back-off and is idempotent, so it resumes safely across runs if the daily limit is hit.
- **No secrets in the repo:** All keys live in `.env`, which is gitignored.
- **Verifiable output:** Insights are frequency counts and crosstabs over the tagged data, not generated summaries — so every number can be traced back to classified rows.

## Classification taxonomy (summary)

- **Frustration types:** stale_recommendations, filter_bubble_lock_in, discovery_friction, algorithmic_sameness, poor_new_release_surfacing, context_blindness, over_personalization, control_loss, none
- **Segments:** lapsed_explorer, active_explorer, passive_listener, genre_loyalist, mood_listener, podcast_first, unknown
- **Desired behaviors:** find_new_artists, break_routine, match_mood_or_context, deep_dive_genre, social_discovery, rediscover_back_catalog, none

(Full taxonomy and definitions in `docs/problemStatement.md`.)