# Feedloom instructions

For unattended briefing runs, read `.agents/skills/ai-news-briefing/SKILL.md` before producing an answer.

- Run the collector first and use only its JSON candidates.
- Do not browse for extra stories or invent missing details.
- Select up to ten items; aim for eight to ten only when enough high-signal candidates merit inclusion, and never fill a quota.
- Keep `state/ai_news_seen.json` out of git.
- Do not commit during a daily run; source and state changes are manual maintenance work.
- TLDR AI is expanded into its linked original stories; sponsor entries are excluded. Validate source maintenance with `python3 -m unittest discover -s tests -v`.
