"""
Interactive CLI interface for the Hyperliquid trading system.

This module provides a command-line interface with tab completion support
for managing orders, positions, and account status.
"""

import cmd

import typer

from models.config import Config
from models.order import LimitOrder

from .api import BackendAPI
from .formatters import AccountFormatter, OrderFormatter, TableFormatter
from .interactive import ModifyWizard, OrderWizard

MIN_CHANGE_LEVERAGE_ARGS = 2
MIN_LEVERAGE = 1
MAX_LEVERAGE = 250


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

    def do_order(self, args: str) -> None:
        """
        Place a new order using interactive wizard.

        This command launches an interactive wizard that guides the user
        through creating a new order with proper validation and market data.
        """
        try:
            with BackendAPI(self.config) as api:
                wizard = OrderWizard(self.config, api)
                order = wizard.run()

                if order.trigger is not None:
                    print("🚧 Trigger orders are not wired to backend submission yet")
                    return

                print("⏳ Submitting order...")

                # Submit order based on type
                try:
                    if isinstance(order, LimitOrder):
                        # Limit order
                        result = api.submit_limit_order(order)
                    else:
                        # Market order
                        result = api.submit_market_order(order)

                    # Display result using formatter
                    formatter = OrderFormatter()
                    try:
                        print(formatter.format(result))
                    except ValueError as format_err:
                        print(format_err)

                except Exception as submission_err:
                    print(f"❌ Failed to submit order: {submission_err}")

        except KeyboardInterrupt:
            print("❌ Order creation cancelled")
        except Exception as e:
            print(f"❌ Failed to create order: {e}")
        finally:
            print()

    def help_order(self) -> None:
        """Show help for the order command."""
        print("order - Launch interactive order creation wizard")
        print("Usage: order")
        print()
        print("This command starts an interactive wizard that guides you through:")
        print("- Selecting a trading coin")
        print("- Choosing order side (buy/sell)")
        print("- Selecting order type (market/limit)")
        print("- Setting price (for limit orders)")
        print("- Specifying quantity")
        print("- Configuring additional options")
        print("- Optionally adding a trigger price with STOP/TAKE selection")
        print()
        print("The wizard provides market data suggestions and validates all inputs.")
        print("Orders without triggers are submitted immediately upon confirmation.")

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
                    ["Open Interest", f"{ticker.open_interest:,.2f}"],
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
        commands = [
            "order",
            "order_status",
            "open_orders",
            "cancel_order",
            "modify_order",
            "change_leverage",
            "info",
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
