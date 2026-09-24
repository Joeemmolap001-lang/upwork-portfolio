# Everyday-problem research

Goal: a list of 1,000+ day-to-day problems people describe online that an app
could solve, grouped into general categories first and specialized categories
after. The list feeds the choice of the four portfolio apps.

## Pipeline

1. **Research** – one agent per category in `categories.json` follows
   `AGENT_BRIEF.md`: web searches for pages quoting Reddit/HN/forum complaints,
   plus well-known problems from general knowledge, each labeled by source
   type. Output: `problems/<category>.json` (36 files).
2. **Merge, dedupe, rank** – `build_list.py` merges the files, drops exact
   and near-duplicate problems across categories, and orders each category by
   subcategory and pain score.
3. **Publish** – `everyday-problems.md` (grouped: general categories first,
   then specialized), `problems.csv` and `problems.json` (flat, filterable).

Current result: **2,030 distinct problems in 36 categories** (see the source
mix at the top of `everyday-problems.md`). About 23% carry a source URL; the
rest are labeled `knowledge`. `reddit_sweep.py` is an optional collector for
adding directly Reddit-sourced quotes later (needs Reddit API credentials).

```bash
python3 research/build_list.py --report        # counts only
python3 research/build_list.py                 # rebuild the deliverables
python3 research/build_list.py --show-dropped  # see which duplicates were merged
```

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
