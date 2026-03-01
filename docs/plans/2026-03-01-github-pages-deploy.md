# GitHub Pages 部署实施计划

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 将现有 A 股复盘 Streamlit 看板重构为 Vanilla JS + Plotly.js 静态页面，部署到 GitHub Pages，并通过 GitHub Actions 每天 16:00 自动抓取数据。

**Architecture:** 单分支方案——代码与数据（data/*.json）全部在 main 分支。GitHub Actions 每天定时运行 Python 脚本抓取 wuylh.com 数据并推送，GitHub Pages 自动反映最新内容。前端通过 `fetch()` 读取 JSON，用 Plotly.js 渲染图表，无需任何构建工具。

**Tech Stack:** Vanilla JS (ES2020), Plotly.js 2.35 (CDN), 纯 CSS，Python 3.12 + requests (GitHub Actions)，gh CLI（仓库创建）

---

## 前置检查

运行以下命令确认环境：

```bash
# 检查 gh CLI 是否已安装
gh --version
# 若未安装（WSL2 Ubuntu）：
# sudo apt install gh
# 然后登录：gh auth login

# 检查 git 远程配置（应为空）
git remote -v
```

---

### Task 1: 创建 GitHub 仓库并推送代码

**Files:**
- Modify: `.gitignore`（添加 `data/index.json` 以外的排除项，无需修改）

**Step 1: 在 GitHub 创建公开仓库**

```bash
# 替换 YOUR_USERNAME 为你的 GitHub 用户名
gh repo create daily-review --public --description "A股每日复盘可视化看板 - GitHub Pages静态版"
```

Expected: 输出仓库 URL，例如 `https://github.com/YOUR_USERNAME/daily-review`

**Step 2: 添加远程并推送**

```bash
# 替换 YOUR_USERNAME
git remote add origin https://github.com/YOUR_USERNAME/daily-review.git
git push -u origin main
```

Expected: 推送成功，显示 `Branch 'main' set up to track remote branch 'main' from 'origin'`

**Step 3: 验证**

```bash
gh repo view --web
```

Expected: 浏览器打开 GitHub 仓库页面，能看到所有文件。

---

### Task 2: 生成 data/index.json 并提交现有数据

**Files:**
- Create: `data/index.json`

**Step 1: 生成 index.json**

```bash
python3 -c "
import json
from pathlib import Path

files = sorted(
    [f.stem for f in Path('data').glob('*.json') if f.stem != 'index'],
    reverse=True
)
Path('data/index.json').write_text(
    json.dumps(files, ensure_ascii=False, indent=2),
    encoding='utf-8'
)
print(f'Created data/index.json with {len(files)} dates: {files}')
"
```

Expected: 输出 `Created data/index.json with 1 dates: ['2026-02-27']`

**Step 2: 提交数据文件**

```bash
git add data/
git commit -m "data: add initial data files and index.json"
git push
```

Expected: 推送成功。

---

### Task 3: 创建 scripts/fetch_data.py（数据抓取脚本）

**Files:**
- Create: `scripts/__init__.py`（空文件）
- Create: `scripts/fetch_data.py`

**Step 1: 创建 scripts 目录和 fetch_data.py**

创建 `scripts/__init__.py`（空文件），然后创建 `scripts/fetch_data.py`：

```python
#!/usr/bin/env python3
"""
GitHub Actions 数据抓取脚本。
从 repo 根目录运行: python scripts/fetch_data.py [--date YYYY-MM-DD]
"""
import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

# 将 repo 根目录加入 Python 路径，以便 import fetcher
sys.path.insert(0, str(Path(__file__).parent.parent))

from fetcher import fetch_today_data  # noqa: E402

DATA_DIR = Path("data")
INDEX_FILE = DATA_DIR / "index.json"


def update_index(date_str: str) -> None:
    """将 date_str 插入 data/index.json 头部（若不存在则创建）。"""
    if INDEX_FILE.exists():
        dates = json.loads(INDEX_FILE.read_text(encoding="utf-8"))
    else:
        dates = []

    if date_str not in dates:
        dates.insert(0, date_str)
        INDEX_FILE.write_text(
            json.dumps(dates, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(f"Updated index.json: added {date_str}")
    else:
        print(f"index.json already contains {date_str}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch daily stock data")
    parser.add_argument("--date", default=None, help="Date in YYYY-MM-DD format")
    args = parser.parse_args()

    date_str = args.date or datetime.now().strftime("%Y-%m-%d")
    data_path = DATA_DIR / f"{date_str}.json"

    DATA_DIR.mkdir(exist_ok=True)

    # 幂等：文件已存在则跳过抓取，仍更新 index
    if data_path.exists():
        print(f"Data for {date_str} already exists, skipping fetch.")
        update_index(date_str)
        return

    print(f"Fetching data for {date_str} ...")
    try:
        data = fetch_today_data(date_str=date_str)
    except ConnectionError as e:
        print(f"ERROR: Fetch failed: {e}", file=sys.stderr)
        sys.exit(1)

    if not data.get("limit_up"):
        print(f"No data for {date_str} (non-trading day?), skipping.")
        sys.exit(0)

    data_path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"Saved {data_path}")
    update_index(date_str)


if __name__ == "__main__":
    main()
```

**Step 2: 本地测试脚本（使用已有日期验证幂等性）**

```bash
python scripts/fetch_data.py --date 2026-02-27
```

Expected:
```
Data for 2026-02-27 already exists, skipping fetch.
index.json already contains 2026-02-27
```

**Step 3: 提交**

```bash
git add scripts/
git commit -m "feat: add scripts/fetch_data.py for GitHub Actions"
git push
```

---

### Task 4: 创建 .github/workflows/fetch.yml（自动化工作流）

**Files:**
- Create: `.github/workflows/fetch.yml`

**Step 1: 创建目录结构**

```bash
mkdir -p .github/workflows
```

**Step 2: 创建 fetch.yml**

```yaml
name: Fetch Daily Stock Data

on:
  schedule:
    # 每天 08:00 UTC = 北京时间 16:00（仅工作日）
    - cron: '0 8 * * 1-5'
  workflow_dispatch:
    inputs:
      date:
        description: '指定抓取日期 (YYYY-MM-DD)，留空则为今天'
        required: false
        default: ''

jobs:
  fetch:
    runs-on: ubuntu-latest
    permissions:
      contents: write

    steps:
      - name: Checkout repository
        uses: actions/checkout@v4

      - name: Set up Python 3.12
        uses: actions/setup-python@v5
        with:
          python-version: '3.12'

      - name: Install dependencies
        run: pip install requests

      - name: Fetch data
        run: |
          if [ -n "${{ github.event.inputs.date }}" ]; then
            python scripts/fetch_data.py --date "${{ github.event.inputs.date }}"
          else
            python scripts/fetch_data.py
          fi

      - name: Commit and push
        run: |
          git config user.name "github-actions[bot]"
          git config user.email "github-actions[bot]@users.noreply.github.com"
          git add data/
          git diff --staged --quiet && echo "No changes to commit" || \
            git commit -m "data: fetch $(date -u +%Y-%m-%d)"
          git push
```

**Step 3: 提交并验证工作流出现在 GitHub**

```bash
git add .github/
git commit -m "ci: add GitHub Actions workflow for daily data fetch"
git push
```

然后访问 `https://github.com/YOUR_USERNAME/daily-review/actions`，确认 "Fetch Daily Stock Data" 工作流已出现。

**Step 4: 手动触发一次验证**

在 GitHub Actions 页面点击 "Run workflow"，等待完成。Expected: 绿色 ✅，data/ 目录有新文件推送。

---

### Task 5: 创建 css/style.css（深色主题样式）

**Files:**
- Create: `css/style.css`

```css
/* ── 全局变量 ─────────────────────────────────────────── */
:root {
  --bg-primary:   #0e1117;
  --bg-secondary: #1c2232;
  --bg-card:      #262b3d;
  --text-primary: #fafafa;
  --text-muted:   #8b95a8;
  --accent:       #ff4b4b;
  --accent-blue:  #4c8bf5;
  --border:       #2e3650;
  --radius:       8px;
}

