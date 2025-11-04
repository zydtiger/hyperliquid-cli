"""
Comprehensive test suite for the backend service and request handlers.

This module provides unit tests for the FastAPI service creation, CLI functionality,
and all API request handlers, including mocking of external dependencies.
"""

import tempfile
from decimal import Decimal
from pathlib import Path
from typing import Generator
from unittest.mock import Mock, patch

import pytest
from fastapi.testclient import TestClient

from backend.service import create_app
from backend.request_handlers import setup_request_handlers
from backend.exchange.hyperliquid_client import HyperliquidClient
from models.api import (
    Ticker,
    CoinMetadata,
    PositionInfo,
    BalanceInfo,
    SpotBalance,
    StakingInfo,
    ExchangeError,
    LeverageType,
    HealthResponse,
    RootResponse,
    HealthStatus,
)
from models.order import (
    OrderInfo,
    OrderSide,
    OrderType,
    OrderStatus,
    OrderTif,
    MarketOrder,
    LimitOrder,
    OrderResult,
)
from models.config import Config, HyperliquidConfig, NetworkType


class TestBackendService:
    """Test cases for backend service functionality."""

    @pytest.fixture
    def mock_config(self) -> Config:
        """Create a mock configuration object for testing."""
        hyperliquid_config = HyperliquidConfig(
            account_address="0x1234567890123456789012345678901234567890",
            private_key="0x1234567890123456789012345678901234567890123456789012345678901234",
            network=NetworkType.MAINNET,
        )
        return Config(hyperliquid=hyperliquid_config)

    @pytest.fixture
    def mock_client(self) -> Mock:
        """Create a mock HyperliquidClient."""
        client = Mock(spec=HyperliquidClient)
        client.test_connection.return_value = True
        return client

    @pytest.fixture
    def sample_ticker(self) -> Ticker:
        """Sample ticker data for testing."""
        return Ticker(
            coin="BTC",
            mark_price=Decimal("43250.50"),
            funding_rate=Decimal("0.0001"),
            open_interest=Decimal("1250.75"),
        )

    @pytest.fixture
    def sample_metadata(self) -> CoinMetadata:
        """Sample metadata for testing."""
        return CoinMetadata(
            coin="BTC",
            size_decimals=8,
            max_leverage=50,
        )

    @pytest.fixture
    def sample_position(self) -> PositionInfo:
        """Sample position for testing."""
        return PositionInfo(
            coin="BTC",
            size=Decimal("0.1"),
            entry_price=Decimal("42000.00"),
            mark_price=Decimal("43250.50"),
            unrealized_pnl=Decimal("125.05"),
            leverage=10,
            leverage_type=LeverageType.ISOLATED,
            margin_used=Decimal("420.00"),
            cum_funding=Decimal("15.25"),
        )

    @pytest.fixture
    def sample_market_order(self) -> MarketOrder:
        """Sample market order for testing."""
        return MarketOrder(
            coin="ETH",
            side=OrderSide.BUY,
            quantity=Decimal("0.1"),
            reduce_only=False,
        )

    @pytest.fixture
    def sample_limit_order(self) -> LimitOrder:
        """Sample limit order for testing."""
        return LimitOrder(
            coin="BTC",
            side=OrderSide.SELL,
            quantity=Decimal("0.05"),
            price=Decimal("50000.0"),
            reduce_only=False,
            time_in_force=OrderTif.GTC,
        )

    @pytest.fixture
    def sample_order_result(self) -> OrderResult:
        """Sample order result for testing."""
        return OrderResult(
            success=True,
            order_id=123456789,
            status=OrderStatus.OPEN,
            message="Order submitted successfully",
        )

    @pytest.fixture
    def sample_balance(self) -> BalanceInfo:
        """Sample balance information for testing."""
        return BalanceInfo(
            perps_account_value=Decimal("3451.743653"),
            perps_total_position_value=Decimal("10.8642"),
            perps_total_raw_usd=Decimal("3440.879453"),
            perps_margin_used=Decimal("5.318932"),
            perps_withdrawable=Decimal("3451.324721"),
            spot_balances=[
                SpotBalance(coin="USDC", total=Decimal("1000.50")),
                SpotBalance(coin="HYPE", total=Decimal("500.0")),
                SpotBalance(coin="UETH", total=Decimal("0.002998111")),
            ],
            staking_info=StakingInfo(
                delegated_amount=Decimal("100.61607572"),
                undelegated_amount=Decimal("25.12345678"),
                pending_withdrawals=Decimal("5.0"),
                pending_withdrawal_count=2,
            ),
        )

    @pytest.fixture
    def temp_config_file(self, mock_config: Config) -> Generator[Path, None, None]:
        """Create a temporary configuration file."""
        config_data = mock_config.model_dump()
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            import yaml

            yaml.dump(config_data, f)
            temp_path = Path(f.name)
        yield temp_path
        temp_path.unlink()

    @pytest.fixture
    def test_app(self, mock_config: Config, mock_client: Mock) -> TestClient:
        """Create a test FastAPI app with mocked dependencies."""
        with patch("backend.service.HyperliquidClient", return_value=mock_client):
            app = create_app(mock_config)
            return TestClient(app)


