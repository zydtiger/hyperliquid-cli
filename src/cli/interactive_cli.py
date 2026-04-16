"""
Interactive CLI interface for the Hyperliquid trading system.

This module provides a command-line interface with tab completion support
for managing orders, positions, and account status.
"""

import cmd
import sys
from decimal import Decimal, InvalidOperation
from typing import IO, cast

import typer

from models.api import LeverageType, PositionInfo
from models.config import Config
from models.order import LimitOrder, MarketOrder, OrderSide, OrderTif

from .api import BackendAPI
from .cli_manual import build_cli_manual
from .command_output_writer import TrailingNewlineNormalizingWriter
from .formatters import AccountFormatter, OrderFormatter, TableFormatter
from .interactive import AskFrontend, ModifyWizard, OrderWizard, PnlTUI, WatchTUI

MIN_CHANGE_LEVERAGE_ARGS = 2
MIN_UPDATE_MARGIN_ARGS = 2
QUICK_ORDER_ARGS = 3
MIN_LEVERAGE = 1
MAX_LEVERAGE = 250
DEFAULT_ORDER_HISTORY_LIMIT = 10


class InteractiveCLI(cmd.Cmd):
    """
    Interactive command-line interface for Hyperliquid trading operations.

    Provides tab completion, command history, and a user-friendly prompt
    for executing trading commands.
    """

    intro = "Welcome to Hyperliquid CLI. Type 'help' or '?' to list commands.\n"
    prompt = "hyperliquid> "

    def __init__(self, config: Config) -> None:
        """Initialize the CLI with configuration."""
        super().__init__()
        self.config = config

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

    def _parse_quick_order(self, args: str) -> MarketOrder | LimitOrder:
        """Parse quick-order arguments into a market or limit order."""
        parts = args.strip().split()
        if len(parts) != QUICK_ORDER_ARGS:
            raise ValueError("Quick order requires exactly 3 arguments")

        try:
            side = OrderSide(parts[0].lower())
        except ValueError as exc:
            raise ValueError("Side must be 'buy' or 'sell'") from exc

        coin = parts[1].upper()
        quantity_spec = parts[2]

        # A single numeric quantity means a market order, while `qty@price`
        # selects the fast limit-order path.
        if "@" not in quantity_spec:
            try:
                quantity = Decimal(quantity_spec)
            except InvalidOperation as exc:
                raise ValueError("Quantity must be a valid decimal value") from exc

            if quantity <= 0:
                raise ValueError("Quantity must be greater than 0")

            return MarketOrder(
                coin=coin,
                side=side,
                quantity=quantity,
                reduce_only=False,
            )

        quantity_text, price_text = quantity_spec.split("@", maxsplit=1)
        if not quantity_text or not price_text:
            raise ValueError("Limit orders must use the format <quantity>@<price>")

        try:
            quantity = Decimal(quantity_text)
        except InvalidOperation as exc:
            raise ValueError("Quantity must be a valid decimal value") from exc

        try:
            price = Decimal(price_text)
        except InvalidOperation as exc:
            raise ValueError("Price must be a valid decimal value") from exc

        if quantity <= 0:
            raise ValueError("Quantity must be greater than 0")
        if price <= 0:
            raise ValueError("Price must be greater than 0")

        return LimitOrder(
            coin=coin,
            side=side,
            quantity=quantity,
            price=price,
            reduce_only=False,
            time_in_force=OrderTif.GTC,
        )

    def _submit_order(self, api: BackendAPI, order: MarketOrder | LimitOrder) -> None:
        """Submit an order and print the formatted result."""
        print("⏳ Submitting order...")

        # Route the quick-order and wizard flows through the same submission
        # logic so validation, formatting, and error handling stay aligned.
        try:
            if isinstance(order, LimitOrder):
                result = api.submit_limit_order(order)
            else:
                result = api.submit_market_order(order)

            formatter = OrderFormatter()
            try:
                print(formatter.format(result))
            except ValueError as format_err:
                print(format_err)

        except Exception as submission_err:
            print(f"❌ Failed to submit order: {submission_err}")

    def do_order(self, args: str) -> None:
        """
        Place a new order using quick args or the interactive wizard.

        Calling `order` with no arguments launches the wizard. Supplying
        `order <buy|sell> <coin> <quantity|quantity@price>` submits a
        market or limit order directly.
        """
        try:
            with BackendAPI(self.config) as api:
                if args.strip():
                    order = self._parse_quick_order(args)
                else:
                    wizard = OrderWizard(self.config, api)
                    order = wizard.run()

                self._submit_order(api, order)

        except KeyboardInterrupt:
            print("❌ Order creation cancelled")
        except ValueError as e:
            print(f"❌ Error: {e}")
            print("Usage: order")
            print("   or: order <buy|sell> <coin> <quantity|quantity@price>")
        except Exception as e:
            print(f"❌ Failed to create order: {e}")
        finally:
            print()

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

    def help_ask(self) -> None:
        """Show help for the ask command."""
        print("ask - Ask the CLI assistant about available commands and usage")
        print("Usage: ask <question>")
        print("   or: ask")
        print()
        print("Examples:")
        print("  ask how do i place a limit order")
        print("  ask")
        print()
        print("With a trailing prompt, ask sends one question to the CLI assistant.")
        print("With no trailing prompt, ask starts an interactive session using the >>> prompt.")
        print("Type /bye, /exit, or /quit to leave the interactive session.")
        print("Responses are returned by the configured OpenAI-compatible agent endpoint.")

    def help_order(self) -> None:
        """Show help for the order command."""
        print("order - Launch the wizard or place a quick market/limit order")
        print("Usage: order")
        print("   or: order <buy|sell> <coin> <quantity|quantity@price>")
        print()
        print("Examples:")
        print("  order")
        print("  order buy ETH 0.25")
        print("  order sell BTC 0.01@105000")
        print()
        print(
            "With no arguments, this command starts an interactive wizard that guides you through:"
        )
        print("- Selecting a trading coin")
        print("- Choosing order side (buy/sell)")
        print("- Selecting order type (market/limit)")
        print("- Setting price (for limit orders)")
        print("- Specifying quantity")
        print("- Configuring additional options")
        print("- Optionally adding a trigger price with STOP/TAKE selection")
        print()
        print("Quick-order syntax:")
        print("- `<quantity>` submits a market order")
        print("- `<quantity>@<price>` submits a GTC limit order")
        print("- Quick orders default to non-reduce-only and do not add triggers")
        print()
        print("The wizard provides market data suggestions and validates all inputs.")
        print("Wizard orders are submitted upon confirmation.")

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

                formatter = AccountFormatter()
                try:
                    print(formatter.format(positions))
                except ValueError as format_err:
                    print(format_err)
                print()

        except Exception as e:
            print(f"❌ Error fetching positions: {e}")

    def help_positions(self) -> None:
        """Show help for the positions command."""
        print("positions - Show current open positions")
        print("Usage: positions")
        print("Displays all open positions with detailed information")

    def do_balances(self, args: str) -> None:
        """Show comprehensive balance information."""
        try:
            with BackendAPI(self.config) as api:
                balances = api.get_balances()
                formatter = AccountFormatter()
                try:
                    print(formatter.format(balances))
                except ValueError as format_err:
                    print(format_err)
                print()
        except Exception as e:
            print(f"❌ Error fetching balances: {e}")

    def help_balances(self) -> None:
        """Show help for the balances command."""
        print("balances - Show comprehensive balance information")
        print("Usage: balances")
        print("Displays perpetuals account, spot balances, and staking information")

    def do_staking(self, args: str) -> None:
        """Show staking status for the configured account."""
        if args.strip():
            print("❌ Error: staking does not take any arguments")
            print("Usage: staking")
            return

        try:
            with BackendAPI(self.config) as api:
                staking_status = api.get_staking_status()
                formatter = AccountFormatter()
                try:
                    print(formatter.format(staking_status))
                except ValueError as format_err:
                    print(format_err)
                print()
        except Exception as e:
            print(f"❌ Error fetching staking status: {e}")

    def help_staking(self) -> None:
        """Show help for the staking command."""
        print("staking - Show staking status for the configured account")
        print("Usage: staking")
        print("Displays total staked HYPE and validators with active delegations")

    def do_conditionals(self, args: str) -> None:
        """Manage conditional orders (not implemented yet)."""
        print("🚧 Conditionals functionality not implemented yet")

    def help_conditionals(self) -> None:
        """Show help for the conditionals command."""
        print("conditionals - Manage conditional orders")
        print("Usage: conditionals <action> <parameters>")
        print("This command is currently under development")

    def do_clear(self, args: str) -> None:
        """Clear the terminal screen."""
        if args.strip():
            print("❌ Error: clear does not take any arguments")
            print("Usage: clear")
            return

        self._clear_screen()

    def help_clear(self) -> None:
        """Show help for the clear command."""
        print("clear - Clear the terminal screen")
        print("Usage: clear")

    def do_cls(self, args: str) -> None:
        """Clear the terminal screen (alias for clear)."""
        self.do_clear(args)

    def help_cls(self) -> None:
        """Show help for the cls command."""
        self.help_clear()

    def do_quit(self, args: str) -> bool:
        """Exit the CLI."""
        return True

    def help_quit(self) -> None:
        """Show help for the quit command."""
        print("quit - Exit the CLI")
        print("Usage: quit")

    def do_exit(self, args: str) -> bool:
        """Exit the CLI (alias for quit)."""
        return self.do_quit(args)

    def help_exit(self) -> None:
        """Show help for the exit command."""
        print("exit - Exit the CLI")
        print("Usage: exit")

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

    def do_order_status(self, args: str) -> None:
        """
        Get status and details of a specific order.

        Usage: order_status <order_id>

        Example: order_status 12345
        """
        if not args.strip():
            print("❌ Error: Order ID is required")
            print("Usage: order_status <order_id>")
            print("Example: order_status 12345")
            return

        try:
            order_id = int(args.strip())
            if order_id <= 0:
                raise ValueError("Order ID must be a positive integer")
        except ValueError as e:
            print(f"❌ Invalid order ID: {e}")
            print("Order ID must be a positive integer")
            return

        try:
            with BackendAPI(self.config) as api:
                order_info = api.get_order_status(order_id)

                # Use the order formatter to display OrderInfo
                formatter = OrderFormatter()
                print()
                try:
                    print(formatter.format(order_info))
                except ValueError as format_err:
                    print(format_err)
                print()

        except Exception as e:
            print(f"❌ Error fetching order status: {e}")

    def help_order_status(self) -> None:
        """Show help for the order_status command."""
        print("order_status - Get status and details of a specific order")
        print("Usage: order_status <order_id>")
        print()
        print("Arguments:")
        print("  order_id    Order identifier (integer OID)")
        print()
        print("Example:")
        print("  order_status 12345")
        print()
        print("This command displays comprehensive order information including:")
        print("- Order ID, coin, side, and type")
        print("- Current status (open, filled, cancelled, etc.)")
        print("- Quantity, filled amount, and remaining amount")
        print("- Price information (limit price, average fill price)")
        print("- Order settings (TIF, reduce-only)")
        print("- Creation timestamp")

    def do_info(self, args: str) -> None:
        """
        Get comprehensive information about a specific coin.

        Usage: info <coin>

        Example: info BTC
        """
        if not args.strip():
            print("❌ Error: Coin symbol is required")
            print("Usage: info <coin>")
            print("Example: info BTC")
            return

        coin = args.strip().upper()

        try:
            with BackendAPI(self.config) as api:
                print(f"\n⏳ Fetching information for {coin}...")

                # Get ticker and metadata
                ticker = api.get_ticker(coin)
                metadata = api.get_metadata(coin)

                # Prepare ticker information
                ticker_data = [
                    ["Coin", ticker.coin],
                    ["Mark Price", f"${ticker.mark_price:,.4f}"],
                    ["Funding Rate", f"{ticker.funding_rate * 100:.4f}%"],
                    [
                        "Open Interest",
                        "n/a" if ticker.open_interest is None else f"${ticker.open_interest:,.2f}",
                    ],
                ]

                # Prepare metadata information
                metadata_data = [
                    ["Coin", metadata.coin],
                    ["Size Decimals", str(metadata.size_decimals)],
                    ["Max Leverage", f"{metadata.max_leverage}x"],
                ]

                # Create and display tables
                formatter = TableFormatter()

                # Ticker table
                ticker_table = formatter.format(
                    (ticker_data[0], ticker_data[1:]),
                    title=f"📊 {coin} Ticker Information",
                )

                # Metadata table
                metadata_table = formatter.format(
                    (metadata_data[0], metadata_data[1:]), title=f"🔵 {coin} Metadata"
                )

                print(ticker_table)
                print(metadata_table)
                print()

        except Exception as e:
            print(f"❌ Error fetching information for {coin}: {e}")

    def help_info(self) -> None:
        """Show help for the info command."""
        print("info - Get comprehensive information about a specific coin")
        print("Usage: info <coin>")
        print()
        print("Arguments:")
        print("  coin        Coin symbol (e.g., BTC, ETH)")
        print()
        print("Example:")
        print("  info BTC")
        print()
        print("This command displays comprehensive coin information including:")
        print("- Current mark price and funding rate")
        print("- Open interest data")
        print("- Market metadata and trading specifications")
        print("- Maximum leverage and size decimal precision")
        print()
        print("Note: Use the coin symbol as it appears on the exchange")

    def do_open_orders(self, args: str) -> None:
        """
        Get all open orders for the account.

        Usage: open_orders
        """
        try:
            with BackendAPI(self.config) as api:
                orders = api.get_open_orders()

                # Use the order formatter to display orders as a table
                formatter = OrderFormatter()
                try:
                    print(formatter.format(orders))
                except ValueError as format_err:
                    print(format_err)
                print()

        except Exception as e:
            print(f"❌ Error fetching open orders: {e}")

    def help_open_orders(self) -> None:
        """Show help for the open_orders command."""
        print("open_orders - Get all open orders for the account")
        print("Usage: open_orders")
        print()
        print("This command displays all currently open orders in a table format including:")
        print("- Order ID, coin, side, and type")
        print("- Current status (open, filled, cancelled, etc.)")
        print("- Quantity, filled amount, and remaining amount")
        print("- Price information (limit price, average fill price)")
        print("- Order settings (TIF, reduce-only)")
        print("- Creation timestamp")
        print()
        print("The orders are displayed in a clean table format for easy scanning.")
        print("If no open orders exist, a message indicating this will be shown.")

    def do_order_history(self, args: str) -> None:
        """
        Get recent filled-order history for the account.

        Usage: order_history [N]
        """
        parts = args.strip().split()
        if len(parts) > 1:
            print("❌ Error: Too many arguments")
            print("Usage: order_history [N]")
            print("Example: order_history 5")
            return

        limit = DEFAULT_ORDER_HISTORY_LIMIT
        if parts:
            try:
                limit = int(parts[0])
                if limit <= 0:
                    raise ValueError("N must be a positive integer")
            except ValueError as e:
                print(f"❌ Invalid history limit: {e}")
                print("Usage: order_history [N]")
                print("Example: order_history 5")
                return

        try:
            with BackendAPI(self.config) as api:
                formatter = OrderFormatter()
                history = api.get_order_history(limit)
                if history:
                    print(formatter.format(history))
                else:
                    print("No filled orders found.")
                print()
        except Exception as e:
            print(f"❌ Error fetching order history: {e}")

    def help_order_history(self) -> None:
        """Show help for the order_history command."""
        print("order_history - Get recent filled-order history")
        print("Usage: order_history [N]")
        print()
        print("Arguments:")
        print("  N           Optional positive integer number of entries to display")
        print()
        print("Examples:")
        print("  order_history")
        print("  order_history 5")
        print()
        print(f"If N is omitted, the default is {DEFAULT_ORDER_HISTORY_LIMIT}.")
        print("Only filled orders are included, ordered newest first.")

    def do_pnl(self, args: str) -> None:
        """
        Show the fullscreen multi-window PnL dashboard.

        Usage: pnl
        """
        if args.strip():
            print("❌ Error: pnl does not take any arguments")
            print("Usage: pnl")
            return

        try:
            with BackendAPI(self.config) as api:
                history_catalog = api.get_pnl_history()
                if not any(history.points for history in history_catalog.histories):
                    print("No PnL history found.")
                else:
                    PnlTUI(history_catalog).run()
                print(flush=True)
        except Exception as e:
            print(f"❌ Error fetching PnL history: {e}")

    def help_pnl(self) -> None:
        """Show help for the pnl command."""
        print("pnl - Show a fullscreen multi-window PnL dashboard")
        print("Usage: pnl")
        print()
        print("Launches a fullscreen TUI with switchable 1d, 3d, 7d, 1m, 3m, 6m, 1y, and")
        print("all-time total, perpetual, and spot PnL charts.")
        print("This command does not accept any arguments.")

    def do_watch(self, args: str) -> None:
        """
        Launch the live watch TUI for a supported market.

        Usage: watch <coin>
        """
        parts = args.strip().split()
        if len(parts) != 1:
            print("❌ Error: watch requires exactly one coin symbol")
            print("Usage: watch <coin>")
            return

        coin = parts[0].upper()

        try:
            with BackendAPI(self.config) as api:
                api.get_watch_snapshot(coin)
                WatchTUI(coin, api.get_watch_snapshot).run()
                print(flush=True)
        except Exception as e:
            print(f"❌ Error fetching watch snapshot for {coin}: {e}")

    def help_watch(self) -> None:
        """Show help for the watch command."""
        print("watch - Launch a live market watch TUI for a supported coin or spot pair")
        print("Usage: watch <coin>")
        print()
        print("Arguments:")
        print("  coin        Market symbol (e.g. BTC, ETH, UBTC/USDC)")
        print()
        print("Examples:")
        print("  watch BTC")
        print("  watch ETH")
        print("  watch UBTC/USDC")
        print()
        print("The watch TUI shows:")
        print("- The last 99 completed candles plus the current live candle")
        print("- Current open interest next to the price header when the market provides it")
        print("- A live order book sized to the visible watch panel height")
        print("- `+` to switch to a shorter candle interval and `-` for a longer interval")

    def do_cancel_order(self, args: str) -> None:
        """
        Cancel a specific order or all open orders.

        Usage: cancel_order <order_id|all>

        Examples:
            cancel_order 12345        # Cancel specific order
            cancel_order all          # Cancel all open orders
        """
        if not args.strip():
            print("❌ Error: Order ID or 'all' is required")
            print("Usage: cancel_order <order_id|all>")
            print("Examples:")
            print("  cancel_order 12345    # Cancel specific order")
            print("  cancel_order all      # Cancel all open orders")
            return

        arg = args.strip().lower()

        # Validate argument
        try:
            if arg == "all":
                print("⏳ Cancelling all open orders...")
                with BackendAPI(self.config) as api:
                    result = api.cancel_order("all")
            else:
                try:
                    order_id = int(arg)
                    if order_id <= 0:
                        print("❌ Order ID must be a positive integer")
                        return
                except ValueError:
                    print(f"❌ Invalid argument: {arg}")
                    print("Must be a positive integer order ID or 'all'")
                    return

                print(f"⏳ Cancelling order {order_id}...")
                with BackendAPI(self.config) as api:
                    result = api.cancel_order(order_id)

            if result.success:
                print(f"✅ {result.message}")
                print()
            else:
                print(f"❌ Error: {result.error or result.message}")

        except Exception as e:
            print(f"❌ Failed to cancel order: {e}")

    def help_cancel_order(self) -> None:
        """Show help for the cancel_order command."""
        print("cancel_order - Cancel a specific order or all open orders")
        print("Usage: cancel_order <order_id|all>")
        print()
        print("Arguments:")
        print("  order_id    Positive integer ID of the order to cancel")
        print("  all         Cancel all open orders")
        print()
        print("Examples:")
        print("  cancel_order 12345    # Cancel specific order")
        print("  cancel_order all      # Cancel all open orders")
        print()
        print("Notes:")
        print("  - Use 'order_status' to check individual order details")
        print("  - Use 'open_orders' to list all open orders")
        print("  - Only open orders can be cancelled")
        print("  - Batch cancellation shows success/failure counts")

    def do_modify_order(self, args: str) -> None:
        """
        Modify an existing order using interactive wizard.

        Usage: modify_order <order_id>

        Example: modify_order 12345
        """
        if not args.strip():
            print("❌ Error: Order ID is required")
            print("Usage: modify_order <order_id>")
            print("Example: modify_order 12345")
            return

        try:
            order_id = int(args.strip())
            if order_id <= 0:
                raise ValueError("Order ID must be a positive integer")
        except ValueError as e:
            print(f"❌ Invalid order ID: {e}")
            print("Order ID must be a positive integer")
            return

        try:
            with BackendAPI(self.config) as api:
                wizard = ModifyWizard(self.config, api)
                modify_request = wizard.run(order_id)

                print("⏳ Modifying order...")

                # Submit modification request
                result = api.modify_order(modify_request)

                # Display result using formatter
                formatter = OrderFormatter()
                try:
                    print(formatter.format(result))
                except ValueError as format_err:
                    print(format_err)

        except KeyboardInterrupt:
            print("❌ Order modification cancelled")
        except Exception as e:
            print(f"❌ Failed to modify order: {e}")
        finally:
            print()

    def do_change_leverage(self, args: str) -> None:
        """
        Change leverage for a specific position.
        Usage: change_leverage <coin> <leverage> [--isolated]
        Examples:
          change_leverage ETH 21
          change_leverage BTC 15 --isolated
        """
        if not args.strip():
            print("❌ Error: Coin and leverage are required")
            print("Usage: change_leverage <coin> <leverage> [--isolated]")
            print("Example: change_leverage ETH 21")
            return

        parts = args.strip().split()
        if len(parts) < MIN_CHANGE_LEVERAGE_ARGS:
            print("❌ Error: Leverage value is required")
            print("Usage: change_leverage <coin> <leverage> [--isolated]")
            print("Example: change_leverage ETH 21")
            return

        coin = parts[0].upper()

        try:
            leverage = int(parts[1])
            if leverage < MIN_LEVERAGE or leverage > MAX_LEVERAGE:
                print(f"❌ Error: Leverage must be between {MIN_LEVERAGE} and {MAX_LEVERAGE}")
                return
        except ValueError:
            print("❌ Error: Leverage must be a valid integer")
            return

        is_cross = "--isolated" not in parts

        try:
            with BackendAPI(self.config) as api:
                print(
                    f"⏳ Changing {coin} leverage to {leverage}x "
                    f"({'cross' if is_cross else 'isolated'} margin)..."
                )

                # Show current position if exists
                try:
                    current_position = api.get_position(coin)
                    print(f"📊 Current {coin} position:")
                    formatter = AccountFormatter()
                    print(formatter.format([current_position]))
                    print()
                except Exception:
                    print(f"🔵 No current {coin} position found or error fetching position data")
                    print()

                # Change leverage
                result = api.change_leverage(leverage, coin, is_cross)

                if result.success:
                    print("✅ Success!")
                    print(f"📈 {result.message}")

                    if result.updated_position:
                        print()
                        print("📊 Updated position:")
                        formatter = AccountFormatter()
                        print(formatter.format([result.updated_position]))
                else:
                    print("❌ Failed!")
                    print(f"Error: {result.message}")

        except Exception as e:
            print(f"❌ Failed to change leverage: {e}")
        finally:
            print()

    def help_change_leverage(self) -> None:
        """Show help for the change_leverage command."""
        print("change_leverage - Change leverage for a specific position")
        print("Usage: change_leverage <coin> <leverage> [--isolated]")
        print()
        print("Arguments:")
        print("  coin        Symbol of the cryptocurrency (e.g., ETH, BTC, SOL)")
        print("  leverage    Target leverage multiplier (1-250)")
        print("  --isolated  Use isolated margin (optional, default is cross margin)")
        print()
        print("Examples:")
        print("  change_leverage ETH 21          # Set ETH leverage to 21x cross margin")
        print("  change_leverage BTC 15 --isolated  # Set BTC leverage to 15x isolated margin")
        print("  change_leverage SOL 10          # Set SOL leverage to 10x cross margin")
        print()
        print("Notes:")
        print("  - You must have an open position for the specified coin")
        print("  - Cross margin uses your entire account balance as collateral")
        print("  - Isolated margin uses only the position's margin as collateral")
        print("  - Leverage values must be between 1 and 250")

    def _print_position(self, title: str, position: PositionInfo) -> None:
        """Print a single position using the account formatter."""
        print(title)
        formatter = AccountFormatter()
        print(formatter.format([position]))

    def _print_removable_margin_hint(self, position: PositionInfo, prefix: str = "💡 Hint") -> None:
        """Print the removable isolated margin hint when available."""
        if position.removable_margin is None:
            return

        print(
            f"{prefix}: estimated removable isolated margin is up to "
            f"${position.removable_margin:,.2f}"
        )

    def _get_update_margin_position(self, api: BackendAPI, coin: str) -> PositionInfo | None:
        """Fetch and validate the position required for isolated margin updates."""
        try:
            current_position = api.get_position(coin)
        except Exception:
            print(f"❌ No current {coin} position found")
            print()
            return None

        self._print_position(f"📊 Current {coin} position:", current_position)
        print()

        if current_position.leverage_type != LeverageType.ISOLATED:
            print(f"❌ {coin} is using cross margin; isolated margin updates are unavailable")
            print()
            return None

        self._print_removable_margin_hint(current_position)
        if current_position.removable_margin is not None:
            print()

        return current_position

    def do_update_margin(self, args: str) -> None:
        """
        Update isolated margin for a specific position.
        Usage: update_margin <coin> <amount>
        Examples:
          update_margin ETH 1
          update_margin ETH -0.5
        """
        if not args.strip():
            print("❌ Error: Coin and amount are required")
            print("Usage: update_margin <coin> <amount>")
            print("Example: update_margin ETH 1")
            return

        parts = args.strip().split()
        if len(parts) < MIN_UPDATE_MARGIN_ARGS:
            print("❌ Error: Margin amount is required")
            print("Usage: update_margin <coin> <amount>")
            print("Example: update_margin ETH 1")
            return

        coin = parts[0].upper()

        try:
            amount = Decimal(parts[1])
        except InvalidOperation:
            print("❌ Error: Margin amount must be a valid decimal value")
            return

        if amount == 0:
            print("❌ Error: Margin amount must be non-zero")
            return

        try:
            with BackendAPI(self.config) as api:
                action = "Adding" if amount > 0 else "Removing"
                direction = "to" if amount > 0 else "from"
                current_position = self._get_update_margin_position(api, coin)
                if current_position is None:
                    return

                print(f"⏳ {action} ${abs(amount):.2f} isolated margin {direction} {coin}...")

                result = api.update_isolated_margin(amount, coin)

                if result.success:
                    print("✅ Success!")
                    print(f"💵 {result.message}")

                    if result.updated_position:
                        print()
                        self._print_position("📊 Updated position:", result.updated_position)
                        if result.updated_position.removable_margin is not None:
                            print()
                            self._print_removable_margin_hint(
                                result.updated_position, prefix="💡 Updated hint"
                            )
                else:
                    print("❌ Failed!")
                    print(f"Error: {result.message}")

        except Exception as e:
            print(f"❌ Failed to update isolated margin: {e}")
        finally:
            print()

    def help_update_margin(self) -> None:
        """Show help for the update_margin command."""
        print("update_margin - Update isolated margin for a specific position")
        print("Usage: update_margin <coin> <amount>")
        print()
        print("Arguments:")
        print("  coin      Symbol of the cryptocurrency (e.g., ETH, BTC, SOL)")
        print("  amount    Signed USD margin delta; positive adds margin and negative removes")
        print()
        print("Examples:")
        print("  update_margin ETH 1       # Add $1.00 isolated margin to ETH")
        print("  update_margin ETH -0.5    # Remove $0.50 isolated margin from ETH")
        print()
        print("Notes:")
        print("  - You must have an open isolated position for the specified coin")
        print("  - Cross margin positions are not eligible for isolated margin updates")
        print("  - The command shows an estimated removable isolated margin hint first")
        print("  - Amounts must be non-zero and use at most 6 decimal places")

    def help_modify_order(self) -> None:
        """Show help for the modify_order command."""
        print("modify_order - Modify an existing order using interactive wizard")
        print("Usage: modify_order <order_id>")
        print()
        print("Arguments:")
        print("  order_id    Positive integer ID of the order to modify")
        print()
        print("Example:")
        print("  modify_order 12345")
        print()
        print("This command starts an interactive wizard that guides you through:")
        print("- Viewing current order details")
        print("- Modifying price (optional)")
        print("- Modifying quantity (optional)")
        print("- Confirming changes before submission")
        print()
        print("Notes:")
        print("  - Only open limit orders can be modified")
        print("  - Press Enter to skip any parameter you don't want to change")
        print("  - The wizard shows current values for reference")
        print("  - Changes are applied immediately upon confirmation")

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
        """
        Run the interactive CLI loop.

        This method starts the main command loop and handles
        keyboard interrupts gracefully.
        """
        while True:
            try:
                self.cmdloop()
                typer.echo("👋 Goodbye!")
                return  # Quit if do_exit, do_quit
            except KeyboardInterrupt:
                try:
                    if typer.confirm("\nQuit?", default=False):
                        typer.echo("👋 Goodbye!")
                        return  # Quit if CTRL+C and then select quit
                    self.intro = ""
                    continue
                except typer.Abort:
                    typer.echo("\n👋 Goodbye!")
                    return  # Quit if CTRL+C and then CTRL+C again
