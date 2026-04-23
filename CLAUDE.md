# Rental Manager — Claude Code Instructions

## Project goal
This is a learning-oriented full-stack app for rental management.

The user is transitioning toward a more technical profile and wants to use AI without losing technical understanding.
The goal is to learn architecture, code reading, controlled refactoring, and practical full-stack development.

## Working style
- Always propose a short plan before making changes.
- Do not modify files until the user explicitly approves the plan.
- Keep changes small, incremental, and easy to review.
- Prefer educational refactors over large rewrites.
- After making changes, explain exactly:
  - which files were modified
  - what changed
  - why it changed

## Scope control
- Do not change backend endpoints unless explicitly asked.
- Do not change the contract of `/dashboard` unless explicitly asked.
- Do not add dependencies unless explicitly approved.
- Do not introduce unnecessary abstractions or overengineering.
- Do not make broad architectural changes without approval.
- Do not touch unrelated files.

## Git workflow
- Assume work should happen in a feature/refactor/test/chore branch, not directly on `main`.
- Before risky or multi-file changes, remind the user to check `git status`.
- After changes, suggest verification before commit.
- Prefer small commits and PR-friendly changes.

## Backend architecture
- `main.py` contains FastAPI endpoints and API behavior.
- `models.py` contains Pydantic models and enums.
- `db.py` contains SQLite persistence logic.
- `adjustments.py` contains rent adjustment calculation logic.
- Avoid mixing persistence logic into API handlers unless explicitly requested.

## Frontend architecture
- `frontend/src/App.jsx` is the data-loading/container component.
- Presentation should be separated into small React components when useful.
- Prefer this responsibility split:
  - App = fetch / state / loading / error
  - child components = rendering / presentation
- Keep React code simple and readable for a learner.

## Frontend learning priorities
When working on frontend, optimize for learning these concepts:
- component
- JSX
- props
- state / useState
- effect / useEffect
- fetch
- map
- key
- conditional rendering
- null handling with `??`
- client/server flow

## Testing and verification
- When backend changes are made, suggest running: `python -m pytest`
- When frontend changes are made, suggest verifying with:
  - `npm run dev`
  - `npm run build` when relevant
- Prefer preserving current behavior unless the task explicitly changes behavior.

## Commands

### Backend
- Run backend: `uvicorn main:app --reload`
- Run tests: `python -m pytest`

### Frontend
- Frontend lives in `frontend/`
- Install dependencies: `npm install`
- Run dev server: `npm run dev`
- Build frontend: `npm run build`

## Communication style
- Be concise but explicit.
- State which files you want to touch before editing.
- If a concept is important for learning, explain it briefly.
- If something is risky or unnecessary, say so clearly.
- If the requested change is too broad, propose a smaller first step.

## Current constraints
- The user wants to understand each step and maintain technical control.
- The user is learning React architecture and should not be skipped past fundamentals too quickly.
- Use AI as a controlled coding assistant, not as an uncontrolled autopilot.