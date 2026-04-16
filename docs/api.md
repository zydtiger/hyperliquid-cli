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
Get ticker information for a specific market.

**Path Parameters:**
- `coin` (string): Symbol of the market (e.g., "BTC", "ETH", "UBTC/USDC")

**Response:**
```json
{
  "coin": "BTC",
  "mark_price": "43250.50",
  "funding_rate": "0.0001",
  "open_interest": "54109437.50"
}
```

**Field Descriptions:**
- `mark_price`: Current mark price for the market.
- `funding_rate`: Current funding rate. Spot markets return `0`.
- `open_interest`: Current open interest in USD notional for perps. Spot markets return `null`.

**Error Responses:**
- `400 Bad Request`: Invalid coin symbol or exchange error
- `500 Internal Server Error`: Unexpected server error

#### GET /watch/{coin}
Get the live watch snapshot for a supported perp or spot market.

**Path Parameters:**
- `coin` (string): Symbol of the market (e.g., "BTC", "ETH", "UBTC/USDC")

**Query Parameters:**
- `interval` (`1m` | `5m` | `15m` | `1h` | `4h` | `1d`, optional): Candle interval to return.
  Defaults to `5m`.
- `depth` (integer, optional): Per-side order book depth to return. Must be between `1` and `50`.
  Defaults to `10`.

**Response:**
```json
{
  "coin": "BTC",
  "interval": "5m",
  "mark_price": "43250.50",
  "open_interest": "54109437.50",
  "updated_at": 1741973030493,
  "candles": [
    {
      "open_time": 1741972800000,
      "close_time": 1741973100000,
      "open": "43210.25",
      "high": "43240.50",
      "low": "43205.10",
      "close": "43230.40",
      "is_closed": true
    },
    {
      "open_time": 1741973100000,
      "close_time": 1741973400000,
      "open": "43230.40",
      "high": "43260.00",
      "low": "43220.25",
      "close": "43250.50",
      "is_closed": false
    }
  ],
  "bids": [
    {
      "price": "43249.50",
      "size": "1.25"
    }
  ],
  "asks": [
    {
      "price": "43250.75",
      "size": "0.50"
    }
  ],
  "size_decimals": 5,
  "order_book_depth": 10,
  "default_interval": "5m",
  "supported_intervals": ["1m", "5m", "15m", "1h", "4h", "1d"]
}
```

**Field Descriptions:**
- `interval`: Candle interval returned by the snapshot.
- `mark_price`: Current live mark price for the market.
- `open_interest`: Current live open interest in USD notional for the market. Spot markets
  return `null`.
- `updated_at`: Timestamp of the last in-memory snapshot update in Unix milliseconds.
- `candles`: Ordered candles from oldest to newest. The backend returns the last 99 completed
  candles plus the current live candle for the requested `interval`.
- `bids`: Top bid levels ordered from highest to lowest price.
- `asks`: Top ask levels ordered from lowest to highest price.
- `size_decimals`: Market metadata precision used by the CLI for watch-price formatting.
- `order_book_depth`: Effective per-side order book depth returned in this snapshot.
- `default_interval`: Initial candle interval shown in the watch TUI.
- `supported_intervals`: Supported candle intervals for the live watch TUI.

**Error Responses:**
- `400 Bad Request`: Invalid market symbol or exchange error
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

#### GET /open_orders
Get all open orders for the configured account.

**Response:**
```json
[
  {
    "order_id": 222605232959,
    "coin": "ETH",
    "side": "buy",
    "order_type": "limit",
    "quantity": "0.003",
    "price": "3000.0",
    "filled_quantity": "0.0",
    "remaining_quantity": "0.003",
    "average_fill_price": null,
    "status": "open",
    "timestamp": 1762271506632,
    "reduce_only": false,
    "time_in_force": "GTC"
  },
  {
    "order_id": 222605232960,
    "coin": "BTC",
    "side": "sell",
    "order_type": "limit",
    "quantity": "0.1",
    "price": "50000.0",
    "filled_quantity": "0.05",
    "remaining_quantity": "0.05",
    "average_fill_price": "49800.0",
    "status": "open",
    "timestamp": 1762271506633,
    "reduce_only": false,
    "time_in_force": "GTC"
  },
  ...
]
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
- `400 Bad Request`: Exchange error or authentication issues
- `500 Internal Server Error`: Unexpected server error

**Usage Example:**
```bash
# Get all open orders
curl http://localhost:8080/open_orders

