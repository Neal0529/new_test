import json
import logging
import os
from typing import Dict

import yaml

LOG_DIR = "logs"
CONFIG_DIR = "config"


def setup_logging():
    """Configure logging to console and file."""
    os.makedirs(LOG_DIR, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler(f"{LOG_DIR}/optimizer.log")
        ]
    )


logger = logging.getLogger(__name__)


def load_config() -> dict:
    """Load configuration."""
    config = {"win_rate_target": 0.80}

    try:
        config_file = os.path.join(CONFIG_DIR, "config.yaml")
        if os.path.exists(config_file):
            with open(config_file, "r", encoding="utf-8") as f:
                yaml_config = yaml.safe_load(f)
                config["win_rate_target"] = yaml_config.get("global", {}).get("win_rate_target", 0.80)
                logger.info(f"Loaded win_rate_target: {config['win_rate_target']}")
    except Exception as e:
        logger.warning(f"Failed to load config: {e}")

    return config


CONFIG = load_config()


def _clamp(value: float, min_val: float, max_val: float) -> float:
    """Clamp value within bounds."""
    return max(min_val, min(max_val, value))


def _tighten_params(params: Dict) -> Dict:
    """Tighten parameters to increase signal quality."""
    params = params.copy()

    params["profit_threshold"] = _clamp(
        params.get("profit_threshold", 0.40) - 0.02,
        0.20, 0.50
    )

    params["concentration_threshold"] = _clamp(
        params.get("concentration_threshold", 15.0) - 1.0,
        5.0, 25.0
    )

    params["total_score_threshold"] = _clamp(
        params.get("total_score_threshold", 70) + 1,
        60, 85
    )

    params["rsi_threshold"] = _clamp(
        params.get("rsi_threshold", 30) + 2,
        20, 50
    )

    params["wave_fib_low"] = _clamp(
        params.get("wave_fib_low", 0.382) + 0.02,
        0.30, 0.45
    )

    params["wave_fib_high"] = _clamp(
        params.get("wave_fib_high", 0.618) - 0.02,
        0.55, 0.70
    )

    if params["wave_fib_high"] <= params["wave_fib_low"]:
        params["wave_fib_high"] = params["wave_fib_low"] + 0.10

    logger.info(f"Tightened params: profit={params['profit_threshold']}, "
                f"conc={params['concentration_threshold']}, score={params['total_score_threshold']}, "
                f"rsi={params['rsi_threshold']}, fib=[{params['wave_fib_low']}, {params['wave_fib_high']}]")

    return params


def _relax_params(params: Dict) -> Dict:
    """Relax parameters to increase signal frequency."""
    params = params.copy()

    params["profit_threshold"] = _clamp(
        params.get("profit_threshold", 0.40) + 0.02,
        0.20, 0.50
    )

    params["concentration_threshold"] = _clamp(
        params.get("concentration_threshold", 15.0) + 1.0,
        5.0, 25.0
    )

    params["total_score_threshold"] = _clamp(
        params.get("total_score_threshold", 70) - 1,
        60, 85
    )

    params["rsi_threshold"] = _clamp(
        params.get("rsi_threshold", 30) - 2,
        20, 50
    )

    params["wave_fib_low"] = _clamp(
        params.get("wave_fib_low", 0.382) - 0.02,
        0.30, 0.45
    )

    params["wave_fib_high"] = _clamp(
        params.get("wave_fib_high", 0.618) + 0.02,
        0.55, 0.70
    )

    logger.info(f"Relaxed params: profit={params['profit_threshold']}, "
                f"conc={params['concentration_threshold']}, score={params['total_score_threshold']}, "
                f"rsi={params['rsi_threshold']}, fib=[{params['wave_fib_low']}, {params['wave_fib_high']}]")

    return params


def optimize_parameters(backtest_result: Dict, current_params: Dict) -> Dict:
    """Optimize trading parameters based on backtest results.

    Args:
        backtest_result: Dictionary with win_rate and other backtest metrics
        current_params: Current parameter values

    Returns:
        Updated parameters dict
    """
    if "win_rate" not in backtest_result:
        logger.error("Missing win_rate in backtest_result")
        return current_params

    win_rate = backtest_result["win_rate"]
    target = CONFIG.get("win_rate_target", 0.80)

    logger.info(f"Optimizing: win_rate={win_rate:.2%}, target={target:.2%}")

    params = current_params.copy()

    if win_rate < target:
        logger.info(f"Win rate {win_rate:.2%} below target {target:.2%}, tightening parameters")
        params = _tighten_params(params)
    elif win_rate > target + 0.05:
        logger.info(f"Win rate {win_rate:.2%} well above target {target:.2%}, relaxing parameters")
        params = _relax_params(params)
    else:
        logger.info(f"Win rate {win_rate:.2%} within acceptable range, keeping parameters unchanged")

    logger.info(f"Optimization complete: {params}")
    return params


if __name__ == "__main__":
    setup_logging()

    print("=== Parameter Optimizer Test ===\n")

    current_params = {
        "profit_threshold": 0.40,
        "concentration_threshold": 15.0,
        "total_score_threshold": 70,
        "rsi_threshold": 30,
        "wave_fib_low": 0.382,
        "wave_fib_high": 0.618,
        "macd_fast": 12,
        "macd_slow": 26,
        "macd_signal": 9,
        "kdj_n": 9,
        "kdj_m1": 3,
        "kdj_m2": 3,
        "rsi_period": 14
    }

    print(f"Initial params:")
    for k, v in current_params.items():
        print(f"  {k}: {v}")
    print()

    test_cases = [
        ({"win_rate": 0.75}, "Too low (75%) - should tighten"),
        ({"win_rate": 0.82}, "Acceptable (82%) - should stay"),
        ({"win_rate": 0.88}, "Too high (88%) - should relax"),
        ({"win_rate": 0.60}, "Very low (60%) - tighten more"),
    ]

    for result, description in test_cases:
        print(f"Test: {description}")
        new_params = optimize_parameters(result, current_params)
        print(f"  Result win_rate: {result['win_rate']:.0%}")
        print(f"  Key changes:")
        print(f"    profit_threshold: {current_params.get('profit_threshold')} -> {new_params.get('profit_threshold')}")
        print(f"    total_score_threshold: {current_params.get('total_score_threshold')} -> {new_params.get('total_score_threshold')}")
        print(f"    rsi_threshold: {current_params.get('rsi_threshold')} -> {new_params.get('rsi_threshold')}")
        print()
        current_params = new_params
