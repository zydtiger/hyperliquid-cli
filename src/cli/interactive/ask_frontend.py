"""Frontend helpers for the interactive `ask` command."""

import json
import threading
from collections.abc import Callable
from typing import Any

import httpx

from models.config import Config

ASK_SESSION_PROMPT = ">>> "
ASK_EXIT_COMMANDS = frozenset({"/bye", "/exit", "/quit"})
ASK_TIMEOUT_SECONDS = 30.0
ASK_LOADING_FRAMES = ("|", "/", "-", "\\")


class AskFrontend:
    """Build prompt payloads and send them to an OpenAI-compatible chat endpoint."""

    def __init__(
        self,
        config: Config,
        manual_builder: Callable[[], str],
    ) -> None:
        self.config = config
        self._history: list[dict[str, str]] = [
            {"role": "system", "content": self.build_system_prompt(manual_builder)}
        ]

    @property
    def history(self) -> list[dict[str, str]]:
        """Return a copy of the current conversation history."""
        return list(self._history)

    def build_system_prompt(self, manual_builder: Callable[[], str]) -> str:
        """Construct the assistant system prompt from the live CLI manual."""
        manual = manual_builder().strip()
        return (
            "You are a helpful assistant to assist the user to navigate hyperliquid-cli, "
            "answer user's questions and construct relevant commands with the following "
            "information. Output should be concise, straight to the point, no markdown, "
            f"plain text.\n\n{manual}"
        )

    def build_chat_request(self, user_message: str) -> dict[str, object]:
        """Build the OpenAI-compatible chat-completions payload."""
        messages: list[dict[str, str]] = [*self._history, {"role": "user", "content": user_message}]
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

    def run_interactive(self) -> None:
        """Run the `>>>` interactive assistant loop until the user exits."""
        while True:
            try:
                user_message = input(ASK_SESSION_PROMPT)
            except EOFError:
                return

            stripped_message = user_message.strip()
            if not stripped_message:
                continue
            if stripped_message.lower() in ASK_EXIT_COMMANDS:
                return

            self._stream_interactive_response(user_message)

    def _stream_interactive_response(self, user_message: str) -> None:
        """Stream one interactive response to stdout and persist the completed turn."""
        request = self.build_chat_request(user_message)
        request["stream"] = True
        response = self._stream_chat_request(request)
        self._history.append({"role": "user", "content": user_message})
        self._history.append({"role": "assistant", "content": response})

    def _stream_chat_request(self, request: dict[str, object]) -> str:
        """Stream the chat completion response and return the combined text."""
        text_parts: list[str] = []
        stop_spinner = threading.Event()
        spinner_thread = threading.Thread(
            target=self._show_loading_indicator,
            args=(stop_spinner,),
            daemon=True,
        )
        spinner_thread.start()
        spinner_active = True

        try:
            with httpx.Client(timeout=ASK_TIMEOUT_SECONDS) as client:
                with client.stream(
                    "POST",
                    self._build_chat_completions_url(),
                    headers=self._build_headers(),
                    json=request,
                ) as response:
                    response.raise_for_status()
                    for line in response.iter_lines():
                        chunk = self._extract_stream_chunk(line)
                        if not chunk:
                            continue
                        if spinner_active:
                            stop_spinner.set()
                            spinner_thread.join()
                            self._clear_loading_indicator()
                            spinner_active = False
                        text_parts.append(chunk)
                        print(chunk, end="", flush=True)
        except httpx.HTTPStatusError as exc:
            message = self._extract_error_message(exc.response)
            raise RuntimeError(f"Agent request failed: {message}") from exc
        except httpx.HTTPError as exc:
            raise RuntimeError(f"Agent request failed: {exc}") from exc
        finally:
            if spinner_active:
                stop_spinner.set()
                spinner_thread.join()
                self._clear_loading_indicator()

        response_text = "".join(text_parts).strip()
        if response_text:
            print("", flush=True)
            print("", flush=True)
            return response_text

        raise RuntimeError("Agent response did not include any text content")

    def _show_loading_indicator(self, stop_spinner: threading.Event) -> None:
        """Render a rotating in-place loading indicator until streaming begins."""
        while not stop_spinner.is_set():
            for frame in ASK_LOADING_FRAMES:
                print(f"\r{frame}", end="", flush=True)
                if stop_spinner.wait(0.1):
                    return

    def _clear_loading_indicator(self) -> None:
        """Clear the loading indicator from the current terminal line."""
        padding = " "
        print(f"\r{padding}\r", end="", flush=True)

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

    def _extract_stream_chunk(self, line: str) -> str:
        """Extract assistant text from one streamed SSE line."""
        stripped_line = line.strip()
        result = ""
        if not stripped_line or not stripped_line.startswith("data:"):
            return result

        payload_text = stripped_line.removeprefix("data:").strip()
        if not payload_text or payload_text == "[DONE]":
            return result

        try:
            payload = json.loads(payload_text)
        except ValueError as exc:
            raise RuntimeError("Agent stream event was malformed") from exc

        if not isinstance(payload, dict):
            raise RuntimeError("Agent stream event was malformed")

        choices = payload.get("choices")
        if isinstance(choices, list) and choices:
            first_choice = choices[0]
            if isinstance(first_choice, dict):
                delta = first_choice.get("delta")
                if isinstance(delta, dict):
                    content = delta.get("content")
                    if isinstance(content, str):
                        result = content
                    elif isinstance(content, list):
                        text_parts = [
                            item.get("text", "")
                            for item in content
                            if isinstance(item, dict) and isinstance(item.get("text"), str)
                        ]
                        result = "".join(text_parts)

        return result

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
