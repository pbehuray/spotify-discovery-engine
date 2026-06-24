# Spotify Review Analysis Engine

A classification engine that ingests user reviews from multiple sources, tags them against a fixed discovery taxonomy using LLM, and produces verifiable frequency counts and crosstabs.

## Project Structure

```
spotify-discovery/
  docs/
    problemStatement.md      # Source of truth for what and why
    build_brief.md           # Technical build spec with phases
    architecture.md          # System architecture documentation
  ingestion/                # Ingestion scripts (Phase 2)
    play_store.py
    app_store.py
    paste_importer.py
  paste_sources.txt         # Hand-collected forum/social posts
  classify.py               # LLM classifier (Phase 3)
  aggregate.py              # Aggregation and insights (Phase 4)
  weekly_run.py             # Weekly refresh orchestrator (Phase 5 - optional)
  test_db.py                # Phase 1 database connection test
  init_db.sql               # SQL to initialize Supabase tables
  requirements.txt          # Python dependencies
  .env                      # API keys (gitignored)
  .gitignore
  README.md
```

## Phase 1: Project Skeleton + Supabase Connection

### Setup Instructions

1. **Create Python virtual environment:**
   ```bash
   python -m venv venv
   venv\Scripts\activate  # On Windows
   # or
   source venv/bin/activate  # On Linux/Mac
   ```

2. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Configure environment variables:**
   - Copy `.env` and add your API keys:
     - `SUPABASE_URL`: Your Supabase project URL (from Project Settings > API)
     - `SUPABASE_KEY`: Your Supabase service role key (sb_secret_... format)
     - `GROQ_API_KEY`: Your Groq API key (from https://console.groq.com/keys)

4. **Initialize Supabase database:**
   - Go to your Supabase project dashboard
   - Navigate to SQL Editor
   - Copy and run the SQL from `init_db.sql`
   - This creates the `raw_reviews` and `tagged_reviews` tables

5. **Run the database connection test:**
   ```bash
   python test_db.py
   ```

### Expected Output

If everything is configured correctly, you should see:
```
============================================================
Phase 1: Supabase Connection Test
============================================================
Connecting to Supabase at: https://your-project.supabase.co

Inserting test row with id: test_001
✓ Insert successful

Reading back test row with id: test_001
✓ Read successful

Retrieved row:
  id: test_001
  source: play_store
  rating: 5
  review_date: 2024-06-19T...
  text: This is a test review for Phase 1 connectivity check.
  scraped_at: 2024-06-19T...

Cleaning up test row...
✓ Cleanup successful

============================================================
✓ All tests passed! Database connection is working.
============================================================
```

### Troubleshooting

- **"SUPABASE_URL and SUPABASE_KEY must be set"**: Check that your `.env` file exists and contains the required values.
- **"Insert failed"**: Make sure you've run `init_db.sql` in your Supabase SQL editor to create the tables.
- **Connection errors**: Verify your Supabase URL and key are correct, and that your Supabase project is active.

## Next Steps

After Phase 1 is verified:
- **Phase 2**: Ingestion from Play Store, App Store, and paste_sources.txt
- **Phase 3**: LLM classification using Groq
- **Phase 4**: Aggregation and insights generation
- **Phase 5**: Weekly refresh automation (optional)

## Notes

- All secrets are in `.env` (gitignored)
- The project uses Supabase's new `sb_secret_...` key format
- Every external call is wrapped in try/except with logging
- All operations are idempotent (safe to re-run)
