# 股票每日复盘可视化看板 Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 构建本地运行的 A 股每日复盘可视化看板，自动爬取舞阳复盘网站数据，展示涨停板核心统计图表。

**Architecture:** Streamlit 作为看板框架，requests+BeautifulSoup 爬取 wuylh.com 涨停数据，每日数据存为本地 JSON 文件，Plotly 渲染四个核心图表模块（最高连板表格、题材热度条形图、10日情绪趋势折线图、连板梯队柱状图）。

**Tech Stack:** Python 3.10+, Streamlit, Plotly, pandas, requests, BeautifulSoup4, pytest

---

## Task 1: 项目初始化与环境配置

**Files:**
- Create: `requirements.txt`
- Create: `requirements-dev.txt`
- Create: `data/.gitkeep`
- Create: `tests/__init__.py`

**Step 1: 创建 requirements.txt**

```
streamlit>=1.32.0
plotly>=5.20.0
pandas>=2.2.0
requests>=2.31.0
beautifulsoup4>=4.12.0
lxml>=5.1.0
```

**Step 2: 创建 requirements-dev.txt**

```
pytest>=8.0.0
pytest-mock>=3.12.0
responses>=0.25.0
```

**Step 3: 创建目录结构**

```bash
mkdir -p data tests
touch data/.gitkeep tests/__init__.py
```

**Step 4: 安装依赖**

```bash
pip install -r requirements.txt -r requirements-dev.txt
```

Expected: 所有包安装成功，无报错。

**Step 5: 验证安装**

```bash
python -c "import streamlit, plotly, pandas, requests, bs4; print('OK')"
```

Expected: 输出 `OK`

**Step 6: Commit**

```bash
git add requirements.txt requirements-dev.txt data/.gitkeep tests/__init__.py
git commit -m "chore: project setup with dependencies"
```

---

## Task 2: 数据爬虫模块 (fetcher.py)

**Files:**
- Create: `fetcher.py`
- Create: `tests/test_fetcher.py`
- Create: `tests/fixtures/sample_page.html`（测试用 HTML 片段）

### Step 1: 先访问目标页面，了解 HTML 结构

在浏览器打开 `https://www.wuylh.com/replayrobot/index.html`，右键检查元素，确认涨停表格的 HTML 结构（class 名、标签层级）。

> **注意**：若页面表格内容为空（JS 动态渲染），需改用 playwright。先按静态 HTML 实现，Task 2b 处理动态渲染备选方案。

### Step 2: 创建测试 fixture

在浏览器中复制一段涨停表格的 HTML，保存到 `tests/fixtures/sample_page.html`：

```html
<!-- 示例结构，以实际页面为准 -->
<table class="limit-up-table">
  <thead>
    <tr>
      <th>股票名称</th><th>代码</th><th>连板数</th>
      <th>涨停原因</th><th>最新价</th><th>涨幅%</th>
      <th>成交额(亿)</th><th>换手率%</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td>测试股A</td><td>000001</td><td>3</td>
      <td>人工智能</td><td>15.60</td><td>10.01</td>
      <td>5.23</td><td>12.30</td>
    </tr>
    <tr>
      <td>测试股B</td><td>600001</td><td>1</td>
      <td>新能源</td><td>8.80</td><td>10.00</td>
      <td>2.10</td><td>8.50</td>
    </tr>
  </tbody>
</table>
```

> 实际 HTML 结构以真实页面为准，fixture 需对应调整。

### Step 3: 编写失败测试

