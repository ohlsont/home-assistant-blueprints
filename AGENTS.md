# AGENTS.md

## Execution preferences
- Use `uv run python` instead of `python` or `python3` for one-off scripts.
- Prefer non-interactive git commands.

## Thread workflow (required)
- Start every thread in a dedicated git worktree and branch (branch prefix: `codex/`).
- Do all edits, tests, and commits inside that worktree, not in the primary checkout.
- When implementation is complete, open a pull request before marking the thread done.
- Keep PRs focused to the thread scope and include verification results in the PR body.

## Editing preferences
- Keep changes minimal and focused.
- Avoid non-ASCII unless the file already uses it.
- Use Conventional Commits for all git commit messages.

## Structure
- Blueprint files live under `blueprints/automation/blockheat/`.
- Update `README.md` when behavior or inputs change.