/* ── Reset ───────────────────────────────────────────── */
*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

body {
  background: var(--bg-primary);
  color: var(--text-primary);
  font-family: 'Segoe UI', 'PingFang SC', system-ui, sans-serif;
  font-size: 14px;
  line-height: 1.5;
}

/* ── Header ──────────────────────────────────────────── */
header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0.75rem 2rem;
  background: var(--bg-secondary);
  border-bottom: 1px solid var(--border);
  position: sticky;
  top: 0;
  z-index: 100;
}

header h1 { font-size: 1.2rem; }

.date-selector {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  color: var(--text-muted);
}

.date-selector select {
  background: var(--bg-card);
  color: var(--text-primary);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 0.3rem 0.6rem;
  font-size: 0.9rem;
  cursor: pointer;
}

/* ── 主容器 ──────────────────────────────────────────── */
main { padding: 1.5rem 2rem; max-width: 1600px; margin: 0 auto; }

section { margin-bottom: 2rem; }

section h2 {
  font-size: 1rem;
  margin-bottom: 1rem;
  padding-bottom: 0.4rem;
  border-bottom: 1px solid var(--border);
}

/* ── Warning Banner ──────────────────────────────────── */
#warning-banner {
  background: #2d2208;
  border: 1px solid #6b4f00;
  border-radius: var(--radius);
  padding: 0.6rem 1rem;
  margin-bottom: 1rem;
  color: #e8c55a;
  font-size: 0.9rem;
}

/* ── 概览卡片 ────────────────────────────────────────── */
.cards-grid {
  display: grid;
  grid-template-columns: repeat(5, 1fr);
  gap: 1rem;
}

