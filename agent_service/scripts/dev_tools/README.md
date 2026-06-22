# dev_tools/

Development-only scripts used during the build and validation phases of ClinixAI.
These are **not part of the running service** — they were moved here from the `agent_service/`
root to keep the service directory clean.

## Categories

| Prefix | Purpose |
|--------|---------|
| `validate_*.py` | End-to-end scenario validation against a running local stack |
| `test_*.py` | Ad-hoc unit/integration tests run manually during development |
| `trace_*.py` | Conversation trace reproduction scripts for debugging |
| `explore_*.py` | One-off MongoDB exploration scripts |
| `clear_*.py` | Data reset scripts (e.g. clear a specific patient's session) |
| `diag_*.py` | Diagnostic scripts for checking preference data |

## Usage

Run from the `agent_service/` directory with the venv active:

```bash
python scripts/dev_tools/validate_phase2.py
```

Most scripts require the full stack (Redis, MongoDB, agent_service) to be running.
