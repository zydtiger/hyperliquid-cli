"""
Account formatter for displaying balance and position information.

This module provides formatted display for both PositionInfo and BalanceInfo objects,
with type routing to handle different account data types appropriately.
"""

from typing import Any

from models.api import BalanceInfo, PositionInfo, StakingStatus

from .base import Formatter
from .table_formatter import TableFormatter


class AccountFormatter(Formatter[BalanceInfo | StakingStatus | list[PositionInfo]]):
    """Formatter for account data including positions and balances."""

    def __init__(self) -> None:
        """Initialize the account formatter."""
        self.table_formatter = TableFormatter()

    def format(self, data: BalanceInfo | StakingStatus | list[PositionInfo], **kwargs: Any) -> str:
        """
        Format account data with type routing.

        Args:
            data: Account data (BalanceInfo, StakingStatus, or List[PositionInfo])

        Returns:
            str: Formatted account information
        """
        # Handle BalanceInfo objects
        if isinstance(data, BalanceInfo):
            return self._format_balances(data)

        if isinstance(data, StakingStatus):
            return self._format_staking_status(data)

        # Handle List[PositionInfo] objects
        if isinstance(data, list) and all(isinstance(p, PositionInfo) for p in data):
            return self._format_positions(data)

        raise ValueError(
            "Unsupported data type: "
            f"{type(data)}. Expected BalanceInfo, StakingStatus, or List[PositionInfo]."
        )

    def _format_balances(self, balance_info: BalanceInfo) -> str:
        """
        Format comprehensive balance information.

        Args:
            balance_info: Balance information object

        Returns:
            str: Formatted balance information
        """
        output = []

        # Perpetuals Account
        perps_data = [
            ["Account Value", f"${balance_info.perps_account_value:,.2f}"],
            ["Total Position Size", f"${balance_info.perps_total_position_value:,.2f}"],
            ["Remaining Raw USD", f"${balance_info.perps_total_raw_usd:,.2f}"],
            ["Margin Used", f"${balance_info.perps_margin_used:,.2f}"],
            ["Withdrawable", f"${balance_info.perps_withdrawable:,.2f}"],
        ]

        perps_table = self.table_formatter.format(
            (["Metric", "Value"], perps_data), title="📈 Perpetuals Account"
        )
        output.append(perps_table)

        # Spot Balances
        if balance_info.spot_balances:
            spot_data = [["Coin", "Total Balance"]]
            for spot_balance in balance_info.spot_balances:
                spot_data.append([spot_balance.coin, f"{spot_balance.total:,.6f}"])

            spot_table = self.table_formatter.format(
                (spot_data[0], spot_data[1:]), title="💰 Spot Balances"
            )
            output.append(spot_table)

        # Staking Information
        if balance_info.staking_info:
            staking = balance_info.staking_info
            staking_data = [
                ["Delegated Amount", f"{staking.delegated_amount:,.8f}"],
                ["Undelegated Amount", f"{staking.undelegated_amount:,.8f}"],
                ["Pending Withdrawals", f"{staking.pending_withdrawals:,.8f}"],
                ["Pending Withdrawal Count", f"{staking.pending_withdrawal_count}"],
            ]

            staking_table = self.table_formatter.format(
                (["Metric", "Value"], staking_data), title="🔒 Staking Information"
            )
            output.append(staking_table)

        return "\n".join(output)

    def _format_staking_status(self, staking_status: StakingStatus) -> str:
        """Format staking status for display."""
        summary_table = self.table_formatter.format(
            (
                ["Metric", "Value"],
                [
                    ["Total Staked", f"{staking_status.total_staked:,.8f} HYPE"],
                    ["Total Reward", f"{staking_status.total_reward:,.8f} HYPE"],
                ],
            ),
            title="🔒 Staking Summary",
        )

        if not staking_status.delegations:
            return f"{summary_table}\n\nNo active HYPE staking delegations found."

        delegation_rows = [
            [
                delegation.validator,
                delegation.name,
                f"{delegation.commission:.2%}" if delegation.commission is not None else None,
                f"{delegation.amount:,.8f}",
            ]
            for delegation in staking_status.delegations
        ]
        delegations_table = self.table_formatter.format(
            (["Validator", "Name", "Commission", "Staked HYPE"], delegation_rows),
            title="🧭 Active Staking Endpoints",
        )
        return f"{summary_table}\n{delegations_table}"

    def _format_positions(self, positions: list[PositionInfo]) -> str:
        """
        Format multiple positions for display.

        Args:
            positions: List of position information objects

        Returns:
            str: Formatted positions table
        """
        if not positions:
            return "\nNo open positions"

        show_removable_margin = any(position.removable_margin is not None for position in positions)
        data = [["Coin", "Size", "Entry", "Mark", "PnL", "Leverage", "Margin"]]
        if show_removable_margin:
            data[0].append("Removable")

        for position in positions:
            row = [
                position.coin,
                f"{position.size:,.6f}",
                f"${position.entry_price:,.2f}",
                f"${position.mark_price:,.2f}",
                f"${position.unrealized_pnl:+,.2f}",
                f"{position.leverage}x",
                f"${position.margin_used:,.2f}",
            ]
            if show_removable_margin:
                row.append(
                    f"${position.removable_margin:,.2f}"
                    if position.removable_margin is not None
                    else ""
                )
            data.append(row)

        return self.table_formatter.format(
            (data[0], data[1:]), title=f"Current Positions ({len(positions)})"
        )
