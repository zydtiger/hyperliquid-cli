"""Tests for the interactive CLI ask frontend."""

import pytest

from cli.cli_manual import build_cli_manual
from cli.interactive.ask_frontend import ASK_SESSION_PROMPT, AskFrontend
from cli.interactive_cli import InteractiveCLI
from models.config import Config, HyperliquidConfig, NetworkType

AGENT_RESPONSE = "Use: order buy ETH 0.25"


@pytest.fixture
def config() -> Config:
    """Create a mock configuration for ask frontend tests."""
    return Config(
        hyperliquid=HyperliquidConfig(
            account_address="0x1234567890123456789012345678901234567890",
            private_key="0x1234567890123456789012345678901234567890123456789012345678901234",
            network=NetworkType.MAINNET,
        )
    )


def test_submit_builds_prompt_from_cli_manual(config: Config):
    """Test ask prompt payload includes the generated CLI manual content."""
    captured_requests: list[dict[str, object]] = []

    def fake_send(self, request: dict[str, object]) -> str:
        captured_requests.append(request)
        return AGENT_RESPONSE

    frontend = AskFrontend(
        config, manual_builder=lambda: "# Hyperliquid CLI Manual\n\nUse order for trades.\n"
    )
    frontend._send_chat_request = fake_send.__get__(frontend, AskFrontend)
    response = frontend.submit("how do i place an order")

    assert response == AGENT_RESPONSE
    assert captured_requests[0]["model"] == config.agent.model_id
    messages = captured_requests[0]["messages"]
    assert isinstance(messages, list)
    assert "Use order for trades." in messages[0]["content"]
    assert "no markdown, plain text" in messages[0]["content"]
    assert messages[-1] == {"role": "user", "content": "how do i place an order"}


def test_submit_preserves_history_between_turns(config: Config):
    """Test ask sessions keep prior turns in the next request payload."""
    captured_requests: list[dict[str, object]] = []

    def fake_send(self, request: dict[str, object]) -> str:
        captured_requests.append(request)
        return AGENT_RESPONSE

    frontend = AskFrontend(config, manual_builder=lambda: "# Hyperliquid CLI Manual\n")
    frontend._send_chat_request = fake_send.__get__(frontend, AskFrontend)
    frontend.submit("first question")
    frontend.submit("second question")

    first_messages = captured_requests[0]["messages"]
    second_messages = captured_requests[1]["messages"]
    assert isinstance(first_messages, list)
    assert isinstance(second_messages, list)
    assert len(first_messages) == 2
    assert second_messages[1:] == [
        {"role": "user", "content": "first question"},
        {"role": "assistant", "content": AGENT_RESPONSE},
        {"role": "user", "content": "second question"},
    ]
    assert frontend.history == [
        {"role": "user", "content": "first question"},
        {"role": "assistant", "content": AGENT_RESPONSE},
        {"role": "user", "content": "second question"},
        {"role": "assistant", "content": AGENT_RESPONSE},
    ]


def test_run_interactive_ignores_blank_input_and_exits(config: Config):
    """Test the interactive ask loop ignores blank lines and exits on /quit."""
    prompted_values: list[str] = []
    outputs: list[str] = []
    user_inputs = iter(["", "how do i cancel orders", "/quit"])

    def fake_send(self, request: dict[str, object]) -> str:
        return AGENT_RESPONSE

    def input_func(prompt: str) -> str:
        prompted_values.append(prompt)
        return next(user_inputs)

    frontend = AskFrontend(config, manual_builder=lambda: "# Hyperliquid CLI Manual\n")
    frontend._send_chat_request = fake_send.__get__(frontend, AskFrontend)
    frontend.run_interactive(input_func=input_func, output_func=outputs.append)

    assert prompted_values == [ASK_SESSION_PROMPT, ASK_SESSION_PROMPT, ASK_SESSION_PROMPT]
    assert outputs == [AGENT_RESPONSE]
    assert frontend.history == [
        {"role": "user", "content": "how do i cancel orders"},
        {"role": "assistant", "content": AGENT_RESPONSE},
    ]


def test_ask_command_prints_agent_response(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    config: Config,
):
    """Test one-shot ask prints the agent response."""
    monkeypatch.setattr(
        "cli.interactive.ask_frontend.AskFrontend._send_chat_request", lambda *_: AGENT_RESPONSE
    )
    cli = InteractiveCLI(config)
    cli.do_ask("how do i place a limit order")
    output = capsys.readouterr().out

    assert AGENT_RESPONSE in output


def test_ask_command_runs_interactive_session(
    monkeypatch: pytest.MonkeyPatch,
    config: Config,
):
    """Test bare ask launches the interactive session helper."""
    launched_sessions: list[Config] = []
    captured_manual: list[str] = []

    class FakeAskFrontend:
        def __init__(self, passed_config: Config, manual_builder):
            launched_sessions.append(passed_config)
            captured_manual.append(manual_builder())

        def submit(self, user_message: str) -> str:
            raise AssertionError(f"submit should not be called for bare ask: {user_message}")

        def run_interactive(self) -> None:
            launched_sessions.append(config)

    monkeypatch.setattr("cli.interactive_cli.AskFrontend", FakeAskFrontend)

    cli = InteractiveCLI(config)
    cli.do_ask("")

    assert launched_sessions == [config, config]
    assert "## ask" in captured_manual[0]


def test_send_chat_request_uses_configured_endpoint(
    monkeypatch: pytest.MonkeyPatch,
    config: Config,
):
    """Test the agent request uses the configured URL, headers, and payload."""
    captured_calls: list[dict[str, object]] = []

    class FakeResponse:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict[str, object]:
            return {"choices": [{"message": {"content": AGENT_RESPONSE}}]}

    class FakeClient:
        def __init__(self, timeout: float):
            self.timeout = timeout

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_val, exc_tb):
            return None

        def post(self, url: str, headers: dict[str, str], json: dict[str, object]) -> FakeResponse:
            captured_calls.append({"url": url, "headers": headers, "json": json})
            return FakeResponse()

    monkeypatch.setattr("cli.interactive.ask_frontend.httpx.Client", FakeClient)

    frontend = AskFrontend(config, manual_builder=lambda: "# Hyperliquid CLI Manual\n")
    response = frontend.submit("how do i place an order")

    assert response == AGENT_RESPONSE
    assert captured_calls[0]["url"] == "your_openai_compatible_base_url_here/chat/completions"
    assert captured_calls[0]["headers"]["Authorization"] == "Bearer your_openai_api_key_here"
    assert captured_calls[0]["json"]["model"] == "your_model_id_here"


def test_extract_response_text_supports_content_parts(config: Config):
    """Test content arrays are flattened into plain text."""
    frontend = AskFrontend(config, manual_builder=lambda: "# Hyperliquid CLI Manual\n")

    response = frontend._extract_response_text(
        {
            "choices": [
                {
                    "message": {
                        "content": [
                            {"type": "output_text", "text": "first line"},
                            {"type": "output_text", "text": "second line"},
                        ]
                    }
                }
            ]
        }
    )

    assert response == "first line\nsecond line"


def test_command_completion_includes_ask_and_balances(config: Config):
    """Test command completion includes the new ask command and existing balances."""
    cli = InteractiveCLI(config)

    assert "ask" in cli.completenames("a")
    assert "balances" in cli.completenames("bal")


def test_build_cli_manual_includes_ask(config: Config):
    """Test the generated manual includes the ask command."""
    cli = InteractiveCLI(config)
    manual = build_cli_manual(cli)

    assert "## ask" in manual
    assert "configured OpenAI-compatible agent endpoint" in manual
