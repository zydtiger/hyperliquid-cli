"""
Base formatter classes for CLI output.

This module provides abstract base classes for implementing different types of
formatters for displaying data in the command-line interface.
"""

from abc import ABC, abstractmethod
from typing import Any, Generic, TypeVar

T = TypeVar("T")


class Formatter(ABC, Generic[T]):
    """
    Abstract base class for formatters.

    This class defines the interface that all formatters must implement.
    It is generic to allow for different input types.
    """

    @abstractmethod
    def format(self, data: T, **kwargs: Any) -> str:
        """
        Format the given data into a string representation.

        Args:
            data: The data to format
            **kwargs: Additional formatting options

        Returns:
            Formatted string representation of the data
        """
        pass
