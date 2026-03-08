# ADR 001: Initial Python Package Scaffold

## Status

Accepted

## Context

`arouter` is the first extraction target from `tmp/whispercpp-listen`.
The immediate goal is to reuse the existing Python parser and test corpus with
minimal translation cost while establishing a stable package boundary.

The surrounding `a*` stack is multi-language:

- `acore`, `acomm`, `yuiclaw` are Rust
- `acaption` is Electron + TypeScript
- `tmp/whispercpp-listen` and `tmp/GOD_MODE` are Python-heavy

## Decision

The initial `arouter` implementation uses:

- Python 3.12
- `pytest` for test execution
- `mypy` for type checking
- `ruff` for linting
- `setuptools` with a `src/` layout

The first migrated slice is limited to:

- transcript normalization
- command-specific alias correction
- intent parsing
- overlay notify utility helpers
- reaction detection
- YouTube/VacuumTube-oriented contextual rewrite
- deterministic text-command execution orchestration
- deterministic command execution dispatch
- ack timing and post-action voice-text policy
- authorized-command execution flow
- biometric/speaker/password command authorization
- biometric signal-file consume/write helpers
- successful/auth-denied WAV storage handling
- segment error reporting
- transcript parse/contextualize/suppress/authorize resolution
- transcribed-segment orchestration after STT
- raw-PCM segment capture/transcription orchestration before STT handoff

## Consequences

- Existing `test_voice_command_loop.py` cases can be migrated incrementally
- `tmp/whispercpp-listen/voice_command_loop.py` can delegate parser/router/dispatch
  behavior to `arouter` without rewriting the routing layer in another language first
- Low-level desktop execution remains eligible for later extraction to `adesk`
  once the orchestration boundary stabilizes
