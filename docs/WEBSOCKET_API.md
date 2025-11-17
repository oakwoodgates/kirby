# Kirby WebSocket API Documentation

> Real-time cryptocurrency market data streaming via WebSocket

---

## Overview

The Kirby WebSocket API provides real-time streaming of comprehensive market data for cryptocurrency trading pairs. Clients can subscribe to specific starlistings and receive updates for candles (OHLCV), funding rates, and open interest as new data is generated.

**Features:**
- ✅ **Real-time updates** via PostgreSQL LISTEN/NOTIFY (~50-100ms latency)
- ✅ **Three data types**: Candles (OHLCV), Funding Rates, and Open Interest
- ✅ **Subscribe to multiple starlistings** simultaneously
- ✅ **Historical data** on connection (optional, up to 1000 candles)
- ✅ **Heartbeat/ping** mechanism for connection health
- ✅ **Automatic reconnection** support
- ✅ **Validated messages** with detailed error responses

---

## Connection

### Endpoint

```
ws://localhost:8000/ws
```

### Connection Limits

- **Max concurrent connections**: 100 (configurable via `WEBSOCKET_MAX_CONNECTIONS` env var)
- **Heartbeat interval**: 30 seconds (configurable via `WEBSOCKET_HEARTBEAT_INTERVAL`)
- **Message size limit**: 1MB (configurable via `WEBSOCKET_MESSAGE_SIZE_LIMIT`)

### Connection Example

**Python:**
```python
import asyncio
import websockets

async def connect():
    async with websockets.connect("ws://localhost:8000/ws") as ws:
        print("Connected!")
        # Your code here

asyncio.run(connect())
```

**JavaScript:**
```javascript
const ws = new WebSocket("ws://localhost:8000/ws");

ws.onopen = () => {
    console.log("Connected!");
};

ws.onmessage = (event) => {
    const data = JSON.parse(event.data);
    console.log("Received:", data);
};
```

---

## Message Protocol

All messages are JSON-formatted strings. Client sends action messages, server responds with typed messages.

### Client Messages

#### 1. Subscribe

Subscribe to one or more starlistings to receive real-time updates for **all three data types** (candles, funding rates, and open interest).

```json
{
    "action": "subscribe",
    "starlisting_ids": [1, 2, 3],
    "history": 100
}
```

**Fields:**
- `action` (string, required): Must be `"subscribe"`
- `starlisting_ids` (array, required): List of starlisting IDs (1-100 IDs)
- `history` (integer, optional): Number of historical candles to send (0-1000, default: 0)

**What you receive after subscribing:**
- ✅ **Candle updates** (`type: "candle"`) - Real-time OHLCV data at the starlisting's interval
- ✅ **Funding rate updates** (`type: "funding"`) - Real-time funding rates (1-minute intervals)
- ✅ **Open interest updates** (`type: "open_interest"`) - Real-time OI data (1-minute intervals)

**Note:** There is **no separate subscription** for funding or OI data. When you subscribe to a starlisting, you automatically receive all three data types. If you only want specific types, filter the messages on the client side by checking `data["type"]`.

**Response:**
```json
{
    "type": "success",
    "message": "Subscribed to 3 starlisting(s)",
    "starlisting_ids": [1, 2, 3]
}
```

Then, if `history > 0`:
```json
{
    "type": "historical",
    "starlisting_id": 1,
    "exchange": "hyperliquid",
    "coin": "BTC",
    "quote": "USD",
    "trading_pair": "BTC/USD",
    "market_type": "perps",
    "interval": "1m",
    "count": 100,
    "data": [
        {
            "time": "2025-11-17T22:00:00+00:00",
            "open": "92100.000000000000000000",
            "high": "92150.000000000000000000",
            "low": "92050.000000000000000000",
            "close": "92125.000000000000000000",
            "volume": "125.458920000000000000",
            "num_trades": 1542
        },
        ...
    ]
}
```

#### 2. Unsubscribe

