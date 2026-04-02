#!/usr/bin/env python
"""Integration test for the ETF trading analysis system."""

import os
import sys
from datetime import date, datetime, timedelta

os.environ["MOCK_NEWS"] = "true"

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from data_fetcher import fetch_etf_data
from quality_checker import check_data_quality
from indicators import compute_macd, compute_kdj, compute_rsi
from wave_theory import detect_wave_pattern
from volume_price import analyze_volume_price
from chip_analysis import evaluate_chip
from news_collector import fetch_news
from sentiment_analyzer import analyze_sentiment
from signal_generator import generate_signal


def run_integration_test():
    """Run full analysis for a single ETF."""
    print("=" * 60)
    print("ETF Trading Analysis System - Integration Test")
    print("=" * 60)

    etf_code = "512000"
    target_date = date.today()
    target_date_str = target_date.strftime("%Y-%m-%d")

    end_date = datetime.now().strftime("%Y-%m-%d")
    start_date = (datetime.now() - timedelta(days=60)).strftime("%Y-%m-%d")

    print(f"\n[1/8] Fetching ETF data for {etf_code}...")
    df = fetch_etf_data(etf_code, start_date, end_date)
    print(f"  Fetched {len(df)} rows")
    if df.empty:
        print("  WARNING: No data fetched, using sample data")
        import pandas as pd
        import numpy as np
        dates = pd.date_range(end=target_date, periods=30, freq="D")
        df = pd.DataFrame({
            "date": dates,
            "open": np.random.uniform(0.5, 0.6, 30),
            "high": np.random.uniform(0.5, 0.6, 30),
            "low": np.random.uniform(0.5, 0.6, 30),
            "close": np.random.uniform(0.5, 0.6, 30),
            "volume": np.random.randint(1000000, 5000000, 30),
            "amount": np.random.uniform(1e8, 1e9, 30)
        })

    print(f"\n[2/8] Checking data quality...")
    df, status = check_data_quality(df)
    print(f"  Quality status: {status}")

    print(f"\n[3/8] Computing technical indicators...")
    close = df["close"]
    high = df["high"]
    low = df["low"]
    volume = df["volume"]

    macd_bull, macd_score = compute_macd(close)
    print(f"  MACD: bull={macd_bull}, score={macd_score}")

    kdj_bull, kdj_score = compute_kdj(high, low, close)
    print(f"  KDJ: bull={kdj_bull}, score={kdj_score}")

    rsi_bull, rsi_score = compute_rsi(close)
    print(f"  RSI: bull={rsi_bull}, score={rsi_score}")

    print(f"\n[4/8] Computing wave pattern...")
    close_arr = close.values
    wave_ready, wave_score = detect_wave_pattern(close_arr)
    print(f"  Wave: ready={wave_ready}, score={wave_score}")

    print(f"\n[5/8] Computing volume-price analysis...")
    vol_score, vol_details = analyze_volume_price(close, volume)
    print(f"  Volume: score={vol_score}")

    print(f"\n[6/8] Computing chip analysis...")
    chip_ok, chip_score = evaluate_chip(0.35, 12.0)
    print(f"  Chip: ok={chip_ok}, score={chip_score}")

    ma_bull = close.iloc[-1] > close.rolling(20).mean().iloc[-1] if len(close) >= 20 else False
    ma_score = 10 if ma_bull else 0
    print(f"  MA: bull={ma_bull}, score={ma_score}")

    total_tech_score = macd_score + kdj_score + rsi_score + wave_score + vol_score + chip_score + ma_score
    print(f"  Total tech score: {total_tech_score}")

    print(f"\n[7/8] Fetching news and sentiment...")
    news_list = fetch_news(["券商"], target_date_str)
    print(f"  Fetched {len(news_list)} news items")

    news_data = analyze_sentiment(news_list)
    print(f"  Sentiment: {news_data['event_flag']}, score={news_data['daily_sentiment']}")

    print(f"\n[8/8] Generating signal...")
    current_price = close.iloc[-1]

    position = {
        "shares": 0,
        "cost": 0,
        "open_date": None,
        "position_value": 0
    }

    tech_scores = {
        "macd_bull": macd_bull,
        "macd_score": macd_score,
        "kdj_bull": kdj_bull,
        "kdj_score": kdj_score,
        "rsi_bull": rsi_bull,
        "rsi_score": rsi_score,
        "wave_ready": wave_ready,
        "wave_score": wave_score,
        "volume_price_score": vol_score,
        "chip_ok": chip_ok,
        "chip_score": chip_score,
        "ma_bull": ma_bull,
        "ma_score": ma_score,
        "total_tech_score": total_tech_score,
        "current_price": current_price
    }

    signal = generate_signal(etf_code, tech_scores, news_data, position)

    print(f"\n{'=' * 60}")
    print("FINAL RESULTS")
    print(f"{'=' * 60}")
    print(f"ETF Code: {etf_code}")
    print(f"Current Price: {current_price:.4f}")
    print(f"Action: {signal['action']}")
    print(f"Reason: {signal['reason']}")
    print(f"Tech Score: {total_tech_score}")
    print(f"Sentiment: {news_data['daily_sentiment']:.4f}")
    print(f"Final Score: {signal.get('score_details', {}).get('total_tech_score', 0)}")
    print(f"{'=' * 60}")

    print("\n[OK] Integration test completed successfully!")

    return signal


if __name__ == "__main__":
    run_integration_test()
