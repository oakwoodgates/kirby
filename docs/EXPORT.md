# Kirby Data Export Guide

Complete guide to exporting market data for AI/ML training, backtesting, and external analysis.

---

## Table of Contents

- [Overview](#overview)
- [Export Scripts](#export-scripts)
- [File Formats](#file-formats)
- [Common Options](#common-options)
- [Usage Examples](#usage-examples)
- [Merged Datasets](#merged-datasets)
- [Integration with ML Frameworks](#integration-with-ml-frameworks)
- [Best Practices](#best-practices)
- [Troubleshooting](#troubleshooting)

---

## Overview

Kirby provides four CLI scripts for exporting market data:

1. **export_candles.py** - OHLCV candle data with multi-interval support
2. **export_funding.py** - Funding rate data with price context
3. **export_oi.py** - Open interest data with volume metrics
4. **export_all.py** - Merged datasets (candles + funding + OI) for ML/backtesting

All exports support:
- ✅ **Both CSV and Parquet formats** (universal vs. ML-optimized)
- ✅ **Multi-interval exports** (single, multiple, or all intervals)
- ✅ **Complete column export** (all data fields included)
- ✅ **Metadata generation** (JSON files with export parameters)
- ✅ **Docker compatibility** (run inside container, save to mounted volume)

---

## Export Scripts

### 1. Export Candles (`export_candles.py`)

Export OHLCV (Open, High, Low, Close, Volume) candle data.

**Key Features:**
- Multi-interval support: export 1m, 15m, 4h, 1d, or all at once
- Configurable time ranges (last N days or custom start/end)
- Both CSV and Parquet output

**Exported Columns:**
```
time, open, high, low, close, volume, num_trades
```

**Usage:**
```bash
# Inside Docker container
docker compose exec collector python -m scripts.export_candles \
  --coin BTC --intervals 1m --days 30

# Local environment
python -m scripts.export_candles --coin BTC --intervals 1m --days 30
```

---

### 2. Export Funding Rates (`export_funding.py`)

Export funding rate data for perpetual futures markets.

**Key Features:**
- Includes all price fields (mark, index, oracle, mid)
- 1-minute precision timestamps
- Funding rate history and premium data

**Exported Columns:**
```
time, funding_rate, premium, mark_price, index_price,
oracle_price, mid_price, next_funding_time
```

**Usage:**
```bash
docker compose exec collector python -m scripts.export_funding \
  --coin BTC --days 30
```

---

### 3. Export Open Interest (`export_oi.py`)

Export open interest (total position size) data.

**Key Features:**
- Open interest in base currency and notional value
- 24-hour volume metrics
- 1-minute precision timestamps

**Exported Columns:**
```
time, open_interest, notional_value,
day_base_volume, day_notional_volume
```

**Usage:**
```bash
docker compose exec collector python -m scripts.export_oi \
  --coin BTC --days 30
```

---

### 4. Export Merged Data (`export_all.py`)

Export merged datasets with candles + funding + OI aligned by timestamp.

**Key Features:**
- **ML-ready**: All features in one aligned dataset
- **Multi-interval**: Export for 1m, 15m, 4h, 1d, or all intervals
- **NULL preservation**: Missing values left as NULL (no imputation)
- **Perfect for backtesting**: Complete market context

**Merged Columns:**
```
time,
open, high, low, close, volume, num_trades,  # from candles
funding_rate, premium, mark_price, index_price, oracle_price, mid_price, next_funding_time,  # from funding
open_interest, notional_value, day_base_volume, day_notional_volume  # from OI
```

**Merge Strategy:**
- Base: Candle timestamps (e.g., 1-minute candles)
- LEFT JOIN funding_rates ON time
- LEFT JOIN open_interest ON time
- Missing values → NULL (no forward-filling or interpolation)

**Usage:**
```bash
# Export BTC 1m merged dataset (ML training)
docker compose exec collector python -m scripts.export_all \
  --coin BTC --intervals 1m --days 90

# Export all intervals (multi-timeframe backtesting)
docker compose exec collector python -m scripts.export_all \
  --coin BTC --intervals all --days 365 --format parquet
```

---

## File Formats

### CSV (Comma-Separated Values)

**Pros:**
- Universal format (Excel, R, Python, etc.)
- Human-readable
- Easy to inspect

**Cons:**
- Larger file size (~10x vs Parquet)
- Slower to read for large datasets

**When to use:** Small exports, manual inspection, Excel analysis

---

### Parquet (Columnar Format)

**Pros:**
- ~10x smaller file size (compression)
- Much faster to read
- Columnar storage (efficient for ML libraries)
- Preserves data types

**Cons:**
- Binary format (not human-readable)
- Requires specific libraries (pandas, pyarrow)

**When to use:** Large exports, ML training, production pipelines

---

## Common Options

All export scripts support these flags:

### Required Arguments

```bash
--coin SYMBOL        # Coin symbol (BTC, ETH, SOL, etc.)
```

For candles and merged exports only:
```bash
--intervals LIST     # Intervals: "1m", "1m,15m,4h", or "all"
```

### Time Range (Mutually Exclusive)

**Option 1: Last N days**
```bash
--days 30            # Export last 30 days from now
```

**Option 2: Custom range**
```bash
--start-time "2025-10-01"         # ISO format
--end-time "2025-11-01"           # ISO format

# Or Unix timestamps
--start-time 1727740800
--end-time 1730419200
```

### Optional Arguments

```bash
--exchange hyperliquid    # Exchange name (default: hyperliquid)
--quote USD               # Quote currency (default: USD)
--market-type perps       # Market type (default: perps)
--format csv              # Export format: csv, parquet, or both (default: both)
--output exports/         # Output directory (default: exports/)
```

---

## Usage Examples

### Example 1: Quick ML Training Dataset

Export BTC 1m merged data for last 90 days (optimal for ML training):

```bash
docker compose exec collector python -m scripts.export_all \
  --coin BTC \
  --intervals 1m \
  --days 90 \
  --format parquet
```

**Output:**
```
exports/merged_hyperliquid_BTC_USD_perps_1m_20251102_143022.parquet
exports/merged_hyperliquid_BTC_USD_perps_1m_20251102_143022.json
```

---

### Example 2: Multi-Timeframe Backtesting

Export all intervals for BTC (1m, 15m, 4h, 1d) for last year:

```bash
docker compose exec collector python -m scripts.export_all \
  --coin BTC \
  --intervals all \
  --days 365 \
  --format parquet
```

**Output:**
```
exports/merged_hyperliquid_BTC_USD_perps_1m_20251102_143022.parquet
exports/merged_hyperliquid_BTC_USD_perps_15m_20251102_143022.parquet
exports/merged_hyperliquid_BTC_USD_perps_4h_20251102_143022.parquet
exports/merged_hyperliquid_BTC_USD_perps_1d_20251102_143022.parquet
(+ 4 JSON metadata files)
```

---

### Example 3: Funding Rate Analysis

Export funding rates only for statistical analysis:

```bash
docker compose exec collector python -m scripts.export_funding \
  --coin BTC \
  --days 180 \
  --format csv
```

**Output:**
```
exports/funding_hyperliquid_BTC_USD_perps_20251102_143530.csv
exports/funding_hyperliquid_BTC_USD_perps_20251102_143530.json
```

---

### Example 4: Custom Date Range for Event Study

Export data around a specific event (e.g., market crash):

```bash
docker compose exec collector python -m scripts.export_all \
  --coin BTC \
  --intervals 1m \
  --start-time "2025-10-15T00:00:00" \
  --end-time "2025-10-20T23:59:59"
```

---

### Example 5: Multiple Coins

Export data for multiple coins (separate commands):

```bash
# BTC
docker compose exec collector python -m scripts.export_all \
  --coin BTC --intervals 1m --days 90 --format parquet

# ETH
docker compose exec collector python -m scripts.export_all \
  --coin ETH --intervals 1m --days 90 --format parquet

# SOL
docker compose exec collector python -m scripts.export_all \
  --coin SOL --intervals 1m --days 90 --format parquet
```

---

## Merged Datasets

### Understanding the Merge

The `export_all.py` script creates ML-ready datasets by merging three data sources:

```
Candles (1m interval)     Funding Rates (1m)     Open Interest (1m)
├─ 2025-11-02 10:00:00   ├─ 2025-11-02 10:00:00  ├─ 2025-11-02 10:00:00
├─ 2025-11-02 10:01:00   ├─ 2025-11-02 10:01:00  ├─ 2025-11-02 10:01:00
├─ 2025-11-02 10:02:00   ├─ 2025-11-02 10:02:00  (missing)
└─ 2025-11-02 10:03:00   (missing)               ├─ 2025-11-02 10:03:00

                            ↓ LEFT JOIN on time ↓

Merged Dataset
├─ 2025-11-02 10:00:00  [candles: ✓] [funding: ✓] [OI: ✓]
├─ 2025-11-02 10:01:00  [candles: ✓] [funding: ✓] [OI: ✓]
├─ 2025-11-02 10:02:00  [candles: ✓] [funding: ✓] [OI: NULL]
└─ 2025-11-02 10:03:00  [candles: ✓] [funding: NULL] [OI: ✓]
```

**Key Points:**
- Candles are the base (always present)
- Funding/OI joined by timestamp
- Missing values are NULL (no imputation)
- Perfect timestamp alignment (minute-precision)

---

### Example: Merged Dataset Structure

```python
import pandas as pd

df = pd.read_parquet('exports/merged_hyperliquid_BTC_USD_perps_1m_20251102_143022.parquet')
print(df.head())
```

**Output:**
```
                     time      open      high       low     close    volume  num_trades  funding_rate  premium  mark_price  ...
0 2025-11-02 10:00:00  67500.50  67800.00  67400.25  67650.75  1234.56         542      0.000123   0.5000    67650.00  ...
1 2025-11-02 10:01:00  67650.75  67700.00  67600.00  67680.00  890.12          421      0.000124   0.5100    67680.50  ...
2 2025-11-02 10:02:00  67680.00  67750.00  67650.00  67720.00  1050.30         512      0.000125      NaN    67720.25  ...
```

---

## Integration with ML Frameworks

### Pandas (Data Analysis)

```python
import pandas as pd

# Load Parquet (recommended)
df = pd.read_parquet('exports/merged_hyperliquid_BTC_USD_perps_1m_20251102.parquet')

# Or load CSV
df = pd.read_csv('exports/merged_hyperliquid_BTC_USD_perps_1m_20251102.csv')

# Basic analysis
print(df.describe())
print(df.isnull().sum())  # Check missing values

# Feature engineering
df['price_change'] = df['close'] - df['open']
df['price_change_pct'] = (df['close'] - df['open']) / df['open'] * 100

# Handle missing values
df_filled = df.fillna(method='ffill')  # Forward-fill
# Or drop rows with NaN
df_clean = df.dropna()
```

---

### PyTorch (Deep Learning)

```python
import pandas as pd
import torch
from torch.utils.data import Dataset, DataLoader

# Load data
df = pd.read_parquet('exports/merged_hyperliquid_BTC_USD_perps_1m_20251102.parquet')

# Select features
feature_cols = ['open', 'high', 'low', 'close', 'volume',
                'funding_rate', 'open_interest']
df_features = df[feature_cols].fillna(0)  # Handle NaN

# Create PyTorch dataset
class CryptoDataset(Dataset):
    def __init__(self, dataframe, sequence_length=60):
        self.data = torch.tensor(dataframe.values, dtype=torch.float32)
        self.sequence_length = sequence_length

    def __len__(self):
        return len(self.data) - self.sequence_length

    def __getitem__(self, idx):
        x = self.data[idx:idx+self.sequence_length]
        y = self.data[idx+self.sequence_length, 3]  # Predict next close price
        return x, y

# Create DataLoader
dataset = CryptoDataset(df_features, sequence_length=60)
dataloader = DataLoader(dataset, batch_size=32, shuffle=True)

# Train your model
for x_batch, y_batch in dataloader:
    # Your training code here
    pass
```

---

### TensorFlow/Keras

```python
import pandas as pd
import numpy as np
from tensorflow import keras

# Load data
df = pd.read_parquet('exports/merged_hyperliquid_BTC_USD_perps_1m_20251102.parquet')

# Select and normalize features
feature_cols = ['open', 'high', 'low', 'close', 'volume',
                'funding_rate', 'open_interest']
df_features = df[feature_cols].fillna(0)

# Normalize (0-1 range)
from sklearn.preprocessing import MinMaxScaler
scaler = MinMaxScaler()
scaled_data = scaler.fit_transform(df_features)

# Create sequences for LSTM
def create_sequences(data, sequence_length=60):
    X, y = [], []
    for i in range(len(data) - sequence_length):
        X.append(data[i:i+sequence_length])
        y.append(data[i+sequence_length, 3])  # Predict close price
    return np.array(X), np.array(y)

X, y = create_sequences(scaled_data)

# Build model
model = keras.Sequential([
    keras.layers.LSTM(50, return_sequences=True, input_shape=(X.shape[1], X.shape[2])),
    keras.layers.LSTM(50),
    keras.layers.Dense(1)
])

model.compile(optimizer='adam', loss='mse')
model.fit(X, y, epochs=10, batch_size=32)
```

---

### Scikit-learn (Classical ML)

```python
import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.model_selection import train_test_split

# Load data
df = pd.read_parquet('exports/merged_hyperliquid_BTC_USD_perps_1m_20251102.parquet')

# Create features
df['price_change'] = df['close'] - df['open']
df['volatility'] = df['high'] - df['low']
df_filled = df.fillna(method='ffill').dropna()

# Features and target
features = ['open', 'high', 'low', 'volume', 'funding_rate', 'open_interest', 'volatility']
X = df_filled[features]
y = df_filled['close'].shift(-1).dropna()  # Predict next close
X = X[:-1]  # Match lengths

# Train/test split
X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, shuffle=False)

# Train model
model = RandomForestRegressor(n_estimators=100)
model.fit(X_train, y_train)

# Evaluate
score = model.score(X_test, y_test)
print(f'R² Score: {score:.4f}')
```

---

## Best Practices

### 1. Choose the Right Format

- **Parquet** for large datasets, ML training, production
- **CSV** for small datasets, manual inspection, Excel analysis
- **Both** if unsure (slight overhead, maximum flexibility)

### 2. Handle Missing Values Appropriately

Export scripts preserve NULLs. Choose your strategy:

```python
# Forward-fill (carry last known value)
df_filled = df.fillna(method='ffill')

# Backward-fill
df_filled = df.fillna(method='bfill')

# Drop rows with any NaN
df_clean = df.dropna()

# Fill with zeros
df_filled = df.fillna(0)

# Interpolate
df_filled = df.interpolate(method='linear')
```

### 3. Optimize Exports for Large Datasets

For multi-year exports:

```bash
# Export one interval at a time
docker compose exec collector python -m scripts.export_all \
  --coin BTC --intervals 1m --days 365 --format parquet

# Or split by time ranges
docker compose exec collector python -m scripts.export_all \
  --coin BTC --intervals 1m \
  --start-time "2024-01-01" --end-time "2024-06-30"
```

### 4. Use Metadata Files

Every export generates a `.json` metadata file:

```python
import json

with open('exports/merged_hyperliquid_BTC_USD_perps_1m_20251102.json') as f:
    metadata = json.load(f)

print(f"Exported: {metadata['row_count']} rows")
print(f"Time range: {metadata['time_range']['start']} to {metadata['time_range']['end']}")
```

### 5. Docker Volume Mounting

Export to host filesystem from Docker:

```yaml
# docker-compose.yml
services:
  collector:
    volumes:
      - ./exports:/app/exports  # Mount exports directory
```

```bash
# Exports will appear in your local ./exports directory
docker compose exec collector python -m scripts.export_all \
  --coin BTC --intervals 1m --days 30
```

---

## Troubleshooting

### Issue: "No data found in specified time range"

**Cause:** No data exists for the requested time range.

**Solutions:**
1. Check what data you have:
   ```bash
   docker compose exec timescaledb psql -U kirby -d kirby -c \
     "SELECT MIN(time), MAX(time), COUNT(*) FROM candles WHERE starlisting_id = 1;"
   ```

2. Reduce the time range or use `--days` with a smaller value

3. Ensure collector has been running and collecting data

---

### Issue: "Starlisting not found"

**Cause:** The specified trading pair/interval doesn't exist in your database.

**Solutions:**
1. Check available starlistings:
   ```bash
   curl http://localhost:8000/starlistings
   ```

2. Verify coin symbol is uppercase: `--coin BTC` not `--coin btc`

3. Ensure starlisting is active in `config/starlistings.yaml`

---

### Issue: Large file sizes with CSV

**Solution:** Use Parquet format instead:

```bash
--format parquet  # ~10x smaller than CSV
```

---

### Issue: Memory errors with large exports

**Solutions:**
1. Export smaller time ranges
2. Use Parquet format (more memory-efficient)
3. Export one interval at a time instead of `--intervals all`

---

### Issue: Import errors (pandas/pyarrow not found)

**Cause:** Dependencies not installed.

**Solutions:**

**Local environment:**
```bash
pip install -e "."  # Installs all dependencies from pyproject.toml
```

**Docker:**
```bash
docker compose build collector  # Rebuild with new dependencies
```

---

### Issue: Permission denied when writing to exports/

**Cause:** Docker user doesn't have write permissions.

**Solution:** Create directory with proper permissions:

```bash
mkdir -p exports
chmod 777 exports  # Or use appropriate ownership
```

---

## Advanced Use Cases

### Backtesting with Backtrader

```python
import pandas as pd
import backtrader as bt

# Load merged dataset
df = pd.read_parquet('exports/merged_hyperliquid_BTC_USD_perps_1m.parquet')
df['datetime'] = pd.to_datetime(df['time'])
df.set_index('datetime', inplace=True)

# Create Backtrader data feed
data = bt.feeds.PandasData(dataname=df)

# Run backtest
cerebro = bt.Cerebro()
cerebro.adddata(data)
cerebro.addstrategy(YourStrategy)
cerebro.run()
```

### Feature Engineering for ML

```python
import pandas as pd

df = pd.read_parquet('exports/merged_hyperliquid_BTC_USD_perps_1m.parquet')

# Technical indicators
df['sma_20'] = df['close'].rolling(20).mean()
df['ema_12'] = df['close'].ewm(span=12).mean()
df['rsi'] = calculate_rsi(df['close'], period=14)

# Price features
df['returns'] = df['close'].pct_change()
df['log_returns'] = np.log(df['close'] / df['close'].shift(1))

# Volume features
df['volume_sma'] = df['volume'].rolling(20).mean()
df['volume_ratio'] = df['volume'] / df['volume_sma']

# Funding features
df['funding_ma'] = df['funding_rate'].rolling(24).mean()
df['funding_std'] = df['funding_rate'].rolling(24).std()

# Save enriched dataset
df.to_parquet('exports/btc_1m_with_features.parquet')
```

---

## Summary

Kirby's export feature provides:
- ✅ **4 export scripts** for different use cases
- ✅ **2 formats** (CSV + Parquet)
- ✅ **Multi-interval support** (1m, 15m, 4h, 1d, all)
- ✅ **Merged datasets** for ML/backtesting
- ✅ **Complete data** with all columns
- ✅ **Metadata files** for reproducibility
- ✅ **Docker-compatible** for production use

For questions or issues, see [GitHub Issues](https://github.com/oakwoodgates/kirby/issues).