# Response when no open orders
[]
```

#### GET /order_history
Get recent filled-order history for the configured account.

**Query Parameters:**
- `limit` (integer, optional): Maximum number of filled history entries to return. Defaults to `10`. Minimum value is `1`.

**Response:**
```json
[
  {
    "time": 1762271507000,
    "coin": "ETH",
    "direction": "Open Long",
    "price": "2020.6",
    "size": "0.005",
    "notional": "10.1030",
    "fee": "0.004000",
    "fee_usdc": "0.004000",
    "fee_token": "USDC",
    "gross_closed_pnl": "0.300000",
    "closed_pnl": "0.296000",
    "order_id": 333001,
    "status": "filled"
  }
]
```

**Field Descriptions:**
- `time`: Fill completion timestamp in Unix milliseconds
- `coin`: Trading pair symbol
- `direction`: Exchange-reported fill direction
- `price`: Average fill price across all fills for the order
- `size`: Total filled size
- `notional`: Total filled notional
- `fee`: Total fee in the reported fee token
- `fee_usdc`: Fee converted to USDC when possible
- `fee_token`: Fee token symbol
- `gross_closed_pnl`: Closed PnL before fees
- `closed_pnl`: Closed PnL after fees
- `order_id`: Unique order identifier from the exchange
- `status`: Historical order status. This endpoint currently returns filled orders only.

**Error Responses:**
- `400 Bad Request`: Exchange error or authentication issue
- `422 Unprocessable Entity`: Invalid `limit` query parameter
- `500 Internal Server Error`: Unexpected server error

**Usage Example:**
```bash
# Get the 10 most recent filled orders
curl "http://localhost:8080/order_history"

# Get the 5 most recent filled orders
curl "http://localhost:8080/order_history?limit=5"
```

#### GET /pnl
Get all supported PnL history windows for the configured account.

**Response:**
```json
{
  "default_window": "7d",
  "histories": [
    {
      "window": "1d",
      "points": [
        {
          "time": 1741886630493,
          "total_pnl": "0.0",
          "perp_pnl": "0.0",
          "spot_pnl": "0.0"
        }
      ]
    },
    {
      "window": "7d",
      "points": [
        {
          "time": 1741973030493,
          "total_pnl": "10.5",
          "perp_pnl": "7.0",
          "spot_pnl": "3.5"
        }
      ]
    }
  ]
}
```

**Field Descriptions:**
- `default_window`: Initial window the frontend should show. This endpoint currently returns `7d`.
- `histories`: Ordered supported windows for the PnL TUI.
- `window`: Window identifier. Supported values are `1d`, `3d`, `7d`, `1m`, `3m`, `6m`, `1y`, `all`.
- `points`: Ordered PnL samples from oldest to newest for that window.
- `time`: Sample timestamp in Unix milliseconds.
- `total_pnl`: Total account PnL sample from the portfolio history.
- `perp_pnl`: Perpetuals-only PnL sample from the corresponding perpetual history bucket.
- `spot_pnl`: Derived spot PnL sample computed as `total_pnl - perp_pnl`.

**Error Responses:**
- `400 Bad Request`: Exchange error or authentication issue
- `500 Internal Server Error`: Unexpected server error

**Usage Example:**
```bash
# Get the ordered PnL windows for the fullscreen TUI
curl http://localhost:8080/pnl
```

#### POST /market_order
Submit a market order for immediate execution at the best available price.

**Request Body:**
```json
{
  "coin": "ETH",
  "side": "buy",
  "quantity": "0.1",
  "reduce_only": false,
  "trigger": {
    "trigger_price": "3500",
    "trigger_type": "take"
  }
}
```

**Field Descriptions:**
- `coin` (string): Trading pair symbol (e.g., "BTC", "ETH")
- `side` (string): Order side ("buy" or "sell")
- `quantity` (string): Order quantity as decimal string
- `reduce_only` (boolean): Whether the order is reduce-only (true/false)
- `trigger` (object|null): Optional trigger configuration for stop-loss or take-profit activation
- `trigger.trigger_price` (string): Trigger price as decimal string
- `trigger.trigger_type` (string): Trigger behavior (`"stop"` or `"take"`)

**Response:**
```json
{
  "success": true,
  "order_id": 123456789,
  "status": "open",
  "message": "Market order submitted successfully"
}
```

**Field Descriptions:**
- `success`: Whether the order was successfully submitted
- `order_id`: Order identifier from the exchange (null if submission failed)
- `status`: Order status ("open", "rejected", etc.)
- `message`: Success/error message
- `error`: Error details (null on success)

**Error Responses:**
- `400 Bad Request`: Invalid order data or exchange error
- `422 Unprocessable Entity`: Request validation failure
- `500 Internal Server Error`: Unexpected server error

**Usage Example:**
```bash
# Submit market buy order
curl -X POST http://localhost:8080/market_order \
  -H "Content-Type: application/json" \
  -d '{
    "coin": "ETH",
    "side": "buy",
    "quantity": "0.1",
    "reduce_only": false
  }'

