"""
FastAPI backend service for the Hyperliquid CLI.

This module provides a REST API service that exposes Hyperliquid exchange
functionality through HTTP endpoints.
"""

import logging
from pathlib import Path
from typing import Optional

import typer
import uvicorn
from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware

from .exchange.hyperliquid_client import HyperliquidClient
from .request_handlers import setup_request_handlers
from models.api import HealthResponse, RootResponse, HealthStatus
from models.config import Config


# Configure logging
logger = logging.getLogger(__name__)

default_config_path = Path.home() / ".hyperliquid-cli" / "config.yaml"


def setup_logging(level: str) -> None:
    """Configure logging with the specified level."""
    logging.basicConfig(
        level=getattr(logging, level.upper()),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )


def create_app(config: Config) -> FastAPI:
    """
    Create and configure the FastAPI application.

    Args:
        config: Configuration object

    Returns:
        FastAPI: Configured FastAPI application instance
    """
    # Setup logging
    setup_logging(config.backend.logging.level)

    # Create FastAPI app
    app = FastAPI(
        title="Hyperliquid API",
        description="REST API for Hyperliquid exchange operations",
        version="1.0.0",
    )

    # Add CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # Configure appropriately for production
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Initialize Hyperliquid client
    try:
        client = HyperliquidClient(config)
        logger.info("Hyperliquid client initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize Hyperliquid client: {e}")
        raise

    # Add request handlers
    setup_request_handlers(app, client)

    # Add health check endpoint
    @app.get("/health")
    async def health_check() -> HealthResponse:
        """Health check endpoint."""
        try:
            is_healthy = client.test_connection()
            return HealthResponse(
                status=HealthStatus.HEALTHY if is_healthy else HealthStatus.UNHEALTHY
            )
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"Service unavailable: {str(e)}",
            )

    # Add root endpoint
    @app.get("/")
    async def root() -> RootResponse:
        """Root endpoint with API information."""
        try:
            is_healthy = client.test_connection()
            return RootResponse(
                api="Hyperliquid API",
                version="1.0.0",
                status=HealthStatus.HEALTHY if is_healthy else HealthStatus.UNHEALTHY,
            )
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"Service unavailable: {str(e)}",
            )

    return app


def entry_func(
    config: Path = typer.Option(
        default_config_path,
        "--config",
        "-c",
        help=f"Path to configuration file (default: {default_config_path})",
        exists=True,
        file_okay=True,
        dir_okay=False,
        readable=True,
    ),
    host: Optional[str] = typer.Option(
        None, "--host", help="Host to bind the server to (overrides config)"
    ),
    port: Optional[int] = typer.Option(
        None, "--port", help="Port to bind the server to (overrides config)"
    ),
    reload: bool = typer.Option(False, "--reload", help="Enable auto-reload for development"),
) -> None:
    """
    Start the Hyperliquid backend API service.

    This command launches a FastAPI server that provides REST API endpoints
    for interacting with the Hyperliquid exchange.
    """
    try:
        # Load configuration
        logger.info(f"Loading configuration from: {config}")
        app_config = Config.from_file(config)

        # Use CLI args to override config if provided
        server_host = host or app_config.backend.host
        server_port = port or app_config.backend.port

        # Create FastAPI app
        app = create_app(app_config)

        logger.info(f"Starting Hyperliquid API server on {server_host}:{server_port}")

        # Start the server
        uvicorn.run(
            app,
            host=server_host,
            port=server_port,
            reload=reload,
            log_level=app_config.backend.logging.level.lower(),
        )

    except Exception as e:
        logger.error(f"Failed to start server: {e}")
        raise typer.Exit(1)


def main() -> None:
    """Entry point for the hyperliquid-backend CLI command."""
    typer.run(entry_func)
