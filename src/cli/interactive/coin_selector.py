"""
Interactive coin selection helpers for the order wizard.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from difflib import SequenceMatcher
from typing import Protocol

from prompt_toolkit import PromptSession
from prompt_toolkit.completion import CompleteEvent, Completer, Completion
from prompt_toolkit.document import Document
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.shortcuts import CompleteStyle

MAX_COIN_SUGGESTIONS = 5
SUBSTRING_MATCH_PRIORITY = 2
FUZZY_MATCH_PRIORITY = 3


class CoinPromptSession(Protocol):
    """Protocol for coin prompt sessions."""

    def prompt(self, message: str) -> str:
        """Prompt for coin input."""
        ...


def normalize_coin_input(value: str) -> str:
    """Normalize coin input for matching."""
    return value.strip().upper()


def _subsequence_score(query: str, coin: str) -> float:
    """Score subsequence matches for short symbol-style queries."""
    if not query:
        return 0.0

    position = 0
    distance = 0

    for character in query:
        match_index = coin.find(character, position)
        if match_index == -1:
            return 0.0
        distance += match_index - position
        position = match_index + 1

    compactness = len(query) / (len(query) + distance + 1)
    coverage = len(query) / len(coin)
    return (compactness + coverage) / 2


def rank_coin_matches(
    query: str, coins: Sequence[str], limit: int = MAX_COIN_SUGGESTIONS
) -> list[str]:
    """
    Rank available coins for a fuzzy query.

    Ordering priority:
    1. Exact match
    2. Prefix match
    3. Substring match
    4. Fuzzy similarity
    """
    normalized_query = normalize_coin_input(query)
    if not normalized_query:
        return list(coins[:limit])

    ranked: list[tuple[int, float, int, str]] = []

    for index, coin in enumerate(coins):
        normalized_coin = coin.upper()

        if normalized_coin == normalized_query:
            ranked.append((0, -1.0, index, coin))
            continue

        if normalized_coin.startswith(normalized_query):
            prefix_score = len(normalized_query) / len(normalized_coin)
            ranked.append((1, -prefix_score, index, coin))
            continue

        if normalized_query in normalized_coin:
            substring_position = normalized_coin.index(normalized_query)
            substring_score = len(normalized_query) / len(normalized_coin)
            ranked.append(
                (SUBSTRING_MATCH_PRIORITY, substring_position - substring_score, index, coin)
            )
            continue

        ratio = SequenceMatcher(None, normalized_query, normalized_coin).ratio()
        subsequence = _subsequence_score(normalized_query, normalized_coin)
        fuzzy_score = max(ratio, subsequence)

        if fuzzy_score <= 0:
            continue

        ranked.append((FUZZY_MATCH_PRIORITY, -fuzzy_score, index, coin))

    ranked.sort()
    return [coin for _, _, _, coin in ranked[:limit]]


class CoinCompleter(Completer):
    """Completion provider for fuzzy coin matching."""

    def __init__(self, coins: Sequence[str]):
        self.coins = list(coins)

    def get_completions(
        self, document: Document, complete_event: CompleteEvent
    ) -> list[Completion]:
        typed_text = document.text_before_cursor
        matches = rank_coin_matches(typed_text, self.coins)
        return [
            Completion(
                text=coin,
                start_position=-len(typed_text),
                display=coin,
            )
            for coin in matches
        ]


def _build_key_bindings() -> KeyBindings:
    """Create key bindings for completion-driven coin selection."""
    bindings = KeyBindings()

    @bindings.add("tab")
    def _start_or_cycle_completion(event) -> None:  # type: ignore[no-untyped-def]
        buffer = event.app.current_buffer
        if buffer.complete_state:
            buffer.complete_next()
            return
        buffer.start_completion(select_first=False)

    @bindings.add("up")
    def _select_previous_completion(event) -> None:  # type: ignore[no-untyped-def]
        buffer = event.app.current_buffer
        if buffer.complete_state:
            buffer.complete_previous()

    @bindings.add("down")
    def _select_next_completion(event) -> None:  # type: ignore[no-untyped-def]
        buffer = event.app.current_buffer
        if buffer.complete_state:
            buffer.complete_next()

    @bindings.add("enter")
    def _accept_current_completion(event) -> None:  # type: ignore[no-untyped-def]
        buffer = event.app.current_buffer
        if buffer.complete_state and buffer.complete_state.current_completion:
            buffer.apply_completion(buffer.complete_state.current_completion)
        buffer.validate_and_handle()

    return bindings


def build_coin_prompt_session(coins: Sequence[str]) -> CoinPromptSession:
    """Build the interactive prompt session for coin selection."""
    return PromptSession(
        completer=CoinCompleter(coins),
        complete_while_typing=True,
        complete_style=CompleteStyle.COLUMN,
        key_bindings=_build_key_bindings(),
    )


def prompt_for_coin_selection(
    coins: Sequence[str],
    session_factory: Callable[[Sequence[str]], CoinPromptSession] | None = None,
) -> str:
    """Prompt until the user selects a valid available coin."""
    canonical_by_symbol = {coin.upper(): coin for coin in coins}
    session = (
        session_factory(coins) if session_factory is not None else build_coin_prompt_session(coins)
    )

    while True:
        typed_value = session.prompt("📝 Enter coin symbol: ")
        normalized_value = normalize_coin_input(typed_value)

        if not normalized_value:
            print("❌ Coin symbol is required")
            continue

        exact_match = canonical_by_symbol.get(normalized_value)
        if exact_match:
            return exact_match

        print("❌ No matching coin selected. Use Tab to view suggestions and select one.")