# Response
{
  "success": true,
  "order_id": 123456789,
  "status": "open",
  "message": "Market order submitted successfully"
}

# Submit market sell order (reduce-only)
curl -X POST http://localhost:8080/market_order \
  -H "Content-Type: application/json" \
  -d '{
    "coin": "BTC",
    "side": "sell",
    "quantity": "0.05",
    "reduce_only": true
  }'

# Submit trigger market stop-loss order
curl -X POST http://localhost:8080/market_order \
  -H "Content-Type: application/json" \
  -d '{
    "coin": "ETH",
    "side": "sell",
    "quantity": "0.02",
    "reduce_only": true,
    "trigger": {
      "trigger_price": "1000",
      "trigger_type": "stop"
    }
  }'
```

#### POST /limit_order
Submit a limit order with specified price and time-in-force policy.

**Request Body:**
```json
{
  "coin": "BTC",
  "side": "sell",
  "quantity": "0.05",
  "price": "50000.0",
  "reduce_only": false,
  "time_in_force": "GTC",
  "trigger": {
    "trigger_price": "4500",
    "trigger_type": "take"
  }
}
```

**Field Descriptions:**
- `coin` (string): Trading pair symbol (e.g., "BTC", "ETH")
- `side` (string): Order side ("buy" or "sell")
- `quantity` (string): Order quantity as decimal string
- `price` (string): Limit price as decimal string
- `reduce_only` (boolean): Whether the order is reduce-only (true/false)
- `time_in_force` (string): Time in force policy ("GTC", "IOC", "ALO")
- `trigger` (object|null): Optional trigger configuration for stop-loss or take-profit activation
- `trigger.trigger_price` (string): Trigger price as decimal string
- `trigger.trigger_type` (string): Trigger behavior (`"stop"` or `"take"`)

**Time-in-Force Options:**
- `GTC`: Good Till Cancelled - active until filled or cancelled
- `IOC`: Immediate or Cancel - execute immediately or cancel remaining quantity
- `ALO`: At Limit Order - active until touched, then becomes limit order

When `trigger` is present, the submitted `price` is still used as the limit price after the trigger fires.
Hyperliquid trigger orders do not expose time-in-force, so `time_in_force` is currently ignored for triggered limit orders.

**Response:**
```json
{
  "success": true,
  "order_id": 987654321,
  "status": "open",
  "message": "Limit order submitted successfully"
}
```

**Error Responses:**
- `400 Bad Request`: Invalid order data or exchange error
- `422 Unprocessable Entity`: Request validation failure
- `500 Internal Server Error`: Unexpected server error

**Usage Example:**
```bash
# Submit limit buy order
curl -X POST http://localhost:8080/limit_order \
  -H "Content-Type: application/json" \
  -d '{
    "coin": "ETH",
    "side": "buy",
    "quantity": "0.1",
    "price": "3000.0",
    "reduce_only": false,
    "time_in_force": "GTC"
  }'

