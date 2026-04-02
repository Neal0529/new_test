import logging
import os
import time
import traceback
from datetime import datetime, timedelta
from typing import Optional

import pandas as pd

try:
    import akshare as ak
except ImportError:
    ak = None

DATA_DIR = "data"
LOG_DIR = "logs"

RETRY_DELAYS = [1, 2, 4]
RETRY_COUNT = 3
REQUEST_DELAY = 0.5
AKSHARE_TIMEOUT = 10


def setup_logging():
    """Configure logging to console and file."""
    os.makedirs(LOG_DIR, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler(f"{LOG_DIR}/fetcher.log")
        ]
    )


logger = logging.getLogger(__name__)


def get_daily_file(etf_code: str) -> str:
    """Get path for daily data CSV."""
    return os.path.join(DATA_DIR, f"{etf_code}_daily.csv")


def get_chip_file(etf_code: str) -> str:
    """Get path for chip data CSV."""
    return os.path.join(DATA_DIR, f"{etf_code}_chip.csv")


def parse_date(date_str: str) -> datetime:
    """Parse date string to datetime object."""
    return pd.to_datetime(date_str).to_pydatetime()


def format_date(dt: datetime) -> str:
    """Format datetime to YYYY-MM-DD string."""
    return dt.strftime("%Y-%m-%d")


def get_trading_dates(akshare_df: pd.DataFrame) -> list:
    """Extract trading dates from akshare DataFrame."""
    if akshare_df.empty:
        return []
    dates = []
    for col in akshare_df.columns:
        if "日期" in str(col) or "date" in str(col).lower():
            dates = akshare_df[col].astype(str).tolist()
            break
    return dates


def normalize_daily_data(df: pd.DataFrame) -> pd.DataFrame:
    """Normalize akshare daily data to standard format."""
    if df.empty:
        return pd.DataFrame(columns=["date", "open", "high", "low", "close", "volume", "amount"])

    result = pd.DataFrame()
    
    for col in df.columns:
        col_lower = str(col).lower()
        if "日期" in col or "date" in col_lower:
            result["date"] = pd.to_datetime(df[col]).dt.strftime("%Y-%m-%d")
        elif "开盘" in col or "open" in col_lower:
            result["open"] = pd.to_numeric(df[col], errors="coerce")
        elif "最高" in col or "high" in col_lower:
            result["high"] = pd.to_numeric(df[col], errors="coerce")
        elif "最低" in col or "low" in col_lower:
            result["low"] = pd.to_numeric(df[col], errors="coerce")
        elif "收盘" in col or "close" in col_lower:
            result["close"] = pd.to_numeric(df[col], errors="coerce")
        elif "成交量" in col or "volume" in col_lower:
            result["volume"] = pd.to_numeric(df[col], errors="coerce")
        elif "成交额" in col or "amount" in col_lower:
            result["amount"] = pd.to_numeric(df[col], errors="coerce")

    if "date" not in result.columns:
        logger.warning("Could not find date column in akshare data")
        return pd.DataFrame(columns=["date", "open", "high", "low", "close", "volume", "amount"])

    return result[["date", "open", "high", "low", "close", "volume", "amount"]]


def fetch_from_akshare(etf_code: str, start_date: str, end_date: str) -> Optional[pd.DataFrame]:
    """Fetch daily data from akshare with retry mechanism."""
    if ak is None:
        logger.error("akshare not installed")
        return None

    for attempt in range(RETRY_COUNT):
        try:
            time.sleep(REQUEST_DELAY)
            
            start_str = start_date.replace("-", "")
            end_str = end_date.replace("-", "")
            
            df = ak.fund_etf_hist_em(
                symbol=etf_code, 
                period="daily", 
                start_date=start_str, 
                end_date=end_str
            )
            
            if df is None or df.empty:
                logger.warning(f"No data returned from akshare for {etf_code}")
                return None
            
            return normalize_daily_data(df)
            
        except Exception as e:
            delay = RETRY_DELAYS[attempt] if attempt < len(RETRY_DELAYS) else RETRY_DELAYS[-1]
            logger.warning(f"Attempt {attempt + 1}/{RETRY_COUNT} failed for {etf_code}: {e}")
            logger.warning(f"Stack trace: {traceback.format_exc()}")
            
            if attempt < RETRY_COUNT - 1:
                logger.info(f"Retrying in {delay} seconds...")
                time.sleep(delay)
            else:
                logger.error(f"All {RETRY_COUNT} attempts failed for {etf_code}")
                return None

    return None


