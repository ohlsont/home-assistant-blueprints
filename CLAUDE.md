# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Is

Blockheat is a Home Assistant custom integration for policy-driven heating control. It decides when to save energy (based on electricity price, PV production, and time windows) and computes temperature targets for a heat pump. The integration is HACS-compatible and configured via a two-step config flow UI.

## Commands

```bash
# Install dev dependencies
uv sync --group dev

# Run all tests
uv run python -m pytest tests -q

# Run a single test file
uv run python -m pytest tests/blockheat/test_engine.py -q

# Run a single test by name
uv run python -m pytest tests/blockheat/test_engine.py -k "test_name" -q

# Coverage gate (CI threshold: 80%)
uv run python -m pytest tests -q --cov=custom_components.blockheat --cov-branch --cov-report=term-missing --cov-fail-under=80

# Format
uv run ruff format custom_components scripts tests

# Lint
uv run ruff check custom_components scripts tests

# Type check
uv run mypy

# Spell check
uv run codespell custom_components scripts tests
```

Always use `uv run` instead of bare `python` or `python3`.

## Releasing

```bash
# Bump version across all files
uv run python scripts/bump_version.py X.Y.Z

# Commit, tag, and push
git add pyproject.toml custom_components/blockheat/manifest.json
git commit -m "chore: bump version to X.Y.Z"
git tag vX.Y.Z
git push && git push --tags
# → release.yml creates GitHub release with HACS zip automatically
```

## Architecture

### Core layers

- **`engine.py`** — Pure computation, no HA dependencies. Computes policy decisions (`PolicyComputation`), comfort targets (`ComfortComputation`), saving targets, and final target with clamping/deadband. All functions are stateless and testable in isolation.
- **`runtime.py`** — HA runtime adapter. Reads entity states, calls the engine, writes results back to HA entities/helpers, fires events, manages periodic scheduling and toggle interval guards.
- **`__init__.py`** — Integration setup, `BlockheatCoordinator` (thin `DataUpdateCoordinator`), service registration.
- **`config_flow.py`** — Two-step config flow: Step 1 maps external entities (sensors, controls); Step 2 is a sectioned tuning wizard for all numeric parameters. Also contains tuning validation helpers.
- **`sensor.py` / `binary_sensor.py`** — Read-only entities exposing targets and policy state.
- **`const.py`** — All config keys, defaults, and entity ID constants.

### Data flow

```
HA entity states (price, outdoor temp, room temps, PV)
  → runtime reads states
  → engine.compute_policy() → saving target
  → engine.compute_comfort() → comfort target
  → engine.compute_final() → final target + deadband check
  → runtime writes control entity + fires events
  → coordinator publishes snapshot → sensors update
```

### Testing structure

- `tests/blockheat/` — Unit tests for the integration
- `tests/conftest.py` — Shared fake HA fixtures (FakeHass, FakeState, etc.)
- `tests/test_release_version_validation.py` — Ensures version matches across `manifest.json` and `pyproject.toml`

### Release version contract

Version must match in two files: `custom_components/blockheat/manifest.json` and `pyproject.toml`. CI blocks release if they diverge.

## Conventions

- Conventional Commits for all commit messages.
- Ruff config: `line-length = 88`, `target-version = "py312"`, lint rules `F`, `I`, `UP`, `B`, `SIM`, `C4`, `PIE`, `T20`, `RUF`, `PT`, `DTZ`, `A`, `RSE`, `TCH`. `print()` is allowed in `scripts/` and `tests/` via per-file-ignores.
- Mypy: `disallow_untyped_defs`, `strict_equality`, `no_implicit_optional`, `warn_return_any`, `warn_unreachable`.
- Codespell runs in CI and pre-commit for typo detection.
- Pre-commit hooks: hygiene checks (YAML/TOML/JSON, trailing whitespace, EOF fixer, no-commit-to-branch main), codespell, ruff format, ruff check, mypy.
- `asyncio_mode = "auto"` in pytest — async tests don't need `@pytest.mark.asyncio`.
- Keep changes minimal. Avoid non-ASCII unless the file already uses it.
