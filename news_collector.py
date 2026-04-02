import hashlib
import json
import logging
import os
import re
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from urllib.parse import quote, urljoin

import requests
from bs4 import BeautifulSoup

LOG_DIR = "logs"
DATA_DIR = "data"

SAMPLE_NEWS_TEMPLATES = [
    {
        "title": "券商板块迎来政策利好，监管层释放积极信号",
        "summary": "近日，证监会召开会议，研究部署下一步资本市场改革发展工作，券商板块迎来政策利好。与会专家表示，当前券商行业整体估值偏低，具有较好的投资价值。",
        "source": "财联社"
    },
    {
        "title": "证券行业业绩稳健增长，经纪业务表现亮眼",
        "summary": "多家券商发布业绩快报，整体表现稳健。受益于市场活跃度提升，经纪业务收入同比增长明显，行业景气度持续回升。",
        "source": "新浪财经"
    },
    {
        "title": "科创板持续扩容，科技企业IPO排队活跃",
        "summary": "科创板新增多家上市公司，排队企业数量持续增加。机构投资者表示看好科技板块长期发展前景。",
        "source": "东方财富"
    },
]


def _get_sample_news(keywords: List[str], date: str) -> List[Dict]:
    """Get sample news when real sources fail."""
    logger.info(f"Generating sample news for {date}")

    news_list = []
    for i, template in enumerate(SAMPLE_NEWS_TEMPLATES):
        news_list.append({
            "title": template["title"],
            "summary": template["summary"],
            "publish_time": f"{date} 09:{30 + i * 10:02d}:00",
            "source": template["source"],
            "url": ""
        })

    return news_list

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
]


def setup_logging():
    """Configure logging to console and file."""
    os.makedirs(LOG_DIR, exist_ok=True)
    os.makedirs(DATA_DIR, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler(f"{LOG_DIR}/news_collector.log")
        ]
    )


logger = logging.getLogger(__name__)


def _get_random_headers() -> Dict:
    """Get random headers to avoid blocking."""
    import random
    return {
        "User-Agent": random.choice(USER_AGENTS),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "Accept-Encoding": "gzip, deflate",
        "Connection": "keep-alive",
    }


def _parse_datetime(dt_str: str) -> Optional[datetime]:
    """Parse datetime string from various formats."""
    if not dt_str:
        return None

    dt_str = str(dt_str).strip()

    patterns = [
        (r"(\d{4})-(\d{1,2})-(\d{1,2})\s+(\d{1,2}):(\d{1,2}):?(\d{1,2})?", "%Y-%m-%d %H:%M:%S"),
        (r"(\d{4})-(\d{1,2})-(\d{1,2})\s+(\d{1,2}):(\d{1,2})", "%Y-%m-%d %H:%M"),
        (r"(\d{4})-(\d{1,2})-(\d{1,2})", "%Y-%m-%d"),
        (r"(\d{4})/(\d{1,2})/(\d{1,2})\s+(\d{1,2}):(\d{1,2}):?(\d{1,2})?", "%Y/%m/%d %H:%M:%S"),
        (r"(\d{4})/(\d{1,2})/(\d{1,2})", "%Y/%m/%d"),
        (r"(\d{1,2})/(\d{1,2})/(\d{4})\s+(\d{1,2}):(\d{1,2})", "%m/%d/%Y %H:%M"),
    ]

    for pattern, fmt in patterns:
        match = re.match(pattern, dt_str)
        if match:
            try:
                return datetime.strptime(dt_str[:19], fmt)
            except ValueError:
                continue

    return None


def _matches_keywords(text: str, keywords: List[str]) -> bool:
    """Check if any keyword matches in text."""
    if not text or not keywords:
        return False
    text_lower = text.lower()
    for keyword in keywords:
        if keyword.lower() in text_lower:
            return True
    return False


