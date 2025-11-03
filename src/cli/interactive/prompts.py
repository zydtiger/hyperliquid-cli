"""
Interactive prompt utilities for the Hyperliquid CLI.

This module provides reusable interactive prompt methods for user input
that can be shared across different CLI components.
"""

from decimal import Decimal, InvalidOperation
from typing import Optional

from models import OrderSide, OrderTif, Config
from ..api import BackendAPI


class Prompts:
    """
    Collection of interactive prompt methods for user input.
    """

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
            print(f"\n[INFO] Available coins: {', '.join(coins[:10])}...")

            while True:
                coin = input("\n[INPUT] Enter coin symbol: ").strip().upper()
                if not coin:
                    print("[ERROR] Coin symbol is required")
                    continue
                if coin in coins:
                    return coin
                else:
                    print(
                        f"[ERROR] '{coin}' is not available. Choose from: {', '.join(coins[:5])}..."
                    )
        except Exception:
            # Fallback if API fails
            print("\n[WARNING] Unable to fetch available coins, using manual input")
            while True:
                coin = input("[INPUT] Enter coin symbol (e.g., BTC): ").strip().upper()
                if coin:
                    return coin
                print("[ERROR] Coin symbol is required")

    def get_side_selection(self) -> OrderSide:
        """
        Prompt user to select order side.

        Returns:
            OrderSide: Selected order side
        """
        while True:
            print("\n[SELECT] Select order side:")
            print("1. Buy")
            print("2. Sell")

            choice = input("Enter choice (1-2): ").strip()

            if choice == "1":
                return OrderSide.BUY
            elif choice == "2":
                return OrderSide.SELL
            else:
                print("[ERROR] Please enter 1 (Buy) or 2 (Sell)")

    def get_order_type_selection(self) -> str:
        """
        Prompt user to select order type.

        Returns:
            str: "market" or "limit"
        """
        while True:
            print("\n[SELECT] Select order type:")
            print("1. Market Order (immediate execution)")
            print("2. Limit Order (price controlled)")

            choice = input("Enter choice (1-2): ").strip()

            if choice == "1":
                return "market"
            elif choice == "2":
                return "limit"
            else:
                print("[ERROR] Please enter 1 (Market) or 2 (Limit)")

    def get_price_input(self, coin: str, side: OrderSide) -> Decimal:
        """
        Prompt user to input limit order price.

        Args:
            coin: Trading pair symbol
            side: Order side (buy/sell)

        Returns:
            Decimal: Order price
        """
        # Try to get current market price for reference
        try:
            ticker = self.api.get_ticker(coin)
            current_price = float(ticker.mark_price)
            print(f"\n[INFO] Current {coin} price: ${current_price:.4f}")

            if side == OrderSide.BUY:
                suggestion = f"Suggested buy price: ${current_price * 0.999:.4f} (slightly below market)"
            else:
                suggestion = f"Suggested sell price: ${current_price * 1.001:.4f} (slightly above market)"
            print(f"[INFO] {suggestion}")
        except Exception:
            print(f"\n[INPUT] Enter {coin} price:")

        while True:
            try:
                price_input = input(f"[INPUT] Enter limit price for {coin}: ").strip()
                price = Decimal(price_input)
                if price <= 0:
                    print("[ERROR] Price must be greater than 0")
                    continue
                return price
            except (InvalidOperation, ValueError):
                print("[ERROR] Please enter a valid number (e.g., 45000.50)")

    def get_quantity_input(self, coin: str) -> Decimal:
        """
        Prompt user to input order quantity.

        Args:
            coin: Trading pair symbol

        Returns:
            Decimal: Order quantity
        """
        # Try to get coin metadata for quantity precision
        try:
            metadata = self.api.get_metadata(coin)
            decimals = metadata.size_decimals
        except Exception:
            decimals = 2

        precision = Decimal(f"1e-{decimals}")
        print(f"\n[INFO] {coin} quantity precision: {precision}")

        while True:
            try:
                quantity_input = input(f"[INPUT] Enter quantity for {coin}: ").strip()
                quantity = Decimal(quantity_input)
                if quantity <= 0:
                    print("[ERROR] Quantity must be greater than 0")
                    continue
                elif quantity % precision != 0:
                    print(f"[ERROR] Quantity must be a multiple of {precision}")
                    continue
                return quantity
            except (InvalidOperation, ValueError):
                print("[ERROR] Please enter a valid number (e.g., 0.1)")

    def get_time_in_force_selection(self) -> OrderTif:
        """
        Prompt user to select time-in-force policy.

        Returns:
            OrderTif: Selected time-in-force policy
        """
        while True:
            print("\n[SELECT] Select time-in-force policy:")
            print("1. GTC - Good Till Cancelled (default)")
            print("2. IOC - Immediate or Cancel")
            print("3. ALO - At Limit Order")

            default_tif = self.config.trading.default_time_in_force
            tif_values = [OrderTif.GTC, OrderTif.IOC, OrderTif.ALO]
            default_index = tif_values.index(default_tif) + 1

            try:
                choice_str = input(
                    f"Enter choice (1-3, default={default_index}): "
                ).strip() or str(default_index)
                choice = int(choice_str)
                return tif_values[choice]

            except (ValueError, IndexError):
                print("[ERROR] Please enter 1, 2, or 3")
                continue

    def get_yes_no_input(self, prompt: str, default: Optional[bool] = None) -> bool:
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
            elif response in ["n", "no", "false", "0"]:
                return False
            else:
                print("[ERROR] Please enter 'y' (yes) or 'n' (no)")


__all__ = [
    "Prompts",
]