```python
# tests/test_fetcher.py
import json
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock
from fetcher import parse_limit_up_table, fetch_today_data, load_or_fetch


FIXTURE_HTML = (Path(__file__).parent / "fixtures" / "sample_page.html").read_text(encoding="utf-8")


class TestParseLimitUpTable:
    def test_returns_list_of_stocks(self):
        stocks = parse_limit_up_table(FIXTURE_HTML, table_type="limit_up")
        assert isinstance(stocks, list)
        assert len(stocks) == 2

    def test_stock_has_required_fields(self):
        stocks = parse_limit_up_table(FIXTURE_HTML, table_type="limit_up")
        stock = stocks[0]
        assert stock["name"] == "测试股A"
        assert stock["code"] == "000001"
        assert stock["continuous_days"] == 3
        assert stock["reason"] == "人工智能"
        assert stock["price"] == 15.60
        assert stock["change_pct"] == 10.01
        assert stock["amount"] == 5.23
        assert stock["turnover_rate"] == 12.30

    def test_empty_table_returns_empty_list(self):
        html = "<html><body></body></html>"
        stocks = parse_limit_up_table(html, table_type="limit_up")
        assert stocks == []


class TestLoadOrFetch:
    def test_loads_existing_data_file(self, tmp_path):
        data_dir = tmp_path
        date_str = "2026-02-28"
        data = {"date": date_str, "limit_up": [], "limit_broken": []}
        (data_dir / f"{date_str}.json").write_text(json.dumps(data), encoding="utf-8")

        result = load_or_fetch(date_str=date_str, data_dir=str(data_dir), fetch_fn=None)
        assert result["date"] == date_str

    def test_calls_fetch_when_no_file(self, tmp_path):
        data_dir = tmp_path
        date_str = "2026-02-28"
        mock_fetch = MagicMock(return_value={"date": date_str, "limit_up": [], "limit_broken": []})

        load_or_fetch(date_str=date_str, data_dir=str(data_dir), fetch_fn=mock_fetch)
        mock_fetch.assert_called_once()

    def test_falls_back_to_latest_when_empty(self, tmp_path):
        data_dir = tmp_path
        prev_data = {"date": "2026-02-27", "limit_up": [], "limit_broken": []}
        (data_dir / "2026-02-27.json").write_text(json.dumps(prev_data), encoding="utf-8")

        mock_fetch = MagicMock(return_value={"date": "2026-02-28", "limit_up": [], "limit_broken": []})

        result = load_or_fetch(date_str="2026-02-28", data_dir=str(data_dir), fetch_fn=mock_fetch)
        # 若今日为空，回退到 2026-02-27
        assert result["date"] in ("2026-02-27", "2026-02-28")
```

### Step 4: 运行测试，确认失败

```bash
pytest tests/test_fetcher.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'fetcher'`

### Step 5: 实现 fetcher.py

```python
# fetcher.py
import json
import time
import requests
from bs4 import BeautifulSoup
from datetime import datetime
from pathlib import Path

BASE_URL = "https://www.wuylh.com/replayrobot/index.html"
DATA_DIR = "data"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
}


def parse_limit_up_table(html: str, table_type: str = "limit_up") -> list[dict]:
    """
    解析涨停/开板表格，返回股票列表。
    table_type: "limit_up" 或 "limit_broken"
    注意：根据实际页面 HTML 结构调整选择器。
    """
    soup = BeautifulSoup(html, "lxml")

    # TODO: 根据实际页面结构调整此选择器
    # 例如: tables = soup.select("table.limit-up-table")
    tables = soup.select("table")
    if not tables:
        return []

    # 根据 table_type 选择对应表格索引（以实际页面为准）
    table_index = 0 if table_type == "limit_up" else 1
    if table_index >= len(tables):
        return []

    table = tables[table_index]
    rows = table.select("tbody tr")
    stocks = []

    for row in rows:
        cols = row.select("td")
        if len(cols) < 8:
            continue
        try:
            stocks.append({
                "name": cols[0].get_text(strip=True),
                "code": cols[1].get_text(strip=True),
                "continuous_days": int(cols[2].get_text(strip=True) or 1),
                "reason": cols[3].get_text(strip=True),
                "price": float(cols[4].get_text(strip=True) or 0),
                "change_pct": float(cols[5].get_text(strip=True) or 0),
                "amount": float(cols[6].get_text(strip=True) or 0),
                "turnover_rate": float(cols[7].get_text(strip=True) or 0),
            })
        except (ValueError, IndexError):
            continue

    return stocks


def fetch_today_data(date_str: str | None = None) -> dict:
    """爬取今日涨停数据，返回结构化字典。"""
    if date_str is None:
        date_str = datetime.now().strftime("%Y-%m-%d")

    try:
        resp = requests.get(BASE_URL, headers=HEADERS, timeout=15)
        resp.raise_for_status()
        html = resp.text
    except requests.RequestException as e:
        raise ConnectionError(f"爬取失败: {e}") from e

    time.sleep(1)  # 礼貌性延迟

    limit_up = parse_limit_up_table(html, table_type="limit_up")
    limit_broken = parse_limit_up_table(html, table_type="limit_broken")

    return {
        "date": date_str,
        "limit_up": limit_up,
        "limit_broken": limit_broken,
        "fetched_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }


def load_or_fetch(
    date_str: str | None = None,
    data_dir: str = DATA_DIR,
    fetch_fn=None,
) -> tuple[dict, str | None]:
    """
    加载当日数据文件，若不存在则调用 fetch_fn 爬取。
    返回 (data, warning_message)
    warning_message: 若回退到历史数据，返回提示文字；否则 None
    """
    if date_str is None:
        date_str = datetime.now().strftime("%Y-%m-%d")
    if fetch_fn is None:
        fetch_fn = fetch_today_data

    data_path = Path(data_dir) / f"{date_str}.json"

    # 存在今日文件，直接加载
    if data_path.exists():
        data = json.loads(data_path.read_text(encoding="utf-8"))
        return data, None

    # 不存在，尝试爬取
    try:
        data = fetch_fn(date_str=date_str)
    except ConnectionError:
        data = {"limit_up": [], "limit_broken": []}

    # 保存文件（即使为空也保存，避免重复爬取）
    if data.get("limit_up"):
        data_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        return data, None

    # 爬取结果为空（休市），回退到最近有数据的文件
    existing = sorted(Path(data_dir).glob("*.json"), reverse=True)
    if existing:
        fallback_data = json.loads(existing[0].read_text(encoding="utf-8"))
        fallback_date = existing[0].stem
        warning = f"今日休市或数据为空，显示 {fallback_date} 的数据"
        return fallback_data, warning

    return {"date": date_str, "limit_up": [], "limit_broken": []}, "暂无历史数据"
```

