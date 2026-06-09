"""Interactive terminal UI for GenomeGuard settings, status, and patches."""

from __future__ import annotations

import logging
import threading
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

from genomeguard.secrets import (
    clear_openai_api_key,
    has_stored_openai_api_key,
    load_openai_api_key,
    mask_api_key,
    package_secrets_dir,
    save_openai_api_key,
)
from genomeguard.utils import (
    OPENAI_API_KEY_ENV,
    ensure_openai_api_key_in_env,
    has_openai_api_key,
    load_config,
    resolve_genome_db,
    save_config,
)

DEFAULT_OPENAI_MODELS = (
    "gpt-4o",
    "gpt-4o-mini",
    "gpt-4-turbo",
    "gpt-4",
    "gpt-3.5-turbo",
    "o3-mini",
    "o1",
    "o1-mini",
)


def _list_patch_files(workspace: Path, config: dict[str, Any]) -> list[Path]:
    patches_dir = workspace / config.get("patches_dir", ".genome/patches")
    if not patches_dir.is_dir():
        return []
    return sorted(patches_dir.glob("*.patch"), key=lambda path: path.stat().st_mtime, reverse=True)


def _format_mtime(path: Path) -> str:
    stamp = datetime.fromtimestamp(path.stat().st_mtime)
    return stamp.strftime("%Y-%m-%d %H:%M")


def _api_key_status() -> str:
    import os

    env_key = os.environ.get(OPENAI_API_KEY_ENV, "").strip()
    if env_key:
        return f"configured — {mask_api_key(env_key)}"
    if has_stored_openai_api_key():
        try:
            stored = load_openai_api_key()
        except Exception:
            stored = None
        if stored:
            return f"stored — {mask_api_key(stored)}"
        return "stored (decrypt failed)"
    return "not configured"


def _daemon_status_line(running: bool) -> str:
    return "[green]running[/]" if running else "[dim]stopped[/]"


def build_overview_text(
    workspace: Path,
    config_path: Path,
    config: dict[str, Any],
    *,
    daemon_running: bool = False,
) -> str:
    db_path = resolve_genome_db(workspace)
    watcher_status = "ready" if db_path.is_file() else "missing — run codegenome analyze && evolve"
    rules = config.get("rules", [])
    rules_preview = "\n".join(f"  • {rule}" for rule in rules[:4])
    if len(rules) > 4:
        rules_preview += f"\n  • … and {len(rules) - 4} more"

    return (
        f"[bold]Workspace[/]       {workspace}\n"
        f"[bold]Config[/]          {config_path}\n"
        f"[bold]Mode[/]            {config.get('mode', 'patch')}\n"
        f"[bold]Poll interval[/]   {config.get('poll_interval_seconds', 2)}s\n"
        f"[bold]OpenAI model[/]    {config.get('openai_model', 'gpt-4o')}\n"
        f"[bold]Daemon[/]          {_daemon_status_line(daemon_running)}\n"
        f"[bold]API key[/]         {_api_key_status()}\n"
        f"[bold]Watcher DB[/]      {watcher_status}\n"
        f"[bold]Patches dir[/]     {workspace / config.get('patches_dir', '.genome/patches')}\n"
        f"[bold]Secrets dir[/]     {package_secrets_dir()}\n"
        f"[bold]Rules ({len(rules)})[/]\n{rules_preview or '  (none)'}"
    )


def build_patches_text(workspace: Path, config: dict[str, Any]) -> str:
    patches = _list_patch_files(workspace, config)
    if not patches:
        patches_dir = workspace / config.get("patches_dir", ".genome/patches")
        return f"[dim]No patch files in {patches_dir}[/]"

    lines = []
    for patch_path in patches[:20]:
        size_kb = patch_path.stat().st_size / 1024
        lines.append(
            f"[cyan]{patch_path.name}[/]  [dim]{_format_mtime(patch_path)}  {size_kb:.1f} KB[/]"
        )
    if len(patches) > 20:
        lines.append(f"[dim]… and {len(patches) - 20} more[/]")
    return "\n".join(lines)


def _fetch_openai_models() -> list[str]:
    ensure_openai_api_key_in_env()
    try:
        from genomeguard.utils import create_openai_client

        client = create_openai_client()
        response = client.models.list()
        chat_models = sorted(
            {
                model.id
                for model in response.data
                if "gpt" in model.id or model.id.startswith("o")
            },
            reverse=True,
        )
        if chat_models:
            return chat_models
    except Exception:
        pass
    return list(DEFAULT_OPENAI_MODELS)