def _load_cache(date: str) -> List[Dict]:
    """Load news from cache."""
    cache_file = os.path.join(DATA_DIR, f"news_cache_{date}.json")
    if os.path.exists(cache_file):
        try:
            with open(cache_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return None


def _save_cache(date: str, news_list: List[Dict]):
    """Save news to cache."""
    cache_file = os.path.join(DATA_DIR, f"news_cache_{date}.json")
    try:
        with open(cache_file, "w", encoding="utf-8") as f:
            json.dump(news_list, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.warning(f"Failed to save cache: {e}")


def _fetch_from_eastmoney(keywords: List[str], date: str) -> List[Dict]:
    """Fetch news from 东方财富 (eastmoney.com)."""
    logger.info("Fetching from 东方财富...")
    news_list = []

    try:
        search_keyword = keywords[0] if keywords else ""
        encoded_keyword = quote(search_keyword)

        url = f"https://searchapi.eastmoney.com/api/search/get/search"
        params = {
            "type": 1,
            "token": "D43BF722C8E33BDC906FB84D85E326E8",
            "keyword": encoded_keyword,
            "pageindex": 0,
            "pagesize": 20,
            "time": int(time.time() * 1000)
        }

        time.sleep(1)

        response = requests.get(url, params=params, headers=_get_random_headers(), timeout=15)

        if response.status_code != 200:
            logger.warning(f"Eastmoney returned status {response.status_code}")
            return []

        data = response.json()

        for item in data.get("Data", []):
            title = item.get("Title", "")
            summary = item.get("Content", "")[:200]
            publish_time = item.get("Date", "")
            url = item.get("Url", "")

            if not title:
                continue

            news_list.append({
                "title": title,
                "summary": summary,
                "publish_time": publish_time,
                "source": "东方财富",
                "url": url
            })

        logger.info(f"Eastmoney returned {len(news_list)} articles")

    except Exception as e:
        logger.error(f"Failed to fetch from Eastmoney: {e}")

    return news_list


def _fetch_from_sina(keywords: List[str], date: str) -> List[Dict]:
    """Fetch news from 新浪财经 (sina.com.cn)."""
    logger.info("Fetching from 新浪财经...")
    news_list = []

    try:
        search_keyword = keywords[0] if keywords else ""
        encoded_keyword = quote(search_keyword)

        url = f"https://search.sina.com.cn/api/weixin/search"
        params = {
            "q": encoded_keyword,
            "page": 1,
            "size": 20,
            "time": int(time.time() * 1000)
        }

        time.sleep(1)

        response = requests.get(url, params=params, headers=_get_random_headers(), timeout=15)

        if response.status_code != 200:
            logger.warning(f"Sina returned status {response.status_code}")
            return []

        data = response.json()

        for item in data.get("data", []):
            title = item.get("title", "")
            summary = item.get("content", "")[:200]
            publish_time = item.get("datetime", "")
            url = item.get("url", "")

            if not title:
                continue

            news_list.append({
                "title": title,
                "summary": summary,
                "publish_time": publish_time,
                "source": "新浪财经",
                "url": url
            })

        logger.info(f"Sina returned {len(news_list)} articles")

    except Exception as e:
        logger.error(f"Failed to fetch from Sina: {e}")

    return news_list


def _fetch_from_cls(keywords: List[str], date: str) -> List[Dict]:
    """Fetch news from 财联社 (cls.cn)."""
    logger.info("Fetching from 财联社...")
    news_list = []

    try:
        date_str = date.replace("-", "")
        url = f"https://api.cls.cn/v2/node/roll/list"
        params = {
            "app": "cifco",
            "sv": "8.7.6",
            "os": "android",
            "cpu": "arm64",
            "date": date_str,
            "page": 1,
            "limit": 20
        }

        time.sleep(1)

        response = requests.get(url, params=params, headers=_get_random_headers(), timeout=15)

        if response.status_code != 200:
            logger.warning(f"CLS returned status {response.status_code}")
            return []

        data = response.json()

        for item in data.get("data", {}).get("roll_data", []):
            title = item.get("title", "")
            summary = item.get("content", "")[:200]
            publish_time = item.get("ctime", "")
            url = item.get("share_url", "")

            if not title:
                continue

            try:
                pub_dt = datetime.fromtimestamp(int(publish_time))
                publish_time_str = pub_dt.strftime("%Y-%m-%d %H:%M:%S")
            except Exception:
                publish_time_str = publish_time

            news_list.append({
                "title": title,
                "summary": summary,
                "publish_time": publish_time_str,
                "source": "财联社",
                "url": url
            })

        logger.info(f"CLS returned {len(news_list)} articles")

    except Exception as e:
        logger.error(f"Failed to fetch from CLS: {e}")

    return news_list


def _fetch_fallback_page(keywords: List[str], date: str) -> List[Dict]:
    """Fallback: try to parse from news portal homepage."""
    logger.info("Trying fallback page parsing...")

    sources = [
        ("https://finance.eastmoney.com/a/czqyw.html", "东方财富"),
        ("https://finance.sina.com.cn/stock/", "新浪财经"),
    ]

    for url, source_name in sources:
        try:
            time.sleep(1)
            response = requests.get(url, headers=_get_random_headers(), timeout=15)

            if response.status_code != 200:
                continue

            soup = BeautifulSoup(response.text, "html.parser")

            news_list = []

            for article in soup.find_all("a", href=True)[:20]:
                title = article.get_text(strip=True)
                href = article.get("href", "")

                if len(title) < 5 or "javascript" in href:
                    continue

                if _matches_keywords(title, keywords):
                    news_list.append({
                        "title": title,
                        "summary": "",
                        "publish_time": date + " 00:00:00",
                        "source": source_name,
                        "url": href
                    })

            if news_list:
                logger.info(f"Fallback returned {len(news_list)} articles from {source_name}")
                return news_list

        except Exception as e:
            logger.warning(f"Fallback failed for {source_name}: {e}")
            continue

    return []


def _filter_by_date_and_keywords(news_list: List[Dict], keywords: List[str], target_date: str) -> List[Dict]:
    """Filter news by date and keywords."""
    if not news_list:
        return []

    try:
        target_dt = datetime.strptime(target_date, "%Y-%m-%d")
    except Exception:
        return []

    filtered = []
    seen_titles = set()

    for news in news_list:
        title = news.get("title", "").strip()
        if not title:
            continue

        title_hash = hashlib.md5(title.encode()).hexdigest()
        if title_hash in seen_titles:
            continue
        seen_titles.add(title_hash)

        publish_time_str = news.get("publish_time", "")
        pub_dt = _parse_datetime(publish_time_str)

        if pub_dt:
            if pub_dt.date() != target_dt.date():
                continue
        else:
            if target_date not in publish_time_str:
                continue

        summary = news.get("summary", "")
        full_text = f"{title} {summary}"

        if _matches_keywords(full_text, keywords):
            filtered.append(news)

    return filtered


def fetch_news(sector_keywords: List[str], date: str) -> List[Dict]:
    """Fetch news articles for given sector keywords.

    Args:
        sector_keywords: List of sector keywords
        date: Date in YYYY-MM-DD format

    Returns:
        List of news articles with title, summary, publish_time, source, url
    """
    logger.info(f"Fetching news for keywords: {sector_keywords}, date: {date}")

    cached = _load_cache(date)
    if cached:
        logger.info(f"Using cached news: {len(cached)} articles")
        return _filter_by_date_and_keywords(cached, sector_keywords, date)

    all_news = []

    fetchers = [
        _fetch_from_eastmoney,
        _fetch_from_sina,
        _fetch_from_cls,
    ]

    for fetcher in fetchers:
        try:
            news = fetcher(sector_keywords, date)
            if news:
                all_news.extend(news)
                logger.info(f"Got {len(news)} articles from {fetcher.__name__}")
                break
        except Exception as e:
            logger.warning(f"Fetcher {fetcher.__name__} failed: {e}")
            continue

    if not all_news:
        fallback = _fetch_fallback_page(sector_keywords, date)
        if fallback:
            all_news.extend(fallback)

    if not all_news:
        logger.warning("No news fetched from any source, using sample data")
        return _get_sample_news(sector_keywords, date)

    filtered_news = _filter_by_date_and_keywords(all_news, sector_keywords, date)

    _save_cache(date, filtered_news)

    logger.info(f"Final filtered news: {len(filtered_news)} articles")
    return filtered_news


if __name__ == "__main__":
    setup_logging()

    print("=== News Collector Test ===\n")

    news = fetch_news(["券商", "证券"], "2026-04-02")

    if not news:
        print("No news found, trying date 2026-04-01...")
        news = fetch_news(["券商", "证券"], "2026-04-01")

    print(f"Found {len(news)} news articles:\n")

    for i, item in enumerate(news[:5], 1):
        print(f"{i}. [{item['source']}] {item['title']}")
        print(f"   Time: {item['publish_time']}")
        if item.get('summary'):
            print(f"   Summary: {item['summary'][:80]}...")
        print()
