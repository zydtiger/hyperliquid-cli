# Hyperliquid Backend API Documentation

This document describes all available REST API endpoints provided by the Hyperliquid backend service.

## Base URL

The API is served from the configured host and port (default: `http://localhost:8080`)

## General Response Format

All endpoints return JSON responses with appropriate HTTP status codes. Error responses include a `detail` field with error information.

## Endpoints

### System Endpoints

#### GET /
Root endpoint with API information.

**Response:**
```json
{
  "api": "Hyperliquid API",
  "version": "1.1.0",
  "status": "running"
}
```

#### GET /health
Health check endpoint to verify service status and connection to the exchange.

**Response:**
```json
{
  "status": "healthy"
}
```

**Error Response (503):**
```json
{
  "detail": "Service unavailable: connection failed"
}
```

### Market Data Endpoints

#### GET /available_coins
Get list of all available trading coins from the exchange.

**Response:**
```json
[
  "BTC",
  "ETH",
  "SOL",
  "DOGE",
  ...
]
```

**Error Responses:**
- `400 Bad Request`: Exchange error (e.g., API rate limits, service unavailable)
- `500 Internal Server Error`: Unexpected server error

#### GET /ticker/{coin}
Get ticker information for a specific cryptocurrency.

**Path Parameters:**
- `coin` (string): Symbol of the cryptocurrency (e.g., "BTC", "ETH")

**Response:**
```json
{
  "coin": "BTC",
  "mark_price": "43250.50",
  "funding_rate": "0.0001",
  "open_interest": "1250.75"
}
```

**Error Responses:**
- `400 Bad Request`: Invalid coin symbol or exchange error
- `500 Internal Server Error`: Unexpected server error

#### GET /metadata/{coin}
Get metadata for a specific cryptocurrency, including trading specifications.

**Path Parameters:**
- `coin` (string): Symbol of the cryptocurrency

**Response:**
```json
{
  "coin": "BTC",
  "size_decimals": 8,
  "max_leverage": 50
}
```

**Error Responses:**
- `400 Bad Request`: Invalid coin symbol or exchange error
- `500 Internal Server Error`: Unexpected server error

### Order Endpoints

#### GET /order_status/{order_id}
Get status and details of a specific order by its ID.

**Path Parameters:**
- `order_id` (integer): Order identifier (OID) from the exchange

**Response:**
```json
{
  "order_id": 220717680685,
  "coin": "ETH",
  "side": "buy",
  "order_type": "limit",
  "quantity": "0.003",
  "price": "3842.3",
  "filled_quantity": "0.003",
  "remaining_quantity": "0.0",
  "average_fill_price": "3842.5",
  "status": "filled",
  "timestamp": 1762141573004,
  "reduce_only": false,
  "time_in_force": "GTC"
}
```

**Field Descriptions:**
- `order_id`: Unique order identifier from the exchange
- `coin`: Trading pair symbol
- `side`: Order side ("buy" or "sell")
- `order_type`: Order type ("limit" or "market")
- `quantity`: Original order quantity
- `price`: Limit price (null for market orders)
- `filled_quantity`: Quantity that has been filled
- `remaining_quantity`: Quantity remaining to be filled
- `average_fill_price`: Average price of filled orders (null if no fills)
- `status`: Order status ("open", "filled", "cancelled", "rejected", "partially_filled")
- `timestamp`: Order creation timestamp (Unix timestamp in milliseconds)
- `reduce_only`: Whether the order is reduce-only (true/false)
- `time_in_force`: Time in force policy ("GTC" = Good Till Cancelled, "IOC" = Immediate or Cancel, "ALO" = At Limit Order, null for market orders)

**Error Responses:**
- `400 Bad Request`: Invalid order ID or exchange error
- `404 Not Found`: Order not found
- `500 Internal Server Error`: Unexpected server error

**Usage Example:**
```bash
# Get order status
curl http://localhost:8080/order_status/220717680685

# Response for cancelled order
{
  "order_id": 217754135125,
  "coin": "ETH",
  "side": "buy",
  "order_type": "limit",
  "quantity": "0.003",
  "price": "3842.3",
  "filled_quantity": "0.0",
  "remaining_quantity": "0.003",
  "average_fill_price": null,
  "status": "cancelled",
  "timestamp": 1761876222838,
  "reduce_only": false,
  "time_in_force": "GTC"
}

# Response for partially filled IOC order
{
  "order_id": 217754135126,
  "coin": "BTC",
  "side": "sell",
  "order_type": "limit",
  "quantity": "0.2",
  "price": "50000.0",
  "filled_quantity": "0.1",
  "remaining_quantity": "0.1",
  "average_fill_price": "49500.0",
  "status": "cancelled",
  "timestamp": 1761876222839,
  "reduce_only": false,
  "time_in_force": "IOC"
}
```

### Portfolio Endpoints

#### GET /positions
Get all current open positions for the configured account.

**Response:**
```json
[
  {
    "coin": "BTC",
    "size": "0.1",
    "entry_price": "42000.00",
    "mark_price": "43250.50",
    "unrealized_pnl": "125.05",
    "leverage": 10,
    "leverage_type": "isolated",
    "margin_used": "420.00",
    "cum_funding": "15.25"
  },
  ...
]
```

**Error Responses:**
- `400 Bad Request`: Exchange error or authentication issues
- `500 Internal Server Error`: Unexpected server error

#### GET /positions/{coin}
Get position information for a specific cryptocurrency.

**Path Parameters:**
- `coin` (string): Symbol of the cryptocurrency

**Response:**
```json
{
  "coin": "BTC",
  "size": "0.1",
  "entry_price": "42000.00",
  "mark_price": "43250.50",
  "unrealized_pnl": "125.05",
  "leverage": 10,
  "leverage_type": "isolated",
  "margin_used": "420.00",
  "cum_funding": "15.25"
}
```

**Error Responses:**
- `400 Bad Request`: Exchange error or authentication issues
- `404 Not Found`: No position found for the specified coin
- `500 Internal Server Error`: Unexpected server error

## Error Handling

The API uses standard HTTP status codes and returns detailed error information in the response body. Common error patterns:

### Exchange Errors (400)
Exchange-related errors are returned as HTTP 400 Bad Request with the exchange error message in the `detail` field.

### Internal Server Errors (500)
Unexpected server errors are returned as HTTP 500 Internal Server Error with a generic "Internal server error" message. Detailed error information is logged on the server.

### Service Unavailable (503)
Service health check failures are returned as HTTP 503 Service Unavailable.

## Usage Example

```bash
# Start the backend service
hyperliquid-backend config.yaml

# Get available coins
curl http://localhost:8080/available_coins

# Get BTC ticker
curl http://localhost:8080/ticker/BTC

# Get order status
curl http://localhost:8080/order_status/220717680685

# Get all positions
curl http://localhost:8080/positions

# Get specific position
curl http://localhost:8080/positions/BTC

# Health check
curl http://localhost:8080/health
```

## Notes

- All monetary values are returned as strings to preserve decimal precision
- The API uses the account configured in the configuration file for portfolio-related endpoints
- Rate limiting and connection management are handled automatically by the underlying Hyperliquid client
- CORS is enabled for all origins (configure appropriately for production use)