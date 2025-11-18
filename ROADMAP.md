# Kirby Roadmap

> Future features and enhancements for Kirby cryptocurrency data platform

**Current Status**: Phase 11 Complete - Authentication & API Keys ✅
**Version**: 1.3.0
**Last Updated**: November 17, 2025

---

## 🎯 Current Capabilities

Kirby is a production-ready cryptocurrency market data platform with:

- ✅ **Real-time Data Collection** - OHLCV candles, funding rates, open interest
- ✅ **REST API** - FastAPI endpoints for candles, funding rates, open interest, and starlistings
- ✅ **WebSocket API** - Real-time streaming of candles, funding rates, and open interest via PostgreSQL LISTEN/NOTIFY
- ✅ **Authentication & API Keys** - Secure API key-based authentication with admin role-based access control
- ✅ **Dual Database** - Separate production and training databases
- ✅ **Data Export** - CSV/Parquet exports for ML training and backtesting
- ✅ **Historical Backfill** - Scripts for candles and funding rate history
- ✅ **Docker Deployment** - Containerized with automated deployment script
- ✅ **Comprehensive Testing** - 79 tests (26 unit, 53 integration)

---

## 📋 Roadmap

### 🔥 High Priority (Production Readiness)

#### 1. Funding Rate & Open Interest API Endpoints ✅ COMPLETE
**Status**: ✅ Complete (November 17, 2025)
**Effort**: Low
**Priority**: High

**Description**: Add REST API endpoints for funding rates and open interest data.

**Why**: Data is already being collected and stored in the database. API endpoints now provide programmatic access to this data.

**Implementation**:
- ✅ Created `/funding/{exchange}/{coin}/{quote}/{market_type}` endpoint
- ✅ Created `/open-interest/{exchange}/{coin}/{quote}/{market_type}` endpoint
- ✅ Followed same pattern as candles.py router
- ✅ Added query parameters: `start_time`, `end_time`, `limit` (default: 1000, max: 5000)
- ✅ Included metadata in responses (exchange, trading pair, count, etc.)
- ✅ Created comprehensive integration tests ([test_api_funding.py](tests/integration/test_api_funding.py))

**Acceptance Criteria**:
- ✅ GET /funding/hyperliquid/BTC/USD/perps returns funding rate data
- ✅ GET /open-interest/hyperliquid/BTC/USD/perps returns OI data
- ✅ Time filtering works (start_time, end_time)
- ✅ Returns all fields: funding_rate, premium, mark_price, index_price, oracle_price, mid_price
- ✅ API docs automatically updated (Swagger UI at /docs)
- ✅ Integration tests created (10 test cases covering success, filters, errors)

---

#### 2. WebSocket Streaming for Funding/OI ✅ COMPLETE
**Status**: ✅ Complete (November 17, 2025)
**Effort**: Medium
**Priority**: High

**Description**: Extend WebSocket API to stream real-time funding rate and open interest updates.

**Why**: Real-time funding/OI data is valuable for trading strategies. WebSocket currently only streams candles.

**Implementation**:
- ✅ Created PostgreSQL NOTIFY triggers for funding_rates table ([migrations/versions/20251117_0002_add_funding_oi_notify_triggers.py](migrations/versions/20251117_0002_add_funding_oi_notify_triggers.py))
- ✅ Created PostgreSQL NOTIFY triggers for open_interest table
- ✅ Extended PostgresNotificationListener to listen on three channels (candle_updates, funding_updates, oi_updates)
- ✅ Added `_handle_funding_notification()` and `_handle_oi_notification()` methods
- ✅ Added `_query_funding_data()` and `_query_oi_data()` methods with full JOINs
- ✅ Updated WebSocket test client ([scripts/test_websocket_client.py](scripts/test_websocket_client.py)) to display funding and OI messages
- ✅ Same subscription mechanism - clients automatically receive all three data types when subscribed to a starlisting