Unsubscribe from one or more starlistings.

```json
{
    "action": "unsubscribe",
    "starlisting_ids": [1]
}
```

**Fields:**
- `action` (string, required): Must be `"unsubscribe"`
- `starlisting_ids` (array, required): List of starlisting IDs to unsubscribe from

**Response:**
```json
{
    "type": "success",
    "message": "Unsubscribed from 1 starlisting(s)",
    "starlisting_ids": [1]
}
```

#### 3. Ping

Send a ping to check connection health.

```json
{
    "action": "ping"
}
```

**Response:**
```json
{
    "type": "pong",
    "timestamp": "2025-11-17T10:00:00Z"
}
```

---

### Server Messages

#### 1. Success

Confirmation of successful action.

```json
{
    "type": "success",
    "message": "Subscribed to 3 starlisting(s)",
    "starlisting_ids": [1, 2, 3]
}
```

#### 2. Error

Error response with details.

```json
{
    "type": "error",
    "message": "Invalid starlisting_id: 999",
    "code": "invalid_starlisting"
}
```

**Error codes:**
- `unknown_action`: Unknown action type
- `invalid_json`: Malformed JSON
- `validation_error`: Message validation failed
- `invalid_starlisting`: Invalid or inactive starlisting ID
- `internal_error`: Internal server error

#### 3. Ping (Heartbeat)

Server sends periodic pings to keep connection alive.

```json
{
    "type": "ping",
    "timestamp": "2025-11-17T10:00:00Z"
}
```

Client should respond with pong (or just ignore).

#### 4. Pong

Response to client ping.

```json
{
    "type": "pong",
    "timestamp": "2025-11-17T10:00:00Z"
}
```

#### 5. Historical Data

Historical candles sent after subscription (if `history > 0`).

```json
{
    "type": "historical",
    "starlisting_id": 1,
    "exchange": "hyperliquid",
    "coin": "BTC",
    "quote": "USD",
    "trading_pair": "BTC/USD",
    "market_type": "perps",
    "interval": "1m",
    "count": 100,
    "data": [...]
}
```

#### 6. Candle Update

Real-time candle update (sent when new candle is created/updated).

```json
{
    "type": "candle",
    "starlisting_id": 1,
    "exchange": "hyperliquid",
    "coin": "BTC",
    "quote": "USD",
    "trading_pair": "BTC/USD",
    "market_type": "perps",
    "interval": "1m",
    "data": {
        "time": "2025-11-17T22:29:00+00:00",
        "open": "92225.000000000000000000",
        "high": "92225.000000000000000000",
        "low": "92204.000000000000000000",
        "close": "92215.000000000000000000",
        "volume": "11.597470000000000000",
        "num_trades": 172
    }
}
```

**Note:** All price and volume fields are returned with **18-decimal precision** to support coins of any price range (from $0.000000000000000001 to $999,999,999,999). The trailing zeros are preserved in the string format.

#### 7. Funding Rate Update

Real-time funding rate update (sent when new funding rate is recorded).

```json
{
    "type": "funding",
    "starlisting_id": 1,
    "exchange": "hyperliquid",
    "coin": "BTC",
    "quote": "USD",
    "trading_pair": "BTC/USD",
    "market_type": "perps",
    "data": {
        "time": "2025-11-17T10:00:00Z",
        "funding_rate": "0.000123456789012345",
        "premium": "0.000050000000000000",
        "mark_price": "67650.750000000000000000",
        "index_price": "67645.500000000000000000",
        "oracle_price": "67648.000000000000000000",
        "mid_price": "67649.250000000000000000",
        "next_funding_time": "2025-11-17T18:00:00Z"
    }
}
```

**Fields:**
- `funding_rate` (string): Current funding rate (positive = longs pay shorts, negative = shorts pay longs)
- `premium` (string): Premium component of funding rate
- `mark_price` (string, nullable): Mark price used for funding calculation
- `index_price` (string, nullable): Index price (spot reference price)
- `oracle_price` (string, nullable): Oracle price
- `mid_price` (string, nullable): Mid price (best bid + best ask) / 2
- `next_funding_time` (string, nullable): ISO timestamp of next funding payment

