import argparse
import json
import logging
import os
from datetime import date, datetime, timedelta
from typing import Dict, List

import pandas as pd
import yaml

from utils import is_trading_day

LOG_DIR = "logs"
CONFIG_DIR = "config"
DATA_DIR = "data"


def setup_logging():
    """Configure logging to console and file."""
    os.makedirs(LOG_DIR, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler(f"{LOG_DIR}/scheduler.log")
        ]
    )


logger = logging.getLogger(__name__)


def load_config() -> dict:
    """Load ETF and global configuration."""
    config_file = os.path.join(CONFIG_DIR, "config.yaml")
    try:
        with open(config_file, "r", encoding="utf-8") as f:
            return yaml.safe_load(f)
    except Exception as e:
        logger.error(f"Failed to load config: {e}")
        return {}


def load_positions() -> dict:
    """Load current positions."""
    pos_file = os.path.join(CONFIG_DIR, "positions.json")
    try:
        with open(pos_file, "r") as f:
            return json.load(f)
    except Exception:
        return {}


def save_positions(positions: dict):
    """Save positions to file."""
    pos_file = os.path.join(CONFIG_DIR, "positions.json")
    try:
        with open(pos_file, "w") as f:
            json.dump(positions, f, indent=2)
        logger.info("Saved positions to file")
    except Exception as e:
        logger.error(f"Failed to save positions: {e}")


def load_dynamic_params() -> dict:
    """Load dynamic parameters."""
    params_file = os.path.join(CONFIG_DIR, "dynamic_params.json")
    try:
        with open(params_file, "r") as f:
            return json.load(f)
    except Exception:
        return {}


def save_dynamic_params(params: dict):
    """Save dynamic parameters."""
    params_file = os.path.join(CONFIG_DIR, "dynamic_params.json")
    try:
        with open(params_file, "w") as f:
            json.dump(params, f, indent=2)
        logger.info("Saved dynamic params")
    except Exception as e:
        logger.error(f"Failed to save dynamic params: {e}")


