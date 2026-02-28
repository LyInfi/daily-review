# 近10日情绪趋势图全量指标 Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 将近10日情绪趋势图扩展为显示 tenDays 全量30个指标，用户可通过 multiselect 自由筛选，分"日级别指标"和"涨停时间分布"两块独立展示。

**Architecture:** 扩展 `_parse_ten_days()` 解析全部30个字段存入 `history_10d`；`_history_entry_from_10d()` 透传所有字段；`app.py` 模块C改为双 multiselect + 双轴折线图，新增时间分布图块。

**Tech Stack:** Python 3.12, uv, Streamlit, Plotly (go.Figure), pandas, pytest

---

## 字段映射参考

tenDays 索引 → Python key → 中文标签 → 轴类型

```
[1]  up_count       上涨家数        左轴（家数）
[2]  down_count     下跌家数        左轴（家数）
[3]  zt_all         总涨停          左轴（家数）  ← 已有
[4]  dt_count       跌停数          左轴（家数）
[5]  lb_count       连板数          左轴（家数）
[6]  up10_count     涨幅10%以上     左轴（家数）
[7]  down9_count    跌幅9%以上      左轴（家数）
[8]  yizi_count     一字涨停        左轴（家数）
[14] zt_925         9:25涨停        左轴（家数）
[19] limit_broken_count  开板数     左轴（家数）  ← 已有
[20] seal_rate      封板率          右轴（比率%） ← 已有
[21] rate_1to2      一进二连板率    右轴（比率%）
[22] rate_2to3      二进三连板率    右轴（比率%）
[23] rate_3to4      三进四连板率    右轴（比率%）
[24] lb_rate        连板率          右轴（比率%）
[25] lb_rate_prev   昨日连板率      右轴（比率%）
[26] zt_amount      涨停总金额(亿)  左轴（金额）
[27] total_amount   总金额(亿)      左轴（金额）
[28] sh_amount      上证成交额(亿)  左轴（金额）
[29] cyb_amount     创业板成交额(亿) 左轴（金额）
[30] kcb_amount     科创板成交额(亿) 左轴（金额）

len=20 字段（取前10个值）：
[9]  shouban        首板
[10] er_lb          二连板
[11] san_lb         三连板
[12] si_lb          四连板
[13] wu_lb          五连板以上
[15] t_before10     10点前
[16] t_1000_1130    10:00-11:30
[17] t_1300_1400    13:00-14:00
[18] t_1400_1500    14:00-15:00
```

---

### Task 1: 扩展 fetcher.py 的 _parse_ten_days()

**Files:**
- Modify: `fetcher.py`（`_parse_ten_days` 函数）
- Test: `tests/test_fetcher.py`

**Step 1: 写失败的测试**

在 `tests/test_fetcher.py` 中找到现有的 `_parse_ten_days` 相关测试，在其后添加新测试：

```python
def test_parse_ten_days_full_fields():
    """_parse_ten_days 应解析全部30个指标字段。"""
    # 构造31个元素的 tenDays，len=10 的正常填，len=20 的填20个值
    ten_days = [None] * 31
    ten_days[0] = ["2026-1-1", "2026-1-2"]
    # len=10 字段
    for idx in [1,2,3,4,5,6,7,8,14,19,20,21,22,23,24,25,26,27,28,29,30]:
        ten_days[idx] = [float(idx)] * 2
    # len=20 字段（取前2个）
    for idx in [9,10,11,12,13,15,16,17,18]:
        ten_days[idx] = [float(idx)] * 20

    from fetcher import _parse_ten_days
    result = _parse_ten_days(ten_days)

    assert len(result) == 2
    entry = result[0]
    assert entry["up_count"] == 1.0
    assert entry["down_count"] == 2.0
    assert entry["zt_all"] == 3.0
    assert entry["dt_count"] == 4.0
    assert entry["lb_count"] == 5.0
    assert entry["up10_count"] == 6.0
    assert entry["down9_count"] == 7.0
    assert entry["yizi_count"] == 8.0
    assert entry["zt_925"] == 14.0
    assert entry["limit_broken_count"] == 19.0
    assert entry["seal_rate"] == 20.0
    assert entry["rate_1to2"] == 21.0
    assert entry["rate_2to3"] == 22.0
    assert entry["rate_3to4"] == 23.0
    assert entry["lb_rate"] == 24.0
    assert entry["lb_rate_prev"] == 25.0
    assert entry["zt_amount"] == 26.0
    assert entry["total_amount"] == 27.0
    assert entry["sh_amount"] == 28.0
    assert entry["cyb_amount"] == 29.0
    assert entry["kcb_amount"] == 30.0
    # len=20 字段取前 n 个
    assert entry["shouban"] == 9.0
    assert entry["er_lb"] == 10.0
    assert entry["san_lb"] == 11.0
    assert entry["si_lb"] == 12.0
    assert entry["wu_lb"] == 13.0
    assert entry["t_before10"] == 15.0
    assert entry["t_1000_1130"] == 16.0
    assert entry["t_1300_1400"] == 17.0
    assert entry["t_1400_1500"] == 18.0
```

