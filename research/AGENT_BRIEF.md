# Research brief: everyday problems an app could solve

You are one of ~36 researchers. Each researcher owns ONE category and must
produce **at least 45 distinct, concrete day-to-day problems** in that
category that a software app (web or mobile) could realistically solve.

## Tools and constraints

- First call `ToolSearch` with query `select:WebSearch` to load the search tool.
- `reddit.com` cannot be fetched and cannot be used as an `allowed_domains`
  filter (both fail). Do NOT try. Instead put words like `reddit`, `r/<sub>`,
  `subreddit`, `redditors` in your queries so that articles, newsletters,
  Quora/forum threads and blog posts that QUOTE or SUMMARIZE Reddit threads
  come up. Also search Hacker News ("Ask HN"), Quora, IndieHackers, app-store
  review roundups, and "pain points" / "pet peeves" listicles.
- `WebFetch` is blocked for almost every site in this environment. Do not
  spend more than one attempt on it; work from search result text.
- Run **at least 12 different searches**, varying phrasing, e.g.:
  `"wish there was an app" <topic> reddit`, `"is there an app that" <topic>`,
  `"why isn't there an app" <topic>`, `<topic> "pet peeve" reddit`,
  `<topic> "drives me crazy" reddit`, `<topic> "biggest struggle" reddit`,
  `<topic> pain points survey`, `<topic> "someone should make"`,
  `r/<relevant subreddit> annoying`, `<topic> complaints app reviews`.
- Prefer the user's own words: when a search result gives you a quote, keep a
  short one (≤ 25 words) in `source_quote` and the page URL in `source_url`.

## What counts as a problem

- Concrete and specific: "Forgetting which leftovers are in the fridge and
  when they were cooked" — yes. "Cooking is hard" — no.
- Describes the PROBLEM as experienced, not the solution.
- Day-to-day or recurring (daily, weekly, monthly, or reliably every few
  months). One-off life events only if the pain is intense and common.
- Realistically addressable by software. Skip pure hardware, policy or
  "people are rude" problems.
- Distinct from every other item in your list. No rewordings.
- Well-known problems from your own knowledge are allowed and useful, but
  label them honestly (`source_type: "knowledge"`), and keep them under
  50% of your list.

## Output

Write ONE file: `research/problems/<slug>.json` (the slug is given to you),
using the Write tool, with exactly this shape:

```json
{
  "category": "<Category name>",
  "group": "general" | "specialized",
  "description": "<one sentence on what this category covers>",
  "items": [
    {
      "title": "<≤ 8 words, noun phrase>",
      "problem": "<one or two sentences, the problem as experienced>",
      "who": "<who has it, e.g. renters with roommates>",
      "frequency": "daily" | "weekly" | "monthly" | "occasional",
      "pain": 1-5,
      "app_solvable": 1-5,
      "workaround": "<what people do today, or 'none'>",
      "subcategory": "<2-5 word grouping; aim for 5-8 subcategories>",
      "source_type": "reddit-quoted" | "hn" | "forum" | "article" | "app-review" | "knowledge",
      "source_url": "<url or empty string>",
      "source_quote": "<≤ 25 words or empty string>"
    }
  ],
  "searches_run": ["<query 1>", "..."],
  "sources": ["<url>", "..."]
}
```

`source_type` rules: `reddit-quoted` only when the page you found attributes
the complaint to Reddit (a subreddit or a Reddit thread). `hn`, `forum`,
`article`, `app-review` when found on such pages. `knowledge` otherwise.

Do not return the list in your final message. Return only: the file path,
the number of items, and the count per `source_type`.
