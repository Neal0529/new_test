import json
import logging
import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional

import numpy as np
import pandas as pd
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
            logging.FileHandler(f"{LOG_DIR}/backtest.log")
        ]
    )


logger = logging.getLogger(__name__)


def load_etf_config() -> dict:
    """Load ETF configuration."""
    config_file = os.path.join(CONFIG_DIR, "config.yaml")
    try:
        with open(config_file, "r", encoding="utf-8") as f:
            return yaml.safe_load(f)
    except Exception as e:
        logger.warning(f"Failed to load config: {e}")
        return {}


def load_positions() -> dict:
    """Load positions from config."""
    pos_file = os.path.join(CONFIG_DIR, "positions.json")
    try:
        with open(pos_file, "r") as f:
            return json.load(f)
    except Exception:
        return {}


def _calculate_holding_days(open_date_str: str) -> int:
    """Calculate holding days."""
    if not open_date_str:
        return 0
    try:
        open_date = datetime.strptime(open_date_str, "%Y-%m-%d")
        today = datetime.now().date()
        open_date_only = open_date.date()
        return (today - open_date_only).days
    except Exception:
        return 0


def run_backtest(etf_code: str, start_date: str, end_date: str, initial_capital: float = 20000, use_news: bool = False) -> Dict:
    """Run backtesting for a single ETF.

    Args:
        etf_code: ETF code string
        start_date: Start date in YYYY-MM-DD format
        end_date: End date in YYYY-MM-DD format
        initial_capital: Starting capital
        use_news: Whether to use news sentiment (default False for backtest speed)

    Returns:
        Dict with win_rate, total_trades, profitable_trades, total_return, max_drawdown, trade_log
    """
    from data_fetcher import fetch_etf_data
    from quality_checker import check_data_quality
    from indicators import compute_macd, compute_kdj, compute_rsi
    from wave_theory import detect_wave_pattern
    from volume_price import analyze_volume_price
    from chip_analysis import evaluate_chip
    from signal_generator import generate_signal

    logger.info(f"Starting backtest for {etf_code} from {start_date} to {end_date}")

    df = fetch_etf_data(etf_code, start_date, end_date)

    if df.empty:
        logger.error(f"No data fetched for {etf_code}")
        return {
            "win_rate": 0.0, "total_trades": 0, "profitable_trades": 0,
            "total_return": 0.0, "max_drawdown": 0.0, "trade_log": []
        }

    df, status = check_data_quality(df)
    logger.info(f"Data loaded: {len(df)} rows, quality status: {status}")

    df = df.reset_index(drop=True)
    df["date"] = pd.to_datetime(df["date"])

    position = {
        "shares": 0,
        "cost": 0.0,
        "open_date": None,
        "position_value": 0.0
    }

    cash = initial_capital
    initial_value = initial_capital
    peak_value = initial_capital
    max_drawdown = 0.0

    trade_log = []
    current_trade = None

    min_days_required = 50

    for i in range(min_days_required, len(df)):
        current_date = df.iloc[i]["date"]
        current_date_str = current_date.strftime("%Y-%m-%d")

        close_price = df.iloc[i]["close"]
        if pd.isna(close_price) or close_price <= 0:
            continue

        close_series = df.iloc[:i+1]["close"]
        high_series = df.iloc[:i+1]["high"]
        low_series = df.iloc[:i+1]["low"]
        volume_series = df.iloc[:i+1]["volume"]

        try:
            macd_bull, macd_score = compute_macd(close_series)
        except Exception:
            macd_bull, macd_score = False, 0

        try:
            kdj_bull, kdj_score = compute_kdj(high_series, low_series, close_series)
        except Exception:
            kdj_bull, kdj_score = False, 0

        try:
            rsi_bull, rsi_score = compute_rsi(close_series)
        except Exception:
            rsi_bull, rsi_score = False, 0

        try:
            close_arr = close_series.values
            wave_ready, wave_score = detect_wave_pattern(close_arr)
        except Exception:
            wave_ready, wave_score = False, 0

        try:
            vol_score, vol_details = analyze_volume_price(close_series, volume_series)
        except Exception:
            vol_score, vol_details = 0, {}

        chip_ok, chip_score = False, 0
        try:
            from data_fetcher import fetch_chip_data
            chip_data = fetch_chip_data(etf_code, current_date_str)
            profit_ratio = chip_data.get("profit_ratio")
            concentration = chip_data.get("concentration_90")
            if profit_ratio is not None and concentration is not None:
                chip_ok, chip_score = evaluate_chip(profit_ratio, concentration)
        except Exception:
            pass

        total_tech_score = macd_score + kdj_score + rsi_score + wave_score + vol_score + chip_score

        ma_bull = close_series.iloc[-1] > close_series.rolling(20).mean().iloc[-1] if len(close_series) >= 20 else False
        ma_score = 10 if ma_bull else 0
        total_tech_score += ma_score

        tech_scores = {
            "macd_bull": macd_bull, "macd_score": macd_score,
            "kdj_bull": kdj_bull, "kdj_score": kdj_score,
            "rsi_bull": rsi_bull, "rsi_score": rsi_score,
            "wave_ready": wave_ready, "wave_score": wave_score,
            "volume_price_score": vol_score,
            "chip_ok": chip_ok, "chip_score": chip_score,
            "ma_bull": ma_bull, "ma_score": ma_score,
            "total_tech_score": total_tech_score,
            "current_price": close_price
        }

        if use_news:
            from news_collector import fetch_news
            from sentiment_analyzer import analyze_sentiment
            etf_config = load_etf_config()
            sector = ""
            for etf_info in etf_config.get("etfs", []):
                if etf_info.get("code") == etf_code:
                    sector = etf_info.get("sector", "")
                    break
            keywords = [sector] if sector else []
            news_list = fetch_news(keywords, current_date_str)
            news_data = analyze_sentiment(news_list)
        else:
            news_data = {
                "daily_sentiment": 0.0,
                "sentiment_trend": 0.0,
                "event_flag": "neutral",
                "keyword_adj": 0.0
            }

        if position["shares"] > 0:
            position["position_value"] = position["shares"] * close_price
            position["open_date"] = position.get("open_date", current_date_str)

        signal = generate_signal(etf_code, tech_scores, news_data, position)

        action = signal.get("action", "HOLD")
        logger.info(f"{current_date_str}: {action} (shares={position['shares']}, price={close_price:.3f})")

        if action == "BUY_2W" and position["shares"] == 0:
            shares_to_buy = 20000 / close_price
            position["shares"] = shares_to_buy
            position["cost"] = close_price
            position["open_date"] = current_date_str
            position["position_value"] = position["shares"] * close_price
            current_trade = {
                "entry_date": current_date_str,
                "entry_price": close_price,
                "shares": shares_to_buy
            }
            logger.info(f"BUY at {close_price:.3f}, shares={shares_to_buy:.2f}")

        elif action == "ADD_2W" and position["shares"] > 0:
            additional_value = 20000
            additional_shares = additional_value / close_price
            total_shares = position["shares"] + additional_shares
            new_cost = ((position["shares"] * position["cost"]) + (additional_shares * close_price)) / total_shares
            position["shares"] = total_shares
            position["cost"] = new_cost
            position["position_value"] = position["shares"] * close_price
            logger.info(f"ADD at {close_price:.3f}, new shares={total_shares:.2f}, avg cost={new_cost:.3f}")

        elif action == "REDUCE_HALF" and position["shares"] > 0:
            shares_to_sell = position["shares"] / 2
            proceeds = shares_to_sell * close_price
            position["shares"] -= shares_to_sell
            position["position_value"] = position["shares"] * close_price
            logger.info(f"REDUCE HALF at {close_price:.3f}, sold={shares_to_sell:.2f}")

        elif action == "CLOSE_ALL" and position["shares"] > 0:
            proceeds = position["shares"] * close_price
            pnl = proceeds - (position["shares"] * position["cost"])
            pnl_pct = (close_price - position["cost"]) / position["cost"] if position["cost"] > 0 else 0
            holding_days = _calculate_holding_days(position.get("open_date"))

            if current_trade:
                current_trade["exit_date"] = current_date_str
                current_trade["exit_price"] = close_price
                current_trade["pnl"] = pnl
                current_trade["pnl_pct"] = pnl_pct
                current_trade["holding_days"] = holding_days
                current_trade["exit_reason"] = signal.get("reason", "unknown")
                trade_log.append(current_trade)
                current_trade = None

            logger.info(f"CLOSE ALL at {close_price:.3f}, P&L={pnl:.2f} ({pnl_pct:.2%})")

            position = {
                "shares": 0,
                "cost": 0.0,
                "open_date": None,
                "position_value": 0.0
            }

        current_value = cash + (position.get("shares", 0) * close_price)
        if current_value > peak_value:
            peak_value = current_value
        drawdown = (peak_value - current_value) / peak_value if peak_value > 0 else 0
        if drawdown > max_drawdown:
            max_drawdown = drawdown

    if position["shares"] > 0 and current_trade:
        close_price = df.iloc[-1]["close"]
        current_trade["exit_date"] = df.iloc[-1]["date"].strftime("%Y-%m-%d")
        current_trade["exit_price"] = close_price
        current_trade["pnl"] = position["shares"] * (close_price - position["cost"])
        current_trade["pnl_pct"] = (close_price - position["cost"]) / position["cost"] if position["cost"] > 0 else 0
        current_trade["holding_days"] = _calculate_holding_days(position.get("open_date"))
        current_trade["exit_reason"] = "end_of_backtest"
        trade_log.append(current_trade)

    total_trades = len(trade_log)
    profitable_trades = sum(1 for t in trade_log if t.get("pnl", 0) > 0)
    win_rate = profitable_trades / total_trades if total_trades > 0 else 0.0

    final_value = cash + (position.get("shares", 0) * df.iloc[-1]["close"])
    total_return = (final_value - initial_capital) / initial_capital if initial_capital > 0 else 0.0

    result = {
        "win_rate": round(win_rate, 4),
        "total_trades": total_trades,
        "profitable_trades": profitable_trades,
        "total_return": round(total_return, 4),
        "max_drawdown": round(max_drawdown, 4),
        "trade_log": trade_log
    }

    logger.info(f"Backtest complete: win_rate={win_rate:.2%}, total_trades={total_trades}, total_return={total_return:.2%}")

    return result


if __name__ == "__main__":
    setup_logging()

    print("=== Backtest Engine Test ===\n")

    end_date = datetime.now().strftime("%Y-%m-%d")
    start_date = (datetime.now() - timedelta(days=180)).strftime("%Y-%m-%d")

    print(f"Testing backtest for 512000")
    print(f"Period: {start_date} to {end_date}")
    print()

    result = run_backtest("512000", start_date, end_date, initial_capital=20000, use_news=False)

    print(f"Win Rate: {result['win_rate']:.2%}")
    print(f"Total Trades: {result['total_trades']}")
    print(f"Profitable Trades: {result['profitable_trades']}")
    print(f"Total Return: {result['total_return']:.2%}")
    print(f"Max Drawdown: {result['max_drawdown']:.2%}")
    print()

    if result["trade_log"]:
        print("Recent trades:")
        for trade in result["trade_log"][-5:]:
            print(f"  {trade['entry_date']} -> {trade['exit_date']}: "
                  f"P&L={trade['pnl']:.2f} ({trade['pnl_pct']:.2%}), "
                  f"days={trade['holding_days']}, reason={trade['exit_reason']}")