**Acceptance Criteria**:
- ✅ Clients can subscribe to funding rate updates (automatic with starlisting subscription)
- ✅ Clients can subscribe to OI updates (automatic with starlisting subscription)
- ✅ Real-time updates broadcast when data changes (verified with live testing)
- ✅ Message format matches REST API responses (consistent metadata + data structure)
- ✅ Test client updated to display funding (💰) and OI (📈) messages
- ✅ All three data types stream in real-time (candles, funding, OI)

---

#### 3. Authentication & API Keys ✅ COMPLETE
**Status**: ✅ Complete (November 17, 2025)
**Effort**: Medium
**Priority**: High

**Description**: Add API key-based authentication for WebSocket and REST endpoints.

**Why**: Production APIs should have access control and usage tracking.

**Implementation**:
- ✅ Designed API key model (User, APIKey, APIKeyUsage tables)
- ✅ Added database migration for users and API keys ([migrations/versions/20251117_0003_add_auth_tables.py](migrations/versions/20251117_0003_add_auth_tables.py))
- ✅ Implemented API key middleware for FastAPI ([src/api/middleware/auth.py](src/api/middleware/auth.py))
- ✅ Added WebSocket authentication (API key in query parameter: `?api_key=kb_xxx`)
- ✅ Created admin endpoints for user and key management ([src/api/routers/admin.py](src/api/routers/admin.py))
- ✅ Implemented key expiration and active status checks
- ✅ Added last_used_at timestamp tracking
- ✅ Updated documentation (README.md with authentication examples)
- ✅ Created comprehensive integration tests ([tests/integration/test_api_auth.py](tests/integration/test_api_auth.py))

**Acceptance Criteria**:
- ✅ REST endpoints require valid API key (Authorization: Bearer header)
- ✅ WebSocket requires valid API key to connect (?api_key=kb_xxx query param)
- ✅ Invalid/expired/inactive keys return 401 Unauthorized
- ✅ Admin endpoints for user creation, key creation/deletion/deactivation
- ✅ Keys have configurable expiration (expires_at field)
- ✅ Usage tracking via last_used_at timestamp
- ✅ Role-based access control (admin vs regular user)
- ✅ SHA-256 hashed API keys with prefix display (kb_xxxxxxx)

---

#### 4. Rate Limiting
**Status**: Not Started
**Effort**: Low
**Priority**: High

**Description**: Implement rate limiting per API key/IP to prevent abuse.

**Why**: Prevent abuse, ensure fair usage, protect infrastructure.

**Implementation**:
- Add rate limiting middleware (slowapi or custom Redis-based)
- Configure limits: 100 requests/minute for REST, 5 WebSocket connections per key
- Return 429 Too Many Requests with Retry-After header
- Add rate limit headers to responses (X-RateLimit-Limit, X-RateLimit-Remaining)
- Different limits for authenticated vs unauthenticated requests
- Admin override for unlimited access

**Acceptance Criteria**:
- ✅ Requests over limit return 429 status
- ✅ Rate limit headers present in all responses
- ✅ Different limits for auth/unauth
- ✅ WebSocket connection limit enforced
- ✅ Limits configurable via environment variables

---

### 🚀 Feature Enhancements

#### 5. Redis Caching Layer
**Status**: Not Started
**Effort**: Medium
**Priority**: Medium

**Description**: Add Redis for caching frequently accessed data and enabling sub-minute data serving.

**Why**: Reduce database load, faster response times, enable horizontal scaling.

**Implementation**:
- Add Redis to docker-compose.yml
- Implement cache layer for:
  - Recent candles (last 100 per starlisting)
  - Active starlistings list
  - Latest funding rates
  - Latest open interest
- Cache invalidation on new data
- TTL-based expiration
- Cache warming on startup
- Metrics for cache hit/miss rates

**Benefits**:
- Faster API responses (< 10ms for cached data)
- Reduced database load
- Foundation for horizontal scaling
- Sub-minute data serving capability

---

#### 6. More Exchanges
**Status**: Not Started
**Effort**: High
**Priority**: Medium

**Description**: Add support for additional cryptocurrency exchanges.

