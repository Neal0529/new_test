import logging
import os
from datetime import date, datetime
from typing import List, Set

LOG_DIR = "logs"

CHINA_HOLIDAYS_2025_2026 = {
    date(2025, 1, 1),
    date(2025, 1, 28),
    date(2025, 1, 29),
    date(2025, 1, 30),
    date(2025, 1, 31),
    date(2025, 2, 1),
    date(2025, 2, 2),
    date(2025, 2, 3),
    date(2025, 2, 4),
    date(2025, 4, 4),
    date(2025, 4, 5),
    date(2025, 4, 6),
    date(2025, 5, 1),
    date(2025, 5, 2),
    date(2025, 5, 3),
    date(2025, 10, 1),
    date(2025, 10, 2),
    date(2025, 10, 3),
    date(2025, 10, 4),
    date(2025, 10, 5),
    date(2025, 10, 6),
    date(2025, 10, 7),
    date(2026, 1, 1),
    date(2026, 1, 26),
    date(2026, 1, 27),
    date(2026, 1, 28),
    date(2026, 1, 29),
    date(2026, 1, 30),
    date(2026, 1, 31),
    date(2026, 2, 1),
    date(2026, 2, 2),
    date(2026, 2, 3),
    date(2026, 4, 4),
    date(2026, 4, 5),
    date(2026, 4, 6),
    date(2026, 5, 1),
    date(2026, 5, 2),
    date(2026, 5, 3),
    date(2026, 10, 1),
    date(2026, 10, 2),
    date(2026, 10, 3),
    date(2026, 10, 4),
    date(2026, 10, 5),
    date(2026, 10, 6),
    date(2026, 10, 7),
    date(2026, 10, 8),
}


def setup_logging():
    """Configure logging."""
    os.makedirs(LOG_DIR, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler(f"{LOG_DIR}/utils.log")
        ]
    )


logger = logging.getLogger(__name__)


def is_trading_day(check_date: date) -> bool:
    """Check if given date is a trading day (weekday + not holiday).

    Args:
        check_date: Date to check

    Returns:
        True if trading day, False otherwise
    """
    if check_date.weekday() >= 5:
        logger.debug(f"{check_date} is weekend, not a trading day")
        return False

    if check_date in CHINA_HOLIDAYS_2025_2026:
        logger.info(f"{check_date} is a holiday, not a trading day")
        return False

    logger.debug(f"{check_date} is a trading day")
    return True


def get_trading_days_between(start_date: date, end_date: date) -> List[date]:
    """Get list of trading days between start and end dates.

    Args:
        start_date: Start date
        end_date: End date

    Returns:
        List of trading dates
    """
    trading_days = []
    current = start_date
    while current <= end_date:
        if is_trading_day(current):
            trading_days.append(current)
        current += timedelta(days=1)
    return trading_days


if __name__ == "__main__":
    setup_logging()

    test_dates = [
        date(2026, 4, 2),
        date(2026, 4, 5),
        date(2026, 5, 1),
        date(2026, 10, 1),
    ]

    for d in test_dates:
        result = is_trading_day(d)
        print(f"{d} ({d.strftime('%A')}): trading={result}")