class TestCreateApp(TestBackendService):
    """Test cases for the create_app function."""

    def test_create_app_success(self, mock_config: Config, mock_client: Mock):
        """Test successful FastAPI app creation."""
        with patch("backend.service.HyperliquidClient", return_value=mock_client):
            app = create_app(mock_config)

            # Verify app is created
            assert app is not None
            assert app.title == "Hyperliquid API"
            assert app.description == "REST API for Hyperliquid exchange operations"
            assert app.version == "1.0.0"

            # Verify client is initialized
            mock_client_cls = patch("backend.service.HyperliquidClient")
            with mock_client_cls:
                create_app(mock_config)

    def test_create_app_client_initialization_failure(self, mock_config: Config):
        """Test app creation when client initialization fails."""
        with patch(
            "backend.service.HyperliquidClient",
            side_effect=Exception("Connection failed"),
        ):
            with pytest.raises(Exception, match="Connection failed"):
                create_app(mock_config)

    def test_create_app_cors_middleware(self, mock_config: Config, mock_client: Mock):
        """Test that CORS middleware is properly configured."""
        with patch("backend.service.HyperliquidClient", return_value=mock_client):
            app = create_app(mock_config)

            # Check CORS middleware is added
            cors_middleware = None
            for middleware in app.user_middleware:
                if (
                    hasattr(middleware.cls, "__name__")
                    and "CORSMiddleware" in middleware.cls.__name__  # type: ignore[attr-defined]
                ):
                    cors_middleware = middleware
                    break

            assert cors_middleware is not None
            assert cors_middleware.kwargs["allow_origins"] == ["*"]
            assert cors_middleware.kwargs["allow_credentials"] is True
            assert cors_middleware.kwargs["allow_methods"] == ["*"]
            assert cors_middleware.kwargs["allow_headers"] == ["*"]

    def test_create_app_request_handlers_setup(
        self, mock_config: Config, mock_client: Mock
    ):
        """Test that request handlers are properly set up."""
        with (
            patch("backend.service.HyperliquidClient", return_value=mock_client),
            patch("backend.service.setup_request_handlers") as mock_setup,
        ):
            app = create_app(mock_config)

            # Verify setup_request_handlers was called
            mock_setup.assert_called_once_with(app, mock_client)

    def test_health_endpoint_integration(self, test_app: TestClient, mock_client: Mock):
        """Test health endpoint integration."""
        mock_client.test_connection.return_value = True

        response = test_app.get("/health")

        assert response.status_code == 200
        expected_response = HealthResponse(status=HealthStatus.HEALTHY)
        assert response.json() == expected_response.model_dump()

    def test_health_endpoint_failure(self, test_app: TestClient, mock_client: Mock):
        """Test health endpoint when connection fails."""
        mock_client.test_connection.return_value = False

        response = test_app.get("/health")

        assert response.status_code == 200
        expected_response = HealthResponse(status=HealthStatus.UNHEALTHY)
        assert response.json() == expected_response.model_dump()

    def test_health_endpoint_exception(self, test_app: TestClient, mock_client: Mock):
        """Test health endpoint when client throws exception."""
        mock_client.test_connection.side_effect = Exception("Service unavailable")

        response = test_app.get("/health")

        assert response.status_code == 503
        assert "Service unavailable" in response.json()["detail"]

    def test_root_endpoint(self, test_app: TestClient, mock_client: Mock):
        """Test root endpoint returns API information."""
        mock_client.test_connection.return_value = True

        response = test_app.get("/")

        assert response.status_code == 200
        expected_response = RootResponse(
            api="Hyperliquid API", version="1.0.0", status=HealthStatus.HEALTHY
        )
        assert response.json() == expected_response.model_dump()


