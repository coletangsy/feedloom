---
name: ai-news-briefing
description: Produce or maintain a daily AI, LLM, data-science, and MLOps news briefing in Traditional Chinese. Use this whenever a request asks to collect, filter, summarize, schedule, or review AI/data-science news, especially when reliable sources, concise impact analysis, exact links, and a quiet no-news outcome matter.
---

# AI news briefing

## Goal

Surface only AI and data-science news that deserves the user's attention. Prefer a short, high-signal briefing over filling a quota.

## Evidence and selection

Run `scripts/ai_news_collect.py` first. Treat its JSON as the sole evidence set for an unattended briefing. Reject candidates that lack an exact article, release, paper, repository, or discussion URL.

Prioritize new models, meaningful benchmarks or research, important open-source tools, material product/API changes, and consequential safety, privacy, policy, or governance developments. Also include material MLOps and data-science changes when they affect practitioners.

Drop duplicate coverage, SEO or aggregation sites, generic fundraising, routine version bumps, marketing without substance, source homepages, and claims that cannot be verified from a candidate. Do not turn unconfirmed reports into facts.

Use at most six items. Group items only when it improves reading; do not manufacture empty categories.

## Output

Write in Traditional Chinese. Never use Markdown tables.

When there are no worthwhile items, output exactly:

```
[SILENT]
```

Otherwise use this structure:

```
AI 新聞摘要
日期：YYYY-MM-DD

模型與研究
1. 標題
   重點：說明發生什麼，以及為何會影響開發者、研究者或自動化工作流。
   來源：精確 URL
```

Use only helpful groups: 模型與研究、開發工具與平台、產品與企業動態、安全、政策與治理、資料科學與 MLOps、值得留意但未確認. The last group must state the uncertainty plainly.

Before producing a non-silent report, save the selected candidate IDs to a temporary JSON file and run the collector with `--mark-seen` and the usual state path. This prevents routine repeats over the next 14 days.
