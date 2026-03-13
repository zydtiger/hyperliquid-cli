"""
Interactive wizard for modifying existing orders.

This module provides a step-by-step wizard for modifying orders
with proper validation and user guidance.
"""

from models import ModifyOrderRequest, Config, OrderType, OrderStatus
from ..api import BackendAPI
from ..formatters.order_formatter import OrderFormatter
from .prompts import Prompts


class ModifyWizard:
    """
    Interactive wizard for order modification.

    This class provides a step-by-step wizard for modifying existing orders
    with proper validation and user guidance.
    """

    def __init__(self, config: Config, api: BackendAPI):
        """
        Initialize the modify wizard.

        Args:
            config: Configuration object
            api: BackendAPI client for market data
        """
        self.config = config
        self.api = api
        self.prompts = Prompts(config, api)
        self.formatter = OrderFormatter()

    def run(self, order_id: int) -> ModifyOrderRequest:
        """
        Run the complete order modification wizard.

        This wizard collects modification parameters from the user,
        constructs a validated modify request, and returns it for submission.

        Args:
            order_id: Order ID to modify

        Returns:
            ModifyOrderRequest: The constructed modification request

        Raises:
            KeyboardInterrupt: If user cancels the operation
            ValueError: If order is not found or not a limit order
        """
        print(f"\n[MODIFY WIZARD] Modify Order #{order_id}")
        print("=" * 40)

        # Step 1: Get current order status
        try:
            order_info = self.api.get_order_status(order_id)
        except Exception as e:
            raise ValueError(f"Failed to get order status: {e}")

        # Validate order is a limit order and open
        if order_info.order_type != OrderType.LIMIT:
            raise ValueError("Only limit orders can be modified")
        if order_info.status != OrderStatus.OPEN:
            raise ValueError(
                f"Order is {order_info.status}, only open orders can be modified"
            )

        # Display current order information
        print("\n📋 Current Order Information:")
        print(self.formatter.format(order_info))

        # Step 2: Get new price (optional)
        new_price = self.prompts.get_price_input(
            order_info.coin,
            order_info.side,
            order_info.price,
        )

        # Step 3: Get new quantity (optional)
        new_quantity = self.prompts.get_quantity_input(
            order_info.coin,
            order_info.quantity,
        )

        # Check if any changes were requested
        if new_price == order_info.price and new_quantity == order_info.quantity:
            print("\n⚠️ No changes specified.")
            raise KeyboardInterrupt

        # Step 4: Show modification summary
        print("\n📋 Modification Summary:")
        print(f"   Order ID: {order_id}")
        print(f"   Coin: {order_info.coin}")

        if new_price != order_info.price:
            print(f"   Price: {order_info.price} → {new_price}")
        else:
            print(f"   Price: {order_info.price} (no change)")

        if new_quantity != order_info.quantity:
            print(f"   Quantity: {order_info.quantity} → {new_quantity}")
        else:
            print(f"   Quantity: {order_info.quantity} (no change)")

        # Step 5: Confirm modification
        if not self.prompts.get_yes_no_input(
            f"\n[CONFIRM] Modify order #{order_id}?", default=False
        ):
            raise KeyboardInterrupt

        # Create modification request
        return ModifyOrderRequest(
            order_id=order_id, price=new_price, quantity=new_quantity
        )


__all__ = [
    "ModifyWizard",
]
