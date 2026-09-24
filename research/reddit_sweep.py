#!/usr/bin/env python3
"""
Reddit sweep: collect posts (and top comments) that describe everyday problems,
so they can later be distilled into a categorized list of app-solvable problems.

Uses Reddit's public JSON endpoints on old.reddit.com (no API key needed).
Polite by default: ~10 requests/minute, backs off on 429, resumable.

Usage:
    python3 research/reddit_sweep.py                 # posts only
    python3 research/reddit_sweep.py --comments      # also fetch top comments on promising threads
    python3 research/reddit_sweep.py --subs research/subreddits.txt --out research/raw --delay 6

Outputs (in --out, default research/raw):
    posts.jsonl      one post per line (deduped by id)
    comments.jsonl   one top-level comment per line
    state.json       resume state: which (subreddit, job) pairs are done
    sweep.log        progress log
"""
import argparse
import json
import os
import random
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

BASE = "https://old.reddit.com"
UA = "linux:upwork-portfolio-research:v0.1 (personal research script; contact via GitHub)"

# Keyword searches run inside each subreddit. old.reddit search understands OR / quotes.
SEARCH_QUERIES = [
    '"is there an app" OR "wish there was an app" OR "app that" OR "looking for an app"',
    '"someone should make" OR "why isn\'t there" OR "why is there no" OR "needs to exist"',
    '"pet peeve" OR "drives me crazy" OR "so annoying" OR "frustrating" OR "hate that"',
    '"struggle with" OR "biggest problem" OR "pain point" OR "keep forgetting"',
]

# Site-wide searches (across all of Reddit), run once.
GLOBAL_QUERIES = [
    '"wish there was an app"',
    '"is there an app that"',
    '"why isn\'t there an app"',
    '"someone should make an app"',
    '"app idea"',
    '"biggest daily annoyance"',
    '"what app do you wish existed"',
    '"is there a website that"',
    '"is there software that"',
    '"looking for an app that"',
]

# Threads worth pulling comments from: title matches this and has enough comments.
COMMENT_WORTHY = re.compile(
    r"\b(app|apps|wish|annoy|frustrat|pet peeve|hate|problem|struggle|drives me|"
    r"someone should|why isn'?t there|why is there no|idea|solution|need|tool|software|website)\b",
    re.I,
)


def log(out_dir, msg):
    line = f"[{time.strftime('%H:%M:%S')}] {msg}"
    print(line, flush=True)
    with open(os.path.join(out_dir, "sweep.log"), "a") as f:
        f.write(line + "\n")


class Client:
    def __init__(self, delay, out_dir):
        self.delay = delay
        self.out_dir = out_dir
        self.requests = 0
        self.last = 0.0

    def get(self, path, params=None, max_tries=5):
        url = BASE + path
        if params:
            url += "?" + urllib.parse.urlencode(params)
        for attempt in range(1, max_tries + 1):
            wait = self.delay - (time.time() - self.last)
            if wait > 0:
                time.sleep(wait + random.uniform(0, 1.0))
            req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
            try:
                with urllib.request.urlopen(req, timeout=30) as resp:
                    self.last = time.time()
                    self.requests += 1
                    remaining = resp.headers.get("x-ratelimit-remaining")
                    reset = resp.headers.get("x-ratelimit-reset")
                    if remaining is not None:
                        try:
                            if float(remaining) < 2 and reset:
                                log(self.out_dir, f"rate limit nearly spent, sleeping {reset}s")
                                time.sleep(float(reset) + 1)
                        except ValueError:
                            pass
                    return json.loads(resp.read().decode("utf-8"))
            except urllib.error.HTTPError as e:
                self.last = time.time()
                if e.code == 429:
                    retry = e.headers.get("Retry-After")
                    sleep_for = float(retry) if retry and retry.isdigit() else 60 * attempt
                    log(self.out_dir, f"429 on {url} – sleeping {sleep_for:.0f}s (attempt {attempt})")
                    time.sleep(sleep_for)
                    continue
                if e.code in (403, 401):
                    body = ""
                    try:
                        body = e.read().decode("utf-8", "replace")[:200]
                    except Exception:
                        pass
                    log(self.out_dir, f"{e.code} on {url}: {body!r}")
                    if attempt >= 2:
                        return None
                    time.sleep(20 * attempt)
                    continue
                if e.code == 404:
                    log(self.out_dir, f"404 on {url}")
                    return None
                if e.code >= 500:
                    log(self.out_dir, f"{e.code} on {url}, retrying")
                    time.sleep(15 * attempt)
                    continue
                log(self.out_dir, f"HTTP {e.code} on {url}")
                return None
            except (urllib.error.URLError, TimeoutError, ConnectionError, OSError) as e:
                self.last = time.time()
                log(self.out_dir, f"network error on {url}: {e} (attempt {attempt})")
                time.sleep(10 * attempt)
        return None