# Response
{
  "success": true,
  "order_id": 987654321,
  "status": "open",
  "message": "Limit order submitted successfully"
}

# Submit IOC limit sell order
curl -X POST http://localhost:8080/limit_order \
  -H "Content-Type: application/json" \
  -d '{
    "coin": "SOL",
    "side": "sell",
    "quantity": "10.0",
    "price": "150.0",
    "reduce_only": false,
    "time_in_force": "IOC"
  }'

# Submit trigger limit take-profit order
curl -X POST http://localhost:8080/limit_order \
  -H "Content-Type: application/json" \
  -d '{
    "coin": "ETH",
    "side": "sell",
    "quantity": "0.02",
    "price": "4000.0",
    "reduce_only": true,
    "time_in_force": "GTC",
    "trigger": {
      "trigger_price": "4500",
      "trigger_type": "take"
    }
  }'
```

#### POST /cancel_order
Cancel a specific order or all open orders.

**Request Body:**
```json
{
  "order_id": 123456
}
```

or

```json
{
  "order_id": "all"
}
```

**Field Descriptions:**
- `order_id` (int|string): Order ID to cancel (integer), or "all" to cancel all open orders

**Response (Successful Cancellation):**
```json
{
  "success": true,
  "order_id": 123456,
  "status": "cancelled",
  "message": "Order 123456 cancelled successfully"
}
```

**Response (Batch Cancellation):**
```json
{
  "success": true,
  "status": "cancelled",
  "message": "Cancelled 3 orders, 0 failed"
}
```

**Response (Already Cancelled Order):**
```json
{
  "success": false,
  "order_id": 123456,
  "status": "cancelled",
  "message": "Order 123456 cancellation failed",
  "error": "Order 123456 is already cancelled"
}
```

**Field Descriptions:**
- `success`: Whether the cancellation was successful
- `order_id`: Order identifier (null for batch cancellation)
- `status`: Order status after cancellation attempt
- `message`: Success/error message with details
- `error`: Error details (null on success)

**Error Responses:**
- `400 Bad Request`: Invalid order ID, order not found, or exchange error
- `500 Internal Server Error`: Unexpected server error

**Usage Examples:**
```bash
# Cancel specific order
curl -X POST http://localhost:8080/cancel_order \
  -H "Content-Type: application/json" \
  -d '{"order_id": 123456}'

# Response
{
  "success": true,
  "order_id": 123456,
  "status": "cancelled",
  "message": "Order 123456 cancelled successfully"
}

# Cancel all open orders
curl -X POST http://localhost:8080/cancel_order \
  -H "Content-Type: application/json" \
  -d '{"order_id": "all"}'

# Response for batch cancellation
{
  "success": true,
  "status": "cancelled",
  "message": "Cancelled 3 orders, 0 failed"
}

