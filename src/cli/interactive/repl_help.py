"""Help text mixin for the interactive Hyperliquid CLI."""

from __future__ import annotations

DEFAULT_ORDER_HISTORY_LIMIT = 10


class ReplHelpMixin:
    """Provides ``help_*`` methods for interactive CLI commands."""

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
        print(
            "   or: order <buy|sell> <coin> <quantity|quantity@price> [--tp <price>] [--sl <price>]"
        )
        print()
        print("Examples:")
        print("  order")
        print("  order buy ETH 0.25")
        print("  order sell BTC 0.01@105000")
        print("  order buy BTC 2@75000 --tp 80000 --sl 60000")
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
        print("- `--tp <price>` adds a full-size reduce-only take-profit trigger-market exit")
        print("- `--sl <price>` adds a full-size reduce-only stop-loss trigger-market exit")
        print("- Quick orders default to non-reduce-only on the primary order")
        print()
        print("The wizard provides market data suggestions and validates all inputs.")
        print("Wizard orders are submitted upon confirmation.")

    def help_status(self) -> None:
        """Show help for the status command."""
        print("status - Show account status and information")
        print("Usage: status")
        print("Displays account configuration and exchange connection status")

    def help_positions(self) -> None:
        """Show help for the positions command."""
        print("positions - Show current open positions")
        print("Usage: positions")
        print("Displays all open positions with detailed information")

    def help_balances(self) -> None:
        """Show help for the balances command."""
        print("balances - Show comprehensive balance information")
        print("Usage: balances")
        print("Displays perpetuals account, spot balances, and staking information")

    def help_staking(self) -> None:
        """Show help for the staking command."""
        print("staking - Show staking status for the configured account")
        print("Usage: staking")
        print("Displays total staked HYPE and validators with active delegations")

    def help_conditionals(self) -> None:
        """Show help for the conditionals command."""
        print("conditionals - Manage conditional orders")
        print("Usage: conditionals <action> <parameters>")
        print("This command is currently under development")

    def help_clear(self) -> None:
        """Show help for the clear command."""
        print("clear - Clear the terminal screen")
        print("Usage: clear")

    def help_cls(self) -> None:
        """Show help for the cls command."""
        self.help_clear()

    def help_quit(self) -> None:
        """Show help for the quit command."""
        print("quit - Exit the CLI")
        print("Usage: quit")

    def help_exit(self) -> None:
        """Show help for the exit command."""
        print("exit - Exit the CLI")
        print("Usage: exit")

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

    def help_pnl(self) -> None:
        """Show help for the pnl command."""
        print("pnl - Show a fullscreen multi-window PnL dashboard")
        print("Usage: pnl")
        print()
        print("Launches a fullscreen TUI with switchable 1d, 3d, 7d, 1m, 3m, 6m, 1y, and")
        print("all-time total, perpetual, and spot PnL charts.")
        print("This command does not accept any arguments.")

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
