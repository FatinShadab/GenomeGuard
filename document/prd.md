# Product Requirement Document (PRD): GenomeGuard

## Subtitle: The Codegenome Immune System (Real-Time Architecture Guardrail)

### Distribution Strategy: Open-Source PyPI Package (`genome-guard`)

---

## 1. Executive Summary & Objective

### 1.1 Problem Statement

As software projects grow, they suffer from **architectural decay**. Developers—well-intentioned or under tight deadlines—inadvertently introduce circular dependencies, break structural boundaries (e.g., UI code directly querying database resources), and create tightly coupled modules. Traditional static analysis tools (linters) capture syntax and formatting rules but lack the semantic and topological understanding required to police system architecture layouts in real time.

### 1.2 Solution Overview

**GenomeGuard** functions as an autonomous "immune system" operating directly on top of `codegenome`. Distributed as a globally installable PyPI package, it monitors a developer's codebase in real time. When an architectural boundary is violated, GenomeGuard catches it via `codegenome`'s active tracking layer and leverages OpenAI models (`gpt-4o`) to evaluate the mutation. Depending on the user-configured CLI mode, it either generates a precise, non-destructive isolation patch (`.patch` file) or autonomously refactors the file to prevent code decay before it reaches production.

### 1.3 Scope Constraint & Design Philosophy

To deliver a highly effective system ready for production pipelines, GenomeGuard completely bypasses complex graphical user interfaces, IDE plugin pipelines, or heavyweight AST engines. It relies entirely on an installable, **headless Python CLI utility** that targets any active local `codegenome` SQLite state database (`.genome/watcher.db`), executing context-aware validation gates with zero system performance overhead.

---

## 2. Minimum Viable Product (MVP) Core Workflow

The engineering architecture operates as a global terminal binary command execution loop triggered by environmental filesystem changes:

```
[Developer Saves File]
          │
          ▼
[Codegenome Auto-Updates `.genome/watcher.db`]
          │
          ▼
[Global CLI `genome-guard` Daemon Detects DB Update]
          │
          ▼
[Extract Changed File + Export JSON Graph Metadata]
          │
          ▼
[OpenAI API (gpt-4o): Evaluates Design vs Rules]
          │
          ▼
 ┌────────┴────────────────────────────────────────┐
 │ If Defect Found                                 │ If Clean
 ▼                                                 ▼
[Run Verification Check (Subprocess Engine)]     [Log: "Architecture Healthy"]
          │
          │ (Passes Syntax Validation)
          ▼
 ┌────────┴────────────────────────────────────────┐
 │ If --mode patch (Default Safety)                │ If --mode enforce
 ▼                                                 ▼
[Generate Unified Diff `.patch` File]           [Safely Overwrite Target File]

```

---

## 3. Detailed Functional Requirements

### 3.1 The Sensor Layer (Database Poller & Context Extraction)

* **Real-time Mutation Detection:** The script bypasses raw OS filesystem watchers to avoid redundant event handling. It continuously polls the file modification timestamp of the target repository's `.genome/watcher.db` or monitors its internal update sequences every 2 seconds.
* **Context Harvesting:** When a database mutation flag is raised, the tool captures the absolute path of the modified resource, extracts its current plaintext code layout, and executes `codegenome export --format json` as a background subprocess to capture the macro-level dependency network graph.

### 3.2 The Architect Layer (OpenAI Semantic Assessment Graph)

* **Context Compacting Strategy:** Rather than overloading context windows with entire codebase directories, GenomeGuard maps the `codegenome` JSON graph format to pass *only* the specific changed code block alongside its immediate upstream and downstream structural nodes.
* **Deterministic Contract Enforcement:** The OpenAI API is configured using standard structured string parameters to ensure responses strictly comply with a valid, non-markdown JSON response schema.

#### 🧠 Core System Prompt Blueprint

```text
You are GenomeGuard, an elite autonomous software architect. 
You are analyzing a modified file alongside its codebase graph context.
Your task is to detect architectural decay:
1. Circular dependencies.
2. Deep nesting / High cyclomatic complexity.
3. Separation of Concerns violations (e.g., mixing business logic with infrastructure/UI).

CRITICAL: Your response must be in valid JSON format matching this schema:
{
  "decay_detected": true/false,
  "reason": "Clear, concise explanation of the design violation",
  "refactored_code": "The complete, fixed file content string here"
}
Do not wrap the JSON output in markdown blocks (like ```json). Return raw stringified JSON text.