@media (max-width: 900px) {
  .cards-grid { grid-template-columns: repeat(3, 1fr); }
}

.card {
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 1rem;
  text-align: center;
}

.card-label {
  font-size: 0.8rem;
  color: var(--text-muted);
  margin-bottom: 0.4rem;
}

.card-value {
  font-size: 1.7rem;
  font-weight: 700;
}

.card-sub {
  font-size: 0.8rem;
  color: var(--text-muted);
  margin-top: 0.2rem;
}

/* ── 双列图表布局 ─────────────────────────────────────── */
.two-col {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 1.5rem;
}

@media (max-width: 900px) {
  .two-col { grid-template-columns: 1fr; }
}

.chart-box {
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 1rem;
}

.chart-box h2 { border-bottom-color: var(--border); }

/* ── 单列图表 ─────────────────────────────────────────── */
.chart-full {
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 1rem;
}

/* ── Multiselect 复选框 chip 样式 ─────────────────────── */
.multiselect-bar {
  display: flex;
  flex-wrap: wrap;
  gap: 0.4rem;
  margin-bottom: 0.8rem;
}

.chip {
  display: inline-flex;
  align-items: center;
  gap: 0.3rem;
  background: var(--bg-secondary);
  border: 1px solid var(--border);
  border-radius: 999px;
  padding: 0.2rem 0.7rem;
  font-size: 0.8rem;
  cursor: pointer;
  user-select: none;
  transition: border-color 0.15s, background 0.15s;
}

.chip input[type="checkbox"] { display: none; }

.chip.selected {
  background: var(--accent-blue);
  border-color: var(--accent-blue);
  color: #fff;
}

/* ── Footer ──────────────────────────────────────────── */
footer {
  text-align: center;
  padding: 1.5rem;
  color: var(--text-muted);
  font-size: 0.8rem;
  border-top: 1px solid var(--border);
  margin-top: 2rem;
}
```

**Step 1: 提交**

```bash
git add css/
git commit -m "feat: add dark theme CSS"
git push
```

---

### Task 6: 创建 js/utils.js（数据处理工具函数）

**Files:**
- Create: `js/utils.js`

这个文件复刻 `processor.py` 的核心逻辑：

```javascript
// js/utils.js
// 复刻 processor.py 的数据处理逻辑

/**
 * 计算今日概览统计（对应 processor.get_summary_stats）
 */
function getSummaryStats(data) {
  const limitUp = data.limit_up || [];
  const limitBroken = data.limit_broken || [];
  const summary = data.summary || {};

  const ztAll = summary.zt_all || 0;
  const sealRate = parseFloat(summary.seal_rate || 0);

  const localTotal = limitUp.length + limitBroken.length;
  const bustRate = localTotal > 0
    ? parseFloat((limitBroken.length / localTotal * 100).toFixed(2))
    : 0.0;

  const maxStock = limitUp.reduce((max, s) =>
    (s.continuous_days || 0) > (max ? max.continuous_days : 0) ? s : max, null);

  const topicCounts = getTopicCounts(limitUp);
  const topTopic = topicCounts.length > 0 ? topicCounts[0].topic : '—';

  return {
    limit_up_count: limitUp.length,
    limit_broken_count: limitBroken.length,
    zt_all: ztAll,
    seal_rate: sealRate,
    bust_rate: bustRate,
    max_continuous: maxStock ? maxStock.continuous_days : 0,
    max_continuous_name: maxStock ? maxStock.name : '—',
    top_topic: topTopic,
  };
}

/**
 * 统计题材热度（对应 processor.get_topic_counts）
 */
function getTopicCounts(stocks) {
  const counter = {};
  const topicStocks = {};

  for (const stock of stocks) {
    const rawReason = stock.reason || '';
    const parts = rawReason
      .replace(/；/g, ';').replace(/、/g, ';').replace(/,/g, ';')
      .split(';')
      .map(r => r.trim())
      .filter(r => r);
    const reasons = parts.length > 0 ? parts : (rawReason ? [rawReason] : []);

    for (const reason of reasons) {
      counter[reason] = (counter[reason] || 0) + 1;
      if (!topicStocks[reason]) topicStocks[reason] = [];
      topicStocks[reason].push(stock.name);
    }
  }

  return Object.entries(counter)
    .sort((a, b) => b[1] - a[1])
    .map(([topic, count]) => ({ topic, count, stocks: topicStocks[topic] }));
}

/**
 * 筛选连板数 >= 2 的股票（对应 processor.get_lb_stocks）
 */
function getLbStocks(stocks) {
  return stocks
    .filter(s => (s.continuous_days || 0) >= 2)
    .sort((a, b) => b.continuous_days - a.continuous_days);
}

/**
 * 计算连板梯队（对应 processor.get_continuous_ladder）
 */
