from enum import Enum


class OrderTif(Enum):
    """Order Time-in-Force values for Hyperliquid orders."""

    ALO = "ALO"  # At Limit Order - active until cancelled
    IOC = "IOC"  # Immediate or Cancel - execute immediately or cancel
    GTC = "GTC"  # Good Till Cancelled - active until filled or cancelled
