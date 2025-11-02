"""
Interactive CLI interface for the Hyperliquid trading system.

This module provides a command-line interface with tab completion support
for managing orders, positions, and account status.
"""

import cmd
import sys
from pathlib import Path
from typing import List

from models import Config
from .api import BackendAPI
from .formatters import TableFormatter


class InteractiveCLI(cmd.Cmd):
    """
    Interactive command-line interface for Hyperliquid trading operations.

    Provides tab completion, command history, and a user-friendly prompt
    for executing trading commands.
    """

    intro = "Welcome to Hyperliquid CLI. Type 'help' or '?' to list commands.\n"
    prompt = "hyperliquid> "

    def __init__(self, config_path: Path) -> None:
        """Initialize the CLI with configuration."""
        super().__init__()
        self.config = Config.from_file(config_path)
        self.running = True

    def do_order(self, args: str) -> None:
        """Place an order (not implemented yet)."""
        print("🚧 Order functionality not implemented yet")

    def help_order(self) -> None:
        """Show help for the order command."""
        print("order - Place a new order")
        print("Usage: order <parameters>")
        print("This command is currently under development")

    def do_status(self, args: str) -> None:
        """Show account status."""
        try:
            with BackendAPI(self.config) as api:
                # Get backend status
                root_data = api.get_root()

                # Prepare status information
                status_info = {
                    "account_address": self.config.hyperliquid.account_address,
                    "network": self.config.hyperliquid.network,
                    "api_status": root_data.status,
                    "api_version": root_data.version,
                }

                # Format and display
                headers = ["Property", "Value"]
                rows = [
                    ["Account", status_info["account_address"]],
                    ["Network", status_info["network"]],
                    ["API Status", status_info["api_status"]],
                    ["API Version", status_info["api_version"]],
                ]

                formatter = TableFormatter()
                print(formatter.format((headers, rows), title="Account Status"))
                print()

        except Exception as e:
            print(f"❌ Error fetching status: {e}")
            print(f"Configured account: {self.config.hyperliquid.account_address}")
            print(f"Network: {self.config.hyperliquid.network}")

    def help_status(self) -> None:
        """Show help for the status command."""
        print("status - Show account status and information")
        print("Usage: status")
        print("Displays account configuration and API connection status")

    def do_positions(self, args: str) -> None:
        """Show current positions."""
        try:
            with BackendAPI(self.config) as api:
                positions = api.get_positions()

                if not positions:
                    print("\nNo open positions\n")
                    return

                # Format positions for display
                headers = [
                    "Coin",
                    "Size",
                    "Entry Price",
                    "Mark Price",
                    "PnL",
                    "Leverage",
                    "Margin",
                ]
                rows = []

                for pos in positions:
                    # Add color indicators for PnL
                    pnl_value = float(pos.unrealized_pnl)
                    pnl_display = f"${abs(pnl_value):.2f}"
                    if pnl_value > 0:
                        pnl_display = f"▲ ${pnl_value:.2f}"
                    elif pnl_value < 0:
                        pnl_display = f"▼ ${abs(pnl_value):.2f}"

                    # Format size with appropriate precision
                    size_display = f"{float(pos.size):.6f}".rstrip("0").rstrip(".")

                    rows.append(
                        [
                            pos.coin,
                            size_display,
                            f"${float(pos.entry_price):.4f}",
                            f"${float(pos.mark_price):.4f}",
                            pnl_display,
                            f"{pos.leverage}x {pos.leverage_type}",
                            f"${float(pos.margin_used):.2f}",
                        ]
                    )

                formatter = TableFormatter()
                print(formatter.format((headers, rows), title="Open Positions"))
                print()

        except Exception as e:
            print(f"❌ Error fetching positions: {e}")

    def help_positions(self) -> None:
        """Show help for the positions command."""
        print("positions - Show current open positions")
        print("Usage: positions")
        print("Displays all open positions with detailed information")

    def do_conditionals(self, args: str) -> None:
        """Manage conditional orders (not implemented yet)."""
        print("🚧 Conditionals functionality not implemented yet")

    def help_conditionals(self) -> None:
        """Show help for the conditionals command."""
        print("conditionals - Manage conditional orders")
        print("Usage: conditionals <action> <parameters>")
        print("This command is currently under development")

    def do_quit(self, args: str) -> bool:
        """Exit the CLI."""
        print("👋 Goodbye!")
        self.running = False
        return True

    def do_exit(self, args: str) -> bool:
        """Exit the CLI (alias for quit)."""
        return self.do_quit(args)

    def do_EOF(self, args: str) -> bool:
        """Handle EOF (Ctrl+D) to exit gracefully."""
        print("\n👋 Goodbye!")
        self.running = False
        return True

    def emptyline(self) -> bool:
        """Do nothing on empty input - override default behavior of repeating last command."""
        return False

    def default(self, line: str) -> None:
        """Handle unknown commands."""
        print(f"❌ Unknown command: {line}")
        print("Type 'help' or '?' to see available commands")

    def completenames(self, text: str, *ignored: str) -> List[str]:
        """Override to provide custom command completion."""
        commands = [
            "order",
            "status",
            "positions",
            "conditionals",
            "quit",
            "exit",
            "help",
            "?",
        ]
        return [cmd for cmd in commands if cmd.startswith(text)]

    def run(self) -> None:
        """
        Run the interactive CLI loop.

        This method starts the main command loop and handles
        keyboard interrupts gracefully.
        """
        ctrl_c_count = 0
        try:
            while self.running:
                try:
                    self.cmdloop()
                    break
                except KeyboardInterrupt:
                    ctrl_c_count += 1
                    if ctrl_c_count >= 2:
                        print("\n👋 Goodbye!")
                        self.running = False
                        break
                    print("\nUse 'quit' or 'exit' to exit, or press Ctrl+C again")
        except Exception as e:
            print(f"❌ Fatal error: {e}", file=sys.stderr)
            raise