def analyze_etf(etf_info: dict, target_date: str, positions: dict) -> Dict:
    """Analyze a single ETF and generate signal."""
    from data_fetcher import fetch_etf_data, fetch_chip_data
    from quality_checker import check_data_quality
    from indicators import compute_macd, compute_kdj, compute_rsi
    from wave_theory import detect_wave_pattern
    from volume_price import analyze_volume_price
    from chip_analysis import evaluate_chip
    from news_collector import fetch_news
    from sentiment_analyzer import analyze_sentiment
    from signal_generator import generate_signal

    etf_code = etf_info.get("code", "")
    sector = etf_info.get("sector", "")

    logger.info(f"Analyzing ETF: {etf_code} ({etf_info.get('name', '')})")

    start_date = (datetime.now() - timedelta(days=730)).strftime("%Y-%m-%d")

    df = fetch_etf_data(etf_code, start_date, target_date)

    if df.empty:
        logger.warning(f"No data for {etf_code}, skipping")
        return None

    df, status = check_data_quality(df)

    if status == "error":
        logger.error(f"Data quality error for {etf_code}, skipping")
        return None

    if len(df) < 20:
        logger.warning(f"Insufficient data for {etf_code}, skipping")
        return None

    current_price = df.iloc[-1]["close"]
    close_series = df["close"]
    high_series = df["high"]
    low_series = df["low"]
    volume_series = df["volume"]

    try:
        macd_bull, macd_score = compute_macd(close_series)
    except Exception as e:
        logger.warning(f"MACD error: {e}")
        macd_bull, macd_score = False, 0

    try:
        kdj_bull, kdj_score = compute_kdj(high_series, low_series, close_series)
    except Exception as e:
        logger.warning(f"KDJ error: {e}")
        kdj_bull, kdj_score = False, 0

    try:
        rsi_bull, rsi_score = compute_rsi(close_series)
    except Exception as e:
        logger.warning(f"RSI error: {e}")
        rsi_bull, rsi_score = False, 0

    try:
        close_arr = close_series.values
        wave_ready, wave_score = detect_wave_pattern(close_arr)
    except Exception as e:
        logger.warning(f"Wave error: {e}")
        wave_ready, wave_score = False, 0

    try:
        vol_score, vol_details = analyze_volume_price(close_series, volume_series)
    except Exception as e:
        logger.warning(f"Volume error: {e}")
        vol_score, vol_details = 0, {}

    chip_ok, chip_score = False, 0
    try:
        chip_data = fetch_chip_data(etf_code, target_date)
        profit_ratio = chip_data.get("profit_ratio")
        concentration = chip_data.get("concentration_90")
        if profit_ratio is not None and concentration is not None:
            chip_ok, chip_score = evaluate_chip(profit_ratio, concentration)
    except Exception as e:
        logger.warning(f"Chip data error: {e}")

    ma_bull = False
    ma_score = 0
    try:
        if len(close_series) >= 20:
            ma_bull = close_series.iloc[-1] > close_series.rolling(20).mean().iloc[-1]
            ma_score = 10 if ma_bull else 0
    except Exception:
        pass

    total_tech_score = macd_score + kdj_score + rsi_score + wave_score + vol_score + chip_score + ma_score

    news_data = {
        "daily_sentiment": 0.0,
        "sentiment_trend": 0.0,
        "event_flag": "neutral",
        "keyword_adj": 0.0
    }

    try:
        keywords = [sector] if sector else []
        news_list = fetch_news(keywords, target_date)
        news_data = analyze_sentiment(news_list)
    except Exception as e:
        logger.warning(f"News error: {e}")

    tech_scores = {
        "macd_bull": macd_bull, "macd_score": macd_score,
        "kdj_bull": kdj_bull, "kdj_score": kdj_score,
        "rsi_bull": rsi_bull, "rsi_score": rsi_score,
        "wave_ready": wave_ready, "wave_score": wave_score,
        "volume_price_score": vol_score,
        "chip_ok": chip_ok, "chip_score": chip_score,
        "ma_bull": ma_bull, "ma_score": ma_score,
        "total_tech_score": total_tech_score,
        "current_price": current_price
    }

    position = positions.get(etf_code, {
        "shares": 0,
        "cost": 0,
        "open_date": None,
        "position_value": 0
    })

    if position.get("shares", 0) > 0:
        position["position_value"] = position["shares"] * current_price

    signal = generate_signal(etf_code, tech_scores, news_data, position)

    result = {
        "etf_code": etf_code,
        "etf_name": etf_info.get("name", ""),
        "current_position": position.get("position_value", 0),
        "action": signal.get("action", "HOLD"),
        "reason": signal.get("reason", ""),
        "tech_score": total_tech_score,
        "sentiment_score": news_data.get("daily_sentiment", 0),
        "final_score": total_tech_score + news_data.get("daily_sentiment", 0) * 20 + news_data.get("keyword_adj", 0) * 15,
        "current_price": current_price
    }

    logger.info(f"Signal for {etf_code}: {result['action']} (score={result['final_score']})")

    return result


