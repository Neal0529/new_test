import json
import logging
import os
from datetime import datetime, timedelta
from typing import Dict, Optional

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
            logging.FileHandler(f"{LOG_DIR}/signal_generator.log")
        ]
    )


logger = logging.getLogger(__name__)


def load_config() -> dict:
    """Load configuration parameters."""
    config = {
        "total_score_threshold": 70,
        "stop_loss": -0.06,
        "take_profit_half": 0.06,
        "take_profit_full": 0.10,
        "holding_days_min": 30,
        "holding_days_max": 90
    }

    try:
        config_file = os.path.join(CONFIG_DIR, "config.yaml")
        if os.path.exists(config_file):
            with open(config_file, "r", encoding="utf-8") as f:
                yaml_config = yaml.safe_load(f)
                global_config = yaml_config.get("global", {})
                config["stop_loss"] = global_config.get("stop_loss", -0.06)
                config["take_profit_half"] = global_config.get("take_profit_half", 0.06)
                config["take_profit_full"] = global_config.get("take_profit_full", 0.10)
                config["holding_days_min"] = global_config.get("holding_days_min", 30)
                config["holding_days_max"] = global_config.get("holding_days_max", 90)

        params_file = os.path.join(CONFIG_DIR, "dynamic_params.json")
        if os.path.exists(params_file):
            with open(params_file, "r") as f:
                params = json.load(f)
                config["total_score_threshold"] = params.get("total_score_threshold", 70)

        logger.info(f"Loaded config: {config}")
    except Exception as e:
        logger.warning(f"Failed to load config: {e}")

    return config


CONFIG = load_config()


def _calculate_holding_days(open_date_str: Optional[str]) -> int:
    """Calculate holding days from open date.

    Args:
        open_date_str: Open date in YYYY-MM-DD format

    Returns:
        Number of holding days
    """
    if not open_date_str:
        return 0

    try:
        open_date = datetime.strptime(open_date_str, "%Y-%m-%d")
        today = datetime.now()
        return (today - open_date).days
    except Exception:
        return 0


def _calculate_pnl(current_price: float, cost: float) -> float:
    """Calculate unrealized P&L percentage.

    Args:
        current_price: Current ETF price
        cost: Average cost basis

    Returns:
        P&L percentage
    """
    if cost <= 0:
        return 0.0
    return (current_price - cost) / cost


def generate_signal(etf_code: str, tech_scores: Dict, news_data: Dict, position: Dict) -> Dict:
    """Generate trading signal for an ETF.

    Args:
        etf_code: ETF code string
        tech_scores: Dictionary with technical analysis scores
        news_data: Dictionary from sentiment analyzer
        position: Position dict with shares, cost, open_date, position_value

    Returns:
        Dict with action, reason, score_details
    """
    required_tech_keys = ["macd_bull", "kdj_bull", "total_tech_score", "current_price"]
    for key in required_tech_keys:
        if key not in tech_scores:
            logger.error(f"Missing required key in tech_scores: {key}")
            return {"action": "HOLD", "reason": "missing_tech_data", "score_details": {}}

    shares = position.get("shares", 0)
    cost = position.get("cost", 0)
    open_date = position.get("open_date")
    holding_days = _calculate_holding_days(open_date)

    current_price = tech_scores.get("current_price", 0)
    if current_price <= 0:
        logger.warning("No current price available")
        return {"action": "HOLD", "reason": "no_price", "score_details": {}}

    pnl = _calculate_pnl(current_price, cost) if shares > 0 and cost > 0 else 0.0

    logger.info(f"Generating signal for {etf_code}: shares={shares}, holding_days={holding_days}, pnl={pnl:.2%}")

    action = "HOLD"
    reason = "default"

    if shares > 0:
        if pnl <= CONFIG["stop_loss"]:
            action = "CLOSE_ALL"
            reason = f"stop_loss triggered: pnl={pnl:.2%}"
        elif pnl >= CONFIG["take_profit_full"] and holding_days >= CONFIG["holding_days_min"]:
            action = "CLOSE_ALL"
            reason = f"take_profit_full reached: pnl={pnl:.2%}, days={holding_days}"
        elif pnl >= CONFIG["take_profit_half"] and holding_days >= CONFIG["holding_days_min"]:
            action = "REDUCE_HALF"
            reason = f"take_profit_half reached: pnl={pnl:.2%}, days={holding_days}"
        elif news_data.get("event_flag") == "strong_bear":
            action = "CLOSE_ALL"
            reason = "strong_bear news event"
        elif holding_days >= CONFIG["holding_days_max"]:
            action = "CLOSE_ALL"
            reason = f"max_holding_days reached: {holding_days}"

    if action == "HOLD":
        if shares == 0:
            if not tech_scores.get("macd_bull", False) or not tech_scores.get("kdj_bull", False):
                action = "HOLD"
                reason = "macd_kdj_not_bullish"

            if action == "HOLD":
                daily_sentiment = news_data.get("daily_sentiment", 0.0)
                keyword_adj = news_data.get("keyword_adj", 0.0)
                event_flag = news_data.get("event_flag", "neutral")

                final_score = tech_scores.get("total_tech_score", 0)
                final_score += daily_sentiment * 20
                final_score += keyword_adj * 15

                if event_flag == "strong_bull":
                    final_score += 20
                elif event_flag == "strong_bear":
                    final_score = 0

                threshold = CONFIG["total_score_threshold"]

                if final_score >= threshold:
                    action = "BUY_2W"
                    reason = f"entry signal: score={final_score:.1f} >= threshold={threshold}"
                else:
                    action = "HOLD"
                    reason = f"insufficient score: {final_score:.1f} < {threshold}"

        else:
            if holding_days >= 5 and pnl > -0.02 and news_data.get("daily_sentiment", 0) > 0:
                if tech_scores.get("kdj_bull", False):
                    current_position_value = position.get("position_value", 0)
                    if current_position_value <= 40000:
                        action = "ADD_2W"
                        reason = f"first add: holding_days={holding_days}, pnl={pnl:.2%}"

            if action == "HOLD" and holding_days >= 10 and pnl > 0.03:
                current_position_value = position.get("position_value", 0)
                if current_position_value <= 60000:
                    action = "ADD_2W"
                    reason = f"second add: holding_days={holding_days}, pnl={pnl:.2%}"

    result = {
        "action": action,
        "reason": reason,
        "score_details": {
            "etf_code": etf_code,
            "shares": shares,
            "holding_days": holding_days,
            "pnl": round(pnl, 4),
            "total_tech_score": tech_scores.get("total_tech_score", 0),
            "daily_sentiment": news_data.get("daily_sentiment", 0),
            "event_flag": news_data.get("event_flag", "neutral"),
            "keyword_adj": news_data.get("keyword_adj", 0)
        }
    }

    logger.info(f"Signal for {etf_code}: action={action}, reason={reason}")
    return result


