"""Leverage and isolated margin command mixin for the interactive CLI."""

from __future__ import annotations

from contextlib import AbstractContextManager
from decimal import Decimal, InvalidOperation

from exchange import HyperliquidClient
from models.api import LeverageType, PositionInfo

from ..commands.parsers import MAX_LEVERAGE, MIN_LEVERAGE, find_position_for_coin
from ..formatters import AccountFormatter

MIN_CHANGE_LEVERAGE_ARGS = 2
MIN_UPDATE_MARGIN_ARGS = 2


class ReplPositionsMixin:
    """Provides change_leverage and update_margin commands for InteractiveCLI."""

    def _client_scope(self) -> AbstractContextManager[HyperliquidClient]:
        raise NotImplementedError

    def _print_position(self, title: str, position: PositionInfo) -> None:
        """Print a single position using the account formatter."""
        print(title)
        print(AccountFormatter().format([position]))

    def _print_removable_margin_hint(self, position: PositionInfo, prefix: str = "💡 Hint") -> None:
        """Print the removable isolated margin hint when available."""
        if position.removable_margin is None:
            return
        print(
            f"{prefix}: estimated removable isolated margin is up to "
            f"${position.removable_margin:,.2f}"
        )

    def _get_update_margin_position(
        self, client: HyperliquidClient, coin: str
    ) -> PositionInfo | None:
        """Fetch and validate the position required for isolated margin updates."""
        try:
            current_position = find_position_for_coin(client.get_positions(), coin)
        except Exception:
            current_position = None

        if current_position is None:
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

    def do_change_leverage(self, args: str) -> None:
        """Change leverage for a specific position."""
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
            with self._client_scope() as client:
                print(
                    f"⏳ Changing {coin} leverage to {leverage}x "
                    f"({'cross' if is_cross else 'isolated'} margin)..."
                )
                try:
                    current_position = find_position_for_coin(client.get_positions(), coin)
                    if current_position is not None:
                        self._print_position(f"📊 Current {coin} position:", current_position)
                    else:
                        print(f"🔵 No current {coin} position found")
                    print()
                except Exception:
                    print(f"🔵 No current {coin} position found or error fetching position data")
                    print()

                result = client.change_leverage(leverage, coin, is_cross=is_cross)
                if result.success:
                    print("✅ Success!")
                    print(f"📈 {result.message}")
                    if result.updated_position:
                        print()
                        self._print_position("📊 Updated position:", result.updated_position)
                else:
                    print("❌ Failed!")
                    print(f"Error: {result.message}")
        except Exception as e:
            print(f"❌ Failed to change leverage: {e}")
        finally:
            print()

    def do_update_margin(self, args: str) -> None:
        """Update isolated margin for a specific position."""
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
            with self._client_scope() as client:
                action = "Adding" if amount > 0 else "Removing"
                direction = "to" if amount > 0 else "from"
                current_position = self._get_update_margin_position(client, coin)
                if current_position is None:
                    return

                print(f"⏳ {action} ${abs(amount):.2f} isolated margin {direction} {coin}...")
                result = client.update_isolated_margin(amount, coin)
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