def run_daily_analysis(target_date: date = None, optimize: bool = False):
    """Run daily analysis for all ETFs.

    Args:
        target_date: Target date for analysis (defaults to today)
        optimize: Whether to run backtest and optimization
    """
    if target_date is None:
        target_date = datetime.now().date()

    if not is_trading_day(target_date):
        logger.info(f"{target_date} is not a trading day, skipping analysis")
        return

    target_date_str = target_date.strftime("%Y-%m-%d")

    logger.info(f"=== Starting daily analysis for {target_date_str} ===")

    config = load_config()
    etf_list = config.get("etfs", [])

    if not etf_list:
        logger.error("No ETFs configured")
        return

    positions = load_positions()

    signals = []
    for etf_info in etf_list:
        try:
            result = analyze_etf(etf_info, target_date_str, positions)
            if result:
                signals.append(result)
        except Exception as e:
            logger.error(f"Failed to analyze ETF {etf_info.get('code')}: {e}")
            continue

    news_summary = {}
    for sig in signals:
        etf_code = sig.get("etf_code", "")
        etf_name = sig.get("etf_name", "")
        news_summary[etf_code] = [
            {"title": f"分析报告: {sig['action']}", "sentiment": sig.get("sentiment_score", 0)}
        ]

    from report_generator import generate_report
    report_path = generate_report(signals, news_summary, target_date)

    for sig in signals:
        etf_code = sig["etf_code"]
        action = sig["action"]
        current_price = sig.get("current_price", 0)

        if etf_code not in positions:
            positions[etf_code] = {
                "shares": 0,
                "cost": 0,
                "open_date": None,
                "position_value": 0
            }

        pos = positions[etf_code]

        if action == "BUY_2W" and pos.get("shares", 0) == 0:
            shares = 20000 / current_price
            pos["shares"] = shares
            pos["cost"] = current_price
            pos["open_date"] = target_date_str
            pos["position_value"] = 20000
            logger.info(f"Executed BUY for {etf_code}: {shares:.2f} shares at {current_price}")

        elif action == "ADD_2W" and pos.get("shares", 0) > 0:
            additional_shares = 20000 / current_price
            total_shares = pos["shares"] + additional_shares
            new_cost = ((pos["shares"] * pos["cost"]) + (additional_shares * current_price)) / total_shares
            pos["shares"] = total_shares
            pos["cost"] = new_cost
            pos["position_value"] = total_shares * current_price
            logger.info(f"Executed ADD for {etf_code}")

        elif action == "REDUCE_HALF" and pos.get("shares", 0) > 0:
            pos["shares"] = pos["shares"] / 2
            pos["position_value"] = pos["shares"] * current_price
            logger.info(f"Executed REDUCE for {etf_code}")

        elif action == "CLOSE_ALL" and pos.get("shares", 0) > 0:
            pos["shares"] = 0
            pos["cost"] = 0
            pos["open_date"] = None
            pos["position_value"] = 0
            logger.info(f"Executed CLOSE for {etf_code}")

    save_positions(positions)

    if optimize or target_date.weekday() >= 5:
        logger.info("Running backtest and optimization...")
        try:
            run_optimization(target_date)
        except Exception as e:
            logger.error(f"Optimization failed: {e}")

    logger.info(f"=== Daily analysis complete ===")


def run_optimization(target_date: date):
    """Run backtest and parameter optimization."""
    from backtest_engine import run_backtest
    from parameter_optimizer import optimize_parameters

    config = load_config()
    etf_list = config.get("etfs", [])

    if not etf_list:
        return

    end_date = target_date.strftime("%Y-%m-%d")
    start_date = (target_date - timedelta(days=365)).strftime("%Y-%m-%d")

    win_rates = []

    for etf_info in etf_list[:2]:
        etf_code = etf_info.get("code")
        try:
            result = run_backtest(etf_code, start_date, end_date, use_news=False)
            wr = result.get("win_rate", 0)
            win_rates.append(wr)
            logger.info(f"Backtest {etf_code}: win_rate={wr:.2%}")
        except Exception as e:
            logger.error(f"Backtest failed for {etf_code}: {e}")

    if not win_rates:
        logger.warning("No backtest results")
        return

    avg_win_rate = sum(win_rates) / len(win_rates)
    logger.info(f"Average win rate: {avg_win_rate:.2%}")

    if avg_win_rate < 0.80 or avg_win_rate > 0.85:
        current_params = load_dynamic_params()
        backtest_result = {"win_rate": avg_win_rate}
        new_params = optimize_parameters(backtest_result, current_params)
        save_dynamic_params(new_params)
        logger.info(f"Parameters optimized: win_rate={avg_win_rate:.2%}")
    else:
        logger.info("Win rate within target, no parameter change needed")


def schedule_jobs():
    """Set up scheduled daily jobs (placeholder)."""
    logger.info("Scheduler configured for daily 15:30 run")


def run():
    """Run the scheduler loop."""
    schedule_jobs()
    logger.info("Scheduler started, waiting for scheduled runs...")


if __name__ == "__main__":
    setup_logging()

    parser = argparse.ArgumentParser(description="ETF Trading Analysis Scheduler")
    parser.add_argument("--date", type=str, help="Target date (YYYY-MM-DD)")
    parser.add_argument("--optimize", action="store_true", help="Run optimization")

    args = parser.parse_args()

    if args.date:
        target_date = datetime.strptime(args.date, "%Y-%m-%d").date()
    else:
        target_date = datetime.now().date()

    logger.info(f"Running analysis for date: {target_date}, optimize: {args.optimize}")

    run_daily_analysis(target_date, args.optimize)