# Response for order already cancelled
{
  "success": false,
  "order_id": 123456,
  "status": "cancelled",
  "message": "Order 123456 cancellation failed",
  "error": "Order 123456 is already cancelled"
}
```

#### POST /modify_order
Modify price and/or quantity of an existing open limit order.

**Request Body:**
```json
{
  "order_id": 123456,
  "price": "3100.0",
  "quantity": "0.05"
}
```

or to keep current price:

```json
{
  "order_id": 123456,
  "price": null,
  "quantity": "0.05"
}
```

or to keep current quantity:

```json
{
  "order_id": 123456,
  "price": "3100.0",
  "quantity": null
}
```

**Field Descriptions:**
- `order_id` (int): Order ID to modify (must be an open limit order)
- `price` (decimal|null): New price (null to keep current price)
- `quantity` (decimal|null): New quantity (null to keep current quantity)

**Response (Successful Modification):**
```json
{
  "success": true,
  "order_id": 123456,
  "status": "open",
  "message": "Order 123456 modified successfully - price: 3100, quantity: 0.05"
}
```

**Response (Order Not Found):**
```json
{
  "success": false,
  "order_id": 123456,
  "status": "rejected",
  "message": "Order modification failed",
  "error": "Order 123456 not found"
}
```

**Response (Invalid Order Status):**
```json
{
  "success": false,
  "order_id": 123456,
  "status": "rejected",
  "message": "Order modification failed",
  "error": "Order 123456 is already filled and cannot be modified"
}
```

**Field Descriptions:**
- `success`: Whether the modification was successful
- `order_id`: Order identifier that was attempted to be modified
- `status`: Order status after modification attempt
- `message`: Success/error message with details
- `error`: Error details (null on success)

**Error Responses:**
- `400 Bad Request`: Invalid order ID, order not open limit order, or exchange error
- `422 Unprocessable Entity`: Request validation failure
- `500 Internal Server Error`: Unexpected server error

**Usage Examples:**
```bash
# Modify both price and quantity
curl -X POST http://localhost:8080/modify_order \
  -H "Content-Type: application/json" \
  -d '{
    "order_id": 123456,
    "price": "3100.0",
    "quantity": "0.05"
  }'

# Response
{
  "success": true,
  "order_id": 123456,
  "status": "open",
  "message": "Order 123456 modified successfully - price: 3100, quantity: 0.05"
}

# Modify only price (keep current quantity)
curl -X POST http://localhost:8080/modify_order \
  -H "Content-Type: application/json" \
  -d '{
    "order_id": 123456,
    "price": "3200.0",
    "quantity": null
  }'

# Modify only quantity (keep current price)
curl -X POST http://localhost:8080/modify_order \
  -H "Content-Type: application/json" \
  -d '{
    "order_id": 123456,
    "price": null,
    "quantity": "0.1"
  }'

# Response for non-existent order
{
  "success": false,
  "order_id": 999999,
  "status": "rejected",
  "message": "Order modification failed",
  "error": "Order 999999 not found"
}

# Response for filled order
{
  "success": false,
  "order_id": 123457,
  "status": "rejected",
  "message": "Order modification failed",
  "error": "Order 123457 is already filled and cannot be modified"
}
```

#### POST /change_leverage
Update leverage for a specific position.

**Request Body:**
```json
{
  "leverage": 21,
  "coin": "ETH",
  "is_cross": true
}
```

**Parameters:**
- `leverage` (int, required): Target leverage multiplier (1-250)
- `coin` (string, required): Symbol of the cryptocurrency
- `is_cross` (boolean, required): Whether to use cross margin (true) or isolated margin (false)

**Response:**
```json
{
  "success": true,
  "message": "Successfully updated ETH leverage to 21x (cross margin)",
  "updated_position": {
    "coin": "ETH",
    "size": "0.1",
    "entry_price": "3000.0",
    "mark_price": "3100.0",
    "unrealized_pnl": "10.0",
    "leverage": 21,
    "leverage_type": "cross",
    "margin_used": "14.29",
    "cum_funding": "0.5"
  }
}
```

**Usage Example:**
```bash
# Change ETH leverage to 21x cross margin
curl -X POST http://localhost:8080/change_leverage \
  -H "Content-Type: application/json" \
  -d '{
    "leverage": 21,
    "coin": "ETH",
    "is_cross": true
  }'

# Change BTC leverage to 15x isolated margin
curl -X POST http://localhost:8080/change_leverage \
  -H "Content-Type: application/json" \
  -d '{
    "leverage": 15,
    "coin": "BTC",
    "is_cross": false
  }'