class TestRequestHandlers(TestBackendService):
    """Test cases for request handlers."""

    def test_setup_request_handlers_registers_endpoints(self, mock_client: Mock):
        """Test that setup_request_handlers properly registers all endpoints."""
        from fastapi import FastAPI

        app = FastAPI()
        setup_request_handlers(app, mock_client)

        # Check that endpoints are registered
        routes = [route.path for route in app.routes]  # type: ignore
        expected_routes = [
            "/available_coins",
            "/ticker/{coin}",
            "/metadata/{coin}",
            "/positions",
            "/positions/{coin}",
            "/balances",
            "/order_status/{order_id}",
            "/market_order",
            "/limit_order",
        ]

        for route in expected_routes:
            assert route in routes

    def test_available_coins_endpoint_success(
        self, test_app: TestClient, mock_client: Mock
    ):
        """Test successful /available_coins endpoint."""
        mock_client.get_available_coins.return_value = ["BTC", "ETH", "SOL"]

        response = test_app.get("/available_coins")

        assert response.status_code == 200
        assert response.json() == ["BTC", "ETH", "SOL"]
        mock_client.get_available_coins.assert_called_once()

    def test_available_coins_endpoint_exchange_error(
        self, test_app: TestClient, mock_client: Mock
    ):
        """Test /available_coins endpoint with exchange error."""
        mock_client.get_available_coins.side_effect = ExchangeError("API rate limited")

        response = test_app.get("/available_coins")

        assert response.status_code == 400
        assert "API rate limited" in response.json()["detail"]

    def test_available_coins_endpoint_unexpected_error(
        self, test_app: TestClient, mock_client: Mock
    ):
        """Test /available_coins endpoint with unexpected error."""
        mock_client.get_available_coins.side_effect = Exception("Unexpected error")

        response = test_app.get("/available_coins")

        assert response.status_code == 500
        assert response.json()["detail"] == "Internal server error"

    def test_ticker_endpoint_success(
        self, test_app: TestClient, mock_client: Mock, sample_ticker: Ticker
    ):
        """Test successful /ticker/{coin} endpoint."""
        mock_client.get_ticker.return_value = sample_ticker

        response = test_app.get("/ticker/BTC")

        assert response.status_code == 200
        expected = {
            "coin": "BTC",
            "mark_price": "43250.50",
            "funding_rate": "0.0001",
            "open_interest": "1250.75",
        }
        assert response.json() == expected
        mock_client.get_ticker.assert_called_once_with("BTC")

    def test_ticker_endpoint_exchange_error(
        self, test_app: TestClient, mock_client: Mock
    ):
        """Test /ticker/{coin} endpoint with exchange error."""
        mock_client.get_ticker.side_effect = ExchangeError("Coin not found")

        response = test_app.get("/ticker/INVALID")

        assert response.status_code == 400
        assert "Coin not found" in response.json()["detail"]

    def test_ticker_endpoint_unexpected_error(
        self, test_app: TestClient, mock_client: Mock
    ):
        """Test /ticker/{coin} endpoint with unexpected error."""
        mock_client.get_ticker.side_effect = Exception("Network error")

        response = test_app.get("/ticker/BTC")

        assert response.status_code == 500
        assert response.json()["detail"] == "Internal server error"

    def test_metadata_endpoint_success(
        self, test_app: TestClient, mock_client: Mock, sample_metadata: CoinMetadata
    ):
        """Test successful /metadata/{coin} endpoint."""
        mock_client.get_metadata.return_value = sample_metadata

        response = test_app.get("/metadata/BTC")

        assert response.status_code == 200
        expected = {"coin": "BTC", "size_decimals": 8, "max_leverage": 50}
        assert response.json() == expected
        mock_client.get_metadata.assert_called_once_with("BTC")

    def test_metadata_endpoint_exchange_error(
        self, test_app: TestClient, mock_client: Mock
    ):
        """Test /metadata/{coin} endpoint with exchange error."""
        mock_client.get_metadata.side_effect = ExchangeError("Invalid coin")

        response = test_app.get("/metadata/INVALID")

        assert response.status_code == 400
        assert "Invalid coin" in response.json()["detail"]

    def test_positions_endpoint_success(
        self, test_app: TestClient, mock_client: Mock, sample_position: PositionInfo
    ):
        """Test successful /positions endpoint."""
        mock_client.get_positions.return_value = [sample_position]

        response = test_app.get("/positions")

        assert response.status_code == 200
        expected = [
            {
                "coin": "BTC",
                "size": "0.1",
                "entry_price": "42000.00",
                "mark_price": "43250.50",
                "unrealized_pnl": "125.05",
                "leverage": 10,
                "leverage_type": "isolated",
                "margin_used": "420.00",
                "cum_funding": "15.25",
            }
        ]
        assert response.json() == expected
        mock_client.get_positions.assert_called_once()

    def test_positions_endpoint_empty(self, test_app: TestClient, mock_client: Mock):
        """Test /positions endpoint with no positions."""
        mock_client.get_positions.return_value = []

        response = test_app.get("/positions")

        assert response.status_code == 200
        assert response.json() == []

    def test_positions_endpoint_exchange_error(
        self, test_app: TestClient, mock_client: Mock
    ):
        """Test /positions endpoint with exchange error."""
        mock_client.get_positions.side_effect = ExchangeError("Authentication failed")

        response = test_app.get("/positions")

        assert response.status_code == 400
        assert "Authentication failed" in response.json()["detail"]

    def test_position_by_coin_endpoint_success(
        self, test_app: TestClient, mock_client: Mock, sample_position: PositionInfo
    ):
        """Test successful /positions/{coin} endpoint."""
        mock_client.get_positions.return_value = [sample_position]

        response = test_app.get("/positions/BTC")

        assert response.status_code == 200
        expected = {
            "coin": "BTC",
            "size": "0.1",
            "entry_price": "42000.00",
            "mark_price": "43250.50",
            "unrealized_pnl": "125.05",
            "leverage": 10,
            "leverage_type": "isolated",
            "margin_used": "420.00",
            "cum_funding": "15.25",
        }
        assert response.json() == expected
        mock_client.get_positions.assert_called_once()

    def test_position_by_coin_endpoint_not_found(
        self, test_app: TestClient, mock_client: Mock
    ):
        """Test /positions/{coin} endpoint when position not found."""
        eth_position = PositionInfo(
            coin="ETH",
            size=Decimal("1.0"),
            entry_price=Decimal("3000.00"),
            mark_price=Decimal("3100.00"),
            unrealized_pnl=Decimal("100.00"),
            leverage=5,
            leverage_type=LeverageType.CROSS,
            margin_used=Decimal("600.00"),
            cum_funding=Decimal("5.00"),
        )
        mock_client.get_positions.return_value = [eth_position]

        response = test_app.get("/positions/BTC")

        assert response.status_code == 404
        assert "No position found for BTC" in response.json()["detail"]

    def test_position_by_coin_endpoint_exchange_error(
        self, test_app: TestClient, mock_client: Mock
    ):
        """Test /positions/{coin} endpoint with exchange error."""
        mock_client.get_positions.side_effect = ExchangeError("API error")

        response = test_app.get("/positions/BTC")

        assert response.status_code == 400
        assert "API error" in response.json()["detail"]

    def test_balances_endpoint_success(
        self, test_app: TestClient, mock_client: Mock, sample_balance: BalanceInfo
    ):
        """Test successful /balances endpoint."""
        mock_client.get_balances.return_value = sample_balance

        response = test_app.get("/balances")

        assert response.status_code == 200

        # Check response structure and key values
        data = response.json()
        assert data["perps_account_value"] == "3451.743653"
        assert data["perps_total_position_value"] == "10.8642"
        assert data["perps_total_raw_usd"] == "3440.879453"
        assert data["perps_margin_used"] == "5.318932"
        assert data["perps_withdrawable"] == "3451.324721"

        # Check spot balances structure
        assert "spot_balances" in data
        assert len(data["spot_balances"]) == 3
        assert any(balance["coin"] == "USDC" for balance in data["spot_balances"])
        assert any(balance["coin"] == "HYPE" for balance in data["spot_balances"])
        assert any(balance["coin"] == "UETH" for balance in data["spot_balances"])

        # Check staking info structure
        assert "staking_info" in data
        assert data["staking_info"]["delegated_amount"] == "100.61607572"
        assert data["staking_info"]["undelegated_amount"] == "25.12345678"
        assert data["staking_info"]["pending_withdrawal_count"] == 2

        mock_client.get_balances.assert_called_once()

    def test_balances_endpoint_exchange_error(
        self, test_app: TestClient, mock_client: Mock
    ):
        """Test /balances endpoint with exchange error."""
        mock_client.get_balances.side_effect = ExchangeError("Authentication failed")

        response = test_app.get("/balances")

        assert response.status_code == 400
        assert "Authentication failed" in response.json()["detail"]

    def test_balances_endpoint_unexpected_error(
        self, test_app: TestClient, mock_client: Mock
    ):
        """Test /balances endpoint with unexpected error."""
        mock_client.get_balances.side_effect = Exception("Network error")

        response = test_app.get("/balances")

        assert response.status_code == 500
        assert response.json()["detail"] == "Internal server error"

    def test_order_status_endpoint_success(
        self, test_app: TestClient, mock_client: Mock
    ):
        """Test successful /order_status/{order_id} endpoint."""
        sample_order = OrderInfo(
            order_id=123456,
            coin="BTC",
            side=OrderSide.BUY,
            order_type=OrderType.LIMIT,
            quantity=Decimal("0.1"),
            price=Decimal("42000.00"),
            filled_quantity=Decimal("0.05"),
            remaining_quantity=Decimal("0.05"),
            average_fill_price=Decimal("42100.00"),
            status=OrderStatus.PARTIALLY_FILLED,
            timestamp=1704067200000,
            reduce_only=False,
            time_in_force=OrderTif.GTC,
        )
        mock_client.get_order_status.return_value = sample_order

        response = test_app.get("/order_status/123456")

        assert response.status_code == 200
        expected = {
            "order_id": 123456,
            "coin": "BTC",
            "side": "buy",
            "order_type": "limit",
            "quantity": "0.1",
            "price": "42000.00",
            "filled_quantity": "0.05",
            "remaining_quantity": "0.05",
            "average_fill_price": "42100.00",
            "status": "partially_filled",
            "timestamp": 1704067200000,
            "reduce_only": False,
            "time_in_force": "GTC",
        }
        assert response.json() == expected
        mock_client.get_order_status.assert_called_once_with(123456)

    def test_order_status_endpoint_exchange_error(
        self, test_app: TestClient, mock_client: Mock
    ):
        """Test /order_status/{order_id} endpoint with exchange error."""
        mock_client.get_order_status.side_effect = ExchangeError("Order not found")

        response = test_app.get("/order_status/999999")

        assert response.status_code == 400
        assert "Order not found" in response.json()["detail"]

    def test_order_status_endpoint_unexpected_error(
        self, test_app: TestClient, mock_client: Mock
    ):
        """Test /order_status/{order_id} endpoint with unexpected error."""
        mock_client.get_order_status.side_effect = Exception("Network error")

        response = test_app.get("/order_status/123456")

        assert response.status_code == 500
        assert response.json()["detail"] == "Internal server error"

    def test_order_status_endpoint_invalid_order_id(
        self, test_app: TestClient, mock_client: Mock
    ):
        """Test /order_status/{order_id} endpoint with invalid order_id."""
        response = test_app.get("/order_status/0")  # Invalid: less than 1

        assert response.status_code == 422  # FastAPI validation error
        assert "greater than or equal to 1" in response.json()["detail"][0]["msg"]

    def test_market_order_endpoint_success(
        self,
        test_app: TestClient,
        mock_client: Mock,
        sample_market_order: MarketOrder,
        sample_order_result: OrderResult,
    ):
        """Test successful /market_order endpoint."""
        mock_client.submit_market_order.return_value = sample_order_result

        response = test_app.post(
            "/market_order",
            json={
                "coin": "ETH",
                "side": "buy",
                "quantity": "0.1",
                "reduce_only": False,
            },
        )

        assert response.status_code == 200
        expected = {
            "success": True,
            "order_id": 123456789,
            "status": "open",
            "message": "Order submitted successfully",
            "error": None,
        }
        assert response.json() == expected
        mock_client.submit_market_order.assert_called_once()

        # Verify the order object passed to client
        call_args = mock_client.submit_market_order.call_args[0][0]
        assert call_args.coin == "ETH"
        assert call_args.side == OrderSide.BUY
        assert call_args.quantity == Decimal("0.1")
        assert call_args.reduce_only is False

    def test_market_order_endpoint_sell_success(
        self,
        test_app: TestClient,
        mock_client: Mock,
    ):
        """Test successful market sell order."""
        order_result = OrderResult(
            success=True,
            order_id=987654321,
            status=OrderStatus.OPEN,
            message="Market order submitted successfully",
        )
        mock_client.submit_market_order.return_value = order_result

        response = test_app.post(
            "/market_order",
            json={
                "coin": "BTC",
                "side": "sell",
                "quantity": "0.05",
                "reduce_only": True,
            },
        )

        assert response.status_code == 200
        assert response.json()["success"] is True
        assert response.json()["order_id"] == 987654321

        # Verify reduce_only flag is properly passed
        call_args = mock_client.submit_market_order.call_args[0][0]
        assert call_args.reduce_only is True

    def test_market_order_endpoint_exchange_error(
        self, test_app: TestClient, mock_client: Mock
    ):
        """Test /market_order endpoint with exchange error."""
        mock_client.submit_market_order.side_effect = ExchangeError(
            "Insufficient balance"
        )

        response = test_app.post(
            "/market_order",
            json={
                "coin": "ETH",
                "side": "buy",
                "quantity": "100.0",  # Large quantity to trigger balance error
                "reduce_only": False,
            },
        )

        assert response.status_code == 400
        assert "Insufficient balance" in response.json()["detail"]

    def test_market_order_endpoint_unexpected_error(
        self, test_app: TestClient, mock_client: Mock
    ):
        """Test /market_order endpoint with unexpected error."""
        mock_client.submit_market_order.side_effect = Exception("Network error")

        response = test_app.post(
            "/market_order",
            json={
                "coin": "ETH",
                "side": "buy",
                "quantity": "0.1",
                "reduce_only": False,
            },
        )

        assert response.status_code == 500
        assert response.json()["detail"] == "Internal server error"

    def test_market_order_endpoint_invalid_request_body(
        self, test_app: TestClient, mock_client: Mock
    ):
        """Test /market_order endpoint with invalid request body."""
        # Missing required field
        response = test_app.post(
            "/market_order",
            json={
                "coin": "ETH",
                "side": "buy",
                # Missing quantity and reduce_only
            },
        )

        assert response.status_code == 422  # FastAPI validation error
        assert "quantity" in str(response.json()["detail"])

    def test_market_order_endpoint_invalid_side(
        self, test_app: TestClient, mock_client: Mock
    ):
        """Test /market_order endpoint with invalid side."""
        response = test_app.post(
            "/market_order",
            json={
                "coin": "ETH",
                "side": "invalid",  # Invalid side
                "quantity": "0.1",
                "reduce_only": False,
            },
        )

        assert response.status_code == 422  # FastAPI validation error

    def test_limit_order_endpoint_success(
        self,
        test_app: TestClient,
        mock_client: Mock,
        sample_limit_order: LimitOrder,
        sample_order_result: OrderResult,
    ):
        """Test successful /limit_order endpoint."""
        mock_client.submit_limit_order.return_value = sample_order_result

        response = test_app.post(
            "/limit_order",
            json={
                "coin": "BTC",
                "side": "sell",
                "quantity": "0.05",
                "price": "50000.0",
                "reduce_only": False,
                "time_in_force": "GTC",
            },
        )

        assert response.status_code == 200
        expected = {
            "success": True,
            "order_id": 123456789,
            "status": "open",
            "message": "Order submitted successfully",
            "error": None,
        }
        assert response.json() == expected
        mock_client.submit_limit_order.assert_called_once()

        # Verify the order object passed to client
        call_args = mock_client.submit_limit_order.call_args[0][0]
        assert call_args.coin == "BTC"
        assert call_args.side == OrderSide.SELL
        assert call_args.quantity == Decimal("0.05")
        assert call_args.price == Decimal("50000.0")
        assert call_args.reduce_only is False
        assert call_args.time_in_force == OrderTif.GTC

    def test_limit_order_endpoint_different_tif(
        self, test_app: TestClient, mock_client: Mock
    ):
        """Test limit order with different time-in-force values."""
        order_result = OrderResult(
            success=True,
            order_id=555666777,
            status=OrderStatus.OPEN,
            message="IOC order submitted successfully",
        )
        mock_client.submit_limit_order.return_value = order_result

        # Test IOC order
        response = test_app.post(
            "/limit_order",
            json={
                "coin": "SOL",
                "side": "buy",
                "quantity": "10.0",
                "price": "150.0",
                "reduce_only": False,
                "time_in_force": "IOC",
            },
        )

        assert response.status_code == 200
        assert response.json()["order_id"] == 555666777

        # Verify TIF is properly passed
        call_args = mock_client.submit_limit_order.call_args[0][0]
        assert call_args.time_in_force == OrderTif.IOC

    def test_limit_order_endpoint_exchange_error(
        self, test_app: TestClient, mock_client: Mock
    ):
        """Test /limit_order endpoint with exchange error."""
        mock_client.submit_limit_order.side_effect = ExchangeError(
            "Insufficient margin"
        )

        response = test_app.post(
            "/limit_order",
            json={
                "coin": "BTC",
                "side": "buy",
                "quantity": "10.0",  # Large quantity with insufficient margin
                "price": "50000.0",
                "reduce_only": False,
                "time_in_force": "GTC",
            },
        )

        assert response.status_code == 400
        assert "Insufficient margin" in response.json()["detail"]

    def test_limit_order_endpoint_unexpected_error(
        self, test_app: TestClient, mock_client: Mock
    ):
        """Test /limit_order endpoint with unexpected error."""
        mock_client.submit_limit_order.side_effect = Exception("Connection timeout")

        response = test_app.post(
            "/limit_order",
            json={
                "coin": "ETH",
                "side": "buy",
                "quantity": "0.1",
                "price": "3000.0",
                "reduce_only": False,
                "time_in_force": "GTC",
            },
        )

        assert response.status_code == 500
        assert response.json()["detail"] == "Internal server error"

    def test_limit_order_endpoint_invalid_request_body(
        self, test_app: TestClient, mock_client: Mock
    ):
        """Test /limit_order endpoint with invalid request body."""
        # Missing required fields
        response = test_app.post(
            "/limit_order",
            json={
                "coin": "ETH",
                "side": "buy",
                # Missing quantity, price, reduce_only, time_in_force
            },
        )

        assert response.status_code == 422  # FastAPI validation error
        errors = response.json()["detail"]
        assert any("quantity" in str(error) for error in errors)
        assert any("price" in str(error) for error in errors)

    def test_limit_order_endpoint_invalid_price(
        self, test_app: TestClient, mock_client: Mock
    ):
        """Test /limit_order endpoint with invalid price (negative)."""
        response = test_app.post(
            "/limit_order",
            json={
                "coin": "ETH",
                "side": "buy",
                "quantity": "0.1",
                "price": "-1000.0",  # Negative price should be rejected by validation
                "reduce_only": False,
                "time_in_force": "GTC",
            },
        )

        # FastAPI should catch negative values via Pydantic validation
        assert response.status_code in [422, 400]

    def test_limit_order_endpoint_invalid_tif(
        self, test_app: TestClient, mock_client: Mock
    ):
        """Test /limit_order endpoint with invalid time-in-force."""
        response = test_app.post(
            "/limit_order",
            json={
                "coin": "ETH",
                "side": "buy",
                "quantity": "0.1",
                "price": "3000.0",
                "reduce_only": False,
                "time_in_force": "INVALID",  # Invalid TIF
            },
        )

        assert response.status_code == 422  # FastAPI validation error


