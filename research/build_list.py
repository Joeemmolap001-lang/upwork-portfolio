#!/usr/bin/env python3
"""
Merge the per-category problem files in research/problems/*.json into the
final deliverables:

    research/1000-everyday-problems.md   grouped by general / specialized category
    research/problems.csv                flat, filterable
    research/problems.json               flat, with ids (for later tooling)

Deduplication: exact title matches, then near-duplicates by token overlap of
title + problem text (Jaccard >= THRESHOLD), within and across categories.
When two items collide the one with the better source (non-"knowledge") and
higher pain score is kept.

Usage:
    python3 research/build_list.py            # build
    python3 research/build_list.py --report   # just print counts
"""
import argparse
import csv
import glob
import json
import os
import re
from collections import Counter, defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
PROBLEMS_DIR = os.path.join(HERE, "problems")
CATEGORIES = os.path.join(HERE, "categories.json")
THRESHOLD = 0.55

STOP = set("""a an the and or of to in on for with at by from is are be been it its this that
these those i you we they he she my your our their his her me us them as if then than so
than too very can could would should will just not no yes do does did done have has had
having when where which who whom why how what while about into over under up down out off
again more most some such only own same other another each every all any few both""".split())

SOURCE_RANK = {"reddit-quoted": 0, "hn": 1, "forum": 1, "app-review": 1, "article": 2, "knowledge": 3}


def tokens(text):
    words = re.findall(r"[a-z0-9']+", (text or "").lower())
    out = set()
    for w in words:
        w = w.strip("'")
        if len(w) < 3 or w in STOP:
            continue
        # crude stemming so "reminders"/"reminder"/"reminding" collide
        for suf in ("ing", "ers", "er", "es", "s", "ed"):
            if w.endswith(suf) and len(w) - len(suf) >= 4:
                w = w[: -len(suf)]
                break
        out.add(w)
    return out


def jaccard(a, b):
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def load_categories():
    with open(CATEGORIES) as f:
        cats = json.load(f)
    return {c["slug"]: c for c in cats}


def load_items(cat_meta):
    items = []
    per_file = {}
    for path in sorted(glob.glob(os.path.join(PROBLEMS_DIR, "*.json"))):
        slug = os.path.splitext(os.path.basename(path))[0]
        try:
            with open(path) as f:
                data = json.load(f)
        except json.JSONDecodeError as e:
            print(f"!! {path}: invalid JSON ({e})")
            continue
        raw = data.get("items", [])
        meta = cat_meta.get(slug, {})
        n = 0
        for it in raw:
            if not it.get("problem") or not it.get("title"):
                continue
            it = dict(it)
            it["category_slug"] = slug
            it["category"] = meta.get("name") or data.get("category") or slug
            it["group"] = meta.get("group") or data.get("group") or "general"
            it["source_type"] = it.get("source_type") or "knowledge"
            for k in ("pain", "app_solvable"):
                try:
                    it[k] = int(it.get(k) or 0)
                except (TypeError, ValueError):
                    it[k] = 0
            it["_tok"] = tokens(it["title"] + " " + it["problem"])
            it["_title_tok"] = tokens(it["title"])
            items.append(it)
            n += 1
        per_file[slug] = n
    return items, per_file


def better(a, b):
    """True if a should be kept over b."""
    ra, rb = SOURCE_RANK.get(a["source_type"], 3), SOURCE_RANK.get(b["source_type"], 3)
    if ra != rb:
        return ra < rb
    if a["pain"] != b["pain"]:
        return a["pain"] > b["pain"]
    return len(a["problem"]) >= len(b["problem"])


def dedupe(items):
    kept = []
    dropped = []
    # sort so the preferred item of any duplicate pair is seen first
    order = sorted(items, key=lambda it: (SOURCE_RANK.get(it["source_type"], 3), -it["pain"], -len(it["problem"])))
    seen_titles = {}
    for it in order:
        key = re.sub(r"[^a-z0-9]+", " ", it["title"].lower()).strip()
        if key in seen_titles:
            dropped.append((it, seen_titles[key], "same title"))
            continue
        dup_of = None
        for k in kept:
            # title-level near match, or strong body overlap
            if jaccard(it["_title_tok"], k["_title_tok"]) >= 0.75 or jaccard(it["_tok"], k["_tok"]) >= THRESHOLD:
                dup_of = k
                break
        if dup_of is not None:
            dropped.append((it, dup_of, "near duplicate"))
            continue
        seen_titles[key] = it
        kept.append(it)
    return kept, dropped