**Step 2: 运行测试确认失败**

```bash
cd /mnt/c/Users/shenx/Documents/AIProject/daily-review
uv run pytest tests/test_fetcher.py::test_parse_ten_days_full_fields -v
```

预期：FAIL，KeyError 或 AssertionError。

**Step 3: 重写 `_parse_ten_days()` 函数**

将 `fetcher.py` 中的 `_parse_ten_days` 替换为：

```python
def _parse_ten_days(ten_days: list) -> list[dict]:
    """
    从 tenDays 数组解析近10日趋势摘要（全量30个指标）。
    len=20 的字段取前 n 个值（n = len(dates)）。
    """
    if not ten_days or len(ten_days) < 21:
        return []

    dates = ten_days[0]
    n = len(dates)

    def _get(idx: int, i: int) -> float:
        """安全取 ten_days[idx][i]，越界或空返回 0.0。"""
        arr = ten_days[idx] if idx < len(ten_days) else []
        if not arr or i >= len(arr):
            return 0.0
        try:
            return float(arr[i] or 0)
        except (ValueError, TypeError):
            return 0.0

    result = []
    for i in range(n):
        parts = str(dates[i]).split("-")
        normalized = f"{parts[0]}-{int(parts[1]):02d}-{int(parts[2]):02d}"
        result.append({
            "date": normalized,
            # 家数类（len=10）
            "up_count": _get(1, i),
            "down_count": _get(2, i),
            "zt_all": _get(3, i),
            "dt_count": _get(4, i),
            "lb_count": _get(5, i),
            "up10_count": _get(6, i),
            "down9_count": _get(7, i),
            "yizi_count": _get(8, i),
            "zt_925": _get(14, i),
            "limit_broken_count": _get(19, i),
            # 比率类（len=10，单位%）
            "seal_rate": _get(20, i),
            "rate_1to2": _get(21, i),
            "rate_2to3": _get(22, i),
            "rate_3to4": _get(23, i),
            "lb_rate": _get(24, i),
            "lb_rate_prev": _get(25, i),
            # 金额类（len=10，单位亿）
            "zt_amount": _get(26, i),
            "total_amount": _get(27, i),
            "sh_amount": _get(28, i),
            "cyb_amount": _get(29, i),
            "kcb_amount": _get(30, i),
            # 时间分布类（len=20，取前 n 个）
            "shouban": _get(9, i),
            "er_lb": _get(10, i),
            "san_lb": _get(11, i),
            "si_lb": _get(12, i),
            "wu_lb": _get(13, i),
            "t_before10": _get(15, i),
            "t_1000_1130": _get(16, i),
            "t_1300_1400": _get(17, i),
            "t_1400_1500": _get(18, i),
        })
    return result
```

**Step 4: 运行测试确认通过**

```bash
uv run pytest tests/test_fetcher.py -v
```

预期：ALL PASS，包括原有测试。

**Step 5: Commit**

