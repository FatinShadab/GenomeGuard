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
    user_credentials_dir,
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

GENOMEGUARD_ASCII_BANNER = r"""[bold cyan]      A ═ T        ____                                 ____                      _[/]
[bold cyan]     G ─── C      / ___| ___ _ __   ___  _ __ ___   ___ / ___|_   _  __ _ _ __   __| |[/]
[bold cyan]    C ───── G    | |  _ / _ \ '_ \ / _ \| '_ ` _ \ / _ \ |  _| | | |/ _` | '___|/ _` |[/]
[bold cyan]     T ─── A     | |_| |  __/ | | | (_) | | | | | |  __/ |_| | |_| | (_| | |   | (_| |[/]
[bold cyan]      G ═ C       \____|\___|_| |_|\___/|_| |_| |_|\___|\____|\__,_|\__,_|_|    \__,_|[/]
[bold cyan]      C ═ G[/]
[bold cyan]     A ─── T                  REAL-TIME IMMUNE ARCHITECTURE SYSTEM[/]
[bold cyan]    G ───── C                 [/][dim]Shielding code community rules & structural integrity[/]
[bold cyan]     C ─── G[/]
[bold cyan]      T ═ A[/]"""


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
        return f"[bold green]Configured (Environment)[/] — {mask_api_key(env_key)}"
    if has_stored_openai_api_key():
        try:
            stored = load_openai_api_key()
        except Exception:
            stored = None
        if stored:
            return f"[bold green]Configured (Encrypted Storage)[/] — {mask_api_key(stored)}"
        return "[bold red]Stored (Decrypt Failed)[/]"
    return "[bold yellow]Not Configured[/]"


def _daemon_status_line(running: bool) -> str:
    return "[bold green]● Running[/]" if running else "[bold red]■ Stopped[/]"


def build_overview_text(
    workspace: Path,
    config_path: Path,
    config: dict[str, Any],
    *,
    daemon_running: bool = False,
) -> str:
    db_path = resolve_genome_db(workspace)
    watcher_status = "[bold green]✔ Ready[/]" if db_path.is_file() else "[bold red]✖ Missing[/] (run codegenome analyze && evolve)"
    rules = config.get("rules", [])
    rules_preview = "\n".join(f"  [cyan]•[/] {rule}" for rule in rules[:6])
    if len(rules) > 6:
        rules_preview += f"\n  [cyan]•[/] … and {len(rules) - 6} more"

    return (
        f"[bold cyan]SYSTEM PROFILE[/]\n"
        f"─────────────────────────────────────────\n"
        f"[bold]Workspace:[/]       {workspace}\n"
        f"[bold]Config:[/]          {config_path}\n"
        f"[bold]Watcher DB:[/]      {watcher_status}\n"
        f"[bold]Secrets Dir:[/]     {user_credentials_dir()}\n\n"
        f"[bold cyan]ENGINE CONFIGURATION[/]\n"
        f"─────────────────────────────────────────\n"
        f"[bold]Mode:[/]            [bold green]{config.get('mode', 'patch').upper()}[/]\n"
        f"[bold]Poll Interval:[/]   {config.get('poll_interval_seconds', 2)}s\n"
        f"[bold]OpenAI Model:[/]    [bold yellow]{config.get('openai_model', 'gpt-4o')}[/]\n"
        f"[bold]API Key:[/]         {_api_key_status()}\n"
        f"[bold]Daemon Status:[/]   {_daemon_status_line(daemon_running)}\n\n"
        f"[bold cyan]ACTIVE LAWS & RULES ({len(rules)})[/]\n"
        f"─────────────────────────────────────────\n"
        f"{rules_preview or '  (none)'}"
    )