class _TuiLogHandler(logging.Handler):
    """Forward daemon log records to a thread-safe UI callback."""

    def __init__(self, emit_line: Callable[[str], None]) -> None:
        super().__init__()
        self._emit_line = emit_line
        self.setFormatter(
            logging.Formatter(
                "%(asctime)s %(levelname)s %(name)s: %(message)s",
                datefmt="%H:%M:%S",
            )
        )

    def emit(self, record: logging.LogRecord) -> None:
        try:
            self._emit_line(self.format(record))
        except Exception:
            self.handleError(record)


def run_tui(workspace: Path, config_path: Path) -> None:
    """Launch the GenomeGuard settings TUI."""
    try:
        from textual import on
        from textual.app import App, ComposeResult
        from textual.containers import Horizontal, Vertical, VerticalScroll
        from textual.widgets import (
            Button,
            Footer,
            Header,
            Input,
            Label,
            ListItem,
            ListView,
            RichLog,
            Static,
            Switch,
        )
    except ImportError as exc:
        raise SystemExit(
            "The TUI requires the 'textual' package. Run: pip install -e ."
        ) from exc

    workspace = workspace.resolve()
    config_path = config_path.resolve()
    ensure_openai_api_key_in_env()

    class GenomeGuardApp(App):
        TITLE = "GenomeGuard"
        SUB_TITLE = str(workspace)
        CSS = """
        Screen {
            layout: vertical;
        }
        #content {
            height: 1fr;
            padding: 1 2;
        }
        #overview-panel, #patches-panel {
            width: 1fr;
            height: 1fr;
            border: solid $accent;
            padding: 1 2;
        }
        #settings-panel {
            height: 1fr;
            padding: 1 2;
        }
        #api-view, #model-view, #daemon-view {
            display: none;
        }
        #daemon-log {
            height: 1fr;
            border: solid $accent;
            margin-top: 1;
        }
        #daemon-controls {
            height: auto;
            margin: 1 0;
        }
        #api-input {
            width: 1fr;
            margin: 1 0;
        }
        #model-list {
            height: 1fr;
            border: solid $accent;
        }
        .panel-title {
            text-style: bold;
            margin-bottom: 1;
        }
        #status-line {
            margin-top: 1;
            color: $success;
        }
        """

        BINDINGS = [
            ("q", "quit", "Quit"),
            ("r", "refresh", "Refresh"),
        ]

        def __init__(self) -> None:
            super().__init__()
            self._config = load_config(str(config_path))
            self._active_view = "dashboard"
            self._daemon_thread: threading.Thread | None = None
            self._daemon_stop = threading.Event()
            self._daemon_log_handler: _TuiLogHandler | None = None

        def compose(self) -> ComposeResult:
            yield Header()
            with Horizontal(id="nav"):
                yield Button("Dashboard", id="nav-dashboard", variant="primary")
                yield Button("API Key", id="nav-api")
                yield Button("Model", id="nav-model")
                yield Button("Daemon", id="nav-daemon")
            with Vertical(id="content"):
                yield Static("", id="dashboard-view")
                with Vertical(id="api-view"):
                    yield Static("Set or update your OpenAI API key (stored encrypted).", classes="panel-title")
                    yield Input(placeholder="sk-...", password=True, id="api-input")
                    with Horizontal():
                        yield Button("Save key", id="save-api", variant="success")
                        yield Button("Clear stored key", id="clear-api", variant="error")
                    yield Static("", id="api-status")
                with Vertical(id="model-view"):
                    yield Static("Select the OpenAI model used by the Critic agent.", classes="panel-title")
                    yield ListView(id="model-list")
                    yield Static("", id="model-status")
                with Vertical(id="daemon-view"):
                    yield Static("Run the GenomeGuard watcher daemon from here.", classes="panel-title")
                    with Horizontal(id="daemon-controls"):
                        yield Button("Start daemon", id="start-daemon", variant="success")
                        yield Button("Stop daemon", id="stop-daemon", variant="error", disabled=True)
                        yield Switch(value=not has_openai_api_key(), id="mock-critic-switch")
                        yield Label(" Mock critic")
                    yield Static("", id="daemon-status")
                    yield RichLog(id="daemon-log", highlight=True, markup=True)
            yield Footer()

        def on_mount(self) -> None:
            self._show_dashboard()
            self._refresh_model_list()
            self._update_daemon_controls()

        @property
        def _daemon_running(self) -> bool:
            return self._daemon_thread is not None and self._daemon_thread.is_alive()

        def _reload_config(self) -> None:
            self._config = load_config(str(config_path))

        def _show_view(self, view: str) -> None:
            self._active_view = view
            for widget_id, visible in (
                ("dashboard-view", view == "dashboard"),
                ("api-view", view == "api"),
                ("model-view", view == "model"),
                ("daemon-view", view == "daemon"),
            ):
                widget = self.query_one(f"#{widget_id}")
                widget.display = visible
            for button_id, active in (
                ("nav-dashboard", view == "dashboard"),
                ("nav-api", view == "api"),
                ("nav-model", view == "model"),
                ("nav-daemon", view == "daemon"),
            ):
                button = self.query_one(f"#{button_id}", Button)
                button.variant = "primary" if active else "default"

        def _append_daemon_log(self, line: str) -> None:
            log_widget = self.query_one("#daemon-log", RichLog)
            log_widget.write(line)

        def _log_daemon_line_from_thread(self, line: str) -> None:
            self.call_from_thread(self._append_daemon_log, line)

        def _attach_daemon_logging(self) -> None:
            from genomeguard.core import configure_logging

            configure_logging()
            self._daemon_log_handler = _TuiLogHandler(self._log_daemon_line_from_thread)
            self._daemon_log_handler.setLevel(logging.INFO)
            logging.getLogger("genomeguard").addHandler(self._daemon_log_handler)

        def _detach_daemon_logging(self) -> None:
            if self._daemon_log_handler is not None:
                logging.getLogger("genomeguard").removeHandler(self._daemon_log_handler)
                self._daemon_log_handler = None

        def _update_daemon_controls(self) -> None:
            running = self._daemon_running
            self.query_one("#start-daemon", Button).disabled = running
            self.query_one("#stop-daemon", Button).disabled = not running
            mock_switch = self.query_one("#mock-critic-switch", Switch)
            mock_switch.disabled = running
            status = self.query_one("#daemon-status", Static)
            if running:
                mode = self._config.get("mode", "patch")
                mock = mock_switch.value
                status.update(
                    f"[green]Daemon running[/] — mode={mode}, "
                    f"mock_critic={'on' if mock else 'off'}"
                )
            else:
                status.update("[dim]Daemon stopped.[/]")

        def _daemon_worker(self, mock_critic: bool) -> None:
            from genomeguard.core import run_daemon

            self._reload_config()
            exit_code = run_daemon(
                workspace,
                self._config,
                mock_critic=mock_critic,
                stop_event=self._daemon_stop,
            )
            if exit_code != 0:
                self._log_daemon_line_from_thread(
                    "[red]Daemon exited: watcher DB missing. "
                    "Run: codegenome analyze . && codegenome evolve .[/]"
                )
            self.call_from_thread(self._on_daemon_stopped)

        def _on_daemon_stopped(self) -> None:
            self._detach_daemon_logging()
            self._daemon_thread = None
            self._daemon_stop = threading.Event()
            self._update_daemon_controls()
            if self._active_view == "dashboard":
                self._show_dashboard()

        def _show_dashboard(self) -> None:
            self._reload_config()
            overview = build_overview_text(
                workspace,
                config_path,
                self._config,
                daemon_running=self._daemon_running,
            )
            patches = build_patches_text(workspace, self._config)
            dashboard = self.query_one("#dashboard-view", Static)
            dashboard.update(
                f"[bold underline]General[/]\n\n{overview}\n\n"
                f"[bold underline]Patches[/]\n\n{patches}"
            )
            self._show_view("dashboard")

        def _refresh_model_list(self) -> None:
            model_list = self.query_one("#model-list", ListView)
            model_list.clear()
            current = self._config.get("openai_model", "gpt-4o")
            models = _fetch_openai_models() if has_openai_api_key() else list(DEFAULT_OPENAI_MODELS)
            for model_id in models:
                prefix = "● " if model_id == current else "  "
                model_list.append(ListItem(Label(f"{prefix}{model_id}"), id=f"model-{model_id}"))

        @on(Button.Pressed, "#nav-dashboard")
        def on_nav_dashboard(self) -> None:
            self._show_dashboard()

        @on(Button.Pressed, "#nav-api")
        def on_nav_api(self) -> None:
            status = self.query_one("#api-status", Static)
            if has_stored_openai_api_key() or has_openai_api_key():
                status.update("[dim]A key is already configured. Enter a new value to replace it.[/]")
            else:
                status.update("[dim]No key saved yet.[/]")
            self._show_view("api")

        @on(Button.Pressed, "#nav-daemon")
        def on_nav_daemon(self) -> None:
            self._update_daemon_controls()
            self._show_view("daemon")

        @on(Button.Pressed, "#start-daemon")
        def on_start_daemon(self) -> None:
            db_path = resolve_genome_db(workspace)
            status = self.query_one("#daemon-status", Static)
            if not db_path.is_file():
                status.update(
                    "[red]Cannot start: .genome/watcher.db missing. "
                    "Run codegenome analyze . && codegenome evolve .[/]"
                )
                return

            ensure_openai_api_key_in_env()
            mock_critic = self.query_one("#mock-critic-switch", Switch).value
            if mock_critic and not has_openai_api_key():
                self._append_daemon_log(
                    "[yellow]No API key — running with mock critic fixtures.[/]"
                )
            elif not mock_critic and not has_openai_api_key():
                status.update("[red]Set an API key or enable mock critic before starting.[/]")
                return

            self._daemon_stop.clear()
            self._attach_daemon_logging()
            self._daemon_thread = threading.Thread(
                target=self._daemon_worker,
                args=(mock_critic,),
                name="genomeguard-daemon",
                daemon=True,
            )
            self._daemon_thread.start()
            self._append_daemon_log("[green]Daemon starting…[/]")
            self._update_daemon_controls()
            if self._active_view == "dashboard":
                self._show_dashboard()

        @on(Button.Pressed, "#stop-daemon")
        def on_stop_daemon(self) -> None:
            if not self._daemon_running:
                return
            self._append_daemon_log("[yellow]Stopping daemon…[/]")
            self._daemon_stop.set()
            self.query_one("#stop-daemon", Button).disabled = True

        @on(Button.Pressed, "#nav-model")
        def on_nav_model(self) -> None:
            self._reload_config()
            status = self.query_one("#model-status", Static)
            if not has_openai_api_key():
                status.update(
                    "[yellow]Configure an API key first to fetch live models. "
                    "Showing common defaults.[/]"
                )
            else:
                status.update(f"Current model: [bold]{self._config.get('openai_model', 'gpt-4o')}[/]")
            self._refresh_model_list()
            self._show_view("model")

        @on(Button.Pressed, "#save-api")
        def on_save_api(self) -> None:
            api_input = self.query_one("#api-input", Input)
            status = self.query_one("#api-status", Static)
            value = api_input.value.strip()
            if not value:
                status.update("[red]Enter a non-empty API key.[/]")
                return
            try:
                save_openai_api_key(value)
                ensure_openai_api_key_in_env(force_reload=True)
            except Exception as exc:
                status.update(f"[red]Save failed: {exc}[/]")
                return
            api_input.value = ""
            status.update(f"[green]Saved encrypted key ({mask_api_key(value)}).[/]")

        @on(Button.Pressed, "#clear-api")
        def on_clear_api(self) -> None:
            status = self.query_one("#api-status", Static)
            clear_openai_api_key()
            __import__("os").environ.pop(OPENAI_API_KEY_ENV, None)
            status.update("[green]Stored API key removed.[/]")

        @on(ListView.Selected, "#model-list")
        def on_model_selected(self, event: ListView.Selected) -> None:
            if not has_openai_api_key():
                self.query_one("#model-status", Static).update(
                    "[red]Set an API key before choosing a model.[/]"
                )
                return
            item_id = str(event.item.id or "")
            if not item_id.startswith("model-"):
                return
            model_id = item_id.removeprefix("model-")
            save_config(str(config_path), {"openai_model": model_id})
            self._reload_config()
            self.query_one("#model-status", Static).update(
                f"[green]Model set to [bold]{model_id}[/][/]"
            )
            self._refresh_model_list()

        def action_refresh(self) -> None:
            if self._active_view == "dashboard":
                self._show_dashboard()
            elif self._active_view == "model":
                self.on_nav_model()
            elif self._active_view == "daemon":
                self._update_daemon_controls()

        def on_unmount(self) -> None:
            if self._daemon_running:
                self._daemon_stop.set()
                if self._daemon_thread is not None:
                    self._daemon_thread.join(timeout=5)
            self._detach_daemon_logging()

    GenomeGuardApp().run()