```

### 3.3 The Surgical Surgeon & Verifier Layer (Safety Defenses)

* **CLI Operational Entrypoints:** Once installed via PyPI, the core execution pipeline processes two explicit operational modes passed as command-line arguments:
* `--mode patch` *(Default Safe Mode)*: Prevents destructive, unreviewed file updates. It compiles the original source layout and the LLM response through Python's native `difflib.unified_diff`, generating a localized, reviewable `.patch` asset into the workspace.
* `--mode enforce` *(Autonomous Mode)*: Permits automated, direct structural modifications to the source code.


* **Deterministic Verification System:** Before any patch or file modification is finalized, the engine writes the LLM output to a temporary shadow file (`.gg_temp.py`) and triggers a native compiler subprocess check (`python -m py_compile .gg_temp.py`). If validation fails, the transformation is abandoned entirely, safeguarding environment stability.

---

## 4. Technical Stack & Package Architecture

### 4.1 Underlying Core Stack

* **Core Graph Engine:** `Ogro-Projukti/codegenome` (configured in live stream mode)
* **Runtime Language:** Python 3.12+
* **Distribution Tooling:** Modern PEP 621 compliant `pyproject.toml` using `setuptools` or `hatchling`
* **External Production Dependencies:** `openai>=1.0.0`

### 4.2 PyPI Source & Workspace Distribution Tree Maps

#### A. Source Distribution Layout (What gets published to PyPI)

```text
genome-guard/
├── pyproject.toml        # Package metadata, configurations, and terminal bin mapping
├── README.md             # PyPI landing page documentation
├── LICENSE               # Open-source distribution license (MIT)
├── AGENTS.md             # Functional breakdown of active agent modules
├── skills.md             # Detailed breakdown of agent capability parameters
└── src/
    └── genomeguard/
        ├── __init__.py
        ├── cli.py        # Argparse handler for global terminal command execution
        ├── core.py       # Orchestration engine (Sensor, Critic, Surgeon)
        └── utils.py      # Subprocess verifiers, sqlite readers, and patch generators

```

#### B. Target Consumer Workspace (Where the package runs in production)

```text
developer-project/
├── .genome/              # Initialized by running codegenome analyze
│   ├── watcher.db        # Active SQLite state monitor tracked by genome-guard
│   └── patches/          # Destination for secure structural `.patch` files
├── guard_config.json     # Declarative architectural validation thresholds
└── src/                  # Developer codebase

```

---

## 5. Hackathon Deliverables Structure

### 5.1 Project Persona Matrix (`AGENTS.md`)

To meet the specific evaluation guidelines of the Codex Challenge, the package internals partition operational code features into four explicit, decoupled virtual agent personas:

1. **The Sensor Agent (Watcher):** A specialized data layer polling routine that monitors local `.genome/watcher.db` database transformations and hooks into graph mutations.
2. **The Critic Agent (Architect):** An LLM-powered orchestration system running `gpt-4o`. It evaluates localized code transformations against the rules declared in `guard_config.json`.
3. **The Surgeon Agent (Refactorer):** An automated rewrite specialist module that processes semantic topological context to synthesize decoupled code corrections.
4. **The Verifier Agent (Safety Gatekeeper):** A non-LLM, rule-bound execution controller managing subprocess compilation checks and routing outputs to safe `.patch` files or direct writes based on the CLI execution flags.

### 5.2 Agent Execution Toolkit (`skills.md`)

The core package core exposes these explicit internal programmatic capabilities to drive the agent ecosystem loop:

* `query_graph_delta()`: Intercepts and parses the active SQLite state tables inside `.genome/watcher.db`.
* `evaluate_decay_metrics()`: Compresses code structure metadata payloads and executes remote OpenAI API inference calls.
* `generate_unified_diff()`: Evaluates structural adjustments and constructs standardized, clean, reviewable `.patch` files.
* `execute_compilation_check()`: Commands isolated operating system subshell execution sequences to validate runtime and syntax integrity.

---

## 6. Hackathon Evaluation Compliance Matrix

| Codex Selection Parameters | Strategy for Winning with the PyPI Architecture Archetype |
| --- | --- |
| **AI-Native Thinking** | The system uses an LLM to evaluate complex, global architectural rules over structural codebase metadata graphs rather than flat files—a level of reasoning impossible with traditional, regex-based linters. |
| **Agent Design & Workflow** | System execution blocks are cleanly separated into decoupled, documented, and sequential script roles fully formalized in the `AGENTS.md` and `skills.md` manifests. |
| **Practical Impact & Originality** | Shifting from a local raw script to an open-source PyPI package (`pip install genome-guard`) transforms the submission into an instantly scalable developer utility. The addition of the safe `--mode patch` feature builds vital developer trust by protecting target codebases from destructive AI write operations. |