function getContinuousLadder(stocks) {
  const groups = {};
  for (const stock of stocks) {
    const days = stock.continuous_days || 0;
    if (days < 2) continue;
    if (!groups[days]) groups[days] = [];
    groups[days].push(stock);
  }

  return Object.keys(groups)
    .map(Number)
    .sort((a, b) => a - b)
    .map(days => {
      const group = groups[days];
      const topStock = group.reduce((max, s) =>
        (s.amount || 0) > (max ? max.amount : 0) ? s : max, null);
      return {
        days,
        count: group.length,
        top_stock: topStock ? topStock.name : '—',
        stocks: group.map(s => s.name),
      };
    });
}

/**
 * 从当日数据的 history_10d 中提取趋势历史
 * 对应 processor.load_history 的逻辑（静态版直接读 history_10d）
 */
function getHistory(data) {
  const h10d = data.history_10d || [];
  return h10d.slice().sort((a, b) => a.date.localeCompare(b.date));
}

/**
 * 数字格式化：超过 1 亿显示 "X.X亿"，否则原样
 */
function formatAmount(val) {
  if (!val) return '0';
  if (val >= 1e8) return (val / 1e8).toFixed(1) + '亿';
  if (val >= 1e4) return (val / 1e4).toFixed(1) + '万';
  return String(val);
}
```

**Step 1: 提交**

```bash
git add js/utils.js
git commit -m "feat: add js/utils.js with data processing logic"
git push
```

---

### Task 7: 创建 js/charts.js（Plotly 图表渲染）

**Files:**
- Create: `js/charts.js`

```javascript
// js/charts.js
// 所有 Plotly 图表渲染函数

// ── 共享深色主题 layout ─────────────────────────────────
const DARK = {
  paper_bgcolor: '#1c2232',
  plot_bgcolor:  '#1c2232',
  font:          { color: '#fafafa', size: 12 },
  xaxis: { gridcolor: '#2e3650', linecolor: '#2e3650', color: '#8b95a8' },
  yaxis: { gridcolor: '#2e3650', linecolor: '#2e3650', color: '#8b95a8' },
  margin: { t: 30, b: 50, l: 50, r: 30 },
};

const CONFIG = { responsive: true, displayModeBar: false };

// ── 指标元数据（对应 app.py 的 DAILY_METRICS 等） ──────────
const DAILY_METRICS = {
  zt_all:             { label: '总涨停',        axis: 'left',  dash: 'solid' },
  limit_broken_count: { label: '开板数',        axis: 'left',  dash: 'solid' },
  dt_count:           { label: '跌停数',        axis: 'left',  dash: 'solid' },
  lb_count:           { label: '连板数',        axis: 'left',  dash: 'solid' },
  up10_count:         { label: '涨幅10%以上',   axis: 'left',  dash: 'solid' },
  down9_count:        { label: '跌幅9%以上',    axis: 'left',  dash: 'solid' },
  yizi_count:         { label: '一字涨停',      axis: 'left',  dash: 'solid' },
  zt_925:             { label: '9:25涨停',      axis: 'left',  dash: 'solid' },
  seal_rate:          { label: '封板率%',       axis: 'right', dash: 'dot'   },
  rate_1to2:          { label: '一进二连板率%', axis: 'right', dash: 'dot'   },
  rate_2to3:          { label: '二进三连板率%', axis: 'right', dash: 'dot'   },
  rate_3to4:          { label: '三进四连板率%', axis: 'right', dash: 'dot'   },
  lb_rate:            { label: '连板率%',       axis: 'right', dash: 'dot'   },
  lb_rate_prev:       { label: '昨日连板率%',   axis: 'right', dash: 'dot'   },
};

const DAILY_DEFAULT = ['zt_all', 'limit_broken_count', 'seal_rate', 'lb_rate'];

const TIMING_METRICS = {
  shouban:     '首板',
  er_lb:       '二连板',
  san_lb:      '三连板',
  si_lb:       '四连板',
  wu_lb:       '五连板以上',
  t_before10:  '10点前',
  t_1000_1130: '10:00-11:30',
  t_1300_1400: '13:00-14:00',
  t_1400_1500: '14:00-15:00',
};

const TIMING_DEFAULT = ['shouban', 'er_lb', 'san_lb'];

const VOLUME_METRICS = {
  zt_amount:    '涨停总金额(亿)',
  total_amount: '总金额(亿)',
  sh_amount:    '上证成交额(亿)',
  cyb_amount:   '创业板成交额(亿)',
  kcb_amount:   '科创板成交额(亿)',
};

const VOLUME_DEFAULT = ['sh_amount', 'cyb_amount', 'total_amount'];