class TestIntegration(TestBackendService):
    """Integration tests combining service and request handlers."""

    def test_full_api_workflow(self, test_app: TestClient, mock_client: Mock):
        """Test a complete API workflow with multiple endpoints."""
        # Setup mock responses
        mock_client.get_available_coins.return_value = ["BTC", "ETH", "SOL"]
        mock_client.get_ticker.return_value = Ticker(
            coin="BTC",
            mark_price=Decimal("43250.50"),
            funding_rate=Decimal("0.0001"),
            open_interest=Decimal("1250.75"),
        )
        mock_client.get_metadata.return_value = CoinMetadata(
            coin="BTC",
            size_decimals=8,
            max_leverage=50,
        )
        position = PositionInfo(
            coin="BTC",
            size=Decimal("0.1"),
            entry_price=Decimal("42000.00"),
            mark_price=Decimal("43250.50"),
            unrealized_pnl=Decimal("125.05"),
            leverage=10,
            leverage_type=LeverageType.ISOLATED,
            margin_used=Decimal("420.00"),
            cum_funding=Decimal("15.25"),
        )
        mock_client.get_positions.return_value = [position]

        # Setup balance mock
        balance = BalanceInfo(
            perps_account_value=Decimal("3451.743653"),
            perps_total_position_value=Decimal("10.8642"),
            perps_total_raw_usd=Decimal("3440.879453"),
            perps_margin_used=Decimal("5.318932"),
            perps_withdrawable=Decimal("3451.324721"),
            spot_balances=[
                SpotBalance(coin="USDC", total=Decimal("1000.50")),
                SpotBalance(coin="HYPE", total=Decimal("500.0")),
            ],
            staking_info=StakingInfo(
                delegated_amount=Decimal("100.61607572"),
                undelegated_amount=Decimal("25.12345678"),
                pending_withdrawals=Decimal("5.0"),
                pending_withdrawal_count=2,
            ),
        )
        mock_client.get_balances.return_value = balance

        # Test health
        response = test_app.get("/health")
        assert response.status_code == 200
        expected_health = HealthResponse(status=HealthStatus.HEALTHY)
        assert response.json() == expected_health.model_dump()

        # Test available coins
        response = test_app.get("/available_coins")
        assert response.status_code == 200
        assert "BTC" in response.json()

        # Test ticker
        response = test_app.get("/ticker/BTC")
        assert response.status_code == 200
        assert response.json()["coin"] == "BTC"

        # Test metadata
        response = test_app.get("/metadata/BTC")
        assert response.status_code == 200
        assert response.json()["max_leverage"] == 50

        # Test positions
        response = test_app.get("/positions")
        assert response.status_code == 200
        assert len(response.json()) == 1

        # Test specific position
        response = test_app.get("/positions/BTC")
        assert response.status_code == 200
        assert response.json()["coin"] == "BTC"

        # Test balances
        response = test_app.get("/balances")
        assert response.status_code == 200
        assert response.json()["perps_account_value"] == "3451.743653"
        assert len(response.json()["spot_balances"]) == 2

        # Verify all client methods were called
        assert mock_client.get_available_coins.called
        assert mock_client.get_ticker.called
        assert mock_client.get_metadata.called
        assert mock_client.get_balances.called
        assert (
            mock_client.get_positions.call_count == 2
        )  # Once for all positions, once for specific

    def test_error_propagation_through_api(
        self, test_app: TestClient, mock_client: Mock
    ):
        """Test that errors are properly propagated through the API layer."""
        mock_client.get_available_coins.side_effect = ExchangeError(
            "Exchange API error"
        )
        mock_client.get_ticker.side_effect = ExchangeError("Invalid coin")
        mock_client.get_metadata.side_effect = ExchangeError("Metadata not found")
        mock_client.get_positions.side_effect = ExchangeError("Authentication failed")
        mock_client.get_balances.side_effect = ExchangeError("Balance access denied")

        # Test all endpoints return 400 for exchange errors
        endpoints = [
            "/available_coins",
            "/ticker/BTC",
            "/metadata/BTC",
            "/positions",
            "/positions/BTC",
            "/balances",
        ]

        for endpoint in endpoints:
            response = test_app.get(endpoint)
            assert response.status_code == 400
            assert "detail" in response.json()

    def test_decimal_precision_preservation(
        self, test_app: TestClient, mock_client: Mock
    ):
        """Test that decimal precision is preserved in API responses."""
        # Use very precise decimal values
        ticker = Ticker(
            coin="BTC",
            mark_price=Decimal("43250.12345678"),
            funding_rate=Decimal("0.000123456789"),
            open_interest=Decimal("1250.987654321"),
        )
        mock_client.get_ticker.return_value = ticker

        response = test_app.get("/ticker/BTC")

        assert response.status_code == 200
        data = response.json()
        assert data["mark_price"] == "43250.12345678"
        assert data["funding_rate"] == "0.000123456789"
        assert data["open_interest"] == "1250.987654321"

    def test_concurrent_requests_handling(
        self, test_app: TestClient, mock_client: Mock
    ):
        """Test that the service handles concurrent requests properly."""
        import concurrent.futures

        # Setup slow mock response
        def slow_get_available_coins():
            import time

            time.sleep(0.1)
            return ["BTC", "ETH"]

        mock_client.get_available_coins.side_effect = slow_get_available_coins

        # Make concurrent requests
        def make_request():
            return test_app.get("/available_coins")

        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(make_request) for _ in range(10)]
            responses = [future.result() for future in futures]

        # All requests should succeed
        for response in responses:
            assert response.status_code == 200
            assert response.json() == ["BTC", "ETH"]

        # Verify the mock was called the correct number of times
        assert mock_client.get_available_coins.call_count == 10