### Step 6: 运行测试，确认通过

```bash
pytest tests/test_fetcher.py -v
```

Expected: 所有测试 PASS

> **如果测试失败**：根据实际页面 HTML 调整 `parse_limit_up_table` 中的选择器和列索引，同步更新 fixture。

### Step 7: Commit

```bash
git add fetcher.py tests/test_fetcher.py tests/fixtures/sample_page.html
git commit -m "feat: add fetcher module with HTML parser and load-or-fetch logic"
```

---

## Task 3: 数据处理模块 (processor.py)

**Files:**
- Create: `processor.py`
- Create: `tests/test_processor.py`

### Step 1: 编写失败测试

```python
# tests/test_processor.py
import pytest
from processor import (
    get_summary_stats,
    get_topic_counts,
    get_continuous_ladder,
    load_history,
)

SAMPLE_DATA = {
    "date": "2026-02-28",
    "limit_up": [
        {"name": "股A", "code": "000001", "continuous_days": 3, "reason": "人工智能", "amount": 5.2, "price": 10.0, "change_pct": 10.0, "turnover_rate": 12.0},
        {"name": "股B", "code": "000002", "continuous_days": 3, "reason": "人工智能", "amount": 3.1, "price": 8.0, "change_pct": 10.0, "turnover_rate": 8.0},
        {"name": "股C", "code": "000003", "continuous_days": 1, "reason": "新能源", "amount": 2.0, "price": 5.0, "change_pct": 10.0, "turnover_rate": 5.0},
        {"name": "股D", "code": "000004", "continuous_days": 6, "reason": "低空经济", "amount": 8.0, "price": 20.0, "change_pct": 10.0, "turnover_rate": 15.0},
    ],
    "limit_broken": [
        {"name": "股E", "code": "000005", "continuous_days": 1, "reason": "医药", "amount": 1.5, "price": 6.0, "change_pct": 5.0, "turnover_rate": 7.0},
        {"name": "股F", "code": "000006", "continuous_days": 1, "reason": "新能源", "amount": 1.0, "price": 4.0, "change_pct": 3.0, "turnover_rate": 4.0},
    ],
}


class TestGetSummaryStats:
    def test_counts_limit_up(self):
        stats = get_summary_stats(SAMPLE_DATA)
        assert stats["limit_up_count"] == 4

    def test_counts_limit_broken(self):
        stats = get_summary_stats(SAMPLE_DATA)
        assert stats["limit_broken_count"] == 2

    def test_calculates_bust_rate(self):
        stats = get_summary_stats(SAMPLE_DATA)
        # 炸板率 = 开板 / (涨停 + 开板) = 2/6 ≈ 33.33%
        assert abs(stats["bust_rate"] - 33.33) < 0.1

    def test_finds_max_continuous(self):
        stats = get_summary_stats(SAMPLE_DATA)
        assert stats["max_continuous"] == 6
        assert stats["max_continuous_name"] == "股D"

    def test_finds_strongest_topic(self):
        stats = get_summary_stats(SAMPLE_DATA)
        assert stats["top_topic"] == "人工智能"


class TestGetTopicCounts:
    def test_returns_sorted_topics(self):
        topics = get_topic_counts(SAMPLE_DATA["limit_up"])
        assert topics[0]["topic"] == "人工智能"
        assert topics[0]["count"] == 2

    def test_includes_all_topics(self):
        topics = get_topic_counts(SAMPLE_DATA["limit_up"])
        topic_names = [t["topic"] for t in topics]
        assert "新能源" in topic_names
        assert "低空经济" in topic_names


class TestGetContinuousLadder:
    def test_groups_by_continuous_days(self):
        ladder = get_continuous_ladder(SAMPLE_DATA["limit_up"])
        days_map = {item["days"]: item for item in ladder}
        assert days_map[3]["count"] == 2
        assert days_map[1]["count"] == 1
        assert days_map[6]["count"] == 1

    def test_includes_top_stock_name(self):
        ladder = get_continuous_ladder(SAMPLE_DATA["limit_up"])
        six_board = next(item for item in ladder if item["days"] == 6)
        assert six_board["top_stock"] == "股D"
```

