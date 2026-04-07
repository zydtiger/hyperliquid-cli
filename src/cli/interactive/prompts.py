"""
Interactive prompt utilities for the Hyperliquid CLI.

This module provides reusable interactive prompt methods for user input
that can be shared across different CLI components.
"""

from decimal import Decimal, InvalidOperation

from models import Config, OrderSide, OrderTif, OrderTrigger, TriggerType

from ..api import BackendAPI

DEFAULT_SIZE_DECIMALS = 2


class Prompts:
    """Collection of interactive prompt methods for user input."""

    def __init__(self, config: Config, api: BackendAPI):
        """
        Initialize prompts with API client.

        Args:
            api: BackendAPI client for fetching market data
        """
        self.config = config
        self.api = api

    def get_coin_selection(self) -> str:
        """
        Prompt user to select a trading coin.

        Returns:
            str: Selected coin symbol
        """
        try:
            coins = self.api.get_available_coins()
            print(f"\n🔵 Available coins: {', '.join(coins[:10])}...")

            while True:
                coin = input("📝 Enter coin symbol: ").strip().upper()
                if not coin:
                    print("❌ Coin symbol is required")
                    continue
                if coin in coins:
                    return coin
                print(f"❌ '{coin}' is not available. Choose from: {', '.join(coins[:5])}...")
        except Exception:
            # Fallback if API fails
            print("\n⚠️ Unable to fetch available coins, using manual input")
            while True:
                coin = input("📝 Enter coin symbol (e.g., BTC): ").strip().upper()
                if coin:
                    return coin
                print("❌ Coin symbol is required")

    def get_side_selection(self) -> OrderSide:
        """
        Prompt user to select order side.

        Returns:
            OrderSide: Selected order side
        """
        while True:
            print("\n🎯 Select order side:")
            print("1. Buy")
            print("2. Sell")

            choice = input("Enter choice (1-2): ").strip()

            if choice == "1":
                return OrderSide.BUY
            if choice == "2":
                return OrderSide.SELL
            print("❌ Please enter 1 (Buy) or 2 (Sell)")

    def get_order_type_selection(self) -> str:
        """
        Prompt user to select order type.

        Returns:
            str: "market" or "limit"
        """
        while True:
            print("\n🎯 Select order type:")
            print("1. Market Order (immediate execution)")
            print("2. Limit Order (price controlled)")

            choice = input("Enter choice (1-2): ").strip()

            if choice == "1":
                return "market"
            if choice == "2":
                return "limit"
            print("❌ Please enter 1 (Market) or 2 (Limit)")

    def get_price_input(
        self, coin: str, side: OrderSide, current_order_price: Decimal | None = None
    ) -> Decimal:
        """
        Prompt user to input limit order price with optional current value display.

        Args:
            coin: Trading pair symbol
            side: Order side (buy/sell)
            current_order_price: Current order price to display (optional, allows skipping)

        Returns:
            Decimal: Order price (current price if user skips when current_order_price provided)
        """
        # Try to get current market price for reference
        try:
            ticker = self.api.get_ticker(coin)
            current_price = float(ticker.mark_price)
            print(f"\n🔵 Current {coin} price: ${current_price:.4f}")

            if side == OrderSide.BUY:
                suggestion = (
                    f"Suggested buy price: ${current_price * 0.999:.4f} (slightly below market)"
                )
            else:
                suggestion = (
                    f"Suggested sell price: ${current_price * 1.001:.4f} (slightly above market)"
                )
            print(f"🔵 {suggestion}")
        except Exception:
            print(f"\n❌ Cannot fetch current {coin} price")

        while True:
            try:
                current_order_prompt = (
                    f" [current: {current_order_price}] (press Enter to skip)"
                    if current_order_price
                    else ""
                )
                price_input = input(
                    f"📝 Enter limit price for {coin}{current_order_prompt}: "
                ).strip()

                if current_order_price and not price_input:
                    return current_order_price

                price = Decimal(price_input)
                if price <= 0:
                    print("❌ Price must be greater than 0")
                    continue
                return price
            except (InvalidOperation, ValueError):
                print("❌ Please enter a valid number (e.g., 45000.50)")

    def get_quantity_input(
        self, coin: str, current_order_quantity: Decimal | None = None
    ) -> Decimal:
        """
        Prompt user to input order quantity with optional current value display.

        Args:
            coin: Trading pair symbol
            current_order_quantity: Current order quantity to display (optional, allows skipping)

        Returns:
            Decimal: Order quantity (current quantity if user skips when
                current_order_quantity provided)
        """
        # Try to get coin metadata for quantity precision
        try:
            metadata = self.api.get_metadata(coin)
            decimals = metadata.size_decimals
        except Exception:
            decimals = DEFAULT_SIZE_DECIMALS

        precision = Decimal(f"1e-{decimals}")
        print(f"\n🔵 {coin} quantity precision: {precision}")

        while True:
            try:
                current_order_prompt = (
                    f" [current: {current_order_quantity}] (press Enter to skip)"
                    if current_order_quantity
                    else ""
                )
                quantity_input = input(
                    f"📝 Enter quantity for {coin}{current_order_prompt}: "
                ).strip()

                if current_order_quantity and not quantity_input:
                    return current_order_quantity

                quantity = Decimal(quantity_input)
                if quantity <= 0:
                    print("❌ Quantity must be greater than 0")
                    continue
                if quantity % precision != 0:
                    print(f"❌ Quantity must be a multiple of {precision}")
                    continue
                return quantity
            except (InvalidOperation, ValueError):
                print("❌ Please enter a valid number (e.g., 0.1)")

    def get_time_in_force_selection(self) -> OrderTif:
        """
        Prompt user to select time-in-force policy.

        Returns:
            OrderTif: Selected time-in-force policy
        """
        while True:
            print("\n🎯 Select time-in-force policy:")
            print("1. GTC - Good Till Cancelled")
            print("2. IOC - Immediate or Cancel")
            print("3. ALO - At Limit Order")

            default_tif = self.config.trading.default_time_in_force
            tif_values = [OrderTif.GTC, OrderTif.IOC, OrderTif.ALO]
            default_index = tif_values.index(default_tif) + 1

            try:
                choice_str = input(f"Enter choice (1-3, default={default_index}): ").strip() or str(
                    default_index
                )
                choice = int(choice_str)
                return tif_values[choice - 1]

            except (ValueError, IndexError):
                print("❌ Please enter 1, 2, or 3")
                continue

    def get_yes_no_input(self, prompt: str, default: bool | None = None) -> bool:
        """
        Prompt user for yes/no input.

        Args:
            prompt: Question to ask
            default: Default value if user just presses Enter

        Returns:
            bool: True for yes, False for no
        """
        default_text = ""
        if default is True:
            default_text = " (Y/n)"
        elif default is False:
            default_text = " (y/N)"

        while True:
            response = input(f"{prompt}{default_text}: ").strip().lower()

            if not response and default is not None:
                return default

            if response in ["y", "yes", "true", "1"]:
                return True
            if response in ["n", "no", "false", "0"]:
                return False
            print("❌ Please enter 'y' (yes) or 'n' (no)")

    def get_trigger_type_selection(self) -> TriggerType:
        """Prompt user to select a trigger type."""
        while True:
            print("\n🎯 Select trigger type:")
            print("1. Stop")
            print("2. Take")

            choice = input("Enter choice (1-2): ").strip()

            if choice == "1":
                return TriggerType.STOP
            if choice == "2":
                return TriggerType.TAKE
            print("❌ Please enter 1 (Stop) or 2 (Take)")

    def get_trigger_price_input(self, coin: str) -> Decimal:
        """Prompt user to input trigger price."""
        while True:
            try:
                trigger_price_input = input(f"📝 Enter trigger price for {coin}: ").strip()
                trigger_price = Decimal(trigger_price_input)
                if trigger_price <= 0:
                    print("❌ Trigger price must be greater than 0")
                    continue
                return trigger_price
            except (InvalidOperation, ValueError):
                print("❌ Please enter a valid number (e.g., 45000.50)")

    def get_trigger_input(self, coin: str) -> OrderTrigger | None:
        """Prompt user to optionally configure a trigger."""
        if not self.get_yes_no_input("\nAdd trigger price?", default=False):
            return None

        return OrderTrigger(
            trigger_type=self.get_trigger_type_selection(),
            trigger_price=self.get_trigger_price_input(coin),
        )


__all__ = [
    "Prompts",
]
