# ETF Trading Analysis System

An automated ETF trading analysis system that generates trading signals based on technical indicators, wave theory, volume analysis, chip distribution, and sentiment analysis.

## Project Structure

```
.
├── config/
│   ├── config.yaml          # ETF list and global parameters
│   ├── dynamic_params.json  # Trading parameters
│   └── positions.json       # Position tracking
├── data/                    # Market data (cached CSV)
├── logs/                    # Application logs
├── reports/                 # Generated reports
├── main.py                  # Entry point
├── scheduler.py             # Task scheduling
├── data_fetcher.py          # Market data fetching (akshare)
├── quality_checker.py       # Data quality validation
├── indicators.py            # Technical indicators (MACD, KDJ, RSI)
├── wave_theory.py           # Elliott wave theory
├── volume_price.py          # Volume/price analysis
├── chip_analysis.py         # Chip/distribution analysis
├── news_collector.py        # News data collection
├── sentiment_analyzer.py    # Sentiment analysis
├── signal_generator.py      # Trading signal generation
├── backtest_engine.py       # Backtesting engine
├── parameter_optimizer.py   # Parameter optimization
└── report_generator.py      # Report generation
```

## Installation

```bash
pip install -r requirements.txt
```

Or with conda:
```bash
conda activate eco_try
pip install pandas numpy scipy akshare tushare snownlp schedule pyyaml
```

## Usage

### Run the main system

```bash
python main.py
```

### Fetch data for a specific ETF

```python
from data_fetcher import fetch_etf_data, fetch_chip_data
from datetime import datetime, timedelta

# Fetch daily data
end_date = datetime.now().strftime("%Y-%m-%d")
start_date = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
df = fetch_etf_data("512000", start_date, end_date)

# Fetch chip data
chip = fetch_chip_data("512000", end_date)
```

### Check data quality

```python
from quality_checker import check_data_quality

cleaned_df, status = check_data_quality(df)
# status: "ok", "warning", or "error"
```

## Configuration

### config.yaml

Defines the ETF list with codes, names, sectors, and position limits:

- `base_position`: Base investment amount
- `max_position`: Maximum position size

Global parameters:
- `win_rate_target`: Target win rate (0.80)
- `stop_loss`: Stop loss threshold (-0.06)
- `take_profit_half`: First profit target (0.06)
- `take_profit_full`: Full profit target (0.10)
- `holding_days_min/max`: Holding period range

### dynamic_params.json

Technical indicator parameters:
- RSI threshold
- MACD parameters
- KDJ parameters
- Wave Fibonacci levels
- Volume MA periods

## Supported ETFs

| Code | Name | Sector |
|------|------|--------|
| 512000 | 券商ETF | 券商 |
| 588000 | 科创50ETF | 科创板 |
| 161725 | 白酒LOF | 白酒 |
| 562500 | 机器人ETF | 机器人 |
| 159792 | 港股通互联网ETF | 港股互联网 |
| 159620 | 中证500ETF | 中证500 |
| 516690 | 游戏ETF | 游戏 |
| 159582 | 半导体ETF | 半导体 |

## Development

### Running Tests

```bash
pytest
pytest test.py::test_function_name
```

### Linting

```bash
flake8 .
black --check .
mypy .
isort --check .
```