```bash
git add fetcher.py tests/test_fetcher.py
git commit -m "feat: extend _parse_ten_days to parse all 30 tenDays metrics"
```

---

### Task 2: 扩展 processor.py 的 _history_entry_from_10d()

**Files:**
- Modify: `processor.py`（`_history_entry_from_10d` 函数）
- Test: `tests/test_processor.py`

**Step 1: 写失败的测试**

在 `tests/test_processor.py` 中找到 `_history_entry_from_10d` 相关测试，添加：

```python
def test_history_entry_from_10d_full_fields():
    """_history_entry_from_10d 应透传全部新字段。"""
    from processor import _history_entry_from_10d
    entry = {
        "date": "2026-02-10",
        "zt_all": 60,
        "limit_broken_count": 14,
        "seal_rate": 81.0,
        "up_count": 2500,
        "down_count": 1000,
        "dt_count": 7,
        "lb_count": 21,
        "up10_count": 55,
        "down9_count": 10,
        "yizi_count": 5,
        "zt_925": 3,
        "rate_1to2": 28.0,
        "rate_2to3": 15.0,
        "rate_3to4": 10.0,
        "lb_rate": 35.0,
        "lb_rate_prev": 30.0,
        "zt_amount": 1111.0,
        "total_amount": 8000.0,
        "sh_amount": 5000.0,
        "cyb_amount": 2000.0,
        "kcb_amount": 800.0,
        "shouban": 49,
        "er_lb": 11,
        "san_lb": 4,
        "si_lb": 3,
        "wu_lb": 1,
        "t_before10": 20,
        "t_1000_1130": 19,
        "t_1300_1400": 15,
        "t_1400_1500": 3,
    }
    result = _history_entry_from_10d(entry)
    assert result["up_count"] == 2500
    assert result["rate_1to2"] == 28.0
    assert result["shouban"] == 49
    assert result["t_1000_1130"] == 19
    assert result["zt_amount"] == 1111.0
```

**Step 2: 运行测试确认失败**

```bash
uv run pytest tests/test_processor.py::test_history_entry_from_10d_full_fields -v
```

预期：FAIL，KeyError。

**Step 3: 重写 `_history_entry_from_10d()` 函数**

将 `processor.py` 中的 `_history_entry_from_10d` 替换为：

```python
# 所有需要从 history_10d 透传的字段（除 date、zt_all、limit_broken_count、seal_rate 之外的新增字段）
_EXTRA_10D_FIELDS = [
    "up_count", "down_count", "dt_count", "lb_count",
    "up10_count", "down9_count", "yizi_count", "zt_925",
    "rate_1to2", "rate_2to3", "rate_3to4", "lb_rate", "lb_rate_prev",
    "zt_amount", "total_amount", "sh_amount", "cyb_amount", "kcb_amount",
    "shouban", "er_lb", "san_lb", "si_lb", "wu_lb",
    "t_before10", "t_1000_1130", "t_1300_1400", "t_1400_1500",
]


def _history_entry_from_10d(entry: dict) -> dict:
    """将 history_10d 中的一条摘要转为 load_history 统一格式。"""
    zt_all = entry.get("zt_all", 0)
    broken = entry.get("limit_broken_count", 0)
    total = zt_all + broken
    bust_rate = round(broken / total * 100, 2) if total > 0 else 0.0
    result = {
        "date": entry["date"],
        "limit_up_count": zt_all,
        "limit_broken_count": broken,
        "zt_all": zt_all,
        "seal_rate": entry.get("seal_rate", 0.0),
        "bust_rate": bust_rate,
        "max_continuous": 0,
        "max_continuous_name": "—",
        "top_topic": "—",
    }
    for field in _EXTRA_10D_FIELDS:
        result[field] = entry.get(field, 0)
    return result
```

**Step 4: 运行测试确认通过**

```bash
uv run pytest tests/test_processor.py -v
```

预期：ALL PASS。

**Step 5: Commit**

```bash
git add processor.py tests/test_processor.py
git commit -m "feat: extend _history_entry_from_10d to pass through all tenDays fields"
```