class TestEdgeCases(TestBackendService):
    """Test edge cases and boundary conditions."""

    def test_empty_coin_symbol(self, test_app: TestClient, mock_client: Mock):
        """Test API with empty coin symbol."""
        mock_client.get_ticker.side_effect = ExchangeError("Invalid coin symbol")

        response = test_app.get("/ticker/")
        assert response.status_code == 404  # FastAPI path validation

    def test_very_long_coin_symbol(self, test_app: TestClient, mock_client: Mock):
        """Test API with very long coin symbol."""
        long_symbol = "A" * 1000
        mock_client.get_ticker.side_effect = ExchangeError("Invalid coin symbol")

        response = test_app.get(f"/ticker/{long_symbol}")
        assert response.status_code == 400

    def test_special_characters_in_coin_symbol(
        self, test_app: TestClient, mock_client: Mock
    ):
        """Test API with special characters in coin symbol."""
        special_symbol = "BTC-USD@2024"
        mock_client.get_ticker.side_effect = ExchangeError("Invalid coin symbol")

        response = test_app.get(f"/ticker/{special_symbol}")
        assert response.status_code == 400

    def test_unicode_in_coin_symbol(self, test_app: TestClient, mock_client: Mock):
        """Test API with unicode characters in coin symbol."""
        unicode_symbol = "₿TC"
        mock_client.get_ticker.side_effect = ExchangeError("Invalid coin symbol")

        response = test_app.get(f"/ticker/{unicode_symbol}")
        assert response.status_code == 400

    def test_case_sensitivity_in_coin_symbol(
        self, test_app: TestClient, mock_client: Mock
    ):
        """Test case sensitivity handling for coin symbols."""
        # Test lowercase
        mock_client.get_ticker.return_value = Ticker(
            coin="btc",
            mark_price=Decimal("43250.50"),
            funding_rate=Decimal("0.0001"),
            open_interest=Decimal("1250.75"),
        )

        response = test_app.get("/ticker/btc")
        assert response.status_code == 200
        assert response.json()["coin"] == "btc"

    def test_numeric_coin_symbol(self, test_app: TestClient, mock_client: Mock):
        """Test API with numeric coin symbol."""
        mock_client.get_ticker.return_value = Ticker(
            coin="123",
            mark_price=Decimal("1.00"),
            funding_rate=Decimal("0.0001"),
            open_interest=Decimal("1000.00"),
        )

        response = test_app.get("/ticker/123")
        assert response.status_code == 200
        assert response.json()["coin"] == "123"
