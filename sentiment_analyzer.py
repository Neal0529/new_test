import logging
import os
import re
from typing import Dict, List

import yaml

LOG_DIR = "logs"
CONFIG_FILE = "config/config.yaml"

DEFAULT_BULL_KEYWORDS = ["降息", "版号", "大基金", "鼓励", "利好"]
DEFAULT_BEAR_KEYWORDS = ["反垄断", "罚款", "禁售", "退市", "调查"]

SNOWNLP_AVAILABLE = False
try:
    from snownlp import SnowNLP
    SNOWNLP_AVAILABLE = True
except ImportError:
    pass


def setup_logging():
    """Configure logging to console and file."""
    os.makedirs(LOG_DIR, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler(f"{LOG_DIR}/sentiment_analyzer.log")
        ]
    )


logger = logging.getLogger(__name__)


def load_keywords() -> tuple:
    """Load sentiment keywords from config file.

    Returns:
        Tuple of (bull_keywords, bear_keywords)
    """
    try:
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                config = yaml.safe_load(f)
            bull_keywords = config.get("news", {}).get("strong_bull_keywords", DEFAULT_BULL_KEYWORDS)
            bear_keywords = config.get("news", {}).get("strong_bear_keywords", DEFAULT_BEAR_KEYWORDS)
            logger.info(f"Loaded keywords from config: bull={bull_keywords}, bear={bear_keywords}")
            return bull_keywords, bear_keywords
    except Exception as e:
        logger.warning(f"Failed to load keywords: {e}")

    return DEFAULT_BULL_KEYWORDS, DEFAULT_BEAR_KEYWORDS


BULL_KEYWORDS, BEAR_KEYWORDS = load_keywords()

POSITIVE_WORDS = {
    "上涨", "增长", "利好", "突破", "创新高", "强势", "看涨", "推荐", "买入",
    "增长", "扩张", "提升", "好转", "复苏", "景气", "活跃", "强劲"
}

NEGATIVE_WORDS = {
    "下跌", "下降", "利空", "跌破", "新低", "弱势", "看跌", "减持", "卖出",
    "减少", "收缩", "下滑", "恶化", "低迷", "萧条", "疲软", "风险"
}


def _score_text_snownlp(text: str) -> float:
    """Score text using SnowNLP.

    Args:
        text: Text to analyze

    Returns:
        Sentiment score from -1 to 1
    """
    try:
        s = SnowNLP(text)
        score = s.sentiments
        return (score - 0.5) * 2
    except Exception as e:
        logger.warning(f"SnowNLP scoring failed: {e}")
        return _score_text_fallback(text)


def _score_text_fallback(text: str) -> float:
    """Fallback rule-based sentiment scoring.

    Args:
        text: Text to analyze

    Returns:
        Sentiment score from -1 to 1
    """
    text_lower = text.lower()
    pos_count = sum(1 for word in POSITIVE_WORDS if word in text_lower)
    neg_count = sum(1 for word in NEGATIVE_WORDS if word in text_lower)

    total = pos_count + neg_count
    if total == 0:
        return 0.0

    return (pos_count - neg_count) / total


def _score_text(text: str) -> float:
    """Score text sentiment.

    Args:
        text: Text to analyze

    Returns:
        Sentiment score from -1 to 1
    """
    if SNOWNLP_AVAILABLE:
        return _score_text_snownlp(text)
    else:
        logger.warning("SnowNLP not available, using fallback scoring")
        return _score_text_fallback(text)


def _check_keywords(text: str) -> tuple:
    """Check for bull/bear keywords in text.

    Args:
        text: Text to check

    Returns:
        Tuple of (has_bull, has_bear)
    """
    has_bull = any(kw in text for kw in BULL_KEYWORDS)
    has_bear = any(kw in text for kw in BEAR_KEYWORDS)
    return has_bull, has_bear


def analyze_sentiment(news_list: List[Dict]) -> Dict:
    """Analyze sentiment of news articles.

    Args:
        news_list: List of news dicts with title, summary, publish_time, source, url

    Returns:
        Dict with daily_sentiment, sentiment_trend, event_flag, keyword_adj
    """
    if not news_list:
        logger.info("No news to analyze, returning neutral sentiment")
        return {
            "daily_sentiment": 0.0,
            "sentiment_trend": 0.0,
            "event_flag": "neutral",
            "keyword_adj": 0.0
        }

    scores = []
    keyword_adj = 0.0
    has_strong_bull = False
    has_strong_bear = False

    for news in news_list:
        title = news.get("title", "")
        summary = news.get("summary", "")
        text = f"{title} {summary}"

        score = _score_text(text)
        scores.append(score)

        has_bull, has_bear = _check_keywords(text)

        if has_bull and not has_bear:
            keyword_adj += 0.1
        elif has_bear and not has_bull:
            keyword_adj -= 0.1
        elif has_bull and has_bear:
            keyword_adj += 0

        if has_bull and score > 0.6:
            has_strong_bull = True
        if has_bear and score < -0.6:
            has_strong_bear = True

    keyword_adj = max(-0.5, min(0.5, keyword_adj))

    daily_sentiment = sum(scores) / len(scores) if scores else 0.0

    sentiment_trend = daily_sentiment

    if has_strong_bull:
        event_flag = "strong_bull"
    elif has_strong_bear:
        event_flag = "strong_bear"
    else:
        event_flag = "neutral"

    result = {
        "daily_sentiment": round(daily_sentiment, 4),
        "sentiment_trend": round(sentiment_trend, 4),
        "event_flag": event_flag,
        "keyword_adj": round(keyword_adj, 4)
    }

    logger.info(f"Sentiment analysis: {result}")

    return result


if __name__ == "__main__":
    setup_logging()

    print("=== Sentiment Analyzer Test ===\n")

    test_news_bull = [
        {
            "title": "央行降息释放流动性，券商板块迎来利好",
            "summary": "央行宣布降息25个基点，市场流动性将得到改善，券商行业有望受益。",
            "publish_time": "2026-04-01 10:00:00",
            "source": "财联社",
            "url": "https://example.com/1"
        },
        {
            "title": "券商行业业绩大幅增长",
            "summary": "多家券商发布年报，业绩同比增长30%，超出市场预期。",
            "publish_time": "2026-04-01 11:00:00",
            "source": "新浪财经",
            "url": "https://example.com/2"
        }
    ]

    test_news_bear = [
        {
            "title": "监管层启动反垄断调查",
            "summary": "监管部门对某大型券商启动反垄断调查，市场担忧情绪升温。",
            "publish_time": "2026-04-01 10:00:00",
            "source": "证券时报",
            "url": "https://example.com/3"
        },
        {
            "title": "券商板块大幅下跌",
            "summary": "受利空消息影响，券商板块今日大幅下跌，跌幅超过5%。",
            "publish_time": "2026-04-01 14:00:00",
            "source": "东方财富",
            "url": "https://example.com/4"
        }
    ]

    print("Test 1: Bullish news with '降息' keyword")
    result1 = analyze_sentiment(test_news_bull)
    print(f"Result: {result1}\n")

    print("Test 2: Bearish news with '反垄断' keyword")
    result2 = analyze_sentiment(test_news_bear)
    print(f"Result: {result2}\n")

    print("Test 3: Empty news list")
    result3 = analyze_sentiment([])
    print(f"Result: {result3}")
