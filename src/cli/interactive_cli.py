"""
Interactive CLI interface for the Hyperliquid trading system.

This module provides a command-line interface with tab completion support
for managing orders, positions, and account status using an in-process
HyperliquidClient.
"""

from __future__ import annotations

import cmd
import sys
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from typing import IO, cast

import typer

from exchange import HyperliquidClient
from models.api import PnlHistoryCatalog, WatchInterval, WatchSnapshot
from models.config import Config
from models.order import (
    LimitOrder,
    MarketOrder,
    ModifyOrderRequest,
    OrderHistoryEntry,
    OrderInfo,
    OrderResult,
)

from .cli_manual import build_cli_manual
from .command_output_writer import TrailingNewlineNormalizingWriter
from .formatters import OrderFormatter
from .interactive import AskFrontend, ModifyWizard, OrderWizard, PnlTUI, WatchTUI
from .interactive.repl_account import ReplAccountMixin
from .interactive.repl_help import ReplHelpMixin
from .interactive.repl_order_create import ReplOrderCreateMixin
from .interactive.repl_orders import ReplOrdersMixin
from .interactive.repl_positions import ReplPositionsMixin


class InteractiveCLI(
    ReplOrderCreateMixin,
    ReplOrdersMixin,
    ReplAccountMixin,
    ReplPositionsMixin,
    ReplHelpMixin,
    cmd.Cmd,
):
    """Interactive command-line interface for Hyperliquid trading operations."""

    intro = "Welcome to Hyperliquid CLI. Type 'help' or '?' to list commands.\n"
    prompt = "hyperliquid> "

    def __init__(self, config: Config, client: HyperliquidClient | None = None) -> None:
        """Initialize the CLI with configuration and optional shared exchange client."""
        super().__init__()
        self.config = config
        self._client = client

    def _create_client(self) -> HyperliquidClient:
        """Create a fresh HyperliquidClient instance."""
        return HyperliquidClient(self.config)

    @contextmanager
    def _client_scope(self) -> Iterator[HyperliquidClient]:
        """Yield the shared REPL client when provided, or open a short-lived one."""
        if self._client is not None:
            yield self._client
            return
        with self._create_client() as client:
            yield client

    def _run_order_wizard(self, client: HyperliquidClient) -> MarketOrder | LimitOrder:
        """Launch the interactive order wizard."""
        return OrderWizard(self.config, client).run()

    def _run_modify_wizard(self, client: HyperliquidClient, order_id: int) -> ModifyOrderRequest:
        """Launch the interactive modify wizard."""
        return ModifyWizard(self.config, client).run(order_id)

    def _run_pnl_tui(self, history_catalog: PnlHistoryCatalog) -> None:
        """Launch the fullscreen PnL TUI."""
        PnlTUI(history_catalog).run()

    def _run_watch_tui(
        self,
        coin: str,
        fetcher: Callable[[str, WatchInterval, int], WatchSnapshot],
    ) -> None:
        """Launch the fullscreen Watch TUI."""
        WatchTUI(coin, fetcher).run()

    def _print_order_output(
        self,
        data: OrderResult | OrderInfo | list[OrderInfo],
        **kwargs: str,
    ) -> None:
        """Render order-related output with the shared formatter."""
        formatter = OrderFormatter()
        try:
            print(formatter.format(data, **kwargs))
        except ValueError as format_err:
            print(format_err)

    def _format_order_history_output(self, history: list[object]) -> str:
        """Format filled-order history entries with OrderFormatter."""
        entries = cast(list[OrderHistoryEntry], history)
        return OrderFormatter().format(entries)

    def _clear_screen(self) -> None:
        """Clear the active terminal screen and move the cursor home."""
        print("\033[2J\033[H", end="")

    def _should_normalize_output(self, line: str) -> bool:
        """Return whether a command should use trailing blank-line normalization."""
        command, _, _ = self.parseline(line)
        return command not in {"pnl", "watch"}

    def onecmd(self, line: str) -> bool:
        """Run one command and normalize its trailing blank line before the next prompt."""
        if not line.strip():
            return super().onecmd(line)

        if not self._should_normalize_output(line):
            return super().onecmd(line)

        original_stdout = sys.stdout
        original_cmd_stdout = self.stdout
        writer = TrailingNewlineNormalizingWriter(original_stdout)
        typed_writer = cast(IO[str], writer)
        sys.stdout = typed_writer
        self.stdout = typed_writer
        try:
            stop = super().onecmd(line)
        finally:
            sys.stdout = original_stdout
            self.stdout = original_cmd_stdout

        writer.finalize(add_blank_line=self._should_add_blank_line(line, stop))
        return stop

    def _should_add_blank_line(self, line: str, stop: bool) -> bool:
        """Return whether a command should end with a normalized blank line."""
        if stop:
            return False
        command_name = line.strip().split(maxsplit=1)[0].lower()
        return command_name != "ask"

    def do_ask(self, args: str) -> None:
        """Ask the CLI assistant a question or launch an interactive chat session."""
        frontend = AskFrontend(self.config, manual_builder=lambda: build_cli_manual(self))
        try:
            if args.strip():
                print(frontend.submit(args))
                return
            frontend.run_interactive()
            print()
        except KeyboardInterrupt:
            print("\n❌ Ask session cancelled\n")
        except Exception as e:
            print(f"❌ Ask failed: {e}\n")

    def do_conditionals(self, args: str) -> None:
        """Manage conditional orders (not implemented yet)."""
        print("🚧 Conditionals functionality not implemented yet")

    def do_clear(self, args: str) -> None:
        """Clear the terminal screen."""
        if args.strip():
            print("❌ Error: clear does not take any arguments")
            print("Usage: clear")
            return
        self._clear_screen()

    def do_cls(self, args: str) -> None:
        """Clear the terminal screen (alias for clear)."""
        self.do_clear(args)

    def do_quit(self, args: str) -> bool:
        """Exit the CLI."""
        return True

    def do_exit(self, args: str) -> bool:
        """Exit the CLI (alias for quit)."""
        return self.do_quit(args)

    def do_EOF(self, args: str) -> bool:  # noqa: N802
        """Handle EOF (Ctrl+D) to exit gracefully."""
        return True

    def emptyline(self) -> bool:
        """Do nothing on empty input - override default behavior of repeating last command."""
        return False

    def default(self, line: str) -> None:
        """Handle unknown commands."""
        print(f"❌ Unknown command: {line}")
        print("Type 'help' or '?' to see available commands")

    def completenames(self, text: str, *ignored: str) -> list[str]:
        """Override to provide custom command completion."""
        command_names = {
            attribute_name.removeprefix("do_")
            for attribute_name in dir(self)
            if attribute_name.startswith("do_")
        }
        command_names.update({"help", "?"})
        return sorted(command for command in command_names if command.startswith(text))

    def run(self) -> None:
        """Run the interactive CLI loop and handle keyboard interrupts gracefully."""
        while True:
            try:
                self.cmdloop()
                typer.echo("👋 Goodbye!")
                return
            except KeyboardInterrupt:
                try:
                    if typer.confirm("\nQuit?", default=False):
                        typer.echo("👋 Goodbye!")
                        return
                    self.intro = ""
                    continue
                except typer.Abort:
                    typer.echo("\n👋 Goodbye!")
                    return
