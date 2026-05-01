# Rental Manager — AI Context

This folder is the source of truth for AI-assisted work on Rental Manager.

It exists so any new ChatGPT or Claude conversation can quickly understand:

- what the project is
- where the current work stands
- how we work
- what is in scope or out of scope
- how to validate changes before committing
- how to hand work from ChatGPT to Claude Code and back

## Recommended reading order

1. `AI_HANDOFF.md`
2. `BACKLOG.md`
3. `DECISIONS.md`
4. `PR_CHECKLIST.md`
5. `PROMPT_TEMPLATES.md`

## Working model

- ChatGPT is used as tutor, product analyst, architect, auditor, and release/process guide.
- Claude Code is used as the coding agent, only after receiving a closed and auditable spec.
- The user can explain problems in Spanish.
- Prompts sent to Claude should be written in concise English to reduce ambiguity and align with technical conventions.
- Evidence beats summaries: do not approve implementation only from an agent report.
