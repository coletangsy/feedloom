# AI news automation instructions

For unattended briefing runs, read `.agents/skills/ai-news-briefing/SKILL.md` before producing an answer.

- Run the collector first and use only its JSON candidates.
- Do not browse for extra stories or invent missing details.
- Keep `state/ai_news_seen.json` out of git.
- Do not commit during a daily run; source and state changes are manual maintenance work.
