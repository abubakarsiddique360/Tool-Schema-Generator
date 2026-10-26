"""Example tools used by the README and the test suite."""

from __future__ import annotations

from typing import Literal


def get_weather(city: str, units: Literal["celsius", "fahrenheit"] = "celsius") -> str:
    """Return the current weather for a city.

    Args:
        city: The city to look up, for example "Dhaka".
        units: Which unit to report the temperature in.
    """
    return f"{city}: 27 degrees"


def search_docs(query: str, limit: int = 10, *, tags: list[str] | None = None) -> list[str]:
    """Search the documentation index.

    Args:
        query: Words to search for.
        limit: Maximum number of results to return.
        tags: Optional tags to filter the results by.
    """
    return []


def send_email(to: str, subject: str, body: str, cc: list[str] | None = None) -> bool:
    """Queue an email for delivery.

    Args:
        to: Recipient address.
        subject: Subject line.
        body: Plain text body.
        cc: Additional recipients, if any.
    """
    return True


def _internal_helper(value: int) -> int:
    """Not exported because the name is private."""
    return value
