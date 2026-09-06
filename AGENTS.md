# Feedloom instructions

## Browser and computer use

- Browser and computer-use tools are authorized by default for in-scope research in this repository. Prefer Google Chrome for browser work unless the user specifies another browser.
- Open research tabs, search, navigate, and read public sources without asking for routine confirmation. Use browser interaction directly when needed; do not require a failed web-reader attempt first.
- Follow the tools' permission requirements for consequential actions. This research authorization does not expand the task to sending messages, purchases, or account/security changes.

## Unattended AI briefing runs

For unattended briefing runs, read `.agents/skills/ai-news-briefing/SKILL.md` before producing an answer.

- Run the collector first and use only its JSON candidates.
- Do not browse for extra stories or invent missing details.
- Follow the skill's selection and delivery rules: up to ten items, without filling a quota; previews do not send or update seen state.
- Keep `state/ai_news_seen.json` out of git.
- Do not commit during a daily run; source and state changes are manual maintenance work.
- TLDR AI is expanded into its linked original stories; sponsor entries are excluded. Validate source maintenance with `python3 -m unittest discover -s tests -v`.