---

### Task 3: 重写 app.py 模块C（近10日情绪趋势）

**Files:**
- Modify: `app.py`（模块C，约100-130行）

注意：app.py 的 UI 层不写自动化测试，手动验证。

**Step 1: 在模块C上方定义指标映射常量**

在 `app.py` 文件顶部的 import 之后（或在模块C代码之前），添加：

```python
# ── 近10日趋势图：指标定义 ─────────────────────────────────────
# 日级别指标（每日1个数据点）
DAILY_METRICS = {
    # key: (中文标签, 轴, 线型)
    "zt_all":        ("总涨停",          "left",  "solid"),
    "limit_broken_count": ("开板数",     "left",  "solid"),
    "up_count":      ("上涨家数",        "left",  "solid"),
    "down_count":    ("下跌家数",        "left",  "solid"),
    "dt_count":      ("跌停数",          "left",  "solid"),
    "lb_count":      ("连板数",          "left",  "solid"),
    "up10_count":    ("涨幅10%以上",     "left",  "solid"),
    "down9_count":   ("跌幅9%以上",      "left",  "solid"),
    "yizi_count":    ("一字涨停",        "left",  "solid"),
    "zt_925":        ("9:25涨停",        "left",  "solid"),
    "seal_rate":     ("封板率%",         "right", "dot"),
    "rate_1to2":     ("一进二连板率%",   "right", "dot"),
    "rate_2to3":     ("二进三连板率%",   "right", "dot"),
    "rate_3to4":     ("三进四连板率%",   "right", "dot"),
    "lb_rate":       ("连板率%",         "right", "dot"),
    "lb_rate_prev":  ("昨日连板率%",     "right", "dot"),
    "zt_amount":     ("涨停总金额(亿)",  "left",  "dash"),
    "total_amount":  ("总金额(亿)",      "left",  "dash"),
    "sh_amount":     ("上证成交额(亿)",  "left",  "dash"),
    "cyb_amount":    ("创业板成交额(亿)","left",  "dash"),
    "kcb_amount":    ("科创板成交额(亿)","left",  "dash"),
}

DAILY_DEFAULT = ["zt_all", "limit_broken_count", "seal_rate", "lb_rate"]

# 时间分布指标（len=20 字段，每日1个数据点，单位：家数）
TIMING_METRICS = {
    "shouban":     "首板",
    "er_lb":       "二连板",
    "san_lb":      "三连板",
    "si_lb":       "四连板",
    "wu_lb":       "五连板以上",
    "t_before10":  "10点前",
    "t_1000_1130": "10:00-11:30",
    "t_1300_1400": "13:00-14:00",
    "t_1400_1500": "14:00-15:00",
}

TIMING_DEFAULT = ["shouban", "er_lb", "san_lb"]
```

**Step 2: 替换模块C（近10日情绪趋势）代码**

找到 `app.py` 中：
```python
# ── 模块 C：近10日情绪趋势（折线图） ──────────────────────────
st.subheader("📊 近10日情绪趋势")
...
st.plotly_chart(fig_line, use_container_width=True)
```

替换为：