**Notes:**
- Funding rates are stored at **1-minute intervals** (buffered from real-time updates)
- All price/rate fields use 18-decimal precision for accuracy
- Historical funding data may only include `funding_rate` and `premium` (prices are null)
- Real-time data includes all fields when available from the exchange

#### 8. Open Interest Update

Real-time open interest update (sent when new OI data is recorded).

```json
{
    "type": "open_interest",
    "starlisting_id": 1,
    "exchange": "hyperliquid",
    "coin": "BTC",
    "quote": "USD",
    "trading_pair": "BTC/USD",
    "market_type": "perps",
    "data": {
        "time": "2025-11-17T10:00:00Z",
        "open_interest": "125000.500000000000000000",
        "notional_value": "8456789000.000000000000000000",
        "day_base_volume": "50000.250000000000000000",
        "day_notional_volume": "3378912500.000000000000000000"
    }
}
```

**Fields:**
- `open_interest` (string): Total open interest in base asset (e.g., BTC)
- `notional_value` (string, nullable): Open interest in quote currency (e.g., USD)
- `day_base_volume` (string, nullable): 24-hour volume in base asset
- `day_notional_volume` (string, nullable): 24-hour volume in quote currency

**Notes:**
- Open interest is stored at **1-minute intervals** (buffered from real-time updates)
- All volume fields use 18-decimal precision
- Only available for perpetual/futures markets (not spot)
- Historical OI data is **not available** - only real-time collection

---

## Complete Examples

### Python Client

See: [scripts/test_websocket_client.py](../scripts/test_websocket_client.py)

```python
import asyncio
import json
import websockets

async def stream_market_data():
    uri = "ws://localhost:8000/ws"

    async with websockets.connect(uri) as websocket:
        # Subscribe to BTC/USD perpetuals with 10 historical candles
        subscribe_msg = {
            "action": "subscribe",
            "starlisting_ids": [1],
            "history": 10
        }

        await websocket.send(json.dumps(subscribe_msg))

        # Receive messages
        while True:
            message = await websocket.recv()
            data = json.loads(message)

            if data["type"] == "candle":
                candle = data["data"]
                print(f"Candle: {candle['time']} | Close: {candle['close']}")

            elif data["type"] == "funding":
                funding = data["data"]
                print(f"Funding: {funding['time']} | Rate: {funding['funding_rate']}")

            elif data["type"] == "open_interest":
                oi = data["data"]
                print(f"OI: {oi['time']} | Open Interest: {oi['open_interest']}")

            elif data["type"] == "historical":
                print(f"Received {data['count']} historical candles")

            elif data["type"] == "ping":
                # Server heartbeat - connection is alive
                pass

asyncio.run(stream_market_data())
```

### JavaScript Client

See: [docs/examples/websocket_client.html](../examples/websocket_client.html)

```javascript
const ws = new WebSocket("ws://localhost:8000/ws");

ws.onopen = () => {
    console.log("Connected!");

    // Subscribe to multiple starlistings
    const subscribeMsg = {
        action: "subscribe",
        starlisting_ids: [1, 2, 3],
        history: 10
    };

    ws.send(JSON.stringify(subscribeMsg));
};

ws.onmessage = (event) => {
    const data = JSON.parse(event.data);

    if (data.type === "candle") {
        console.log("Candle:", data.data);
    } else if (data.type === "funding") {
        console.log("Funding Rate:", data.data);
    } else if (data.type === "open_interest") {
        console.log("Open Interest:", data.data);
    } else if (data.type === "historical") {
        console.log(`Received ${data.count} historical candles`);
    } else if (data.type === "ping") {
        // Server heartbeat - connection is alive
    }
};

ws.onerror = (error) => {
    console.error("WebSocket error:", error);
};

ws.onclose = () => {
    console.log("Connection closed");
    // Implement reconnection logic here
};
```