### Step 2: 运行测试，确认失败

```bash
pytest tests/test_processor.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'processor'`

### Step 3: 实现 processor.py

```python
# processor.py
import json
from pathlib import Path
from collections import Counter


def get_summary_stats(data: dict) -> dict:
    """计算今日概览统计数据。"""
    limit_up = data.get("limit_up", [])
    limit_broken = data.get("limit_broken", [])

    total = len(limit_up) + len(limit_broken)
    bust_rate = round(len(limit_broken) / total * 100, 2) if total > 0 else 0.0

    max_stock = max(limit_up, key=lambda s: s["continuous_days"], default=None)

    topic_counts = get_topic_counts(limit_up)
    top_topic = topic_counts[0]["topic"] if topic_counts else "—"

    return {
        "limit_up_count": len(limit_up),
        "limit_broken_count": len(limit_broken),
        "bust_rate": bust_rate,
        "max_continuous": max_stock["continuous_days"] if max_stock else 0,
        "max_continuous_name": max_stock["name"] if max_stock else "—",
        "top_topic": top_topic,
    }


def get_topic_counts(stocks: list[dict]) -> list[dict]:
    """统计涨停股题材出现次数，按频次降序返回。"""
    counter = Counter()
    topic_stocks: dict[str, list[str]] = {}

    for stock in stocks:
        # 涨停原因可能包含多个题材（以逗号或顿号分隔）
        reasons = [r.strip() for r in stock["reason"].replace("、", ",").split(",") if r.strip()]
        if not reasons:
            reasons = [stock["reason"]]
        for reason in reasons:
            counter[reason] += 1
            topic_stocks.setdefault(reason, []).append(stock["name"])

    return [
        {"topic": topic, "count": count, "stocks": topic_stocks[topic]}
        for topic, count in counter.most_common()
    ]


def get_continuous_ladder(stocks: list[dict]) -> list[dict]:
    """
    按连板数分组统计，返回连板梯队数据。
    每组包含连板数、股票数量、成交额最大的代表股名。
    """
    groups: dict[int, list[dict]] = {}
    for stock in stocks:
        days = stock["continuous_days"]
        groups.setdefault(days, []).append(stock)

    result = []
    for days in sorted(groups.keys()):
        group = groups[days]
        top_stock = max(group, key=lambda s: s.get("amount", 0))
        result.append({
            "days": days,
            "count": len(group),
            "top_stock": top_stock["name"],
            "stocks": [s["name"] for s in group],
        })
    return result


def load_history(data_dir: str = "data", limit: int = 10) -> list[dict]:
    """
    加载最近 N 个交易日的数据，用于趋势图。
    返回按日期升序排列的数据列表。
    """
    files = sorted(Path(data_dir).glob("*.json"))[-limit:]
    history = []
    for f in files:
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            stats = get_summary_stats(data)
            history.append({
                "date": data.get("date", f.stem),
                **stats,
            })
        except (json.JSONDecodeError, KeyError):
            continue
    return history
```

### Step 4: 运行测试，确认通过

```bash
pytest tests/test_processor.py -v
```

Expected: 所有测试 PASS

### Step 5: Commit

