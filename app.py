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

if len(history) < 2:
    st.info("历史数据不足，积累更多交易日后趋势图将自动显示。")
else:
    hist_df = pd.DataFrame(history)

    fig_line = go.Figure()
    fig_line.add_trace(go.Scatter(
        x=hist_df["date"], y=hist_df["limit_up_count"],
        name="连板股数（展示）", line={"color": "#4C78A8"},
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