def build(kept, cat_meta, out_md, out_csv, out_json):
    by_cat = defaultdict(list)
    for it in kept:
        by_cat[it["category_slug"]].append(it)
    ordered_slugs = [s for s in cat_meta if s in by_cat] + [s for s in by_cat if s not in cat_meta]

    # assign ids in output order
    n = 0
    flat = []
    for slug in ordered_slugs:
        group = by_cat[slug]
        group.sort(key=lambda it: (it.get("subcategory") or "", -it["pain"], it["title"]))
        for it in group:
            n += 1
            it["id"] = n
            flat.append(it)

    src = Counter(it["source_type"] for it in flat)
    general = [s for s in ordered_slugs if cat_meta.get(s, {}).get("group", "general") == "general"]
    special = [s for s in ordered_slugs if s not in general]

    lines = []
    lines.append("# 1,000 everyday problems an app could solve\n")
    lines.append(
        f"{len(flat)} distinct problems across {len(ordered_slugs)} categories: "
        f"{len(general)} general-life categories first, then {len(special)} specialized ones.\n"
    )
    lines.append(
        "Each entry: **title** — the problem as people experience it · *who* · frequency · "
        "pain (1–5) · app-solvable (1–5) · current workaround · source.\n"
    )
    lines.append("Source labels: `reddit-quoted` = a page attributing the complaint to a Reddit thread; "
                 "`hn`/`forum`/`article`/`app-review` = found on such a page; `knowledge` = well-known "
                 "problem added from general knowledge, not tied to a specific page.\n")
    lines.append("Source mix: " + ", ".join(f"{k} {v}" for k, v in src.most_common()) + "\n")
    lines.append("\n## Contents\n")
    lines.append("**General**\n")
    for s in general:
        lines.append(f"- [{cat_meta.get(s, {}).get('name', s)}](#{s}) ({len(by_cat[s])})")
    lines.append("\n**Specialized**\n")
    for s in special:
        lines.append(f"- [{cat_meta.get(s, {}).get('name', s)}](#{s}) ({len(by_cat[s])})")

    def section(title, slugs):
        lines.append(f"\n---\n\n# {title}\n")
        for s in slugs:
            meta = cat_meta.get(s, {})
            lines.append(f"\n<a id=\"{s}\"></a>\n")
            lines.append(f"## {meta.get('name', s)}\n")
            if meta.get("desc"):
                lines.append(f"*{meta['desc']}*\n")
            current_sub = None
            for it in by_cat[s]:
                sub = it.get("subcategory") or "Other"
                if sub != current_sub:
                    lines.append(f"\n### {sub}\n")
                    current_sub = sub
                src_bit = it["source_type"]
                if it.get("source_url"):
                    src_bit = f"[{it['source_type']}]({it['source_url']})"
                quote = f' — "{it["source_quote"]}"' if it.get("source_quote") else ""
                lines.append(
                    f"{it['id']}. **{it['title']}** — {it['problem']}  \n"
                    f"    *{it.get('who', '')}* · {it.get('frequency', '')} · pain {it['pain']}/5 · "
                    f"app-solvable {it['app_solvable']}/5 · workaround: {it.get('workaround') or 'none'} · "
                    f"source: {src_bit}{quote}"
                )

    section("Part 1 — General, everyday life", general)
    section("Part 2 — Specialized groups and situations", special)

    with open(out_md, "w") as f:
        f.write("\n".join(lines) + "\n")

    fields = ["id", "group", "category", "subcategory", "title", "problem", "who", "frequency",
              "pain", "app_solvable", "workaround", "source_type", "source_url", "source_quote"]
    with open(out_csv, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        for it in flat:
            w.writerow({k: it.get(k, "") for k in fields})
    with open(out_json, "w") as f:
        json.dump([{k: it.get(k, "") for k in fields} for it in flat], f, ensure_ascii=False, indent=1)
    return flat, by_cat, src


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--report", action="store_true")
    ap.add_argument("--show-dropped", action="store_true")
    args = ap.parse_args()

    cat_meta = load_categories()
    items, per_file = load_items(cat_meta)
    kept, dropped = dedupe(items)

    print(f"files: {len(per_file)}  raw items: {len(items)}  kept: {len(kept)}  dropped: {len(dropped)}")
    for slug, n in sorted(per_file.items()):
        k = sum(1 for it in kept if it["category_slug"] == slug)
        print(f"  {slug:45s} raw {n:4d}  kept {k:4d}")
    print("source types (kept):", dict(Counter(it["source_type"] for it in kept)))
    if args.show_dropped:
        for it, of, why in dropped:
            print(f"  DROP [{it['category_slug']}] {it['title']!r}  ~  [{of['category_slug']}] {of['title']!r} ({why})")
    if args.report:
        return

    flat, by_cat, src = build(
        kept, cat_meta,
        os.path.join(HERE, "1000-everyday-problems.md"),
        os.path.join(HERE, "problems.csv"),
        os.path.join(HERE, "problems.json"),
    )
    print(f"wrote {len(flat)} problems to 1000-everyday-problems.md, problems.csv, problems.json")


if __name__ == "__main__":
    main()