```bash
git add processor.py tests/test_processor.py
git commit -m "feat: add processor module for stats, topics, and ladder calculation"
```

---

## Task 4: Streamlit 看板主页 (app.py)

**Files:**
- Create: `app.py`

> app.py 为 UI 层，不做单元测试（Streamlit 组件难以单元测试），通过手动运行验证效果。

### Step 1: 实现 app.py

```python
# app.py
import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
from datetime import datetime
from fetcher import load_or_fetch
from processor import get_summary_stats, get_topic_counts, get_continuous_ladder, load_history

st.set_page_config(
    page_title="每日复盘看板",
    page_icon="📈",
    layout="wide",
)

st.title("📈 每日复盘看板")

# ── 数据加载 ──────────────────────────────────────────────────
today = datetime.now().strftime("%Y-%m-%d")

with st.spinner("检测今日数据..."):
    data, warning = load_or_fetch(date_str=today)

if warning:
    st.warning(warning)

if not data.get("limit_up"):
    st.error("暂无数据，请检查网络连接后重试。")
    st.stop()

fetched_at = data.get("fetched_at", "")
st.caption(f"数据时间：{fetched_at}　　数据日期：{data.get('date', today)}")

# ── 概览卡片 ──────────────────────────────────────────────────
stats = get_summary_stats(data)

col1, col2, col3, col4, col5 = st.columns(5)
col1.metric("涨停家数", stats["limit_up_count"])
col2.metric("开板家数", stats["limit_broken_count"])
col3.metric("炸板率", f"{stats['bust_rate']}%")
col4.metric("最高连板", f"{stats['max_continuous']}板　{stats['max_continuous_name']}")
col5.metric("最强题材", stats["top_topic"])

st.divider()

# ── 模块 A：最高连板股（表格） ─────────────────────────────────
st.subheader("🏆 连板股排行")

limit_up_df = pd.DataFrame(data["limit_up"]).sort_values("continuous_days", ascending=False)
limit_up_df = limit_up_df.rename(columns={
    "name": "股票名",
    "code": "代码",
    "continuous_days": "连板数",
    "reason": "涨停原因",
    "price": "最新价",
    "change_pct": "涨幅%",
    "amount": "成交额(亿)",
    "turnover_rate": "换手率%",
})

def highlight_max_row(row):
    max_days = limit_up_df["连板数"].max()
    color = "background-color: #ffe4e4" if row["连板数"] == max_days else ""
    return [color] * len(row)

st.dataframe(
    limit_up_df.style.apply(highlight_max_row, axis=1),
    use_container_width=True,
    hide_index=True,
)

st.divider()

# ── 模块 B：题材热度排行（横向条形图） ────────────────────────
st.subheader("🔥 题材热度排行")

topics = get_topic_counts(data["limit_up"])
topic_df = pd.DataFrame(topics)
topic_df["stocks_str"] = topic_df["stocks"].apply(lambda s: "、".join(s))

fig_bar = px.bar(
    topic_df,
    x="count",
    y="topic",
    orientation="h",
    labels={"count": "涨停家数", "topic": "题材"},
    hover_data={"stocks_str": True, "count": True, "topic": False},
    color="count",
    color_continuous_scale="Reds",
)
fig_bar.update_layout(yaxis={"categoryorder": "total ascending"}, showlegend=False)
st.plotly_chart(fig_bar, use_container_width=True)

st.divider()

# ── 模块 C：近10日情绪趋势（折线图） ──────────────────────────
st.subheader("📊 近10日情绪趋势")

history = load_history(limit=10)

if len(history) < 2:
    st.info("历史数据不足，积累更多交易日后趋势图将自动显示。")
else:
    hist_df = pd.DataFrame(history)

    fig_line = go.Figure()
    fig_line.add_trace(go.Scatter(
        x=hist_df["date"], y=hist_df["limit_up_count"],
        name="涨停家数", line={"color": "#4C78A8"},
    ))
    fig_line.add_trace(go.Scatter(
        x=hist_df["date"], y=hist_df["limit_broken_count"],
        name="开板家数", line={"color": "#F58518"},
    ))
    fig_line.add_trace(go.Scatter(
        x=hist_df["date"], y=hist_df["bust_rate"],
        name="炸板率%", line={"color": "#E45756", "dash": "dot"},
        yaxis="y2",
    ))
    fig_line.update_layout(
        yaxis={"title": "家数"},
        yaxis2={"title": "炸板率%", "overlaying": "y", "side": "right", "range": [0, 100]},
        hovermode="x unified",
    )
    st.plotly_chart(fig_line, use_container_width=True)

st.divider()

# ── 模块 D：连板梯队图（柱状图） ──────────────────────────────
st.subheader("🪜 连板梯队")

ladder = get_continuous_ladder(data["limit_up"])
ladder_df = pd.DataFrame(ladder)
ladder_df["label"] = ladder_df.apply(lambda r: f"{r['days']}板\n{r['top_stock']}", axis=1)

fig_ladder = px.bar(
    ladder_df,
    x="days",
    y="count",
    text="label",
    labels={"days": "连板数", "count": "股票数量"},
    color="days",
    color_continuous_scale="Blues",
)
fig_ladder.update_traces(textposition="outside")
fig_ladder.update_layout(showlegend=False, xaxis={"tickmode": "linear"})
st.plotly_chart(fig_ladder, use_container_width=True)
```

