---
name: ai-news-briefing
description: Produce or maintain a daily AI, LLM, data-science, and MLOps news briefing in Traditional Chinese. Use this whenever a request asks to collect, filter, summarize, schedule, or review AI/data-science news, especially when reliable sources, concise impact analysis, exact links, and a quiet no-news outcome matter.
---

# AI news briefing

## Goal

Surface only AI and data-science news that deserves the user's attention. Prefer a short, high-signal briefing over filling a quota.

## Evidence and selection

Run `scripts/ai_news_collect.py` first. Treat its JSON as the sole evidence set for an unattended briefing. Reject candidates that lack an exact article, release, paper, repository, or discussion URL.

Always prioritize major model or API changes, coding agents, important open-source tools, material MLOps developments, and consequential security issues.

Use strong recent community discussion as an additional prioritization signal when candidate points or comment counts are available. Popularity is not evidence: it must not override source quality, materiality, or the requirement for an exact story or discussion URL.

Include policy, enterprise products, research, and consumer AI features only when the development is material. Drop funding, executive changes, marketing case studies, routine releases, and promotional claims without substantive evidence.

Drop duplicate coverage, SEO or aggregation sites, source homepages, and claims that cannot be verified from a candidate. Do not turn unconfirmed reports into facts.

Use up to ten items. Aim for eight to ten only when enough high-signal candidates merit inclusion; otherwise keep the briefing shorter. Group items only when it improves reading; do not manufacture empty categories.

## Output

Write in Traditional Chinese. Never use Markdown tables.

Format the briefing as Markdown for email: use headings for the title and groups, bold the date and each story title, and link `來源` to the exact candidate URL. Keep each numbered story—title, summary, and source—on one logical line with no hard line breaks inside it. Email clients may wrap that line visually to fit the screen.

## Gmail delivery

Send the completed briefing with the Gmail `send_email` action using `payload.mime_type: "text/plain"`, `payload.charset: "utf-8"`, and the Markdown briefing as `payload.body.content`. Never use `text/markdown`: some mail clients render that MIME type as a downloadable attachment instead of the message body. Do not set a filename or attachment disposition.

After sending, read the sent message and confirm it has a nonempty body and a root MIME type of `text/plain` or `multipart/alternative`. If this check fails, report delivery formatting failed rather than claiming the briefing was delivered correctly.

When there are no worthwhile items, output exactly:

```
[SILENT]
```

Otherwise use this structure:

```
# AI 新聞摘要
**日期：YYYY-MM-DD**

## 模型與研究
1. **標題** — 說明發生什麼，以及為何會影響開發者、研究者或自動化工作流。[來源](精確 URL)
```

Use only helpful groups: 模型與研究、開發工具與平台、產品與企業動態、安全、政策與治理、資料科學與 MLOps、值得留意但未確認. The last group must state the uncertainty plainly.

Before producing a non-silent report, save the selected candidate IDs to a temporary JSON file and run the collector with `--mark-seen` and the usual state path. This prevents routine repeats over the next 14 days.