def load_subs(path):
    subs = []
    with open(path) as f:
        for raw in f:
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            name, _, flags = line.partition("|")
            name = name.strip()
            flag_set = {x.strip() for x in flags.split(",") if x.strip()}
            if name and name not in [s[0] for s in subs]:
                subs.append((name, flag_set))
    return subs


def load_state(out_dir):
    p = os.path.join(out_dir, "state.json")
    if os.path.exists(p):
        with open(p) as f:
            return json.load(f)
    return {"done": [], "seen_posts": [], "comments_done": []}


def save_state(out_dir, state):
    p = os.path.join(out_dir, "state.json")
    tmp = p + ".tmp"
    with open(tmp, "w") as f:
        json.dump(state, f)
    os.replace(tmp, p)


def slim_post(d, source):
    text = d.get("selftext") or ""
    return {
        "id": d.get("id"),
        "subreddit": d.get("subreddit"),
        "title": d.get("title"),
        "selftext": text[:2500],
        "score": d.get("score"),
        "upvote_ratio": d.get("upvote_ratio"),
        "num_comments": d.get("num_comments"),
        "created_utc": d.get("created_utc"),
        "permalink": "https://www.reddit.com" + (d.get("permalink") or ""),
        "flair": d.get("link_flair_text"),
        "source": source,
    }


def listing_children(data):
    if not data or not isinstance(data, dict):
        return []
    return [c["data"] for c in data.get("data", {}).get("children", []) if c.get("kind") == "t3"]


def fetch_listing(client, path, params, pages):
    out, after = [], None
    for _ in range(pages):
        p = dict(params)
        if after:
            p["after"] = after
        data = client.get(path, p)
        kids = listing_children(data)
        out.extend(kids)
        after = (data or {}).get("data", {}).get("after") if data else None
        if not after or not kids:
            break
    return out


def write_posts(out_dir, posts, seen):
    new = 0
    with open(os.path.join(out_dir, "posts.jsonl"), "a") as f:
        for p in posts:
            if not p.get("id") or p["id"] in seen:
                continue
            seen.add(p["id"])
            f.write(json.dumps(p, ensure_ascii=False) + "\n")
            new += 1
    return new


def sweep_posts(client, subs, state, out_dir, pages, deep_pages):
    seen = set(state["seen_posts"])
    done = set(state["done"])
    jobs = []
    for name, flags in subs:
        if "search-only" not in flags:
            jobs.append((name, "top_year", flags))
            jobs.append((name, "top_all", flags))
        for i in range(len(SEARCH_QUERIES)):
            jobs.append((name, f"search_{i}", flags))
    for i in range(len(GLOBAL_QUERIES)):
        jobs.append(("_global", f"global_{i}", set()))

    total = len(jobs)
    for n, (name, job, flags) in enumerate(jobs, 1):
        key = f"{name}:{job}"
        if key in done:
            continue
        n_pages = deep_pages if "deep" in flags else pages
        if job == "top_year":
            posts = fetch_listing(client, f"/r/{name}/top.json", {"t": "year", "limit": 100}, n_pages)
        elif job == "top_all":
            posts = fetch_listing(client, f"/r/{name}/top.json", {"t": "all", "limit": 100}, max(1, n_pages - 1))
        elif job.startswith("search_"):
            q = SEARCH_QUERIES[int(job.split("_")[1])]
            posts = fetch_listing(
                client, f"/r/{name}/search.json",
                {"q": q, "restrict_sr": 1, "sort": "top", "t": "all", "limit": 100}, 1,
            )
        else:
            q = GLOBAL_QUERIES[int(job.split("_")[1])]
            posts = fetch_listing(client, "/search.json", {"q": q, "sort": "top", "t": "all", "limit": 100}, 3)
        slim = [slim_post(d, key) for d in posts]
        new = write_posts(out_dir, slim, seen)
        done.add(key)
        state["done"] = sorted(done)
        state["seen_posts"] = sorted(seen)
        save_state(out_dir, state)
        log(out_dir, f"[{n}/{total}] {key}: {len(slim)} posts, {new} new (total {len(seen)}, requests {client.requests})")