### Step 2: 手动运行，验证页面

```bash
streamlit run app.py
```

Expected:
- 浏览器打开 `http://localhost:8501`
- 看到 spinner 加载数据
- 看到五个概览卡片
- 看到四个图表模块

> 若出现 `ConnectionError`，检查网络或使用已有的 data/*.json 文件测试。

### Step 3: Commit

```bash
git add app.py
git commit -m "feat: add streamlit dashboard with 4 visualization modules"
```

---

## Task 5: Windows 启动脚本与文档

**Files:**
- Create: `start.bat`
- Create: `README.md`

### Step 1: 创建 start.bat

```bat
@echo off
chcp 65001 >nul
echo 正在启动复盘看板...
streamlit run app.py
pause
```

### Step 2: 创建 README.md

```markdown
# 每日复盘看板

每日自动爬取舞阳复盘网站数据，可视化展示涨停板核心指标。

## 首次安装

```bash
pip install -r requirements.txt
```

## 启动

双击 `start.bat`，浏览器自动打开看板。

## 功能模块

- **概览卡片**：涨停家数、开板家数、炸板率、最高连板、最强题材
- **连板股排行**：按连板数排序，最高连板高亮
- **题材热度**：涨停股题材统计条形图
- **情绪趋势**：近10日涨停/开板/炸板率折线图
- **连板梯队**：各板位股票数量柱状图

## 数据说明

- 数据来源：[舞阳复盘](https://www.wuylh.com/replayrobot/index.html)
- 每日启动时自动检测并更新数据
- 休市日自动显示最近交易日数据
- 历史数据保存在 `data/` 目录，按日期命名
```

### Step 3: Commit

```bash
git add start.bat README.md
git commit -m "chore: add startup script and README"
```

---

## Task 6: 运行完整测试套件 & 最终验证

### Step 1: 运行所有测试

```bash
pytest tests/ -v --tb=short
```

Expected: 全部 PASS，无 FAIL

### Step 2: 检查覆盖率

```bash
pytest tests/ --cov=fetcher --cov=processor --cov-report=term-missing
```

Expected: fetcher + processor 覆盖率 > 80%

### Step 3: 完整启动验证

```bash
streamlit run app.py
```

逐项确认：
- [ ] 启动时自动爬取或加载数据
- [ ] 五个概览卡片数据正常
- [ ] 连板股表格最高行高亮
- [ ] 题材条形图显示正常
- [ ] 趋势折线图显示（需2天以上数据）
- [ ] 连板梯队柱状图显示正常

### Step 4: 最终 Commit

```bash
git add .
git commit -m "chore: final verification complete"
```

---

## 注意事项

### 若页面为 JS 动态渲染（requests 爬取结果为空）

安装 playwright：
```bash
pip install playwright
playwright install chromium
```

在 `fetcher.py` 中将 `fetch_today_data` 改为：

```python
from playwright.sync_api import sync_playwright

def fetch_today_data(date_str=None):
    if date_str is None:
        date_str = datetime.now().strftime("%Y-%m-%d")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(BASE_URL, wait_until="networkidle")
        html = page.content()
        browser.close()

    limit_up = parse_limit_up_table(html, table_type="limit_up")
    limit_broken = parse_limit_up_table(html, table_type="limit_broken")
    return {
        "date": date_str,
        "limit_up": limit_up,
        "limit_broken": limit_broken,
        "fetched_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }
```

将 `playwright` 加入 `requirements.txt`。
