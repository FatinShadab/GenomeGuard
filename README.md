# GenomeGuard

GenomeGuard is an autonomous, real-time AI agent loop that sits directly on top of [codegenome](https://pypi.org/project/codegenome/). It monitors architectural mutations via `.genome/watcher.db`, evaluates them against configurable rules, and produces safe `.patch` files or enforced rewrites.

## Prerequisites

- Python 3.12+
- [codegenome](https://pypi.org/project/codegenome/) installed and initialized in your project:

```bash
codegenome analyze .
codegenome evolve .
```

## Install

From the repository root (editable dev install):

```bash
python -m venv .venv
.venv\Scripts\activate        # Windows
# source .venv/bin/activate   # macOS/Linux

pip install -e ".[dev]"
```

This registers the `genome-guard` console script (`genomeguard.cli:main`).

## Run

```bash
genome-guard --workspace .
```

Options:

| Flag | Description |
|------|-------------|
| `--workspace PATH` | Project root containing `.genome/watcher.db` (default: `.`) |
| `--config PATH` | Path to `guard_config.json` (default: `<workspace>/guard_config.json`) |
| `--mode patch\|enforce` | Override config mode |
| `--once` | Single poll cycle then exit (debug / CI) |
| `--mock-critic` / `--no-mock-critic` | Use offline mock LLM fixtures (default: enabled) |

Legacy smoke test:

```bash
python genome_guard.py sensor --workspace .
```

## Package layout

```
src/genomeguard/
  __init__.py      # __version__ = "0.1.0"
  cli.py           # argparse + main()
  core.py          # daemon orchestrator (Sensor→Critic→Verifier→Surgeon)
  utils.py         # config, paths, subprocess, diffs, compilation checks
  watcher.py       # Sensor — SQLite delta polling
  graph.py         # Sensor — codegenome export + graph compaction
  critic.py        # Critic — prompt + mock LLM + JSON parsing
  surgeon.py       # Surgeon — patch / enforce writes
  verifier.py      # Verifier — compilation gate
```

See [AGENTS.md](AGENTS.md) for the four agent personas and [skills.md](skills.md) for programmatic API surfaces.

## Tests

All tests run fully offline with mocked LLM responses — no `OPENAI_API_KEY` required.

```bash
pytest -v
```

Test modules:

- `tests/test_sensor.py` — graph compaction and path normalization
- `tests/test_critic_parser.py` — JSON parsing and markdown fence stripping
- `tests/test_surgeon.py` — patch creation and enforce writes
- `tests/test_verifier.py` — compilation gate
- `tests/test_orchestrator.py` — daemon handoffs and loop-drain guard
- `tests/test_pipeline_integration.py` — end-to-end mocked pipeline

## OpenAI integration

OpenAI API wiring is enabled in the final setup step (Session 7). Until then, `--mock-critic` uses local fixtures under `tests/fixtures/`.

## License

MIT — see [LICENSE](LICENSE).
