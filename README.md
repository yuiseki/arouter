# arouter

Agentic routing and execution orchestration for voice-command driven behavior.

## Initial Scope

- command-specific transcript normalization
- intent parsing
- semantic routing
- execution orchestration

Current migrated slice:

- overlay notify helpers
- password unlock secret extraction
- `parse_command()` and related transcript alias correction
- `detect_non_command_reaction()`
- `contextualize_command_with_vacuumtube_state()`
- `TextCommandRouter.execute_text_command()`

## Development

```bash
python3 -m venv .venv
.venv/bin/pip install -e '.[dev]'
.venv/bin/pytest
.venv/bin/mypy src
.venv/bin/ruff check .
```
