"""Frontend helpers for the interactive `ask` command."""

from collections.abc import Callable
from typing import Any

import httpx

from models.config import Config

ASK_SESSION_PROMPT = ">>> "
ASK_EXIT_COMMANDS = frozenset({"/bye", "/exit", "/quit"})
ASK_TIMEOUT_SECONDS = 30.0


class AskFrontend:
    """Build prompt payloads and send them to an OpenAI-compatible chat endpoint."""

    def __init__(
        self,
        config: Config,
        manual_builder: Callable[[], str],
    ) -> None:
        self.config = config
        self._manual_builder = manual_builder
        self._history: list[dict[str, str]] = []

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
            "information. Output should be concise, straight to the point, no markdown, "
            f"plain text.\n\n{manual}"
        )

    def build_chat_request(self, user_message: str) -> dict[str, object]:
        """Build the OpenAI-compatible chat-completions payload."""
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
        """Submit one prompt to the chat endpoint and persist the turn history."""
        request = self.build_chat_request(user_message)
        response = self._send_chat_request(request)
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

    def _send_chat_request(self, request: dict[str, object]) -> str:
        """Send the chat completion request to the configured agent endpoint."""
        try:
            with httpx.Client(timeout=ASK_TIMEOUT_SECONDS) as client:
                response = client.post(
                    self._build_chat_completions_url(),
                    headers=self._build_headers(),
                    json=request,
                )
                response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            message = self._extract_error_message(exc.response)
            raise RuntimeError(f"Agent request failed: {message}") from exc
        except httpx.HTTPError as exc:
            raise RuntimeError(f"Agent request failed: {exc}") from exc

        return self._extract_response_text(response.json())

    def _build_chat_completions_url(self) -> str:
        """Return the full chat completions URL from the configured base URL."""
        base_url = self.config.agent.openai_base_url.rstrip("/")
        return f"{base_url}/chat/completions"

    def _build_headers(self) -> dict[str, str]:
        """Return the headers required for an OpenAI-compatible request."""
        return {
            "Authorization": f"Bearer {self.config.agent.api_key}",
            "Content-Type": "application/json",
        }

    def _extract_response_text(self, payload: dict[str, Any]) -> str:
        """Extract assistant text from an OpenAI-compatible chat response."""
        choices = payload.get("choices")
        if not isinstance(choices, list) or not choices:
            raise RuntimeError("Agent response did not include any choices")

        first_choice = choices[0]
        if not isinstance(first_choice, dict):
            raise RuntimeError("Agent response choice was malformed")

        message = first_choice.get("message")
        if not isinstance(message, dict):
            raise RuntimeError("Agent response message was malformed")

        content = message.get("content")
        if isinstance(content, str) and content.strip():
            return content.strip()
        if isinstance(content, list):
            text_parts = [
                item.get("text", "").strip()
                for item in content
                if isinstance(item, dict) and isinstance(item.get("text"), str)
            ]
            combined_text = "\n".join(part for part in text_parts if part)
            if combined_text:
                return combined_text

        raise RuntimeError("Agent response did not include any text content")

    def _extract_error_message(self, response: httpx.Response) -> str:
        """Extract a readable error from a failed agent response."""
        try:
            payload = response.json()
        except ValueError:
            text = response.text.strip()
            return text or f"HTTP {response.status_code}"

        if isinstance(payload, dict):
            error = payload.get("error")
            if isinstance(error, dict):
                message = error.get("message")
                if isinstance(message, str) and message.strip():
                    return message.strip()
            detail = payload.get("detail")
            if isinstance(detail, str) and detail.strip():
                return detail.strip()

        return f"HTTP {response.status_code}"


__all__ = [
    "ASK_EXIT_COMMANDS",
    "ASK_SESSION_PROMPT",
    "ASK_TIMEOUT_SECONDS",
    "AskFrontend",
]
