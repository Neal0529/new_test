import json
import logging
import os
from datetime import date, datetime
from typing import Dict, List

import yaml

LOG_DIR = "logs"
REPORTS_DIR = "reports"
CONFIG_DIR = "config"


def setup_logging():
    """Configure logging to console and file."""
    os.makedirs(LOG_DIR, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler(f"{LOG_DIR}/report.log")
        ]
    )


logger = logging.getLogger(__name__)


def load_etf_config() -> Dict[str, str]:
    """Load ETF code to name mapping."""
    mapping = {}
    try:
        config_file = os.path.join(CONFIG_DIR, "config.yaml")
        if os.path.exists(config_file):
            with open(config_file, "r", encoding="utf-8") as f:
                config = yaml.safe_load(f)
                for etf in config.get("etfs", []):
                    mapping[etf.get("code", "")] = etf.get("name", "")
            logger.info(f"Loaded {len(mapping)} ETF mappings")
    except Exception as e:
        logger.warning(f"Failed to load ETF config: {e}")
    return mapping


ETF_NAMES = load_etf_config()


def _format_action(action: str) -> str:
    """Format action with color."""
    colors = {
        "BUY_2W": "#28a745",
        "ADD_2W": "#17a2b8",
        "REDUCE_HALF": "#ffc107",
        "CLOSE_ALL": "#dc3545",
        "HOLD": "#6c757d"
    }
    color = colors.get(action, "#6c757d")
    return f'<span style="color: {color}; font-weight: bold;">{action}</span>'


def _format_sentiment(score: float) -> str:
    """Format sentiment with emoji."""
    if score > 0.2:
        return "🟢 Positive"
    elif score < -0.2:
        return "🔴 Negative"
    else:
        return "⚪ Neutral"