// ── 连板股排行（横向柱状图） ──────────────────────────────
function renderLbRanking(elementId, lbStocks) {
  if (!lbStocks.length) {
    document.getElementById(elementId).innerHTML = '<p style="color:#8b95a8;text-align:center;padding:2rem">暂无连板股数据</p>';
    return;
  }
  // 取前15条，降序展示（Plotly 横向 bar 从底到顶，需 reverse 让最高的在上）
  const stocks = lbStocks.slice(0, 15).reverse();
  const colors = stocks.map(s =>
    s.continuous_days === lbStocks[0].continuous_days ? '#ff4b4b' : '#4c8bf5'
  );

  Plotly.newPlot(elementId, [{
    type: 'bar',
    orientation: 'h',
    x: stocks.map(s => s.continuous_days),
    y: stocks.map(s => `${s.name}(${s.code})`),
    text: stocks.map(s => `${s.continuous_days}板`),
    textposition: 'outside',
    marker: { color: colors },
    hovertemplate: '%{y}<br>连板数: %{x}<extra></extra>',
  }], {
    ...DARK,
    xaxis: { ...DARK.xaxis, title: '连板数', dtick: 1 },
    yaxis: { ...DARK.yaxis, automargin: true },
    height: Math.max(250, stocks.length * 28),
  }, CONFIG);
}

// ── 题材热度（横向柱状图） ────────────────────────────────
function renderTopicHeat(elementId, topics) {
  if (!topics.length) {
    document.getElementById(elementId).innerHTML = '<p style="color:#8b95a8;text-align:center;padding:2rem">暂无题材数据</p>';
    return;
  }
  const top = topics.slice(0, 20).reverse();
  Plotly.newPlot(elementId, [{
    type: 'bar',
    orientation: 'h',
    x: top.map(t => t.count),
    y: top.map(t => t.topic),
    text: top.map(t => `${t.count}家`),
    textposition: 'outside',
    marker: {
      color: top.map(t => t.count),
      colorscale: 'Reds',
      showscale: false,
    },
    customdata: top.map(t => t.stocks.join('、')),
    hovertemplate: '%{y}<br>涨停家数: %{x}<br>%{customdata}<extra></extra>',
  }], {
    ...DARK,
    xaxis: { ...DARK.xaxis, title: '涨停家数' },
    yaxis: { ...DARK.yaxis, automargin: true },
    height: Math.max(250, top.length * 26),
  }, CONFIG);
}

// ── 近10日情绪趋势（双轴折线图） ─────────────────────────
function renderDailyTrend(elementId, history, selectedKeys) {
  const dates = history.map(h => h.date);
  const traces = selectedKeys.map(key => {
    const meta = DAILY_METRICS[key];
    return {
      type: 'scatter',
      mode: 'lines+markers',
      name: meta.label,
      x: dates,
      y: history.map(h => h[key] || 0),
      line: { dash: meta.dash },
      yaxis: meta.axis === 'right' ? 'y2' : 'y',
    };
  });

  Plotly.newPlot(elementId, traces, {
    ...DARK,
    xaxis: { ...DARK.xaxis, type: 'category' },
    yaxis: { ...DARK.yaxis, title: '家数' },
    yaxis2: { ...DARK.yaxis, title: '比率%', overlaying: 'y', side: 'right' },
    hovermode: 'x unified',
    legend: { orientation: 'h', y: -0.25, font: { size: 11 } },
    height: 380,
  }, CONFIG);
}

// ── 近10日涨停时间分布 ────────────────────────────────────
function renderTimingDist(elementId, history, selectedKeys) {
  const dates = history.map(h => h.date);
  const traces = selectedKeys.map(key => ({
    type: 'scatter',
    mode: 'lines+markers',
    name: TIMING_METRICS[key],
    x: dates,
    y: history.map(h => h[key] || 0),
  }));

  Plotly.newPlot(elementId, traces, {
    ...DARK,
    xaxis: { ...DARK.xaxis, type: 'category' },
    yaxis: { ...DARK.yaxis, title: '家数' },
    hovermode: 'x unified',
    legend: { orientation: 'h', y: -0.25, font: { size: 11 } },
    height: 340,
  }, CONFIG);
}

// ── 近10日市场涨跌家数 ────────────────────────────────────
function renderBreadth(elementId, history) {
  const dates = history.map(h => h.date);
  Plotly.newPlot(elementId, [
    {
      type: 'scatter', mode: 'lines+markers',
      name: '上涨家数', x: dates,
      y: history.map(h => h.up_count || 0),
      line: { color: '#ff4b4b' },
    },
    {
      type: 'scatter', mode: 'lines+markers',
      name: '下跌家数', x: dates,
      y: history.map(h => h.down_count || 0),
      line: { color: '#4c8bf5' },
    },
  ], {
    ...DARK,
    xaxis: { ...DARK.xaxis, type: 'category' },
    yaxis: { ...DARK.yaxis, title: '家数' },
    hovermode: 'x unified',
    legend: { orientation: 'h', y: -0.25, font: { size: 11 } },
    height: 300,
  }, CONFIG);
}