def fetch_chip_from_akshare(etf_code: str, date: str) -> Optional[dict]:
    """Fetch chip data from akshare."""
    if ak is None:
        return None

    try:
        df = ak.stock_cyq_em(symbol=etf_code, date=date)
        
        if df is None or df.empty:
            logger.warning(f"No chip data returned from akshare for {etf_code} on {date}")
            return None

        profit_ratio = None
        concentration_90 = None

        for col in df.columns:
            col_str = str(col)
            if "盈利" in col_str or "profit" in col_str.lower():
                profit_ratio = pd.to_numeric(df[col].iloc[0], errors="coerce")
            elif "集中" in col_str or "concentration" in col_str.lower():
                concentration_90 = pd.to_numeric(df[col].iloc[0], errors="coerce")

        return {
            "profit_ratio": profit_ratio,
            "concentration_90": concentration_90
        }

    except Exception as e:
        logger.warning(f"Failed to fetch chip data for {etf_code} on {date}: {e}")
        return None


def fetch_etf_data(etf_code: str, start_date: str, end_date: str, min_days: int = 200) -> pd.DataFrame:
    """Fetch ETF price data with local caching.

    Args:
        etf_code: ETF code (e.g., "512000")
        start_date: Start date in YYYY-MM-DD format
        end_date: End date in YYYY-MM-DD format
        min_days: Minimum required days (default 200). If cached data is shorter,
                  try to refresh but use existing cache if refresh fails.

    Returns:
        DataFrame with columns: date, open, high, low, close, volume, amount
    """
    setup_logging()
    os.makedirs(DATA_DIR, exist_ok=True)

    cache_file = get_daily_file(etf_code)
    today = format_date(datetime.now().date())
    existing_df = None

    if os.path.exists(cache_file):
        try:
            existing_df = pd.read_csv(cache_file, parse_dates=["date"])
            existing_df["date"] = pd.to_datetime(existing_df["date"]).dt.strftime("%Y-%m-%d")
            last_date = existing_df["date"].max()
            
            cached_days = len(existing_df)
            logger.info(f"Found existing cache for {etf_code}: {cached_days} days, last date: {last_date}")
            
            if last_date >= end_date and cached_days >= min_days:
                logger.info(f"Using cached data for {etf_code} up to {last_date} ({cached_days} days)")
                return existing_df[(existing_df["date"] >= start_date) & (existing_df["date"] <= end_date)]
            
            if cached_days >= 50:
                logger.warning(f"Cached data for {etf_code} has only {cached_days} days (need {min_days} for full analysis). "
                             f"Using available data.")
                return existing_df[(existing_df["date"] >= start_date) & (existing_df["date"] <= end_date)]
            
            if cached_days < 50 and cached_days > 0:
                logger.warning(f"Cached data for {etf_code} has only {cached_days} days, "
                             f"less than minimum 50 days. Attempting to refresh...")
                
                new_start = format_date(parse_date(last_date) + timedelta(days=1))
                new_data = fetch_from_akshare(etf_code, new_start, end_date)
                
                if new_data is not None and not new_data.empty:
                    combined = pd.concat([existing_df, new_data], ignore_index=True)
                    combined = combined.drop_duplicates(subset=["date"], keep="last")
                    combined = combined.sort_values("date")
                    combined.to_csv(cache_file, index=False)
                    logger.info(f"Updated cache for {etf_code}")
                    return combined[combined["date"].between(start_date, end_date)]
                
                if cached_days >= 20:
                    logger.warning(f"Refresh failed. Using existing cached data ({cached_days} days)")
                    return existing_df[(existing_df["date"] >= start_date) & (existing_df["date"] <= end_date)]
                
                logger.error(f"Cache too short ({cached_days} days) and refresh failed")
                
        except Exception as e:
            logger.error(f"Error reading cache for {etf_code}: {e}")
            logger.warning(f"Cache error, using data if available")
            if existing_df is not None and len(existing_df) >= 20:
                return existing_df[(existing_df["date"] >= start_date) & (existing_df["date"] <= end_date)]

    full_start_date = format_date(parse_date(end_date) - timedelta(days=300))
    logger.info(f"Full fetch for {etf_code} from {full_start_date} to {end_date}")
    df = fetch_from_akshare(etf_code, full_start_date, end_date)
    
    if df is not None and not df.empty:
        df.to_csv(cache_file, index=False)
        logger.info(f"Saved initial cache for {etf_code}: {len(df)} days")
        return df
    else:
        if existing_df is not None and len(existing_df) >= 20:
            logger.warning(f"Full fetch failed. Using existing cached data ({len(existing_df)} days) as fallback")
            return existing_df[(existing_df["date"] >= start_date) & (existing_df["date"] <= end_date)]
        
        logger.warning(f"No data fetched for {etf_code}, returning empty DataFrame")
        df = pd.DataFrame(columns=["date", "open", "high", "low", "close", "volume", "amount"])

    return df


