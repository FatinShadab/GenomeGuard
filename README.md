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
| `--mock-critic` / `--no-mock-critic` | Offline mock LLM fixtures (default: off when `OPENAI_API_KEY` is set, else on with warning) |

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

Default CI runs exclude live network calls — no `OPENAI_API_KEY` required:

```bash
pytest -v -m "not integration"
```

Run the full suite including live OpenAI integration (requires a key):

```bash
export OPENAI_API_KEY=sk-...   # Windows: set OPENAI_API_KEY=sk-...
pytest -v
```

Test modules:

- `tests/test_sensor.py` — graph compaction and path normalization
- `tests/test_critic_parser.py` — JSON parsing and markdown fence stripping
- `tests/test_surgeon.py` — patch creation and enforce writes
- `tests/test_verifier.py` — compilation gate
- `tests/test_orchestrator.py` — daemon handoffs and loop-drain guard
- `tests/test_pipeline_integration.py` — end-to-end mocked pipeline
- `tests/test_openai_integration.py` — live OpenAI critic (`@pytest.mark.integration`)

## OpenAI Setup

Live Critic analysis requires an OpenAI API key. **Never commit real keys** — use environment variables or a local `.env` file (gitignored).

1. Copy the template and set your key locally:

```bash
cp .env.example .env
# edit .env — do not commit this file
```

2. Export the variable in your shell (alternative to `.env`):

```bash
export OPENAI_API_KEY=sk-...   # Windows PowerShell: $env:OPENAI_API_KEY="sk-..."
```

3. Optional model override in `guard_config.json`:

```json
{
  "openai_model": "gpt-4o"
}
```

4. Run with live API (default when the key is present):

```bash
genome-guard --workspace . --no-mock-critic
```

Force offline mock fixtures even with a key (cheap local runs):

```bash
genome-guard --workspace . --mock-critic
```

**Cost note:** Only changed files detected via `.genome/watcher.db` trigger OpenAI calls — not the entire codebase on every poll.

### Manual E2E checklist

- [ ] `pip install -e ".[dev]"` in the GenomeGuard repo
- [ ] Create a sample project with an intentional architecture violation
- [ ] `cd sample && codegenome analyze . && codegenome evolve .` (background terminal)
- [ ] `export OPENAI_API_KEY=...` (or load from `.env`)
- [ ] `genome-guard --workspace . --mode patch`
- [ ] Edit the sample file, save, confirm `.genome/patches/*.patch` generated
- [ ] Repeat with `--mode enforce` on a throwaway branch only

## License

MIT — see [LICENSE](LICENSE).
