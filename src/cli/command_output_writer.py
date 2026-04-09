"""Writers for normalizing interactive CLI command output."""

from io import TextIOBase
from typing import TextIO


class TrailingNewlineNormalizingWriter(TextIOBase):
    """Proxy stdout and normalize command output to end with one blank line."""

    _target: TextIO
    _pending: str
    _wrote_output: bool

    def __init__(self, target: TextIO) -> None:
        self._target = target
        self._pending = ""
        self._wrote_output = False

    def write(self, text: str) -> int:
        """Write text while buffering only the trailing newline suffix."""
        if not text:
            return 0

        self._wrote_output = True
        combined = self._pending + text
        cutoff = len(combined)
        while cutoff > 0 and combined[cutoff - 1] == "\n":
            cutoff -= 1

        body = combined[:cutoff]
        self._pending = combined[cutoff:]
        if body:
            self._target.write(body)
        return len(text)

    def flush(self) -> None:
        """Flush the underlying stream."""
        self._target.flush()

    def writable(self) -> bool:
        """Report that the proxy supports writes."""
        return True

    def finalize(self, add_blank_line: bool) -> None:
        """Flush buffered output with optional blank-line normalization."""
        if add_blank_line and self._wrote_output:
            self._target.write("\n\n")
        else:
            self._target.write(self._pending)
        self._pending = ""
        self._target.flush()
