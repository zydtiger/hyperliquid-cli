"""Frontend helpers for the interactive `ask` command."""

from collections.abc import Callable

from models.config import Config

ASK_SESSION_PROMPT = ">>> "
ASK_EXIT_COMMANDS = frozenset({"/bye", "/exit", "/quit"})
ASK_STUB_RESPONSE = "Feature still implementing."


class AskFrontend:
    """Build prompt payloads for the CLI assistant and return stub responses."""

    def __init__(
        self,
        config: Config,
        manual_builder: Callable[[], str],
        responder: Callable[[dict[str, object]], str] | None = None,
    ) -> None:
        self.config = config
        self._manual_builder = manual_builder
        self._history: list[dict[str, str]] = []
        self._responder = responder or self._stub_responder

    @property
    def history(self) -> list[dict[str, str]]:
        """Return a copy of the current conversation history."""
        return list(self._history)

    def build_system_prompt(self) -> str:
        """Construct the assistant system prompt from the live CLI manual."""
        manual = self._manual_builder().strip()
        return (
            "You are a helpful assistant to assist the user to navigate hyperliquid-cli, "
            "answer user's questions and construct relevant commands with the following "
            f"information:\n\n{manual}"
        )

    def build_chat_request(self, user_message: str) -> dict[str, object]:
        """Build the future chat-completions style payload."""
        messages: list[dict[str, str]] = [
            {"role": "system", "content": self.build_system_prompt()},
            *self._history,
            {"role": "user", "content": user_message},
        ]
        return {
            "model": self.config.agent.model_id,
            "messages": messages,
        }

    def submit(self, user_message: str) -> str:
        """Submit one prompt to the stub responder and persist the turn history."""
        request = self.build_chat_request(user_message)
        response = self._responder(request)
        self._history.append({"role": "user", "content": user_message})
        self._history.append({"role": "assistant", "content": response})
        return response

    def run_interactive(
        self,
        input_func: Callable[[str], str] = input,
        output_func: Callable[[str], None] = print,
    ) -> None:
        """Run the `>>>` interactive assistant loop until the user exits."""
        while True:
            try:
                user_message = input_func(ASK_SESSION_PROMPT)
            except EOFError:
                return

            stripped_message = user_message.strip()
            if not stripped_message:
                continue
            if stripped_message.lower() in ASK_EXIT_COMMANDS:
                return

            output_func(self.submit(user_message))

    @staticmethod
    def _stub_responder(request: dict[str, object]) -> str:
        """Return a fixed placeholder response until transport is implemented."""
        _ = request
        return ASK_STUB_RESPONSE


__all__ = [
    "ASK_EXIT_COMMANDS",
    "ASK_SESSION_PROMPT",
    "ASK_STUB_RESPONSE",
    "AskFrontend",
]