if __name__ == "__main__":
    setup_logging()

    print("=== Signal Generator Tests ===\n")

    position_empty = {"shares": 0, "cost": 0, "open_date": None, "position_value": 0}
    position_open = {"shares": 10000, "cost": 1.0, "open_date": "2026-03-01", "position_value": 20000}

    tech_scores_bull = {
        "macd_bull": True, "macd_score": 20,
        "kdj_bull": True, "kdj_score": 15,
        "rsi_bull": True, "rsi_score": 10,
        "wave_ready": True, "wave_score": 15,
        "volume_price_score": 10,
        "chip_ok": True, "chip_score": 10,
        "ma_bull": True, "ma_score": 10,
        "total_tech_score": 90,
        "current_price": 1.0
    }

    news_bull = {
        "daily_sentiment": 0.3,
        "sentiment_trend": 0.25,
        "event_flag": "strong_bull",
        "keyword_adj": 0.2
    }

    news_bear = {
        "daily_sentiment": -0.3,
        "sentiment_trend": -0.25,
        "event_flag": "strong_bear",
        "keyword_adj": -0.2
    }

    news_neutral = {
        "daily_sentiment": 0.0,
        "sentiment_trend": 0.0,
        "event_flag": "neutral",
        "keyword_adj": 0.0
    }

    test_cases = [
        ("512000", tech_scores_bull, news_bull, position_empty, "Entry: no position, bullish tech+news"),
        ("512000", tech_scores_bull, news_neutral, position_empty, "Hold: no position, neutral news"),
        ("512000", tech_scores_bull, news_bull, {**position_open, "open_date": "2026-01-01", "position_value": 20000}, "Exit: max holding days"),
        ("512000", tech_scores_bull, news_bull, {**position_open, "position_value": 20000, "cost": 1.08}, "Exit: take profit full"),
        ("512000", tech_scores_bull, news_bull, {**position_open, "position_value": 20000, "cost": 1.04}, "Reduce half: take profit half"),
        ("512000", tech_scores_bull, news_bear, position_open, "Exit: strong bear news"),
        ("512000", tech_scores_bull, news_neutral, {**position_open, "cost": 0.94}, "Exit: stop loss"),
        ("512000", {**tech_scores_bull, "kdj_bull": False}, news_bull, position_empty, "Hold: kdj not bullish"),
    ]

    for etf, tech, news, pos, description in test_cases:
        if "cost" in pos and "current_price" not in tech:
            tech = {**tech, "current_price": tech.get("current_price", 1.0)}
        elif "current_price" not in tech:
            tech = {**tech, "current_price": 1.0}

        result = generate_signal(etf, tech, news, pos)
        print(f"{description}")
        print(f"  Action: {result['action']}, Reason: {result['reason']}")
        print()
