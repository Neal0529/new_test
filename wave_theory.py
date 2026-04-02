import json
import logging
import os
from typing import List, Optional, Tuple

import numpy as np

LOG_DIR = "logs"
CONFIG_FILE = "config/dynamic_params.json"

DEFAULT_PARAMS = {
    "wave_fib_low": 0.382,
    "wave_fib_high": 0.618
}

SCIPY_AVAILABLE = False
try:
    from scipy.signal import argrelextrema
    SCIPY_AVAILABLE = True
except ImportError:
    argrelextrema = None


def setup_logging():
    """Configure logging to console and file."""
    os.makedirs(LOG_DIR, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler(f"{LOG_DIR}/wave_theory.log")
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


def _find_peaks_troughs(prices: np.ndarray, order: int = 10) -> Tuple[np.ndarray, np.ndarray]:
    """Find local maxima and minima using scipy or fallback.

    Args:
        prices: Price array
        order: Lookback period for extrema

    Returns:
        Tuple of (peak_indices, trough_indices)
    """
    if SCIPY_AVAILABLE and argrelextrema is not None:
        try:
            peaks = argrelextrema(prices, np.greater, order=order)[0]
            troughs = argrelextrema(prices, np.less, order=order)[0]
            return peaks, troughs
        except Exception as e:
            logger.warning(f"scipy argrelextrema failed: {e}")

    peaks_list = []
    troughs_list = []

    for i in range(order, len(prices) - order):
        window = prices[i - order:i + order + 1]
        if prices[i] == np.max(window):
            peaks_list.append(i)
        if prices[i] == np.min(window):
            troughs_list.append(i)

    return np.array(peaks_list), np.array(troughs_list)


def detect_wave_pattern(close_prices: np.ndarray, fib_low: Optional[float] = None, fib_high: Optional[float] = None) -> Tuple[bool, int]:
    """Detect Elliott wave C-wave retracement pattern.

    Args:
        close_prices: 1D numpy array of closing prices (at least 50)
        fib_low: Fibonacci low threshold (optional, uses config)
        fib_high: Fibonacci high threshold (optional, uses config)

    Returns:
        Tuple of (is_ready: bool, score: int)
    """
    if fib_low is None:
        fib_low = PARAMS["wave_fib_low"]
    if fib_high is None:
        fib_high = PARAMS["wave_fib_high"]

    n = len(close_prices)
    if n < 50:
        logger.warning(f"Insufficient data: {n} < 50")
        return False, 0

    peaks, troughs = _find_peaks_troughs(close_prices, order=10)

    if len(peaks) == 0 or len(troughs) == 0:
        logger.debug("No peaks or troughs found")
        return False, 0

    current_close = close_prices[-1]
    current_idx = n - 1

    recent_peaks = peaks[peaks < current_idx - 5]
    if len(recent_peaks) == 0:
        logger.debug("No recent peaks")
        return False, 0

    last_peak_idx = recent_peaks[-1]
    last_peak_price = close_prices[last_peak_idx]

    troughs_after_peak = troughs[(troughs > last_peak_idx) & (troughs < current_idx)]
    if len(troughs_after_peak) == 0:
        logger.debug("No trough after last peak")
        return False, 0

    trough_prices = close_prices[troughs_after_peak]
    min_trough_idx_local = np.argmin(trough_prices)
    last_trough_idx = troughs_after_peak[min_trough_idx_local]
    last_trough_price = close_prices[last_trough_idx]

    wave_range = last_peak_price - last_trough_price
    if wave_range <= 0:
        logger.debug("Invalid wave range (negative)")
        return False, 0

    retracement = (last_peak_price - current_close) / wave_range

    logger.info(f"Wave: peak_idx={last_peak_idx}, trough_idx={last_trough_idx}, "
                f"retracement={retracement:.3f}, fib=[{fib_low}, {fib_high}]")

    in_fib_zone = fib_low <= retracement <= fib_high

    recent_max = np.max(close_prices[max(0, current_idx - 3):current_idx])
    if current_idx >= 1:
        recent_max = max(recent_max, close_prices[current_idx - 1])
    breakout = current_close >= recent_max

    is_ready = in_fib_zone and breakout

    if is_ready:
        logger.info(f"Wave pattern READY: retracement={retracement:.3f}, breakout={breakout}")
        return True, 15

    logger.debug(f"Not ready: retracement={retracement:.3f}, in_fib={in_fib_zone}, breakout={breakout}")
    return False, 0


if __name__ == "__main__":
    setup_logging()

    np.random.seed(42)
    prices = [1.0 + np.random.randn() * 0.005 for _ in range(50)]
    for i in range(50, 60):
        prices.append(prices[-1] * 1.01)

    prices.append(1.63)
    prices.append(1.65)

    for i in range(60, 80):
        prices.append(prices[-1] * 0.99)

    prices.append(1.0)

    for i in range(81, 97):
        target = 1.65 - (1.65 - 1.0) * 0.5
        prices.append(target + (i - 81) * 0.001)

    prices.append(1.325)
    prices.append(1.330)
    prices.append(1.340)
    prices.append(1.350)

    close_prices = np.array(prices)

    peak_price = close_prices[61]
    trough_price = close_prices[79]
    current_price = close_prices[-1]
    retracement = (peak_price - current_price) / (peak_price - trough_price)

    print(f"Test: peak={peak_price:.3f}, trough={trough_price:.3f}, current={current_price:.3f}")
    print(f"Expected retracement: ~0.5 (fib zone 0.382-0.618)")
    print()

    is_ready, score = detect_wave_pattern(close_prices)
    print(f"Result: is_ready={is_ready}, score={score}")
