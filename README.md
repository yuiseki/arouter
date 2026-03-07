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
- `execute_command()` for deterministic intent dispatch
- ack / post-action voice policy helpers
- authorized command execution flow helper
- segment WAV storage and auth-denied handling helpers
- segment error reporting helper
- transcript resolution helper for mic-loop command gating
- transcribed segment orchestration helper for the mic loop

## Current Integration

`tmp/whispercpp-listen/voice_command_loop.py` now delegates:

- transcript normalization
- password secret extraction
- command parsing
- non-command reaction detection
- VacuumTube-aware contextual rewrites
- one-shot text command routing
- deterministic command execution dispatch
- ack timing and post-action voice-text policy
- authorized-command execution flow for the mic loop
- successful/auth-denied WAV retention handling
- subprocess/runtime error reporting
- transcript parse/contextualize/suppress/authorize resolution
- transcribed-segment orchestration after STT

## Development

```bash
python3 -m venv .venv
.venv/bin/pip install -e '.[dev]'
.venv/bin/pytest
.venv/bin/mypy src
.venv/bin/ruff check .
```
