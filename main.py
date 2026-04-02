import argparse
import logging
import os
from datetime import date, datetime, timedelta

LOG_DIR = "logs"


def setup_logging():
    """Configure logging."""
    os.makedirs(LOG_DIR, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler(f"{LOG_DIR}/main.log")
        ]
    )


logger = logging.getLogger(__name__)


def run_once(date_str: str = None, optimize: bool = False):
    """Run daily analysis once."""
    from scheduler import run_daily_analysis

    if date_str:
        target_date = datetime.strptime(date_str, "%Y-%m-%d").date()
    else:
        target_date = datetime.now().date()

    logger.info(f"Running daily analysis for {target_date}")
    run_daily_analysis(target_date, optimize)


def run_backtest(etf_code: str, start_date: str, end_date: str, optimize: bool = False):
    """Run backtest for a single ETF."""
    from backtest_engine import run_backtest
    from parameter_optimizer import optimize_parameters
    import json

    logger.info(f"Running backtest for {etf_code} from {start_date} to {end_date}")

    result = run_backtest(etf_code, start_date, end_date, use_news=False)

    print(f"\n=== Backtest Results for {etf_code} ===")
    print(f"Win Rate: {result['win_rate']:.2%}")
    print(f"Total Trades: {result['total_trades']}")
    print(f"Profitable Trades: {result['profitable_trades']}")
    print(f"Total Return: {result['total_return']:.2%}")
    print(f"Max Drawdown: {result['max_drawdown']:.2%}")

    if result.get("trade_log"):
        print(f"\nRecent trades:")
        for trade in result["trade_log"][-5:]:
            print(f"  {trade['entry_date']} -> {trade['exit_date']}: "
                  f"P&L={trade['pnl']:.2f} ({trade['pnl_pct']:.2%})")

    if optimize:
        logger.info("Running parameter optimization...")

        params_file = "config/dynamic_params.json"
        try:
            with open(params_file, "r") as f:
                current_params = json.load(f)
        except Exception:
            current_params = {}

        new_params = optimize_parameters(result, current_params)

        params_file = "config/dynamic_params.json"
        with open(params_file, "w") as f:
            json.dump(new_params, f, indent=2)

        logger.info(f"Parameters optimized and saved to {params_file}")
        print(f"\nUpdated parameters saved to {params_file}")


def main():
    """Main entry point."""
    setup_logging()

    parser = argparse.ArgumentParser(description="ETF Trading Analysis System")

    parser.add_argument("--once", action="store_true", help="Run daily analysis once")
    parser.add_argument("--date", type=str, help="Target date (YYYY-MM-DD)")
    parser.add_argument("--backtest", nargs=3, metavar=("ETF_CODE", "START", "END"),
                        help="Run backtest for a single ETF")
    parser.add_argument("--optimize", action="store_true", help="Run optimization after backtest")

    args = parser.parse_args()

    if args.backtest:
        etf_code, start, end = args.backtest
        run_backtest(etf_code, start, end, args.optimize)
    elif args.once or args.date:
        run_once(args.date, args.optimize)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
