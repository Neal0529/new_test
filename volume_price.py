import json
import logging
import os
from typing import Dict, Tuple

import numpy as np
import pandas as pd

LOG_DIR = "logs"
CONFIG_FILE = "config/dynamic_params.json"

DEFAULT_PARAMS = {
    "volume_ma_short": 5,
    "volume_ma_long": 20
}


def setup_logging():
    """Configure logging to console and file."""
    os.makedirs(LOG_DIR, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler(f"{LOG_DIR}/volume_price.log")
        ]
    )


logger = logging.getLogger(__name__)


def load_params() -> dict:
    """Load dynamic parameters from config file."""
    try:
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, "r") as f:
                params = json.load(f)
            logger.info(f"Loaded params from {CONFIG_FILE}")
            return {**DEFAULT_PARAMS, **params}
    except Exception as e:
        logger.warning(f"Failed to load params: {e}")
    return DEFAULT_PARAMS.copy()


PARAMS = load_params()


def _check_volume_health(volume: pd.Series, short: int, long: int) -> Tuple[bool, float]:
    """Check if short-term volume MA exceeds long-term volume MA.

    Args:
        volume: Volume series
        short: Short MA period
        long: Long MA period

    Returns:
        Tuple of (is_healthy, ma_short_value)
    """
    if len(volume) < long:
        return False, 0.0

    ma_short = volume.rolling(window=short, min_periods=short).mean().iloc[-1]
    ma_long = volume.rolling(window=long, min_periods=long).mean().iloc[-1]

    is_healthy = ma_short > ma_long

    return is_healthy, ma_short


def _check_candle_bullish(close: pd.Series) -> Tuple[bool, int]:
    """Check if at least 2 of last 3 days are bullish (close > previous close).

    Since we don't have open prices, we use price increase as proxy:
    bullish = today's close > yesterday's close.

    Args:
        close: Close price series

    Returns:
        Tuple of (is_bullish, bullish_count)
    """
    if len(close) < 4:
        return False, 0

    bullish_count = 0
    last_3_days = []

    for i in range(1, 4):
        is_bullish = close.iloc[-i] > close.iloc[-i - 1]
        last_3_days.append(is_bullish)
        if is_bullish:
            bullish_count += 1

    is_bullish = bullish_count >= 2

    return is_bullish, bullish_count


def _detect_volume_shrink(volume: pd.Series, close: pd.Series, window: int = 5) -> Tuple[bool, int]:
    """Detect "地量" (extremely low volume) pattern.

    Find any day in last 10 days where volume < 0.7 * min(previous 5 days volume).
    After that day, the next 2 days' closes are not lower than the low of shrinkage day.

    Args:
        volume: Volume series
        close: Close price series
        window: Lookback window

    Returns:
        Tuple of (is_shrink, shrink_day_index)
    """
    check_days = min(10, window + 5)
    if len(volume) < window + check_days:
        return False, -1

    for i in range(check_days, 0, -1):
        current_idx = len(volume) - i

        prev_window_vol = volume.iloc[current_idx - window:current_idx]
        min_prev_vol = prev_window_vol.min()

        current_vol = volume.iloc[current_idx]

        if current_vol < 0.7 * min_prev_vol:
            shrink_price = close.iloc[current_idx]

            if current_idx + 1 < len(close):
                next1_close = close.iloc[current_idx + 1]
                next2_close = close.iloc[current_idx + 2] if current_idx + 2 < len(close) else None

                if next2_close is not None:
                    if next1_close >= shrink_price and next2_close >= shrink_price:
                        logger.info(f"Volume shrinkage detected at day {current_idx}, "
                                    f"vol={current_vol}, min_prev={min_prev_vol}")
                        return True, current_idx

    return False, -1


def analyze_volume_price(close: pd.Series, volume: pd.Series) -> Tuple[int, Dict]:
    """Analyze volume-price relationship.

    Args:
        close: Series of closing prices
        volume: Series of volumes

    Returns:
        Tuple of (total_score, details_dict)
    """
    if len(close) < 20 or len(volume) < 20:
        logger.warning("Insufficient data for volume-price analysis")
        return 0, {"error": "insufficient data"}

    short_period = PARAMS["volume_ma_short"]
    long_period = PARAMS["volume_ma_long"]

    vol_healthy, ma_short = _check_volume_health(volume, short_period, long_period)

    ma_long = volume.rolling(window=long_period, min_periods=long_period).mean().iloc[-1]

    candle_bull, bullish_count = _check_candle_bullish(close)

    volume_shrink, shrink_idx = _detect_volume_shrink(volume, close)

    total_score = 0
    if vol_healthy:
        total_score += 5
    if candle_bull:
        total_score += 5
    if volume_shrink:
        total_score += 5

    details = {
        "vol_healthy": vol_healthy,
        "candle_bull": candle_bull,
        "volume_shrink": volume_shrink,
        "ma_short": ma_short,
        "ma_long": ma_long,
        "last_3_days_candles": bullish_count,
        "shrink_day_index": shrink_idx,
        "short_period": short_period,
        "long_period": long_period
    }

    logger.info(f"Volume-price analysis: score={total_score}, details={details}")

    return total_score, details


if __name__ == "__main__":
    setup_logging()

    np.random.seed(42)
    n = 30

    prices = [1.0]
    for i in range(1, n):
        prices.append(prices[-1] * (1 + np.random.randn() * 0.02))

    volumes = [1000000 + np.random.randn() * 100000 for _ in range(n)]

    volumes[20] = 100000
    volumes[21] = 1050000
    volumes[22] = 1080000

    close = pd.Series(prices)
    volume = pd.Series(volumes)

    print(f"Testing with {n} days")
    print(f"Volume at day 20 (shrinkage): {volumes[20]}")
    print(f"Min volume days 15-19: {min(volumes[15:20])}")
    print(f"Expected: 100000 < 0.7 * {min(volumes[15:20])} = {0.7 * min(volumes[15:20])}")
    print()

    score, details = analyze_volume_price(close, volume)

    print(f"Total score: {score}")
    print(f"Details: {details}")