def sweep_comments(client, state, out_dir, min_comments, max_threads):
    posts_path = os.path.join(out_dir, "posts.jsonl")
    if not os.path.exists(posts_path):
        log(out_dir, "no posts.jsonl yet; run the post sweep first")
        return
    candidates = []
    with open(posts_path) as f:
        for line in f:
            p = json.loads(line)
            if (p.get("num_comments") or 0) >= min_comments and COMMENT_WORTHY.search(p.get("title") or ""):
                candidates.append(p)
    candidates.sort(key=lambda p: (p.get("num_comments") or 0), reverse=True)
    candidates = candidates[:max_threads]
    done = set(state["comments_done"])
    log(out_dir, f"{len(candidates)} threads selected for comments ({len(done)} already done)")
    for n, p in enumerate(candidates, 1):
        if p["id"] in done:
            continue
        path = p["permalink"].replace("https://www.reddit.com", "") + ".json"
        data = client.get(path, {"limit": 100, "depth": 1, "sort": "top"})
        got = 0
        if isinstance(data, list) and len(data) > 1:
            with open(os.path.join(out_dir, "comments.jsonl"), "a") as f:
                for c in data[1].get("data", {}).get("children", []):
                    if c.get("kind") != "t1":
                        continue
                    d = c["data"]
                    body = d.get("body") or ""
                    if len(body) < 25 or (d.get("score") or 0) < 3:
                        continue
                    f.write(json.dumps({
                        "id": d.get("id"),
                        "post_id": p["id"],
                        "subreddit": p["subreddit"],
                        "post_title": p["title"],
                        "body": body[:2000],
                        "score": d.get("score"),
                        "permalink": "https://www.reddit.com" + (d.get("permalink") or ""),
                    }, ensure_ascii=False) + "\n")
                    got += 1
        done.add(p["id"])
        state["comments_done"] = sorted(done)
        save_state(out_dir, state)
        log(out_dir, f"[{n}/{len(candidates)}] comments r/{p['subreddit']} '{p['title'][:60]}': {got} kept")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--subs", default=os.path.join(os.path.dirname(__file__), "subreddits.txt"))
    ap.add_argument("--out", default=os.path.join(os.path.dirname(__file__), "raw"))
    ap.add_argument("--delay", type=float, default=6.0, help="seconds between requests")
    ap.add_argument("--pages", type=int, default=1, help="pages of 100 for /top per subreddit")
    ap.add_argument("--deep-pages", type=int, default=3, help="pages for subs flagged 'deep'")
    ap.add_argument("--comments", action="store_true", help="also fetch comments on promising threads")
    ap.add_argument("--min-comments", type=int, default=25)
    ap.add_argument("--max-threads", type=int, default=400)
    ap.add_argument("--only", default="", help="comma-separated subreddit names to restrict to (testing)")
    ap.add_argument("--probe", action="store_true", help="single request to check Reddit is reachable, then exit")
    args = ap.parse_args()

    os.makedirs(args.out, exist_ok=True)
    client = Client(args.delay, args.out)

    if args.probe:
        data = client.get("/r/AppIdeas/top.json", {"t": "year", "limit": 3}, max_tries=1)
        kids = listing_children(data)
        print("reachable" if kids else "NOT reachable", "-", [k.get("title") for k in kids])
        sys.exit(0 if kids else 1)

    subs = load_subs(args.subs)
    if args.only:
        keep = {s.strip().lower() for s in args.only.split(",")}
        subs = [s for s in subs if s[0].lower() in keep]
    state = load_state(args.out)
    log(args.out, f"starting: {len(subs)} subreddits, delay {args.delay}s")
    sweep_posts(client, subs, state, args.out, args.pages, args.deep_pages)
    if args.comments:
        sweep_comments(client, state, args.out, args.min_comments, args.max_threads)
    log(args.out, f"finished; {client.requests} requests this run")


if __name__ == "__main__":
    main()
