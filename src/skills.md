# GenomeGuard Core Capabilities

The core package exposes these explicit internal programmatic capabilities to drive the agent ecosystem loop.

## `query_graph_delta()`

Intercepts and parses the active SQLite state tables inside `.genome/watcher.db`.

- Reads the watcher database for the most recent file mutation.
- Returns the last-modified file path and timestamp.
- Triggers context extraction when a delta is detected.

## `evaluate_decay_metrics()`

Compresses code structure metadata payloads and executes remote OpenAI API inference calls.

- Builds the OpenAI prompt payload from changed file content, graph context, and `guard_config.json` rules.
- Calls the OpenAI API using the configured model.
- Parses and validates the structured JSON response (`decay_detected`, `reason`, `refactored_code`).

## `generate_unified_diff()`

Evaluates structural adjustments and constructs standardized, clean, reviewable `.patch` files.

- Uses `difflib.unified_diff` to compare original and refactored source.
- Writes the resulting unified diff to the directory specified by `patches_dir` in config.

## `execute_compilation_check()`

Commands isolated operating system subshell execution sequences to validate runtime and syntax integrity.

- Writes candidate code to the configured `temp_file`.
- Invokes `python -m py_compile` via subprocess on the temp copy.
- Returns pass/fail so the Verifier can gate Surgeon output.