```python
# ── 模块 C：近10日情绪趋势（折线图） ──────────────────────────
st.subheader("📊 近10日情绪趋势")

history = load_history(limit=10)

if len(history) < 2:
    st.info("历史数据不足，积累更多交易日后趋势图将自动显示。")
else:
    hist_df = pd.DataFrame(history)

    # ── 块一：日级别指标 ──
    daily_options = list(DAILY_METRICS.keys())
    daily_labels = {k: DAILY_METRICS[k][0] for k in daily_options}
    selected_daily = st.multiselect(
        "选择日级别指标",
        options=daily_options,
        default=DAILY_DEFAULT,
        format_func=lambda k: daily_labels[k],
        key="trend_daily",
    )

    if not selected_daily:
        st.info("请至少选择一个日级别指标。")
    else:
        fig_daily = go.Figure()
        for key in selected_daily:
            label, axis, dash = DAILY_METRICS[key]
            yaxis = "y2" if axis == "right" else "y"
            fig_daily.add_trace(go.Scatter(
                x=hist_df["date"],
                y=hist_df.get(key, [0] * len(hist_df)),
                name=label,
                line={"dash": dash},
                yaxis=yaxis,
            ))
        fig_daily.update_layout(
            yaxis={"title": "家数 / 金额(亿)"},
            yaxis2={"title": "比率%", "overlaying": "y", "side": "right", "range": [0, 100]},
            hovermode="x unified",
            legend={"orientation": "h", "y": -0.2},
        )
        st.plotly_chart(fig_daily, use_container_width=True)

st.divider()

# ── 模块 C2：近10日涨停时间分布 ────────────────────────────────
st.subheader("⏰ 近10日涨停时间分布")

if len(history) < 2:
    st.info("历史数据不足，积累更多交易日后趋势图将自动显示。")
else:
    timing_options = list(TIMING_METRICS.keys())
    selected_timing = st.multiselect(
        "选择涨停时间段 / 连板梯度",
        options=timing_options,
        default=TIMING_DEFAULT,
        format_func=lambda k: TIMING_METRICS[k],
        key="trend_timing",
    )

    if not selected_timing:
        st.info("请至少选择一个时间段指标。")
    else:
        fig_timing = go.Figure()
        for key in selected_timing:
            label = TIMING_METRICS[key]
            fig_timing.add_trace(go.Scatter(
                x=hist_df["date"],
                y=hist_df.get(key, [0] * len(hist_df)),
                name=label,
                mode="lines+markers",
            ))
        fig_timing.update_layout(
            yaxis={"title": "家数"},
            hovermode="x unified",
            legend={"orientation": "h", "y": -0.2},
        )
        st.plotly_chart(fig_timing, use_container_width=True)
```

**注意：** 删除原来 `history = load_history(limit=10)` 这一行（已移入 `if len(history) < 2` 块前）。同时删除原有的 `st.divider()` 和 `st.plotly_chart(fig_line, ...)` 代码。

**Step 3: 手动启动 Streamlit 验证**

```bash
uv run streamlit run app.py
```

检查：
- 近10日情绪趋势模块有 multiselect，默认显示4条曲线，双轴正确
- 近10日涨停时间分布模块有 multiselect，默认显示3条曲线，单轴
- 选择/取消选择指标后图表实时更新
- 选空时出现提示文字而不是报错

**Step 4: 运行全部测试（回归）**

```bash
uv run pytest -v
```

预期：ALL PASS（app.py 无自动化测试，不影响覆盖率）。

**Step 5: Commit**

```bash
git add app.py
git commit -m "feat: rewrite trend chart with full metrics multiselect and timing distribution chart"
```

---

### Task 4: 验证旧缓存文件兼容性

**目的：** 确保 `data/2026-02-27.json`（旧缓存，只有4个字段的 history_10d）在新代码下不报错。

**Step 1: 手动测试**

```bash
uv run python3 -c "
from processor import load_history
history = load_history(limit=10)
print('entries:', len(history))
print('keys:', list(history[0].keys()) if history else 'empty')
print('shouban sample:', history[0].get('shouban', 'MISSING'))
"
```

预期：`shouban` 值为 `0`（旧缓存文件 history_10d 里没有此字段，默认填0）。

**Step 2: 重新抓取今日数据覆盖旧缓存（可选，生产验证）**

```bash
uv run python3 -c "
from fetcher import fetch_today_data
import json, pathlib
data = fetch_today_data('2026-02-27')
print('history_10d keys:', list(data['history_10d'][0].keys()) if data.get('history_10d') else 'empty')
"
```

预期：所有30个字段都存在。

**Step 3: 最终回归测试 + 覆盖率**

```bash
uv run pytest --cov=fetcher --cov=processor --cov-report=term-missing -v
```

预期：覆盖率 ≥ 90%（新增代码已有测试覆盖）。

**Step 4: Commit（如有改动）**

```bash
git add .
git commit -m "test: verify backward compatibility with old cache files"
```
