import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
from datetime import datetime
from fetcher import load_or_fetch
from processor import get_summary_stats, get_topic_counts, get_continuous_ladder, load_history

# ── 近10日趋势图：指标定义 ─────────────────────────────────────
# 日级别指标（key → (中文标签, 轴, 线型)）
DAILY_METRICS = {
    "zt_all":             ("总涨停",          "left",  "solid"),
    "limit_broken_count": ("开板数",          "left",  "solid"),
    "dt_count":           ("跌停数",          "left",  "solid"),
    "lb_count":           ("连板数",          "left",  "solid"),
    "up10_count":         ("涨幅10%以上",     "left",  "solid"),
    "down9_count":        ("跌幅9%以上",      "left",  "solid"),
    "yizi_count":         ("一字涨停",        "left",  "solid"),
    "zt_925":             ("9:25涨停",        "left",  "solid"),
    "seal_rate":          ("封板率%",         "right", "dot"),
    "rate_1to2":          ("一进二连板率%",   "right", "dot"),
    "rate_2to3":          ("二进三连板率%",   "right", "dot"),
    "rate_3to4":          ("三进四连板率%",   "right", "dot"),
    "lb_rate":            ("连板率%",         "right", "dot"),
    "lb_rate_prev":       ("昨日连板率%",     "right", "dot"),
}

DAILY_DEFAULT = ["zt_all", "limit_broken_count", "seal_rate", "lb_rate"]

# 市场涨跌家数（量级为千，单独一张图）
BREADTH_METRICS = {
    "up_count":   "上涨家数",
    "down_count": "下跌家数",
}

# 成交额指标（单位亿，量级远大于家数类，单独一张图）
VOLUME_METRICS = {
    "zt_amount":    "涨停总金额(亿)",
    "total_amount": "总金额(亿)",
    "sh_amount":    "上证成交额(亿)",
    "cyb_amount":   "创业板成交额(亿)",
    "kcb_amount":   "科创板成交额(亿)",
}

VOLUME_DEFAULT = ["sh_amount", "cyb_amount", "total_amount"]

# 时间分布指标（key → 中文标签）
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
col1.metric("涨停家数（全市场）", stats["zt_all"] if stats["zt_all"] > 0 else stats["limit_up_count"])
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
if topics:
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
else:
    st.info("暂无题材数据")

st.divider()

# ── 模块 C：近10日情绪趋势（折线图） ──────────────────────────
st.subheader("📊 近10日情绪趋势")

history = load_history(limit=10)

hist_df = pd.DataFrame(history) if len(history) >= 2 else pd.DataFrame()

if len(history) < 2:
    st.info("历史数据不足，积累更多交易日后趋势图将自动显示。")
else:
    # 块一：日级别指标
    selected_daily = st.multiselect(
        "选择日级别指标",
        options=list(DAILY_METRICS.keys()),
        default=DAILY_DEFAULT,
        format_func=lambda k: DAILY_METRICS[k][0],
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
                y=hist_df[key] if key in hist_df.columns else [0] * len(hist_df),
                name=label,
                line={"dash": dash},
                yaxis=yaxis,
            ))
        fig_daily.update_layout(
            xaxis={"type": "category"},
            yaxis={"title": "家数 / 金额(亿)"},
            yaxis2={"title": "比率%", "overlaying": "y", "side": "right"},
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
    selected_timing = st.multiselect(
        "选择涨停时间段 / 连板梯度",
        options=list(TIMING_METRICS.keys()),
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
                y=hist_df[key] if key in hist_df.columns else [0] * len(hist_df),
                name=label,
                mode="lines+markers",
            ))
        fig_timing.update_layout(
            xaxis={"type": "category"},
            yaxis={"title": "家数"},
            hovermode="x unified",
            legend={"orientation": "h", "y": -0.2},
        )
        st.plotly_chart(fig_timing, use_container_width=True)

st.divider()

# ── 模块 C3：近10日市场涨跌家数 ────────────────────────────────
st.subheader("📈 近10日市场涨跌家数")

if len(history) < 2:
    st.info("历史数据不足，积累更多交易日后趋势图将自动显示。")
else:
    fig_breadth = go.Figure()
    for key, label in BREADTH_METRICS.items():
        fig_breadth.add_trace(go.Scatter(
            x=hist_df["date"],
            y=hist_df[key] if key in hist_df.columns else [0] * len(hist_df),
            name=label,
            mode="lines+markers",
        ))
    fig_breadth.update_layout(
        xaxis={"type": "category"},
        yaxis={"title": "家数"},
        hovermode="x unified",
        legend={"orientation": "h", "y": -0.2},
    )
    st.plotly_chart(fig_breadth, use_container_width=True)

st.divider()

# ── 模块 C4：近10日成交额 ───────────────────────────────────────
st.subheader("💰 近10日成交额")

if len(history) < 2:
    st.info("历史数据不足，积累更多交易日后趋势图将自动显示。")
else:
    selected_volume = st.multiselect(
        "选择成交额指标",
        options=list(VOLUME_METRICS.keys()),
        default=VOLUME_DEFAULT,
        format_func=lambda k: VOLUME_METRICS[k],
        key="trend_volume",
    )

    if not selected_volume:
        st.info("请至少选择一个成交额指标。")
    else:
        fig_volume = go.Figure()
        for key in selected_volume:
            fig_volume.add_trace(go.Scatter(
                x=hist_df["date"],
                y=hist_df[key] if key in hist_df.columns else [0] * len(hist_df),
                name=VOLUME_METRICS[key],
                mode="lines+markers",
            ))
        fig_volume.update_layout(
            xaxis={"type": "category"},
            yaxis={"title": "成交额(亿)"},
            hovermode="x unified",
            legend={"orientation": "h", "y": -0.2},
        )
        st.plotly_chart(fig_volume, use_container_width=True)

# ── 模块 D：连板梯队图（柱状图） ──────────────────────────────
st.subheader("🪜 连板梯队")

ladder = get_continuous_ladder(data["limit_up"])
if ladder:
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
else:
    st.info("暂无连板梯队数据")