# Response for successful update
{
  "success": true,
  "message": "Successfully updated ETH leverage to 21x (cross margin)",
  "updated_position": {
    "coin": "ETH",
    "size": "0.1",
    "entry_price": "3000.0",
    "mark_price": "3100.0",
    "unrealized_pnl": "10.0",
    "leverage": 21,
    "leverage_type": "cross",
    "margin_used": "14.29",
    "cum_funding": "0.5"
  }
}

# Response for non-existent position
{
  "success": false,
  "message": "No open position found for ETH",
  "updated_position": null
}

# Response for invalid leverage
{
  "success": false,
  "message": "Failed to update leverage: Invalid leverage value",
  "updated_position": null
}
```

#### POST /update_isolated_margin
Update isolated margin for a specific position.

The underlying Hyperliquid exchange call acknowledges success with:
```json
{
  "status": "ok",
  "response": {
    "type": "default"
  }
}
```

The backend treats that exchange acknowledgement as success, then refreshes the position and returns the normalized API response below.

**Request Body:**
```json
{
  "coin": "ETH",
  "amount": "1.0"
}
```

**Parameters:**
- `coin` (string, required): Symbol of the cryptocurrency
- `amount` (decimal, required): Signed USD isolated margin delta; positive adds margin and negative removes

**Response:**
```json
{
  "success": true,
  "message": "Successfully added $1.00 isolated margin to ETH",
  "updated_position": {
    "coin": "ETH",
    "size": "0.1",
    "entry_price": "3000.0",
    "mark_price": "3100.0",
    "unrealized_pnl": "10.0",
    "leverage": 15,
    "leverage_type": "isolated",
    "margin_used": "101.0",
    "removable_margin": "13.34",
    "cum_funding": "0.5"
  }
}
```

`updated_position` may be `null` if the exchange update succeeds but the post-update position refresh fails.

**Usage Example:**
```bash
# Add $1.00 isolated margin to ETH
curl -X POST http://localhost:8080/update_isolated_margin \
  -H "Content-Type: application/json" \
  -d '{
    "coin": "ETH",
    "amount": "1.0"
  }'

# Remove $0.50 isolated margin from ETH
curl -X POST http://localhost:8080/update_isolated_margin \
  -H "Content-Type: application/json" \
  -d '{
    "coin": "ETH",
    "amount": "-0.5"
  }'

# Response for successful add
{
  "success": true,
  "message": "Successfully added $1.00 isolated margin to ETH",
  "updated_position": {
    "coin": "ETH",
    "size": "0.1",
    "entry_price": "3000.0",
    "mark_price": "3100.0",
    "unrealized_pnl": "10.0",
    "leverage": 15,
    "leverage_type": "isolated",
    "margin_used": "101.0",
    "removable_margin": "13.34",
    "cum_funding": "0.5"
  }
}

# Response for successful removal
{
  "success": true,
  "message": "Successfully removed $0.50 isolated margin from ETH",
  "updated_position": {
    "coin": "ETH",
    "size": "0.1",
    "entry_price": "3000.0",
    "mark_price": "3100.0",
    "unrealized_pnl": "10.0",
    "leverage": 15,
    "leverage_type": "isolated",
    "margin_used": "100.5",
    "removable_margin": "12.84",
    "cum_funding": "0.5"
  }
}

# Response for invalid amount precision
{
  "detail": [
    {
      "type": "value_error",
      "loc": ["body", "amount"],
      "msg": "Value error, Amount must have at most 6 decimal places",
      "input": "0.1234567"
    }
  ]
}
```

### Portfolio Endpoints

#### GET /positions
Get all current open positions for the configured account.

`removable_margin` is an estimated isolated-margin removal hint. It is `null` for cross-margin positions.

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
    "removable_margin": "25.00",
    "cum_funding": "15.25"
  },
  ...
]
```

**Error Responses:**
- `400 Bad Request`: Exchange error or authentication issues
- `500 Internal Server Error`: Unexpected server error

#### GET /balances
Get comprehensive balance information for the configured account, including perpetuals, spot balances, and staking information.

