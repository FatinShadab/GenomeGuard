# GenomeGuard Agent Personas

GenomeGuard partitions operational code into four explicit, decoupled virtual agent personas.

## 1. Sensor Agent (Watcher)

A specialized data-layer polling routine that monitors local `.genome/watcher.db` database transformations and hooks into graph mutations.

- **Module:** `genomeguard.watcher`, `genomeguard.graph`
- Polls `.genome/watcher.db` every N seconds (configured via `poll_interval_seconds` in `guard_config.json`).
- Detects file modification timestamps and database update sequences.
- Emits changed file paths for downstream analysis.
- Harvests context by extracting the modified file's plaintext and invoking `codegenome export --format json` as a background subprocess.

## 2. Critic Agent (Architect)

An LLM-powered orchestration system running `gpt-4o`. It evaluates localized code transformations against the rules declared in `guard_config.json`.

- **Module:** `genomeguard.critic`
- Receives changed file content plus JSON graph context from the Sensor.
- Calls OpenAI (`openai_model` from config, default `gpt-4o`) with a structured system prompt.
- Returns structured decay analysis JSON matching the schema:

```json
{
  "decay_detected": true,
  "reason": "Clear, concise explanation of the design violation",
  "refactored_code": "The complete, fixed file content string here"
}
```

## 3. Surgeon Agent (Refactorer)

An automated rewrite specialist module that processes semantic topological context to synthesize decoupled code corrections.

- **Module:** `genomeguard.surgeon`
- Receives the `refactored_code` string from the Critic.
- In `--mode patch` (default): generates a unified diff `.patch` file into `patches_dir`.
- In `--mode enforce`: directly overwrites the target source file with the refactored content.

## 4. Verifier Agent (Safety Gatekeeper)

A non-LLM, rule-bound execution controller managing subprocess compilation checks and routing outputs to safe `.patch` files or direct writes based on CLI execution flags.

- **Module:** `genomeguard.verifier`
- Writes LLM output to a temporary shadow file (`temp_file` from config) before any permanent change.
- Runs `python -m py_compile` on the temp copy via subprocess.
- Discards all changes on compilation failure, safeguarding environment stability.
- Only permits the Surgeon to act after verification passes.

## Orchestrator

The daemon loop wiring all four personas lives in `genomeguard.core` (`run_daemon`, `process_single_change`). Shared utilities (config, paths, diffs, compilation checks) are in `genomeguard.utils`. CLI entry point: `genomeguard.cli:main`.