def _generate_html(signals: List[Dict], news_summary: Dict, report_date: date) -> str:
    """Generate HTML report."""

    action_counts = {"BUY_2W": 0, "ADD_2W": 0, "REDUCE_HALF": 0, "CLOSE_ALL": 0, "HOLD": 0}
    for sig in signals:
        action = sig.get("action", "HOLD")
        action_counts[action] = action_counts.get(action, 0) + 1

    html = f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>ETF Trading Analysis Report - {report_date.strftime('%Y-%m-%d')}</title>
    <style>
        body {{
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            margin: 20px;
            background-color: #f5f5f5;
        }}
        .container {{
            max-width: 1200px;
            margin: 0 auto;
            background-color: white;
            padding: 20px;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        h1 {{
            color: #333;
            border-bottom: 2px solid #007bff;
            padding-bottom: 10px;
        }}
        h2 {{
            color: #555;
            margin-top: 30px;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            margin-top: 15px;
        }}
        th, td {{
            padding: 12px;
            text-align: left;
            border-bottom: 1px solid #ddd;
        }}
        th {{
            background-color: #007bff;
            color: white;
        }}
        tr:hover {{
            background-color: #f5f5f5;
        }}
        .summary-box {{
            display: flex;
            justify-content: space-between;
            margin: 20px 0;
            padding: 15px;
            background-color: #f8f9fa;
            border-radius: 5px;
        }}
        .summary-item {{
            text-align: center;
            padding: 10px 20px;
        }}
        .summary-item .count {{
            font-size: 24px;
            font-weight: bold;
        }}
        .buy {{ color: #28a745; }}
        .add {{ color: #17a2b8; }}
        .reduce {{ color: #ffc107; }}
        .close {{ color: #dc3545; }}
        .hold {{ color: #6c757d; }}
        .news-item {{
            padding: 10px;
            margin: 5px 0;
            background-color: #f8f9fa;
            border-left: 3px solid #007bff;
            border-radius: 3px;
        }}
        .footer {{
            margin-top: 30px;
            text-align: center;
            color: #999;
            font-size: 12px;
        }}
    </style>
</head>
<body>
    <div class="container">
        <h1>📊 ETF Trading Analysis Report</h1>
        <p><strong>Date:</strong> {report_date.strftime('%Y-%m-%d')}</p>
        
        <h2>📈 Signal Summary</h2>
        <div class="summary-box">
            <div class="summary-item">
                <div class="count buy">{action_counts.get('BUY_2W', 0)}</div>
                <div>BUY</div>
            </div>
            <div class="summary-item">
                <div class="count add">{action_counts.get('ADD_2W', 0)}</div>
                <div>ADD</div>
            </div>
            <div class="summary-item">
                <div class="count reduce">{action_counts.get('REDUCE_HALF', 0)}</div>
                <div>REDUCE</div>
            </div>
            <div class="summary-item">
                <div class="count close">{action_counts.get('CLOSE_ALL', 0)}</div>
                <div>CLOSE</div>
            </div>
            <div class="summary-item">
                <div class="count hold">{action_counts.get('HOLD', 0)}</div>
                <div>HOLD</div>
            </div>
        </div>
        
        <h2>📋 Trading Signals</h2>
        <table>
            <thead>
                <tr>
                    <th>ETF Code</th>
                    <th>Name</th>
                    <th>Position (¥)</th>
                    <th>Action</th>
                    <th>Reason</th>
                    <th>Tech Score</th>
                    <th>Sentiment</th>
                    <th>Final Score</th>
                </tr>
            </thead>
            <tbody>
'''

    for sig in signals:
        etf_code = sig.get("etf_code", "")
        etf_name = ETF_NAMES.get(etf_code, etf_code)
        position = sig.get("current_position", 0)
        action = sig.get("action", "HOLD")
        reason = sig.get("reason", "")
        tech_score = sig.get("tech_score", 0)
        sentiment_score = sig.get("sentiment_score", 0.0)
        final_score = sig.get("final_score", 0)

        html += f'''                <tr>
                    <td>{etf_code}</td>
                    <td>{etf_name}</td>
                    <td>¥{position:,.0f}</td>
                    <td>{_format_action(action)}</td>
                    <td>{reason}</td>
                    <td>{tech_score}</td>
                    <td>{_format_sentiment(sentiment_score)}</td>
                    <td><strong>{final_score}</strong></td>
                </tr>
'''

    html += f'''            </tbody>
        </table>
'''

    if news_summary:
        html += '''
        <h2>📰 Latest News</h2>
'''
        for etf_code, news_list in news_summary.items():
            etf_name = ETF_NAMES.get(etf_code, etf_code)
            html += f'''
        <h3>{etf_name} ({etf_code})</h3>
'''
            for news in news_list[:3]:
                title = news.get("title", "")
                sentiment = news.get("sentiment", 0)
                sentiment_emoji = "🟢" if sentiment > 0.2 else "🔴" if sentiment < -0.2 else "⚪"
                html += f'''
        <div class="news-item">
            {sentiment_emoji} {title}
        </div>
'''

    html += f'''
        <div class="footer">
            <p>Generated at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
            <p>ETF Trading Analysis System v1.0</p>
        </div>
    </div>
</body>
</html>
'''
    return html


def _generate_text(signals: List[Dict], news_summary: Dict, report_date: date) -> str:
    """Generate text report."""

    action_counts = {"BUY_2W": 0, "ADD_2W": 0, "REDUCE_HALF": 0, "CLOSE_ALL": 0, "HOLD": 0}
    for sig in signals:
        action = sig.get("action", "HOLD")
        action_counts[action] = action_counts.get(action, 0) + 1

    lines = []
    lines.append("=" * 80)
    lines.append(f"ETF Trading Analysis Report - {report_date.strftime('%Y-%m-%d')}")
    lines.append("=" * 80)

    lines.append("\n📈 SIGNAL SUMMARY")
    lines.append("-" * 40)
    lines.append(f"  BUY:      {action_counts.get('BUY_2W', 0):>3}")
    lines.append(f"  ADD:      {action_counts.get('ADD_2W', 0):>3}")
    lines.append(f"  REDUCE:   {action_counts.get('REDUCE_HALF', 0):>3}")
    lines.append(f"  CLOSE:    {action_counts.get('CLOSE_ALL', 0):>3}")
    lines.append(f"  HOLD:     {action_counts.get('HOLD', 0):>3}")

    lines.append("\n📋 TRADING SIGNALS")
    lines.append("-" * 80)
    lines.append(f"{'Code':<10} {'Name':<15} {'Position':>12} {'Action':<12} {'Tech':>6} {'Sent':>6} {'Final':>6}")
    lines.append("-" * 80)

    for sig in signals:
        etf_code = sig.get("etf_code", "")
        etf_name = ETF_NAMES.get(etf_code, etf_code)[:12]
        position = sig.get("current_position", 0)
        action = sig.get("action", "HOLD")
        tech_score = sig.get("tech_score", 0)
        sentiment_score = sig.get("sentiment_score", 0.0)
        final_score = sig.get("final_score", 0)

        lines.append(f"{etf_code:<10} {etf_name:<15} ¥{position:>9,.0f} {action:<12} {tech_score:>6.0f} {sentiment_score:>6.2f} {final_score:>6.0f}")

    if news_summary:
        lines.append("\n📰 LATEST NEWS")
        lines.append("-" * 40)
        for etf_code, news_list in news_summary.items():
            etf_name = ETF_NAMES.get(etf_code, etf_code)
            lines.append(f"\n{etf_name} ({etf_code}):")
            for news in news_list[:3]:
                title = news.get("title", "")[:60]
                sentiment = news.get("sentiment", 0)
                emoji = "🟢" if sentiment > 0.2 else "🔴" if sentiment < -0.2 else "⚪"
                lines.append(f"  {emoji} {title}")

    lines.append("\n" + "=" * 80)
    lines.append(f"Generated at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append("=" * 80)

    return "\n".join(lines)


def generate_report(signals: List[Dict], news_summary: Dict, report_date: date) -> str:
    """Generate analysis report.

    Args:
        signals: List of signal dicts
        news_summary: Dict of news by ETF code
        report_date: Date object for the report

    Returns:
        Path to saved HTML report
    """
    os.makedirs(REPORTS_DIR, exist_ok=True)

    if not signals:
        logger.warning("No signals provided, generating empty report")
        signals = []
    if not news_summary:
        news_summary = {}

    date_str = report_date.strftime("%Y-%m-%d")

    html_content = _generate_html(signals, news_summary, report_date)
    html_file = os.path.join(REPORTS_DIR, f"{date_str}_report.html")
    with open(html_file, "w", encoding="utf-8") as f:
        f.write(html_content)
    logger.info(f"Saved HTML report to {html_file}")

    text_content = _generate_text(signals, news_summary, report_date)
    text_file = os.path.join(REPORTS_DIR, f"{date_str}_report.txt")
    with open(text_file, "w", encoding="utf-8") as f:
        f.write(text_content)
    logger.info(f"Saved text report to {text_file}")

    print(text_content)

    return html_file


if __name__ == "__main__":
    setup_logging()

    print("=== Report Generator Test ===\n")

    test_signals = [
        {
            "etf_code": "512000",
            "current_position": 0,
            "action": "BUY_2W",
            "reason": "entry signal: score=119 >= threshold=70",
            "tech_score": 90,
            "sentiment_score": 0.3,
            "final_score": 119
        },
        {
            "etf_code": "588000",
            "current_position": 20000,
            "action": "HOLD",
            "reason": "insufficient score: 65 < 70",
            "tech_score": 65,
            "sentiment_score": 0.0,
            "final_score": 65
        },
        {
            "etf_code": "159582",
            "current_position": 35000,
            "action": "CLOSE_ALL",
            "reason": "stop_loss triggered: pnl=-6.5%",
            "tech_score": 40,
            "sentiment_score": -0.3,
            "final_score": 40
        }
    ]

    test_news = {
        "512000": [
            {"title": "券商板块迎来政策利好", "sentiment": 0.5},
            {"title": "监管层释放积极信号", "sentiment": 0.3},
        ],
        "159582": [
            {"title": "半导体行业业绩下滑", "sentiment": -0.4},
        ]
    }

    report_date = date.today()
    html_path = generate_report(test_signals, test_news, report_date)

    print(f"\n✅ Report saved to: {html_path}")