---

## Best Practices

### 1. Reconnection Logic

Always implement automatic reconnection with exponential backoff:

```python
import asyncio
import websockets

async def connect_with_retry():
    retry_delay = 1
    max_delay = 60

    while True:
        try:
            async with websockets.connect("ws://localhost:8000/ws") as ws:
                retry_delay = 1  # Reset on successful connection
                await handle_messages(ws)

        except Exception as e:
            print(f"Connection failed: {e}")
            print(f"Retrying in {retry_delay} seconds...")
            await asyncio.sleep(retry_delay)
            retry_delay = min(retry_delay * 2, max_delay)
```

### 2. Message Handling

Always validate message types before processing:

```python
data = json.loads(message)
msg_type = data.get("type")

if msg_type == "candle":
    handle_candle(data)
elif msg_type == "error":
    handle_error(data)
elif msg_type == "ping":
    # Heartbeat - connection is alive
    pass
```

### 3. Error Handling

Handle errors gracefully and log details:

```python
if data["type"] == "error":
    error_code = data.get("code")
    error_msg = data.get("message")

    if error_code == "invalid_starlisting":
        # Handle invalid starlisting
        print(f"Invalid starlisting: {error_msg}")
    elif error_code == "validation_error":
        # Handle validation error
        print(f"Validation failed: {error_msg}")
```

### 4. Subscription Management

Track your subscriptions locally to avoid duplicate subscriptions:

```python
class WebSocketClient:
    def __init__(self):
        self.subscribed_ids = set()

    async def subscribe(self, starlisting_ids):
        # Filter out already subscribed IDs
        new_ids = [sid for sid in starlisting_ids if sid not in self.subscribed_ids]

        if not new_ids:
            return

        # Subscribe to new IDs
        await self.ws.send(json.dumps({
            "action": "subscribe",
            "starlisting_ids": new_ids,
            "history": 0
        }))

        self.subscribed_ids.update(new_ids)
```

### 5. Historical Data

Request historical data only on initial connection, not on reconnections:

```python
is_initial_connection = True

async def connect():
    global is_initial_connection

    history = 100 if is_initial_connection else 0
    is_initial_connection = False

    await subscribe(starlisting_ids, history=history)
```

---

## Performance Considerations

### Latency

- **Real-time updates**: ~50-100ms from database insert to WebSocket broadcast
- **Historical data**: Query time depends on amount of data requested
- **Network latency**: Add your network RTT

### Throughput

- **Max connections**: 100 concurrent WebSocket connections (configurable)
- **Max subscriptions per client**: Up to 100 starlistings
- **Message rate per starlisting**:
  - **Candles**: Depends on interval (e.g., 1m = 1 update/minute, 15m = 1 update/15 minutes)
  - **Funding rates**: 1 update/minute (buffered from real-time)
  - **Open interest**: 1 update/minute (buffered from real-time)
- **Total message rate**: (candle updates) + (funding updates) + (OI updates) per subscribed starlisting

### Scaling

Current implementation:
- **Single-server deployment** with PostgreSQL LISTEN/NOTIFY
- **No Redis required** for MVP
- **Vertical scaling**: Increase server resources

Future enhancements:
- **Redis pub/sub** for horizontal scaling
- **Load balancer** for multiple API instances
- **Separate WebSocket server** for dedicated WebSocket handling

---

## Troubleshooting

### Connection Rejected

**Error**: Connection immediately closes with code 1008

**Cause**: Server at capacity (100 connections)

**Solution**: Wait and retry, or increase `WEBSOCKET_MAX_CONNECTIONS` env var

### Invalid Starlisting

**Error**: `{"type": "error", "code": "invalid_starlisting"}`

**Cause**: Starlisting ID doesn't exist or is inactive

**Solution**:
1. Get valid starlisting IDs from REST API: `GET /starlistings`
2. Verify starlisting is active

