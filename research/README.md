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

## Network requirement

The Claude Code cloud environment must allow outbound access to
`old.reddit.com` and `www.reddit.com` (Edit the environment → Network access).
Reddit also blocks Anthropic's built-in web fetcher, so the script runs from
the container itself.