// ── 近10日成交额 ──────────────────────────────────────────
function renderVolume(elementId, history, selectedKeys) {
  const dates = history.map(h => h.date);
  const traces = selectedKeys.map(key => ({
    type: 'scatter',
    mode: 'lines+markers',
    name: VOLUME_METRICS[key],
    x: dates,
    y: history.map(h => h[key] || 0),
  }));

  Plotly.newPlot(elementId, traces, {
    ...DARK,
    xaxis: { ...DARK.xaxis, type: 'category' },
    yaxis: { ...DARK.yaxis, title: '成交额(亿)' },
    hovermode: 'x unified',
    legend: { orientation: 'h', y: -0.25, font: { size: 11 } },
    height: 340,
  }, CONFIG);
}

// ── 连板梯队（柱状图） ────────────────────────────────────
function renderLadder(elementId, ladder) {
  if (!ladder.length) {
    document.getElementById(elementId).innerHTML = '<p style="color:#8b95a8;text-align:center;padding:2rem">暂无连板梯队数据</p>';
    return;
  }

  Plotly.newPlot(elementId, [{
    type: 'bar',
    x: ladder.map(l => l.days),
    y: ladder.map(l => l.count),
    text: ladder.map(l => `${l.days}板\n${l.top_stock}`),
    textposition: 'outside',
    marker: {
      color: ladder.map(l => l.days),
      colorscale: 'Blues',
      showscale: false,
    },
    customdata: ladder.map(l => l.stocks.join('、')),
    hovertemplate: '%{x}板<br>%{y}只<br>%{customdata}<extra></extra>',
  }], {
    ...DARK,
    xaxis: { ...DARK.xaxis, title: '连板数', tickmode: 'linear', dtick: 1 },
    yaxis: { ...DARK.yaxis, title: '股票数量' },
    height: 320,
  }, CONFIG);
}
```

**Step 1: 提交**

```bash
git add js/charts.js
git commit -m "feat: add js/charts.js with all Plotly chart renderers"
git push
```

---

### Task 8: 创建 js/app.js（主逻辑与交互协调）

**Files:**
- Create: `js/app.js`

```javascript
// js/app.js
// 主逻辑：加载数据、日期切换、多选交互、渲染协调

// ── 当前选中的 multiselect 状态 ──────────────────────────
let state = {
  daily:  [...DAILY_DEFAULT],
  timing: [...TIMING_DEFAULT],
  volume: [...VOLUME_DEFAULT],
  history: [],
};

// ── 工具：fetch JSON（带错误处理） ─────────────────────────
async function fetchJSON(url) {
  const resp = await fetch(url);
  if (!resp.ok) throw new Error(`HTTP ${resp.status}: ${url}`);
  return resp.json();
}

// ── 初始化日期下拉框 ──────────────────────────────────────
async function initDateSelect() {
  let dates;
  try {
    dates = await fetchJSON('data/index.json');
  } catch (e) {
    showError('无法加载 data/index.json：' + e.message);
    return;
  }

  const sel = document.getElementById('date-select');
  dates.forEach(d => {
    const opt = document.createElement('option');
    opt.value = d;
    opt.textContent = d;
    sel.appendChild(opt);
  });

  sel.value = dates[0]; // 默认最新日期
  sel.addEventListener('change', () => loadAndRender(sel.value));
  await loadAndRender(dates[0]);
}

// ── 加载指定日期数据并渲染 ───────────────────────────────
async function loadAndRender(dateStr) {
  showLoading(true);
  let data;
  try {
    data = await fetchJSON(`data/${dateStr}.json`);
  } catch (e) {
    showError(`加载 ${dateStr} 数据失败：${e.message}`);
    showLoading(false);
    return;
  }

  renderAll(data);
  showLoading(false);
}

// ── 渲染全部模块 ─────────────────────────────────────────
function renderAll(data) {
  const stats   = getSummaryStats(data);
  const lbStocks = getLbStocks(data.limit_up || []);
  const topics  = getTopicCounts(data.limit_up || []);
  const ladder  = getContinuousLadder(data.limit_up || []);
  const history = getHistory(data);
  state.history = history;

  // 更新 caption
  document.getElementById('data-caption').textContent =
    `数据日期：${data.date || ''}　　抓取时间：${data.fetched_at || ''}`;

  // 概览卡片
  renderCards(stats);

  // 图表
  renderLbRanking('chart-lb',      lbStocks);
  renderTopicHeat('chart-topic',   topics);
  renderLadder('chart-ladder',     ladder);

  if (history.length >= 2) {
    renderDailyTrend('chart-daily',   history, state.daily);
    renderTimingDist('chart-timing',  history, state.timing);
    renderBreadth('chart-breadth',    history);
    renderVolume('chart-volume',      history, state.volume);
    document.getElementById('section-history').style.display = '';
  } else {
    document.getElementById('section-history').style.display = 'none';
  }
}