### No Updates Received

**Problem**: Subscribed but no updates (candles, funding, or OI)

**Debugging**:
1. Check if collector is running: `docker compose logs -f collector`
2. Verify data is being stored:
   - Candles: `docker compose exec timescaledb psql -U kirby -d kirby -c "SELECT COUNT(*) FROM candles WHERE starlisting_id = 1;"`
   - Funding: `docker compose exec timescaledb psql -U kirby -d kirby -c "SELECT COUNT(*) FROM funding_rates WHERE starlisting_id = 1;"`
   - Open Interest: `docker compose exec timescaledb psql -U kirby -d kirby -c "SELECT COUNT(*) FROM open_interest WHERE starlisting_id = 1;"`
3. Check WebSocket connection is active (receiving heartbeat pings)
4. Verify starlisting is active and collector is running for that market
5. Check collector logs for buffer flush messages (funding/OI updates every minute)

### Connection Timeout

**Problem**: Connection closes after period of inactivity

**Cause**: Network proxy/firewall timing out idle connections

**Solution**: Server sends automatic heartbeat pings every 30 seconds (configurable). If using a proxy, ensure it allows WebSocket keepalive messages.

---

## Configuration

### Environment Variables

```bash
# WebSocket Settings
WEBSOCKET_MAX_CONNECTIONS=100        # Max concurrent connections
WEBSOCKET_HEARTBEAT_INTERVAL=30      # Heartbeat interval (seconds)
WEBSOCKET_MESSAGE_SIZE_LIMIT=1048576 # Max message size (bytes, 1MB default)

# CORS (for browser clients)
CORS_ORIGINS=http://localhost:3000,http://localhost:8080
```

### Docker Compose

WebSocket service is included in the main API:

```yaml
api:
  image: kirby:latest
  ports:
    - "8000:8000"
  environment:
    - WEBSOCKET_MAX_CONNECTIONS=100
    - WEBSOCKET_HEARTBEAT_INTERVAL=30
```

---

## Testing

### Manual Testing

Use the included test clients:

**Python:**
```bash
# Default: Connect to ws://localhost:8000/ws, subscribe to starlistings 1,2
python scripts/test_websocket_client.py

# Custom configuration
WEBSOCKET_URL=ws://localhost:8000/ws \
STARLISTING_IDS=1,2,3 \
HISTORY=50 \
python scripts/test_websocket_client.py
```

**JavaScript (Browser):**
```bash
# Open in browser
open docs/examples/websocket_client.html

# Or via server
python -m http.server 8080
# Then visit: http://localhost:8080/docs/examples/websocket_client.html
```

### Automated Testing

Run integration tests:

```bash
pytest tests/integration/test_api_websocket.py -v
```

---

## Future Enhancements

### Completed Features

- ✅ **Funding rate streams** - Real-time funding rate updates (1-minute buffered)
- ✅ **Open interest streams** - Real-time OI updates (1-minute buffered)

### Planned Features

- [ ] **Redis pub/sub** for horizontal scaling
- [ ] **Authentication** via API keys
- [ ] **Rate limiting** per client
- [ ] **Subscription filters** (e.g., only receive updates when volume > X)
- [ ] **Compression** (e.g., permessage-deflate)
- [ ] **Binary protocol** (e.g., MessagePack) for reduced bandwidth

### Migration to Redis

When scaling beyond single server:

1. Add Redis to docker-compose
2. Implement `src/utils/pubsub.py` with `RedisPubSub` class
3. Update collectors to publish to Redis after DB write
4. Update `PostgresNotificationListener` to subscribe to Redis channels
5. No changes to WebSocket router or client code

---

## Support

**Issues**: https://github.com/YOUR_USERNAME/kirby/issues

**Documentation**: See [README.md](../README.md) and [CLAUDE.md](../CLAUDE.md)

**Questions**: Open a GitHub discussion or issue

---

**Happy Streaming!** 📡🚀
