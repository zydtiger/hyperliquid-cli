"""
Interactive wizard components for the Hyperliquid CLI.

This module provides step-by-step wizards for creating orders and
configuring trading parameters.
"""

from typing import Union
from models import MarketOrder, LimitOrder, Config
from ..api import BackendAPI
from ..formatters.order_formatter import OrderFormatter
from .prompts import Prompts


class OrderWizard:
    """
    Interactive wizard for order creation.

    This class provides a step-by-step wizard for creating orders
    with proper validation and user guidance.
    """

    def __init__(self, config: Config, api: BackendAPI):
        """
        Initialize the order wizard.

        Args:
            api: BackendAPI client for market data
        """
        self.config = config
        self.api = api
        self.prompts = Prompts(config, api)
        self.formatter = OrderFormatter()

    def run(self) -> Union[MarketOrder, LimitOrder]:
        """
        Run the complete order creation wizard.

        This wizard collects all necessary order parameters from the user,
        constructs a validated order object, and returns it for submission.

        Returns:
            Union[MarketOrder, LimitOrder]: The constructed order object

        Raises:
            KeyboardInterrupt: If user cancels the operation
        """
        print("\n[ORDER WIZARD] Create New Order")
        print("=" * 30)

        # Step 1: Select coin
        coin = self.prompts.get_coin_selection()

        # Step 2: Select side
        side = self.prompts.get_side_selection()

        # Step 3: Select order type and configure specific parameters
        order_type = self.prompts.get_order_type_selection()

        order: Union[MarketOrder, LimitOrder]

        if order_type == "limit":
            # Get price for limit orders
            price = self.prompts.get_price_input(coin, side)
            time_in_force = self.prompts.get_time_in_force_selection()

            # Get quantity
            quantity = self.prompts.get_quantity_input(coin)

            # Additional options
            reduce_only = self.prompts.get_yes_no_input(
                "\nReduce only position?", default=False
            )

            # Create limit order
            order = LimitOrder(
                coin=coin,
                side=side,
                quantity=quantity,
                price=price,
                time_in_force=time_in_force,
                reduce_only=reduce_only,
            )
        else:  # market
            # Get quantity
            quantity = self.prompts.get_quantity_input(coin)

            # Additional options
            reduce_only = self.prompts.get_yes_no_input(
                "\nReduce only position?", default=False
            )

            # Create market order
            order = MarketOrder(
                coin=coin, side=side, quantity=quantity, reduce_only=reduce_only
            )

        # Show order summary
        print()
        print(self.formatter.format(order))

        # Confirm order submission
        if not self.prompts.get_yes_no_input(
            "\n[CONFIRM] Submit this order?", default=False
        ):
            raise KeyboardInterrupt

        return order


__all__ = [
    "OrderWizard",
]
