import logging
import os
from typing import Tuple

import numpy as np
import pandas as pd

LOG_DIR = "logs"


def setup_logging():
    """Configure logging to console and file."""
    os.makedirs(LOG_DIR, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler(f"{LOG_DIR}/quality.log")
        ]
    )


logger = logging.getLogger(__name__)


def fill_missing_dates(df: pd.DataFrame) -> Tuple[pd.DataFrame, int]:
    """Fill missing trading dates in the DataFrame.

    Args:
        df: Input DataFrame with date column

    Returns:
        Tuple of (filled DataFrame, count of missing dates)
    """
    if df.empty or "date" not in df.columns:
        return df, 0

    df = df.copy()
    df["date"] = pd.to_datetime(df["date"])
    df = df.set_index("date")

    full_date_range = pd.date_range(start=df.index.min(), end=df.index.max(), freq="B")
    missing_count = len(full_date_range) - len(df)

    if missing_count > 0:
        df = df.reindex(full_date_range)
        df.index.name = "date"

    return df.reset_index(), missing_count


def fix_null_values(df: pd.DataFrame) -> Tuple[pd.DataFrame, int]:
    """Fix null values in OHLCV columns using forward fill.

    Args:
        df: Input DataFrame

    Returns:
        Tuple of (fixed DataFrame, count of nulls filled)
    """
    df = df.copy()
    ohlcv_cols = ["open", "high", "low", "close", "volume"]
    ohlcv_cols = [c for c in ohlcv_cols if c in df.columns]

    initial_nulls = df[ohlcv_cols].isnull().sum().sum()

    if df[ohlcv_cols].iloc[0].isnull().any():
        first_row_nulls = df[ohlcv_cols].iloc[0].isnull()
        if first_row_nulls.any():
            df = df.iloc[1:].reset_index(drop=True)

    df[ohlcv_cols] = df[ohlcv_cols].ffill()

    final_nulls = df[ohlcv_cols].isnull().sum().sum()
    filled_count = initial_nulls - final_nulls

    return df, filled_count


def fix_zero_volume(df: pd.DataFrame) -> Tuple[pd.DataFrame, int]:
    """Replace zero volume with previous day's volume or 1.

    Args:
        df: Input DataFrame

    Returns:
        Tuple of (fixed DataFrame, count of zero volumes fixed)
    """
    df = df.copy()
    if "volume" not in df.columns:
        return df, 0

    zero_count = (df["volume"] == 0).sum()

    if zero_count > 0:
        df["volume"] = df["volume"].replace(0, np.nan)
        df["volume"] = df["volume"].bfill()
        df["volume"] = df["volume"].fillna(1)
        logger.warning(f"Fixed {zero_count} zero volume values")

    return df, zero_count


def detect_outliers(df: pd.DataFrame) -> Tuple[pd.DataFrame, int]:
    """Detect and cap price outliers based on 20-day moving average.

    Args:
        df: Input DataFrame

    Returns:
        Tuple of (fixed DataFrame, count of outliers capped)
    """
    df = df.copy()
    price_cols = ["open", "high", "low", "close"]
    price_cols = [c for c in price_cols if c in df.columns]

    outlier_count = 0

    for col in price_cols:
        ma = df[col].rolling(window=20, min_periods=1).mean()

        upper_bound = ma * 1.2
        lower_bound = ma * 0.8

        upper_outliers = df[col] > upper_bound
        lower_outliers = df[col] < lower_bound

        df.loc[upper_outliers, col] = upper_bound[upper_outliers]
        df.loc[lower_outliers, col] = lower_bound[lower_outliers]

        outliers = upper_outliers.sum() + lower_outliers.sum()
        outlier_count += outliers

    if outlier_count > 0:
        logger.warning(f"Capped {outlier_count} price outliers")

    return df, outlier_count


def fix_negative_values(df: pd.DataFrame) -> Tuple[pd.DataFrame, int]:
    """Fix negative price or volume values.

    Args:
        df: Input DataFrame

    Returns:
        Tuple of (fixed DataFrame, count of negative values fixed)
    """
    df = df.copy()
    numeric_cols = ["open", "high", "low", "close", "volume"]
    numeric_cols = [c for c in numeric_cols if c in df.columns]

    neg_count = 0

    for col in numeric_cols:
        neg_mask = df[col] < 0
        neg_count += neg_mask.sum()

        if neg_count > 0:
            df[col] = df[col].abs()
            logger.warning(f"Fixed {neg_count} negative values in {col}")

    return df, neg_count


