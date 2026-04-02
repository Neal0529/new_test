# Agent Guidelines for This Repository

## Project Overview

This is an automated ETF trading analysis system written in Python. It includes modules for data fetching, technical indicators, wave theory analysis, volume/price analysis, chip analysis, news collection, sentiment analysis, signal generation, backtesting, parameter optimization, and reporting.

## Build, Lint, and Test Commands

### Running the Application
```bash
# Run main application
python main.py

# Run with python3
python3 main.py
```

### Running Tests
```bash
# Run all tests with pytest
pytest

# Run a single test file
pytest test.py

# Run a specific test function
pytest test.py::test_function_name

# Run tests with verbose output
pytest -v

# Run tests matching a pattern
pytest -k "test_pattern"
```

### Linting and Formatting
```bash
# Run flake8 linter
flake8 .

# Run black formatter (check only)
black --check .

# Run black formatter (auto-fix)
black .

# Run mypy type checker
mypy .

# Run isort import sorter
isort --check .
```

## Project Structure

```
.
├── config/
│   ├── config.yaml          # Main configuration
│   ├── dynamic_params.json  # Dynamic trading parameters
│   └── positions.json       # Position tracking
├── data/                    # Market data storage
├── logs/                    # Application logs
├── reports/                 # Generated reports
├── main.py                  # Entry point
├── scheduler.py             # Task scheduling
├── data_fetcher.py          # Market data fetching
├── quality_checker.py       # Data quality validation
├── indicators.py            # Technical indicators
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

## Code Style Guidelines

### Imports
- Use absolute imports when possible
- Group imports in this order: stdlib, third-party, local
- Use `isort` to sort imports automatically
- Maximum line length: 100 characters

Example:
```python
import os
import sys
from typing import List, Optional
from datetime import datetime

import numpy as np
import pandas as pd

from .indicators import calculate_ma
from .signal_generator import SignalGenerator
```

### Formatting
- Follow PEP 8 style guide
- Use 4 spaces for indentation (no tabs)
- Use Black for automatic formatting
- Add trailing commas in multi-line imports
- Use f-strings for string formatting (Python 3.6+)

### Types
- Use type hints for all function signatures
- Use `Optional[X]` instead of `Union[X, None]`
- Prefer explicit return types
- Use mypy for type checking

Example:
```python
def calculate_ema(prices: List[float], period: int) -> Optional[List[float]]:
    """Calculate Exponential Moving Average."""
    if not prices or period <= 0:
        return None
    # ... implementation
```

### Naming Conventions
- Classes: `PascalCase` (e.g., `SignalGenerator`)
- Functions/variables: `snake_case` (e.g., `calculate_ema`)
- Constants: `UPPER_SNAKE_CASE` (e.g., `MAX_LOOKBACK_PERIOD`)
- Private methods: prefix with underscore (e.g., `_internal_calc`)
- Avoid single-letter names except in loops

### Error Handling
- Use specific exception types
- Include meaningful error messages
- Prefer `raise CustomError("message")` over `raise CustomError()`
- Use context managers (`with`) for resource management
- Handle exceptions at appropriate levels
- Log errors before raising

Example:
```python
try:
    df = load_market_data(symbol, start_date, end_date)
except ValueError as e:
    logger.error(f"Invalid parameters for {symbol}: {e}")
    raise DataFetchError(f"Failed to fetch data for {symbol}") from e
```

### Trading-Specific Guidelines
- All monetary values should use `Decimal` for precision
- Use timezone-aware timestamps for market data
- Document indicator parameters and assumptions
- Include input validation for all trading parameters
- Log all trading decisions with rationale

### General Guidelines
- Keep functions small and focused (max ~50 lines)
- Write docstrings for all public functions
- Use descriptive variable names
- Avoid magic numbers; use constants
- Write tests for new functionality
- Keep dependencies minimal

## VSCode Settings

No special VSCode configuration required.