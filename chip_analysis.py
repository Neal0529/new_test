import json
import logging
import os
from typing import Dict, Optional, Tuple

LOG_DIR = "logs"
CONFIG_FILE = "config/dynamic_params.json"

DEFAULT_PARAMS = {
    "profit_threshold": 0.40,
    "concentration_threshold": 15.0
}


def setup_logging():
    """Configure logging to console and file."""
    os.makedirs(LOG_DIR, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler(f"{LOG_DIR}/chip_analysis.log")
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


def evaluate_chip(profit_ratio: Optional[float], concentration: Optional[float], thresholds: Optional[Dict] = None) -> Tuple[bool, int]:
    """Evaluate chip (筹码) distribution.

    Args:
        profit_ratio: Percentage of shares in profit (0.0 to 1.0)
        concentration: 90% cost concentration (0.0 to 100.0)
        thresholds: Optional dict with profit_threshold and concentration_threshold

    Returns:
        Tuple of (is_ok: bool, score: int)
    """
    if thresholds is None:
        thresholds = PARAMS.copy()

    profit_threshold = thresholds.get("profit_threshold", PARAMS["profit_threshold"])
    concentration_threshold = thresholds.get("concentration_threshold", PARAMS["concentration_threshold"])

    if profit_ratio is None or concentration is None:
        logger.warning(f"Missing chip data: profit_ratio={profit_ratio}, concentration={concentration}")
        return False, 0

    if profit_ratio < 0 or profit_ratio > 1:
        logger.warning(f"profit_ratio out of bounds: {profit_ratio} (expected 0-1)")
    if concentration < 0 or concentration > 100:
        logger.warning(f"concentration out of bounds: {concentration} (expected 0-100)")

    condition_a = profit_ratio < profit_threshold
    condition_b = concentration < concentration_threshold

    is_ok = condition_a and condition_b
    score = 10 if is_ok else 0

    logger.info(f"Chip analysis: profit_ratio={profit_ratio:.3f}, concentration={concentration:.2f}, "
                f"thresholds=[profit={profit_threshold}, conc={concentration_threshold}], "
                f"conditions=[A={condition_a}, B={condition_b}], result={is_ok}, score={score}")

    return is_ok, score


if __name__ == "__main__":
    setup_logging()

    print("=== Chip Analysis Tests ===\n")

    test_cases = [
        (0.35, 12.0, None, "Normal: should pass"),
        (0.50, 12.0, None, "High profit: should fail"),
        (0.35, 20.0, None, "High concentration: should fail"),
        (0.50, 20.0, None, "Both high: should fail"),
        (None, 12.0, None, "Missing profit_ratio: should fail"),
        (0.35, None, None, "Missing concentration: should fail"),
        (0.35, 12.0, {"profit_threshold": 0.30, "concentration_threshold": 10.0}, "Custom thresholds: should fail"),
        (0.25, 8.0, None, "Low profit + low conc: should pass"),
    ]

    for profit, conc, thresholds, description in test_cases:
        is_ok, score = evaluate_chip(profit, conc, thresholds)
        result = "PASS" if is_ok else "FAIL"
        print(f"{description}")
        print(f"  Input: profit_ratio={profit}, concentration={conc}")
        print(f"  Result: {result}, score={score}")
        print()

    print(f"Default thresholds: profit_threshold={PARAMS['profit_threshold']}, "
          f"concentration_threshold={PARAMS['concentration_threshold']}")