// ── 渲染概览卡片 ─────────────────────────────────────────
function renderCards(stats) {
  const displayZt = stats.zt_all > 0 ? stats.zt_all : stats.limit_up_count;
  setCard('card-zt',     '涨停家数（全市场）', displayZt);
  setCard('card-broken', '开板家数',           stats.limit_broken_count);
  setCard('card-seal',   '封板率',             stats.seal_rate + '%');
  setCard('card-max',    '最高连板',
    `${stats.max_continuous}板`,               stats.max_continuous_name);
  setCard('card-topic',  '最强题材',           stats.top_topic);
}

function setCard(id, label, value, sub) {
  const el = document.getElementById(id);
  el.querySelector('.card-label').textContent = label;
  el.querySelector('.card-value').textContent = value;
  const subEl = el.querySelector('.card-sub');
  if (subEl) subEl.textContent = sub || '';
}

// ── 构建 multiselect chip 组 ─────────────────────────────
function buildMultiselect(containerId, metaMap, defaults, stateKey, chartFn, chartId) {
  const container = document.getElementById(containerId);
  container.innerHTML = '';

  Object.entries(metaMap).forEach(([key, meta]) => {
    const label = typeof meta === 'string' ? meta : meta.label;
    const chip = document.createElement('label');
    chip.className = 'chip' + (defaults.includes(key) ? ' selected' : '');

    const cb = document.createElement('input');
    cb.type = 'checkbox';
    cb.value = key;
    cb.checked = defaults.includes(key);

    cb.addEventListener('change', () => {
      chip.classList.toggle('selected', cb.checked);
      if (cb.checked) {
        state[stateKey].push(key);
      } else {
        state[stateKey] = state[stateKey].filter(k => k !== key);
      }
      if (state.history.length >= 2) {
        chartFn(chartId, state.history, state[stateKey]);
      }
    });

    chip.appendChild(cb);
    chip.appendChild(document.createTextNode(label));
    container.appendChild(chip);
  });
}

// ── UI 辅助 ──────────────────────────────────────────────
function showLoading(on) {
  document.getElementById('loading').style.display = on ? '' : 'none';
}

function showError(msg) {
  const el = document.getElementById('warning-banner');
  el.textContent = '⚠️ ' + msg;
  el.style.display = '';
}

// ── 入口 ─────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  // 初始化所有 multiselect
  buildMultiselect('ms-daily',  DAILY_METRICS,  DAILY_DEFAULT,  'daily',
    renderDailyTrend, 'chart-daily');
  buildMultiselect('ms-timing', TIMING_METRICS, TIMING_DEFAULT, 'timing',
    renderTimingDist, 'chart-timing');
  buildMultiselect('ms-volume', VOLUME_METRICS, VOLUME_DEFAULT, 'volume',
    renderVolume,     'chart-volume');

  initDateSelect();
});
```

**Step 1: 提交**

```bash
git add js/app.js
git commit -m "feat: add js/app.js with main orchestration logic"
git push
```

---

### Task 9: 创建 index.html（主页面）

**Files:**
- Create: `index.html`

```html
<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>每日复盘看板</title>
  <link rel="stylesheet" href="css/style.css">
  <!-- Plotly.js CDN -->
  <script src="https://cdn.plot.ly/plotly-2.35.2.min.js" charset="utf-8"></script>
</head>
<body>

<header>
  <h1>📈 每日复盘看板</h1>
  <div class="date-selector">
    <label for="date-select">日期：</label>
    <select id="date-select"></select>
    <span id="loading" style="display:none; color:#8b95a8; font-size:0.85rem;">加载中…</span>
  </div>
</header>