def fetch_chip_data(etf_code: str, date: str) -> dict:
    """Fetch chip data with local caching.

    Args:
        etf_code: ETF code
        date: Date in YYYY-MM-DD format

    Returns:
        Dict with profit_ratio and concentration_90
    """
    setup_logging()
    os.makedirs(DATA_DIR, exist_ok=True)

    cache_file = get_chip_file(etf_code)
    chip_data = fetch_chip_from_akshare(etf_code, date)

    if chip_data is None:
        return {"profit_ratio": None, "concentration": None}

    if os.path.exists(cache_file):
        try:
            existing_df = pd.read_csv(cache_file)
            existing_df["date"] = existing_df["date"].astype(str)
            
            if date in existing_df["date"].values:
                logger.info(f"Using cached chip data for {etf_code} on {date}")
                row = existing_df[existing_df["date"] == date].iloc[0]
                return {
                    "profit_ratio": row.get("profit_ratio"),
                    "concentration_90": row.get("concentration_90")
                }
        except Exception as e:
            logger.error(f"Error reading chip cache for {etf_code}: {e}")

    new_row = pd.DataFrame([{
        "date": date,
        "profit_ratio": chip_data.get("profit_ratio"),
        "concentration_90": chip_data.get("concentration_90")
    }])

    if os.path.exists(cache_file):
        new_row.to_csv(cache_file, mode="a", header=False, index=False)
    else:
        new_row.to_csv(cache_file, index=False)

    logger.info(f"Updated chip cache for {etf_code} on {date}")
    
    return {
        "profit_ratio": chip_data.get("profit_ratio"),
        "concentration_90": chip_data.get("concentration_90")
    }


if __name__ == "__main__":
    setup_logging()
    
    test_code = "512000"
    end_date = datetime.now().strftime("%Y-%m-%d")
    start_date = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
    
    print(f"Testing fetch_etf_data for {test_code} ({start_date} to {end_date})")
    df = fetch_etf_data(test_code, start_date, end_date)
    print(f"Fetched {len(df)} rows")
    if not df.empty:
        print(df.head())
    
    print(f"\nTesting fetch_chip_data for {test_code} on {end_date}")
    chip = fetch_chip_data(test_code, end_date)
    print(f"Chip data: {chip}")