def build_patches_text(workspace: Path, config: dict[str, Any]) -> str:
    patches = _list_patch_files(workspace, config)
    if not patches:
        patches_dir = workspace / config.get("patches_dir", ".genome/patches")
        return (
            f"[bold cyan]PATCHES REPOSITORY[/]\n"
            f"─────────────────────────────────────────\n\n"
            f"[dim]No patch files found in {patches_dir}[/]\n"
            f"[dim]The Surgeon agent will write patches here when architectural decay is detected.[/]"
        )

    lines = [
        f"[bold cyan]PATCHES REPOSITORY ({len(patches)})[/]\n"
        f"─────────────────────────────────────────"
    ]
    for patch_path in patches[:20]:
        size_kb = patch_path.stat().st_size / 1024
        lines.append(
            f" [bold green]✔[/] [bold]{patch_path.name}[/]\n"
            f"   [dim]Modified: {_format_mtime(patch_path)}   Size: {size_kb:.1f} KB[/]"
        )
    if len(patches) > 20:
        lines.append(f"\n [dim]… and {len(patches) - 20} more patches available[/]")
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
            TabbedContent,
            TabPane,
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
        SUB_TITLE = f"Workspace: {workspace}"
        CSS = """
        Screen {
            background: $background;
            color: $text;
        }

        Header {
            background: $accent;
            color: $text;
            text-style: bold;
        }

        Footer {
            background: $surface;
            color: $text;
        }

        TabbedContent {
            height: 1fr;
        }

        TabPane {
            padding: 1 2;
            background: $background;
        }

        #dashboard-banner {
            height: auto;
            border: double $accent;
            background: $surface;
            padding: 1 3;
            margin-bottom: 1;
            color: $text;
            width: 100%;
        }

        /* Dashboard Grid Layout */
        #dashboard-grid {
            height: 1fr;
            layout: grid;
            grid-size: 2;
            grid-columns: 1fr 1fr;
            grid-gutter: 2;
        }

        #overview-panel, #patches-panel {
            border: tall $accent;
            background: $surface;
            padding: 1 2;
            height: 1fr;
        }

        .panel-header {
            text-style: bold;
            margin-bottom: 1;
            color: $accent;
        }

        .panel-desc {
            margin-bottom: 1;
            color: $text-muted;
            height: auto;
        }

        /* API Panel */
        #api-panel {
            border: tall $accent;
            background: $surface;
            padding: 2 4;
            max-width: 80;
            height: auto;
            align: center middle;
            margin: 2 4;
        }

        #api-input {
            margin: 1 0;
        }

        #api-buttons {
            height: auto;
            align: center middle;
            margin-top: 1;
            width: 100%;
        }

        #api-buttons Button {
            margin: 0 2;
        }

        #api-status {
            margin-top: 1;
            text-align: center;
            height: auto;
        }

        /* Model Panel */
        #model-panel {
            border: tall $accent;
            background: $surface;
            padding: 1 2;
            height: 1fr;
        }

        #model-list {
            border: solid $accent-darken-1;
            background: $background;
            margin-top: 1;
            height: 1fr;
        }

        #model-list ListItem {
            padding: 1 2;
        }

        #model-list ListItem:hover {
            background: $accent-muted;
        }

        #model-list ListItem.--focus {
            background: $accent;
            color: $text;
            text-style: bold;
        }

        #model-status {
            margin-top: 1;
            text-style: bold;
            height: auto;
        }

        /* Daemon Panel */
        #daemon-panel {
            border: tall $accent;
            background: $surface;
            padding: 1 2;
            height: 1fr;
        }

        #daemon-controls {
            height: auto;
            align: left middle;
            margin: 1 0;
            background: $background;
            padding: 1 2;
            border: solid $accent-muted;
            width: 100%;
        }

        #daemon-controls Button {
            margin-right: 2;
        }

        #mock-switch-container {
            width: auto;
            align: left middle;
            height: auto;
        }

        #mock-label {
            margin-left: 1;
            text-style: bold;
            height: auto;
        }

        #daemon-status {
            margin: 1 0;
            text-style: bold;
            height: auto;
        }

        #daemon-log {
            height: 1fr;
            border: solid $accent-darken-1;
            background: $background;
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
            with TabbedContent(id="tabs"):
                with TabPane("Dashboard", id="dashboard"):
                    yield Static(GENOMEGUARD_ASCII_BANNER, id="dashboard-banner")
                    with Horizontal(id="dashboard-grid"):
                        with VerticalScroll(id="overview-panel"):
                            yield Static("", id="overview-content")
                        with VerticalScroll(id="patches-panel"):
                            yield Static("", id="patches-content")
                with TabPane("API Key", id="api"):
                    with Vertical(id="api-panel"):
                        yield Static("[bold cyan]OPENAI CREDENTIALS[/]", classes="panel-header")
                        yield Static(
                            "Configure your OpenAI API key. The key is encrypted using machine-local "
                            "credentials and saved in the package source tree. It is never committed to git.",
                            classes="panel-desc"
                        )
                        yield Input(placeholder="sk-...", password=True, id="api-input")
                        with Horizontal(id="api-buttons"):
                            yield Button("Save Key", id="save-api", variant="success")
                            yield Button("Clear Key", id="clear-api", variant="error")
                        yield Static("", id="api-status")
                with TabPane("Model", id="model"):
                    with Vertical(id="model-panel"):
                        yield Static("[bold cyan]CRITIC MODEL SELECTION[/]", classes="panel-header")
                        yield Static(
                            "Select which OpenAI model the Critic agent should use to analyze code changes "
                            "and detect architectural decay.",
                            classes="panel-desc"
                        )
                        yield Static("", id="model-status")
                        yield ListView(id="model-list")
                with TabPane("Daemon", id="daemon"):
                    with Vertical(id="daemon-panel"):
                        yield Static("[bold cyan]DAEMON CONTROL CENTER[/]", classes="panel-header")
                        yield Static(
                            "The GenomeGuard daemon polls the CodeGenome watcher database in real-time. "
                            "When a file is modified, it runs the Sensor → Critic → Verifier → Surgeon pipeline.",
                            classes="panel-desc"
                        )
                        with Horizontal(id="daemon-controls"):
                            yield Button("Start Daemon", id="start-daemon", variant="success")
                            yield Button("Stop Daemon", id="stop-daemon", variant="error", disabled=True)
                            with Horizontal(id="mock-switch-container"):
                                yield Switch(value=not has_openai_api_key(), id="mock-critic-switch")
                                yield Label("Mock Critic Mode", id="mock-label")
                        yield Static("", id="daemon-status")
                        yield RichLog(id="daemon-log", highlight=True, markup=True)
            yield Footer()

        def on_mount(self) -> None:
            self._update_daemon_controls()

        @property
        def _daemon_running(self) -> bool:
            return self._daemon_thread is not None and self._daemon_thread.is_alive()

        def _reload_config(self) -> None:
            self._config = load_config(str(config_path))

        @on(TabbedContent.TabActivated)
        async def on_tab_activated(self, event: TabbedContent.TabActivated) -> None:
            active_id = event.tabbed_content.active
            self._active_view = active_id
            if active_id == "dashboard":
                self._show_dashboard()
            elif active_id == "api":
                status = self.query_one("#api-status", Static)
                if has_stored_openai_api_key() or has_openai_api_key():
                    status.update("[dim]A key is already configured. Enter a new value to replace it.[/]")
                else:
                    status.update("[dim]No key saved yet.[/]")
            elif active_id == "model":
                await self.on_nav_model()
            elif active_id == "daemon":
                self._update_daemon_controls()

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
            self.query_one("#overview-content", Static).update(overview)
            self.query_one("#patches-content", Static).update(patches)

        async def _refresh_model_list(self) -> None:
            model_list = self.query_one("#model-list", ListView)
            await model_list.clear()
            current = self._config.get("openai_model", "gpt-4o")
            models = _fetch_openai_models() if has_openai_api_key() else list(DEFAULT_OPENAI_MODELS)
            for model_id in models:
                prefix = "● " if model_id == current else "  "
                model_list.append(ListItem(Label(f"{prefix}{model_id}")))

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

        async def on_nav_model(self) -> None:
            self._reload_config()
            status = self.query_one("#model-status", Static)
            if not has_openai_api_key():
                status.update(
                    "[yellow]Configure an API key first to fetch live models. "
                    "Showing common defaults.[/]"
                )
            else:
                status.update(f"Current model: [bold]{self._config.get('openai_model', 'gpt-4o')}[/]")
            await self._refresh_model_list()

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
        async def on_model_selected(self, event: ListView.Selected) -> None:
            if not has_openai_api_key():
                self.query_one("#model-status", Static).update(
                    "[red]Set an API key before choosing a model.[/]"
                )
                return
            label = event.item.query_one(Label)
            content = getattr(label, "renderable", getattr(label, "content", ""))
            model_id = str(content).strip().lstrip("●").strip()
            if not model_id:
                return
            save_config(str(config_path), {"openai_model": model_id})
            self._reload_config()
            self.query_one("#model-status", Static).update(
                f"[green]Model set to [bold]{model_id}[/][/]"
            )
            await self._refresh_model_list()

        async def action_refresh(self) -> None:
            if self._active_view == "dashboard":
                self._show_dashboard()
            elif self._active_view == "model":
                await self.on_nav_model()
            elif self._active_view == "daemon":
                self._update_daemon_controls()

        def on_unmount(self) -> None:
            if self._daemon_running:
                self._daemon_stop.set()
                if self._daemon_thread is not None:
                    self._daemon_thread.join(timeout=5)
            self._detach_daemon_logging()

    GenomeGuardApp().run()
