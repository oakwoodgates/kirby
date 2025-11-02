# Exports Directory

This directory contains exported market data files for AI/ML training and backtesting.

## Export Scripts

Kirby provides four export scripts for different use cases:

### 1. Export Candles (`export_candles.py`)
Export OHLCV candle data for specified intervals.

```bash
# Export BTC 1m candles for last 30 days
python -m scripts.export_candles --coin BTC --intervals 1m --days 30

# Export all intervals for SOL
python -m scripts.export_candles --coin SOL --intervals all --days 90 --format parquet
```

### 2. Export Funding Rates (`export_funding.py`)
Export funding rate data with all price fields.

```bash
# Export BTC funding rates for last 30 days
python -m scripts.export_funding --coin BTC --days 30
```

### 3. Export Open Interest (`export_oi.py`)
Export open interest data with volume metrics.

```bash
# Export BTC open interest for last 30 days
python -m scripts.export_oi --coin BTC --days 30
```

### 4. Export Merged Data (`export_all.py`)
Export merged dataset with candles + funding + open interest aligned by timestamp.
Perfect for ML training and backtesting.

```bash
# Export BTC 1m merged dataset for last 90 days
python -m scripts.export_all --coin BTC --intervals 1m --days 90

# Export all intervals as Parquet
python -m scripts.export_all --coin BTC --intervals all --days 365 --format parquet
```

## File Formats

- **CSV**: Universal format, human-readable, larger file size
- **Parquet**: Columnar format, compressed, ~10x smaller, optimized for ML libraries

## Metadata Files

Each export generates a `.json` metadata file with:
- Export timestamp
- Data range
- Row count
- File size
- Export parameters

## Using Exported Data

### With Pandas
```python
import pandas as pd

# Load CSV
df = pd.read_csv('exports/merged_hyperliquid_BTC_USD_perps_1m_20251102_143022.csv')

# Load Parquet (faster, smaller)
df = pd.read_parquet('exports/merged_hyperliquid_BTC_USD_perps_1m_20251102_143022.parquet')
```

### With PyTorch
```python
import pandas as pd
import torch

df = pd.read_parquet('exports/merged_hyperliquid_BTC_USD_perps_1m_20251102_143022.parquet')

# Convert to tensors
features = torch.tensor(df[['open', 'high', 'low', 'close', 'volume', 'funding_rate', 'open_interest']].values, dtype=torch.float32)
```

## Documentation

For complete documentation, see [docs/EXPORT.md](../docs/EXPORT.md).
