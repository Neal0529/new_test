import json
import logging
import os
from typing import Optional, Tuple

import numpy as np
import pandas as pd

LOG_DIR = "logs"
CONFIG_FILE = "config/dynamic_params.json"

DEFAULT_PARAMS = {
    "macd_fast": 12,
    "macd_slow": 26,
    "macd_signal": 9,
    "kdj_n": 9,
    "kdj_m1": 3,
    "kdj_m2": 3,
    "rsi_period": 14,
    "rsi_threshold": 30
}


def setup_logging():
    """Configure logging to console and file."""
    os.makedirs(LOG_DIR, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler(f"{LOG_DIR}/indicators.log")
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


def calculate_ema(series: pd.Series, period: int) -> pd.Series:
    """Calculate Exponential Moving Average.

    Args:
        series: Price series
        period: EMA period

    Returns:
        EMA series
    """
    return series.ewm(span=period, adjust=False).mean()


def calculate_macd_internal(close: pd.Series) -> pd.DataFrame:
    """Calculate MACD components.

    Args:
        close: Closing price series

    Returns:
        DataFrame with MACD, signal, and histogram
    """
    fast = PARAMS["macd_fast"]
    slow = PARAMS["macd_slow"]
    signal = PARAMS["macd_signal"]

    ema_fast = calculate_ema(close, fast)
    ema_slow = calculate_ema(close, slow)

    macd = ema_fast - ema_slow
    signal_line = calculate_ema(macd, signal)
    histogram = macd - signal_line

    return pd.DataFrame({
        "macd": macd,
        "signal": signal_line,
        "histogram": histogram
    })


def compute_macd(close: pd.Series) -> Tuple[bool, float]:
    """Compute MACD indicator.

    Args:
        close: Series of closing prices

    Returns:
        Tuple of (macd_bull: bool, score: float)
    """
    if len(close) < PARAMS["macd_slow"]:
        logger.warning(f"Insufficient data for MACD: need {PARAMS['macd_slow']}, got {len(close)}")
        return False, 0.0

    try:
        macd_df = calculate_macd_internal(close)

        macd_val = macd_df["macd"].iloc[-1]
        signal_val = macd_df["signal"].iloc[-1]
        histogram = macd_df["histogram"].iloc[-1]

        if len(macd_df) >= 2:
            histogram_prev = macd_df["histogram"].iloc[-2]
            histogram_rising = histogram > histogram_prev
        else:
            histogram_rising = False

        bullish = (macd_val > signal_val) and (histogram > 0 or histogram_rising)
        score = 20.0 if bullish else 0.0

        if bullish:
            logger.info(f"MACD bullish: macd={macd_val:.4f}, signal={signal_val:.4f}, hist={histogram:.4f}")

        return bullish, score

    except Exception as e:
        logger.error(f"Error computing MACD: {e}")
        return False, 0.0


def calculate_kdj_internal(high: pd.Series, low: pd.Series, close: pd.Series) -> pd.DataFrame:
    """Calculate KDJ indicator.

    Args:
        high: High price series
        low: Low price series
        close: Close price series

    Returns:
        DataFrame with K, D, J values
    """
    n = PARAMS["kdj_n"]
    m1 = PARAMS["kdj_m1"]
    m2 = PARAMS["kdj_m2"]

    low_min = low.rolling(window=n, min_periods=1).min()
    high_max = high.rolling(window=n, min_periods=1).max()

    rsv = (close - low_min) / (high_max - low_min) * 100
    rsv = rsv.fillna(50)

    k = pd.Series(index=close.index, dtype=float)
    d = pd.Series(index=close.index, dtype=float)

    k.iloc[0] = 50.0
    d.iloc[0] = 50.0

    for i in range(1, len(close)):
        k.iloc[i] = k.iloc[i-1] * (m1 - 1) / m1 + rsv.iloc[i] / m1
        d.iloc[i] = d.iloc[i-1] * (m2 - 1) / m2 + k.iloc[i] / m2

    j = 3 * k - 2 * d

    return pd.DataFrame({"k": k, "d": d, "j": j})


def compute_kdj(high: pd.Series, low: pd.Series, close: pd.Series) -> Tuple[bool, float]:
    """Compute KDJ indicator.

    Args:
        high: Series of high prices
        low: Series of low prices
        close: Series of closing prices

    Returns:
        Tuple of (kdj_bull: bool, score: float)
    """
    if len(close) < PARAMS["kdj_n"]:
        logger.warning(f"Insufficient data for KDJ: need {PARAMS['kdj_n']}, got {len(close)}")
        return False, 0.0

    try:
        kdj_df = calculate_kdj_internal(high, low, close)

        k = kdj_df["k"].iloc[-1]
        d = kdj_df["d"].iloc[-1]
        j = kdj_df["j"].iloc[-1]

        if len(kdj_df) >= 2:
            k_prev = kdj_df["k"].iloc[-2]
            j_prev = kdj_df["j"].iloc[-2]
            j_rising = j > j_prev
        else:
            j_rising = False

        bullish = (k > d) and (j > 20) and (j > k or j_rising)
        score = 15.0 if bullish else 0.0

        if bullish:
            logger.info(f"KDJ bullish: k={k:.2f}, d={d:.2f}, j={j:.2f}")

        return bullish, score

    except Exception as e:
        logger.error(f"Error computing KDJ: {e}")
        return False, 0.0


def calculate_rsi_internal(close: pd.Series, period: int = None) -> pd.Series:
    """Calculate RSI indicator.

    Args:
        close: Closing price series
        period: RSI period

    Returns:
        RSI series
    """
    if period is None:
        period = PARAMS["rsi_period"]

    delta = close.diff()

    gain = delta.where(delta > 0, 0)
    loss = -delta.where(delta < 0, 0)

    avg_gain = gain.ewm(alpha=1/period, min_periods=period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1/period, min_periods=period, adjust=False).mean()

    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))

    return rsi


