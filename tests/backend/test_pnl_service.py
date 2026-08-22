"""
Tests for the backend /pnl endpoint.
"""

from decimal import Decimal
from unittest.mock import Mock, patch

import pytest
from fastapi.testclient import TestClient

from backend.exchange.hyperliquid_client import HyperliquidClient
from backend.service import create_app
from models.api import DEFAULT_PNL_WINDOW, ExchangeError, PnlHistory, PnlHistoryCatalog, PnlPoint
from models.config import Config, HyperliquidConfig, NetworkType


@pytest.fixture
def mock_config() -> Config:
    """Create a mock configuration object for testing."""
    return Config(
        hyperliquid=HyperliquidConfig(
            account_address="0x1234567890123456789012345678901234567890",
            private_key="0x1234567890123456789012345678901234567890123456789012345678901234",
            network=NetworkType.MAINNET,
        )
    )


@pytest.fixture
def mock_client() -> Mock:
    """Create a mock HyperliquidClient."""
    client = Mock(spec=HyperliquidClient)
    client.test_connection.return_value = True
    return client


@pytest.fixture
def test_app(mock_config: Config, mock_client: Mock) -> TestClient:
    """Create a test FastAPI app with mocked dependencies."""
    with patch("backend.service.HyperliquidClient", return_value=mock_client):
        return TestClient(create_app(mock_config))


@pytest.fixture
def sample_pnl_history() -> PnlHistoryCatalog:
    """Sample multi-window PnL history for testing."""
    return PnlHistoryCatalog(
        default_window=DEFAULT_PNL_WINDOW,
        histories=[
            PnlHistory(
                window="1d",
                points=[
                    PnlPoint(
                        time=1741886630493,
                        total_pnl=Decimal("0.0"),
                        perp_pnl=Decimal("0.0"),
                        spot_pnl=Decimal("0.0"),
                    )
                ],
            ),
            PnlHistory(
                window="7d",
                points=[
                    PnlPoint(
                        time=1741886630493,
                        total_pnl=Decimal("0.0"),
                        perp_pnl=Decimal("0.0"),
                        spot_pnl=Decimal("0.0"),
                    ),
                    PnlPoint(
                        time=1741973030493,
                        total_pnl=Decimal("10.5"),
                        perp_pnl=Decimal("7.0"),
                        spot_pnl=Decimal("3.5"),
                    ),
                ],
            ),
        ],
    )


def test_pnl_endpoint_success(
    test_app: TestClient,
    mock_client: Mock,
    sample_pnl_history: PnlHistoryCatalog,
) -> None:
    """Test successful /pnl endpoint response."""
    mock_client.get_pnl_history.return_value = sample_pnl_history

    response = test_app.get("/pnl")

    assert response.status_code == 200
    assert response.json() == {
        "default_window": "7d",
        "histories": [
            {
                "window": "1d",
                "points": [
                    {
                        "time": 1741886630493,
                        "total_pnl": "0.0",
                        "perp_pnl": "0.0",
                        "spot_pnl": "0.0",
                    }
                ],
            },
            {
                "window": "7d",
                "points": [
                    {
                        "time": 1741886630493,
                        "total_pnl": "0.0",
                        "perp_pnl": "0.0",
                        "spot_pnl": "0.0",
                    },
                    {
                        "time": 1741973030493,
                        "total_pnl": "10.5",
                        "perp_pnl": "7.0",
                        "spot_pnl": "3.5",
                    },
                ],
            },
        ],
    }
    mock_client.get_pnl_history.assert_called_once_with()


def test_pnl_endpoint_exchange_error(test_app: TestClient, mock_client: Mock) -> None:
    """Test /pnl endpoint when the exchange layer fails."""
    mock_client.get_pnl_history.side_effect = ExchangeError("Authentication failed")

    response = test_app.get("/pnl")

    assert response.status_code == 400
    assert "Authentication failed" in response.json()["detail"]


def test_pnl_endpoint_unexpected_error(test_app: TestClient, mock_client: Mock) -> None:
    """Test /pnl endpoint when an unexpected error occurs."""
    mock_client.get_pnl_history.side_effect = Exception("Network error")

    response = test_app.get("/pnl")

    assert response.status_code == 500
    assert response.json()["detail"] == "Internal server error"
