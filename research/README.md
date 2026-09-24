# Everyday-problem research

Goal: a list of ~1,000 day-to-day problems people describe online that an app
could solve, grouped into general categories first and specialized categories
after. The list feeds the choice of the four portfolio apps.

## Pipeline

1. **Collect** – `reddit_sweep.py` pulls posts (and top comments) from the
   subreddits in `subreddits.txt` using Reddit's public JSON endpoints.
   Raw data lands in `raw/` (git-ignored: it contains usernames and is large).
2. **Distill** – the raw posts/comments are read in batches and each concrete
   problem is extracted as one record: problem, who has it, how often,
   current workaround, source link and a short quote.
3. **Dedupe and rank** – near-duplicates are merged across subreddits; each
   problem gets a pain score and an "app-solvable" score.
4. **Publish** – `1000-everyday-problems.md` (grouped by category) and
   `problems.csv` (flat, filterable).

## Running the collector

```bash
# Check Reddit is reachable from this machine
python3 research/reddit_sweep.py --probe

# Full sweep, posts only (~1–2 h at the default polite rate)
python3 research/reddit_sweep.py

# Add top comments from the most promising threads (~40 min more)
python3 research/reddit_sweep.py --comments

# Test on a few subreddits
python3 research/reddit_sweep.py --only AppIdeas,SomebodyMakeThis --pages 1
```

The collector is resumable: `raw/state.json` records what is done, so a
stopped run continues where it left off.

## Requirements

1. **Network** – the Claude Code cloud environment must allow outbound access to
   `www.reddit.com` and `oauth.reddit.com` (Edit the environment → Network
   access). Reddit blocks Anthropic's built-in web fetcher, so the script runs
   from the container itself.
2. **Reddit API credentials** – Reddit refuses anonymous requests from cloud
   servers, so the collector uses the official OAuth API. Create a free app at
   https://www.reddit.com/prefs/apps (type *script*, any name, redirect URI
   `http://localhost:8080`), then store the two values as environment
   variables in the same environment settings:
   - `REDDIT_CLIENT_ID` – the short string under the app name
   - `REDDIT_CLIENT_SECRET` – the "secret" field

   The collector uses app-only auth (read-only public data); no Reddit
   password is needed. Without these variables it falls back to anonymous
   `old.reddit.com`, which works from a home connection but not from the cloud.