**Why**: Multi-exchange data enables arbitrage detection, price comparison, and comprehensive market analysis.

**Target Exchanges**:
1. **Binance** (perpetuals + spot)
2. **Bybit** (perpetuals)
3. **OKX** (perpetuals + spot)
4. **Coinbase** (spot)

**Implementation** (per exchange):
- Create collector class in `src/collectors/{exchange}.py`
- Implement WebSocket connection and data parsing
- Add exchange to `config/starlistings.yaml`
- Test data collection and storage
- Update documentation

**Challenges**:
- Each exchange has different API formats
- WebSocket message structures vary
- Rate limiting differences
- Symbol naming conventions differ

---

#### 7. Order Book Depth Data
**Status**: Not Started
**Effort**: High
**Priority**: Low

**Description**: Collect and stream order book snapshots (bids/asks at multiple price levels).

**Why**: Critical for market microstructure analysis, liquidity measurement, spread analysis.

**Implementation**:
- Design schema for order book data (time, starlisting_id, side, price, quantity, level)
- Create TimescaleDB hypertable with compression
- Implement collectors for order book snapshots
- REST API endpoints for historical order book data
- WebSocket streaming for real-time order book updates
- Data retention policies (high volume data)

**Considerations**:
- Very high data volume (snapshots every 100ms-1s)
- Requires efficient compression
- Query performance challenges
- Storage costs

---

#### 8. Trade Tape / Tick Data
**Status**: Not Started
**Effort**: Very High
**Priority**: Low

**Description**: Collect individual trade events (price, size, timestamp, side).

**Why**: High-frequency analysis, precise backtesting, market impact studies.

**Implementation**:
- Design schema for trade data
- TimescaleDB hypertable with aggressive compression
- Collectors for trade streams
- Aggregation queries (VWAP, volume profiles)
- REST API for trade history
- WebSocket for real-time trades

**Considerations**:
- Extremely high data volume (100s-1000s of trades/second)
- Storage challenges (TBs of data)
- Query performance critical
- Expensive to maintain

---

### 📊 Operations & Monitoring

#### 9. Prometheus + Grafana Monitoring
**Status**: Not Started
**Effort**: Medium
**Priority**: Medium

**Description**: Add comprehensive metrics collection and visualization.

**Why**: Production observability, performance monitoring, alerting.

**Metrics to Track**:
- Request rate, latency (P50, P95, P99)
- WebSocket connection count
- Data freshness per starlisting
- Database query performance
- Error rates by endpoint
- Collector uptime and lag
- Cache hit/miss rates (if Redis added)

**Implementation**:
- Add prometheus_client to API
- Create /metrics endpoint
- Add Grafana to docker-compose
- Create dashboards for:
  - API performance
  - Data collection health
  - Database performance
  - System resources
- Configure alerting (PagerDuty, email, Slack)

---

#### 10. Automated Data Retention Policies
**Status**: Not Started
**Effort**: Low
**Priority**: Low

**Description**: Automatically delete old data based on interval and age.

**Why**: Manage database growth, control storage costs.

**Policies**:
- 1m candles: Keep 30 days
- 5m candles: Keep 90 days
- 15m candles: Keep 180 days
- 1h+ candles: Keep forever
- Funding/OI: Keep 180 days
- Order book: Keep 7 days (if implemented)
- Trades: Keep 30 days (if implemented)

**Implementation**:
- Use TimescaleDB retention policies
- Create migration to add policies
- Add monitoring for data volume by interval
- Document retention policy in README

---

#### 11. Automated Backfill on New Starlisting
**Status**: Not Started
**Effort**: Medium
**Priority**: Low

**Description**: Automatically trigger backfill when new starlisting is added to config.

**Why**: Faster onboarding of new markets, reduce manual work.

**Implementation**:
- Detect new starlistings in sync_config.py
- Queue backfill tasks (Celery or simple async queue)
- Background worker to process backfill queue
- Status tracking (in-progress, completed, failed)
- Retry logic for failed backfills
- Admin API to view/manage backfill status

---

