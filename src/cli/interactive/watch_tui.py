"""
Fullscreen TUI for monitoring a live perpetual market.
"""

from __future__ import annotations

from collections.abc import Callable
from threading import Event, Thread

from prompt_toolkit.application import Application
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.layout import Layout
from prompt_toolkit.layout.containers import Window
from prompt_toolkit.styles import Style

from models.api import WatchInterval, WatchSnapshot

from .watch_screen import WatchScreenControl


class WatchTUI:
    """Launch a fullscreen TUI for a live perpetual market snapshot."""

    def __init__(
        self,
        coin: str,
        snapshot_fetcher: Callable[[str, WatchInterval, int], WatchSnapshot],
        poll_interval_seconds: float = 0.5,
    ) -> None:
        self.coin = coin
        self.snapshot_fetcher = snapshot_fetcher
        self.poll_interval_seconds = poll_interval_seconds
        self._stop_event = Event()
        self._wake_event = Event()
        self._refresh_requested = Event()
        self.control = WatchScreenControl(coin, self._request_refresh)

    def run(self) -> None:
        """Run the watch TUI and poll the backend until the user exits."""
        app = self._build_application()
        self._refresh_snapshot()
        poller = Thread(target=self._poll_loop, args=(app,), daemon=True)
        poller.start()
        try:
            app.run()
        finally:
            self._stop_event.set()
            self._wake_event.set()
            poller.join(timeout=1.0)

    def _poll_loop(self, app: Application[None]) -> None:
        while not self._stop_event.is_set():
            woke_early = self._wake_event.wait(self.poll_interval_seconds)
            self._wake_event.clear()
            if self._stop_event.is_set():
                break
            if woke_early and not self._refresh_requested.is_set():
                continue
            self._refresh_requested.clear()
            self._refresh_snapshot()
            app.invalidate()

    def _refresh_snapshot(self) -> None:
        try:
            self.control.set_snapshot(
                self.snapshot_fetcher(
                    self.coin,
                    self.control.current_interval(),
                    self.control.current_order_book_depth(),
                )
            )
        except Exception as exc:
            self.control.set_error(str(exc))

    def _request_refresh(self) -> None:
        if self._stop_event.is_set():
            return
        self._refresh_requested.set()
        self._wake_event.set()

    def _change_interval(self, delta: int) -> None:
        previous_interval = self.control.current_interval()
        self.control.advance_interval(delta)
        if self.control.current_interval() != previous_interval:
            self._refresh_snapshot()

    def _build_application(self) -> Application[None]:
        bindings = KeyBindings()

        @bindings.add("q")
        @bindings.add("escape")
        @bindings.add("enter")
        @bindings.add("c-c")
        def _exit(event) -> None:  # type: ignore[no-untyped-def]
            self._stop_event.set()
            self._wake_event.set()
            event.app.exit()

        @bindings.add("+")
        @bindings.add("=")
        def _shorter_interval(event) -> None:  # type: ignore[no-untyped-def]
            self._change_interval(-1)
            event.app.invalidate()

        @bindings.add("-")
        @bindings.add("_")
        def _longer_interval(event) -> None:  # type: ignore[no-untyped-def]
            self._change_interval(1)
            event.app.invalidate()

        return Application(
            layout=Layout(Window(content=self.control, always_hide_cursor=True)),
            key_bindings=bindings,
            full_screen=True,
            erase_when_done=True,
            mouse_support=False,
            style=Style.from_dict(
                {
                    "root": "bg:#101418 #d7dadc",
                    "header": "bold #f8f8f2",
                    "subheader": "#8be9fd",
                    "footer": "#7f8c8d",
                    "chart": "#8be9fd",
                    "ask": "#ff6b6b",
                    "bid": "#50fa7b",
                    "mid": "bold #f1fa8c",
                    "error": "#ff5555",
                }
            ),
        )


__all__ = ["WatchScreenControl", "WatchTUI"]
