4 Hidden Engineering Landmines to Avoid
While writing the code across these sessions, keep these subtle technical edge cases in mind:

1. The Cross-Platform Path Traversal Bug
The Risk: codegenome might store source file paths inside watcher.db as relative paths or posix-style paths (src/main.py), while your local Python script on a Windows environment might interpret paths with backslashes (src\main.py).

The Fix (Session 1): When parsing paths from the SQLite database or passing them to the graph extraction subprocess, always wrap them in standard Python Path objects or standardize them using .as_posix() to prevent path-matching failures:

Python
from pathlib import Path
normalized_path = Path(changed_path).resolve().as_posix()
2. The Multi-Write Race Condition
The Risk: When operating in --mode enforce, GenomeGuard overwrites the offending file. This overwrite changes the project state, which triggers codegenome evolve . to update the SQLite database again, potentially causing an endless loop where GenomeGuard repeatedly analyzes its own refactored code.

The Fix (Session 5): When GenomeGuard successfully modifies or patches a file, your daemon loop should temporarily update its own last_seen_mtime tracker to match the new file write state before entering the next sleep cycle, successfully bypassing self-induced triggers.

3. Subprocess Environment Context Loss
The Risk: Running codegenome export --format json via a bare subprocess.run can sometimes fail in virtual environments if Python path configurations aren't inherited properly.

The Fix (Session 1): Ensure your background execution blocks pass the active shell environment along with the call:

Python
import os
subprocess.run(["codegenome", "export", "--format", "json"], env=os.environ.copy())
4. guard_config.json Missing Values
The Risk: If a user installs your package via PyPI and runs it inside an uninitialized folder, your utility might throw an unhandled KeyError if fields like openai_model or patches_dir are omitted from a customized local configuration.

The Fix (Session 1): Implement clean dictionary fallbacks inside your configuration loading mechanism:

Python
config.get("openai_model", "gpt-4o")
config.get("mode", "patch")