**Response:**
```json
{
  "perps_account_value": "3451.743653",
  "perps_total_position_value": "10.8642",
  "perps_total_raw_usd": "3440.879453",
  "perps_margin_used": "5.318932",
  "perps_withdrawable": "3451.324721",
  "spot_balances": [
    {
      "coin": "USDC",
      "total": "1000.50"
    },
    {
      "coin": "HYPE",
      "total": "500.0"
    },
    {
      "coin": "UETH",
      "total": "0.002998111"
    }
  ],
  "staking_info": {
    "delegated_amount": "100.61607572",
    "undelegated_amount": "25.12345678",
    "pending_withdrawals": "5.0",
    "pending_withdrawal_count": 2
  }
}
```

**Field Descriptions:**
- `perps_account_value`: Total perpetuals account value
- `perps_total_position_value`: Total notional position size in perpetuals
- `perps_total_raw_usd`: Remaining raw USD in perpetuals account
- `perps_margin_used`: Total margin used by perpetual positions
- `perps_withdrawable`: Available withdrawal amount from perpetuals account
- `spot_balances`: Array of spot coin balances (empty if no spot holdings)
- `staking_info`: Staking delegations and rewards (null if no staking activity)

**Error Responses:**
- `400 Bad Request`: Exchange error or authentication issues
- `500 Internal Server Error`: Unexpected server error

**Usage Example:**
```bash
# Get comprehensive balance information
curl http://localhost:8080/balances
```

#### GET /staking
Get staking status for the configured account.

**Response:**
```json
{
  "total_staked": "100.61607572",
  "total_reward": "2.00000000",
  "delegations": [
    {
      "validator": "validator-1",
      "name": "CMI",
      "commission": "0.05",
      "amount": "70.50000000"
    },
    {
      "validator": "validator-2",
      "name": "HyperStake",
      "commission": "0.10",
      "amount": "30.11607572"
    }
  ]
}
```

**Field Descriptions:**
- `total_staked`: Total delegated HYPE for the configured account
- `total_reward`: Total rewarded HYPE across staking reward history
- `delegations`: Active validator delegations with positive HYPE amounts only
- `delegations[].validator`: Validator identifier returned by the exchange SDK
- `delegations[].name`: Validator display name from validator summaries
- `delegations[].commission`: Validator commission rate as a decimal fraction
- `delegations[].amount`: Staked HYPE amount delegated to that validator

**Error Responses:**
- `400 Bad Request`: Exchange error or authentication issues
- `500 Internal Server Error`: Unexpected server error

**Usage Example:**
```bash
# Get staking status
curl http://localhost:8080/staking
```

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

# Get all open orders
curl http://localhost:8080/open_orders

# Submit market order
curl -X POST http://localhost:8080/market_order \
  -H "Content-Type: application/json" \
  -d '{
    "coin": "ETH",
    "side": "buy",
    "quantity": "0.1",
    "reduce_only": false
  }'

# Submit limit order
curl -X POST http://localhost:8080/limit_order \
  -H "Content-Type: application/json" \
  -d '{
    "coin": "BTC",
    "side": "sell",
    "quantity": "0.05",
    "price": "50000.0",
    "reduce_only": false,
    "time_in_force": "GTC"
  }'

# Cancel specific order
curl -X POST http://localhost:8080/cancel_order \
  -H "Content-Type: application/json" \
  -d '{"order_id": 123456}'

# Cancel all open orders
curl -X POST http://localhost:8080/cancel_order \
  -H "Content-Type: application/json" \
  -d '{"order_id": "all"}'

# Modify order (both price and quantity)
curl -X POST http://localhost:8080/modify_order \
  -H "Content-Type: application/json" \
  -d '{
    "order_id": 123456,
    "price": "3100.0",
    "quantity": "0.05"
  }'

# Modify order (only price)
curl -X POST http://localhost:8080/modify_order \
  -H "Content-Type: application/json" \
  -d '{
    "order_id": 123456,
    "price": "3200.0",
    "quantity": null
  }'

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