def compute_rsi(close: pd.Series, period: Optional[int] = None) -> Tuple[bool, float]:
    """Compute RSI indicator.

    Args:
        close: Series of closing prices
        period: RSI period (optional, uses config default)

    Returns:
        Tuple of (rsi_bull: bool, score: float)
    """
    if period is None:
        period = PARAMS["rsi_period"]

    if len(close) < period + 1:
        logger.warning(f"Insufficient data for RSI: need {period + 1}, got {len(close)}")
        return False, 0.0

    try:
        rsi_series = calculate_rsi_internal(close, period)

        rsi = rsi_series.iloc[-1]
        threshold = PARAMS["rsi_threshold"]

        if len(rsi_series) >= 2:
            rsi_prev = rsi_series.iloc[-2]
            rsi_rising = rsi > rsi_prev
        else:
            rsi_rising = False

        bullish = (rsi > threshold) and rsi_rising
        score = 10.0 if bullish else 0.0

        if bullish:
            logger.info(f"RSI bullish: rsi={rsi:.2f}, threshold={threshold}")

        return bullish, score

    except Exception as e:
        logger.error(f"Error computing RSI: {e}")
        return False, 0.0


if __name__ == "__main__":
    setup_logging()

    np.random.seed(42)
    n = 50
    base_price = 1.0
    prices = [base_price]
    for _ in range(n - 1):
        change = np.random.randn() * 0.02
        prices.append(prices[-1] * (1 + change))

    close = pd.Series(prices, name="close")
    high = pd.Series([p * (1 + abs(np.random.randn() * 0.01)) for p in prices], name="high")
    low = pd.Series([p * (1 - abs(np.random.randn() * 0.01)) for p in prices], name="low")

    print(f"Testing with {n} price points")
    print(f"Close price range: {close.min():.4f} - {close.max():.4f}")
    print()

    macd_bull, macd_score = compute_macd(close)
    print(f"MACD: bullish={macd_bull}, score={macd_score}")

    kdj_bull, kdj_score = compute_kdj(high, low, close)
    print(f"KDJ: bullish={kdj_bull}, score={kdj_score}")

    rsi_bull, rsi_score = compute_rsi(close)
    print(f"RSI: bullish={rsi_bull}, score={rsi_score}")
