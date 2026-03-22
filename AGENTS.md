# AGENTS.md

Shared project instructions for all AI agents (Claude Code, Codex, etc.).

## What This Is

Blockheat is a Home Assistant custom integration for policy-driven heating control. It decides when to save energy (based on electricity price, PV production, and time windows) and computes temperature targets for a heat pump. The integration is HACS-compatible and configured via a two-step config flow UI.

## Home Hardware

The physical heating system is documented in [`docs/home-architecture.md`](docs/home-architecture.md).

Key points for development:
- **Heat pump**: Qvantum ETK6500 (exhaust-air). Manual: [`docs/Qvantum-ETK-Manual.pdf`](docs/Qvantum-ETK-Manual.pdf)
- **External sensor**: Ohmigo WiFi replaces the ETK6500's built-in room sensor. Blockheat writes its target to `number.ohmigo_temperature_2`, which the heat pump reads as room temperature.
- **Control method**: Indirect -- Blockheat manipulates the reported room temp to make the heat pump's own thermostat start/stop as desired.

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
uv run python -m pytest tests -q --cov=custom_components/blockheat --cov-branch --cov-report=term-missing --cov-fail-under=80

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

## Gotchas

- **No direct commits to main**: Pre-commit hook blocks `git commit` on the `main` branch. Always work on a feature branch.
- **Pre-commit runs automatically** on commit. To run manually: `uv run pre-commit run --all-files`
- **Mirror sync is enforced**: If you edit only one of the two component directories, CI and `test_mirror_sync` will fail.

## Releasing

```bash
# Bump version across all files
uv run python scripts/bump_version.py X.Y.Z

# Commit, tag, and push
git add pyproject.toml custom_components/blockheat/manifest.json
git commit -m "chore: bump version to X.Y.Z"
git tag vX.Y.Z
git push && git push --tags
# -> release.yml creates GitHub release with HACS zip automatically
```

## Architecture

### Core layers

- **`engine.py`** -- Pure computation, no HA dependencies. Computes policy decisions (`PolicyComputation`), comfort targets (`ComfortComputation`), saving targets, and final target with clamping/deadband. All functions are stateless and testable in isolation.
- **`runtime.py`** -- HA runtime adapter. Reads entity states, calls the engine, writes results back to HA control entity, fires events, manages periodic scheduling and toggle interval guards.
- **`__init__.py`** -- Integration setup, `BlockheatCoordinator` (thin `DataUpdateCoordinator`), service registration.
- **`config_flow.py`** -- Two-step config flow: Step 1 maps external entities (sensors, controls); Step 2 is a sectioned tuning wizard for all numeric parameters. Also contains tuning validation helpers.
- **`sensor.py` / `binary_sensor.py`** -- Read-only entities exposing targets and policy state.
- **`const.py`** -- All config keys, defaults, and entity ID constants.

### Data flow

```
HA entity states (price, outdoor temp, room temps, PV)
  -> runtime reads states
  -> engine.compute_policy() -> saving target
  -> engine.compute_comfort() -> comfort target
  -> engine.compute_final() -> final target + deadband check
  -> runtime writes control entity + fires events
  -> coordinator publishes snapshot -> sensors update
```

### Testing structure

- `tests/blockheat/` -- Unit tests for the integration
- `tests/conftest.py` -- Shared fake HA fixtures (FakeHass, FakeState, etc.)
- `tests/test_release_version_validation.py` -- Ensures version matches across `manifest.json` and `pyproject.toml`

### Release version contract

Version must match in two files: `custom_components/blockheat/manifest.json` and `pyproject.toml`. CI blocks release if they diverge.

## Structure

- Integration files live under `custom_components/blockheat/`.
- Update `README.md` when behavior or inputs change.

## Execution preferences

- Use `uv run python` instead of `python` or `python3` for one-off scripts.
- Prefer non-interactive git commands.

## Thread workflow (Codex)

- Start every thread in a dedicated git worktree and branch (branch prefix: `codex/`).
- Do all edits, tests, and commits inside that worktree, not in the primary checkout.
- When implementation is complete, open a pull request before marking the thread done.
- After opening the PR, monitor CI/checks until they pass (or explicitly note that no checks are configured).
- Before closing the thread, verify whether behavior/input changes require documentation updates and apply them.
- Keep PRs focused to the thread scope and include verification results in the PR body.

## Conventions

- Conventional Commits for all commit messages.
- Ruff config: `line-length = 88`, `target-version = "py312"`, lint rules `F`, `I`, `UP`, `B`, `SIM`, `C4`, `PIE`, `T20`, `RUF`, `PT`, `DTZ`, `A`, `RSE`, `TCH`. `print()` is allowed in `scripts/` and `tests/` via per-file-ignores.
- Mypy: `disallow_untyped_defs`, `strict_equality`, `no_implicit_optional`, `warn_return_any`, `warn_unreachable`.
- Codespell runs in CI and pre-commit for typo detection.
- Pre-commit hooks: hygiene checks (YAML/TOML/JSON, trailing whitespace, EOF fixer, no-commit-to-branch main), codespell, ruff format, ruff check, mypy.
- `asyncio_mode = "auto"` in pytest -- async tests don't need `@pytest.mark.asyncio`.
- Keep changes minimal and focused. Avoid non-ASCII unless the file already uses it.