def validate_chip_data(df: pd.DataFrame) -> Tuple[pd.DataFrame, int, int]:
    """Validate chip data columns if present.

    Args:
        df: Input DataFrame

    Returns:
        Tuple of (fixed DataFrame, warning_count, null_count)
    """
    df = df.copy()
    warning_count = 0
    null_count = 0

    if "profit_ratio" in df.columns:
        df["profit_ratio"] = pd.to_numeric(df["profit_ratio"], errors="coerce")
        invalid = (df["profit_ratio"] < 0) | (df["profit_ratio"] > 1)
        if invalid.any():
            df.loc[invalid, "profit_ratio"] = np.nan
            null_count += invalid.sum()

        null_run = df["profit_ratio"].isnull().astype(int).groupby(
            df["profit_ratio"].notnull().cumsum()
        ).sum()
        if (null_run > 3).any():
            warning_count += 1
            logger.warning("profit_ratio missing for >3 consecutive days")

    if "concentration_90" in df.columns:
        df["concentration_90"] = pd.to_numeric(df["concentration_90"], errors="coerce")
        invalid = (df["concentration_90"] < 0) | (df["concentration_90"] > 100)
        if invalid.any():
            df.loc[invalid, "concentration_90"] = np.nan
            null_count += invalid.sum()

        null_run = df["concentration_90"].isnull().astype(int).groupby(
            df["concentration_90"].notnull().cumsum()
        ).sum()
        if (null_run > 3).any():
            warning_count += 1
            logger.warning("concentration_90 missing for >3 consecutive days")

    if "profit_ratio" in df.columns or "concentration_90" in df.columns:
        chip_cols = [c for c in ["profit_ratio", "concentration_90"] if c in df.columns]
        df[chip_cols] = df[chip_cols].ffill()

    return df, warning_count, null_count


def check_data_quality(df: pd.DataFrame) -> Tuple[pd.DataFrame, str]:
    """Validate and clean ETF data before indicator calculations.

    Args:
        df: DataFrame with columns date, open, high, low, close, volume, amount
            (optionally profit_ratio, concentration_90 for chip data)

    Returns:
        Tuple of (cleaned DataFrame, status flag)
        Status is "ok", "warning", or "error"
    """
    setup_logging()

    if df.empty:
        logger.error("Empty DataFrame provided")
        return df, "error"

    df = df.copy()

    if "date" not in df.columns:
        logger.error("No date column in DataFrame")
        return df, "error"

    status = "ok"
    issues_count = 0

    df, missing_count = fill_missing_dates(df)
    if missing_count > 2:
        status = "warning"
        issues_count += missing_count
        logger.warning(f"Missing {missing_count} trading dates")
    elif missing_count > 0:
        logger.info(f"Filled {missing_count} missing dates")

    df, filled_nulls = fix_null_values(df)
    if filled_nulls > 0:
        logger.info(f"Filled {filled_nulls} null values")

    df, zero_vol = fix_zero_volume(df)
    issues_count += zero_vol

    df, outliers = detect_outliers(df)
    if outliers > 0:
        status = "warning"
        issues_count += outliers

    df, negatives = fix_negative_values(df)
    if negatives > 0:
        status = "warning"
        issues_count += negatives

    df, chip_warnings, chip_nulls = validate_chip_data(df)
    if chip_warnings > 0:
        status = "warning"
        issues_count += chip_warnings

    if status == "ok" and issues_count > 0:
        status = "warning"

    logger.info(f"Data quality check complete. Status: {status}, Issues: {issues_count}")

    return df, status


if __name__ == "__main__":
    setup_logging()

    test_data = {
        "date": ["2026-03-01", "2026-03-02", "2026-03-03", "2026-03-04", "2026-03-05"],
        "open": [1.0, 1.1, None, 1.2, 1.15],
        "high": [1.05, 1.15, 1.05, 1.25, 1.20],
        "low": [0.98, 1.08, 0.98, 1.18, 1.10],
        "close": [1.02, 1.12, 1.02, 1.22, 1.18],
        "volume": [1000, 0, 1500, 1200, 1100],
        "amount": [1.02e9, 1.12e9, 1.02e9, 1.22e9, 1.18e9],
    }
    test_df = pd.DataFrame(test_data)

    print("=== Original Data ===")
    print(test_df)
    print()

    cleaned_df, status = check_data_quality(test_df)

    print("=== Cleaned Data ===")
    print(cleaned_df)
    print()
    print(f"Status: {status}")