<main>
  <!-- Warning Banner -->
  <div id="warning-banner" style="display:none"></div>

  <!-- Caption -->
  <p id="data-caption" style="color:#8b95a8; font-size:0.8rem; margin-bottom:1rem;"></p>

  <!-- 概览卡片 -->
  <section>
    <h2>📊 今日概览</h2>
    <div class="cards-grid">
      <div class="card" id="card-zt">
        <div class="card-label"></div>
        <div class="card-value">—</div>
        <div class="card-sub"></div>
      </div>
      <div class="card" id="card-broken">
        <div class="card-label"></div>
        <div class="card-value">—</div>
        <div class="card-sub"></div>
      </div>
      <div class="card" id="card-seal">
        <div class="card-label"></div>
        <div class="card-value">—</div>
        <div class="card-sub"></div>
      </div>
      <div class="card" id="card-max">
        <div class="card-label"></div>
        <div class="card-value">—</div>
        <div class="card-sub"></div>
      </div>
      <div class="card" id="card-topic">
        <div class="card-label"></div>
        <div class="card-value" style="font-size:1.1rem;">—</div>
        <div class="card-sub"></div>
      </div>
    </div>
  </section>

  <!-- 连板股排行 & 题材热度 -->
  <section>
    <div class="two-col">
      <div class="chart-box">
        <h2>🏆 连板股排行</h2>
        <div id="chart-lb"></div>
      </div>
      <div class="chart-box">
        <h2>🔥 题材热度</h2>
        <div id="chart-topic"></div>
      </div>
    </div>
  </section>

  <!-- 连板梯队 -->
  <section>
    <div class="chart-full">
      <h2>🪜 连板梯队</h2>
      <div id="chart-ladder"></div>
    </div>
  </section>

  <!-- 历史趋势区块（数据不足时隐藏） -->
  <div id="section-history">

    <!-- 近10日情绪趋势 -->
    <section>
      <div class="chart-full">
        <h2>📊 近10日情绪趋势</h2>
        <div class="multiselect-bar" id="ms-daily"></div>
        <div id="chart-daily"></div>
      </div>
    </section>

    <!-- 近10日涨停时间分布 -->
    <section>
      <div class="chart-full">
        <h2>⏰ 近10日涨停时间分布</h2>
        <div class="multiselect-bar" id="ms-timing"></div>
        <div id="chart-timing"></div>
      </div>
    </section>

    <!-- 近10日市场涨跌家数 -->
    <section>
      <div class="chart-full">
        <h2>📈 近10日市场涨跌家数</h2>
        <div id="chart-breadth"></div>
      </div>
    </section>

    <!-- 近10日成交额 -->
    <section>
      <div class="chart-full">
        <h2>💰 近10日成交额</h2>
        <div class="multiselect-bar" id="ms-volume"></div>
        <div id="chart-volume"></div>
      </div>
    </section>

  </div><!-- /section-history -->

</main>

<footer>
  数据来源：<a href="https://www.wuylh.com/replayrobot/index.html" target="_blank" style="color:#4c8bf5">舞阳复盘</a>
  &nbsp;·&nbsp; 每日 16:00 自动更新
</footer>

<!-- JS（顺序重要：utils → charts → app） -->
<script src="js/utils.js"></script>
<script src="js/charts.js"></script>
<script src="js/app.js"></script>

</body>
</html>
```

**Step 1: 提交**

```bash
git add index.html
git commit -m "feat: add index.html static dashboard page"
git push
```

---

### Task 10: 启用 GitHub Pages

**Step 1: 通过 gh CLI 启用 Pages**

```bash
# 启用 GitHub Pages，source 为 main 分支根目录
gh api repos/:owner/:repo/pages \
  --method POST \
  --field source='{"branch":"main","path":"/"}' \
  2>/dev/null || echo "Pages 可能已启用，请手动确认"
```

**若上述命令失败，手动操作：**
1. 打开 `https://github.com/YOUR_USERNAME/daily-review/settings/pages`
2. Source → "Deploy from a branch"
3. Branch → `main`，Folder → `/ (root)`
4. 点击 Save

**Step 2: 等待部署完成（约 1-2 分钟）**

```bash
# 轮询部署状态
gh api repos/:owner/:repo/pages --jq '.status'
```

Expected: 输出 `built`

**Step 3: 获取并访问 Pages URL**

```bash
gh api repos/:owner/:repo/pages --jq '.html_url'
```

Expected: 输出类似 `https://YOUR_USERNAME.github.io/daily-review/`

在浏览器打开该 URL，验证看板正常显示。

---

### Task 11: 端到端验证

**Step 1: 验证页面功能**

打开 `https://YOUR_USERNAME.github.io/daily-review/`，逐项检查：

- [ ] 页面标题 "📈 每日复盘看板" 显示
- [ ] 日期下拉框有数据（如 "2026-02-27"）
- [ ] 概览卡片（5个）显示数字
- [ ] 连板股排行图表渲染
- [ ] 题材热度图表渲染
- [ ] 连板梯队图表渲染
- [ ] 若有历史数据：趋势图、时间分布图显示

**Step 2: 验证 GitHub Actions 工作流**

```bash
# 手动触发一次工作流（测试今天的日期）
gh workflow run fetch.yml
# 等待 30 秒后查看状态
gh run list --workflow=fetch.yml --limit=3
```

Expected: 最新一次 run 状态为 `completed / success`

**Step 3: 更新 README.md**

在 `README.md` 开头添加在线访问链接：

```markdown
## 在线访问

GitHub Pages: https://YOUR_USERNAME.github.io/daily-review/

（每个工作日 16:00 自动更新数据）
```

```bash
git add README.md
git commit -m "docs: add GitHub Pages link to README"
git push
```

---

## 整体提交顺序回顾

```
Task 1  → git push (推送已有代码)
Task 2  → data: add initial data files and index.json
Task 3  → feat: add scripts/fetch_data.py
Task 4  → ci: add GitHub Actions workflow
Task 5  → feat: add dark theme CSS
Task 6  → feat: add js/utils.js
Task 7  → feat: add js/charts.js
Task 8  → feat: add js/app.js
Task 9  → feat: add index.html
Task 10 → (启用 Pages，无代码提交)
Task 11 → docs: add GitHub Pages link to README
```