#### 12. Health Check Dashboard
**Status**: Not Started
**Effort**: Medium
**Priority**: Low

**Description**: Web dashboard showing system health at a glance.

**Why**: Easy monitoring without diving into logs or Grafana.

**Features**:
- Collector status (running, last heartbeat, lag)
- Data freshness (time since last candle per starlisting)
- WebSocket connection count
- Database size and growth rate
- Recent errors
- Quick links to logs and metrics

**Implementation**:
- Simple HTML page served by FastAPI
- Auto-refresh every 10s
- Color-coded status indicators
- Accessible at /dashboard endpoint

---

### 🔐 Security & Infrastructure

#### 13. SSL/TLS (wss://) Support
**Status**: Not Started
**Effort**: Medium
**Priority**: Medium

**Description**: Add SSL/TLS encryption for secure WebSocket and HTTPS connections.

**Why**: Encrypted connections are essential for production, especially for financial data.

**Implementation**:
- Add nginx reverse proxy to docker-compose
- Configure Let's Encrypt for automatic SSL certificates
- Proxy HTTP → HTTPS (redirect)
- Proxy ws:// → wss://
- Configure SSL best practices (TLS 1.3, strong ciphers)
- Auto-renewal of certificates

**Benefits**:
- Encrypted data transmission
- Required by many corporate firewalls
- Better security posture
- Professional production setup

---

#### 14. Horizontal Scaling
**Status**: Not Started
**Effort**: High
**Priority**: Low

**Description**: Enable multi-instance API deployment with load balancing.

**Why**: Handle more connections, higher request volumes, redundancy.

**Implementation**:
- Replace PostgreSQL LISTEN/NOTIFY with Redis pub/sub
- Shared session state in Redis
- Load balancer (nginx or HAProxy)
- Multiple API instances in docker-compose
- Sticky sessions for WebSocket connections
- Health check endpoints for load balancer

**Requirements**:
- Redis (caching + pub/sub)
- Load balancer
- Shared file storage for logs (optional)

---

#### 15. Automated Backups
**Status**: Not Started
**Effort**: Low
**Priority**: Medium

**Description**: Scheduled automated backups to cloud storage.

**Why**: Data protection, disaster recovery.

**Implementation**:
- Daily cron job for pg_dump
- Upload to Digital Ocean Spaces / AWS S3
- Retention policy (keep 7 daily, 4 weekly, 12 monthly)
- Backup rotation script
- Test restore procedure
- Monitoring for backup success/failure

**Backup Locations**:
- Digital Ocean Spaces (if on DO)
- AWS S3 (multi-region)
- Local encrypted backup drive (optional)

---

## 🎯 Recommended Priority Order

If implementing sequentially, here's the recommended order:

1. ~~**Funding/OI API Endpoints**~~ - ✅ Complete
2. ~~**WebSocket for Funding/OI**~~ - ✅ Complete
3. ~~**Authentication**~~ - ✅ Complete
4. **Rate Limiting** - Essential for production (next priority)
5. **Redis Caching** - Foundation for scaling and performance
6. **SSL/TLS Support** - Security best practice
7. **More Exchanges** - Expand data sources
8. **Prometheus Monitoring** - Production observability
9. **Automated Backups** - Data protection
10. **Horizontal Scaling** - When growth demands it
11. **Order Book / Trades** - If needed for specific use cases

---

## 📌 Notes

### Out of Scope (Separate Apps)

The following features are intentionally **excluded** from Kirby's roadmap as they belong in separate applications:

- **ML Features**: Computed indicators, feature engineering, model training
- **Trading Features**: Strategy backtesting, portfolio simulation, order execution
- **Analysis Tools**: Charting, pattern recognition, signal generation

**Why**: Kirby is focused on being a **high-performance data ingestion, formatting, and API platform**. ML and trading features should be built in separate applications that consume Kirby's API.

### Contributing

Have ideas for new features? Open an issue or discussion on GitHub!

---

**Last Updated**: November 17, 2025
**Maintainer**: Kirby Team
