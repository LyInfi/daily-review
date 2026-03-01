# 每日复盘看板

每日自动获取舞阳复盘网站数据，可视化展示涨停板核心指标。

## 在线访问

GitHub Pages: https://lyinfi.github.io/daily-review/

（每个工作日 16:00 自动更新数据）

## 首次安装

```bash
pip install -r requirements.txt
```

或使用 [uv](https://github.com/astral-sh/uv)（更快）：

```bash
uv venv .venv
uv pip install -r requirements.txt
```

## 启动

**Windows：** 双击 `start.bat`，浏览器自动打开看板。

**命令行：**

```bash
streamlit run app.py
```

浏览器访问 `http://localhost:8501`

## 功能模块

| 模块 | 描述 |
|------|------|
| **概览卡片** | 涨停家数、开板家数、炸板率、最高连板、最强题材 |
| **连板股排行** | 连板股按连板数排序，最高连板高亮显示 |
| **题材热度** | 涨停股题材统计横向条形图 |
| **情绪趋势** | 近10日涨停/开板/炸板率折线图 |
| **连板梯队** | 各板位股票数量柱状图 |

## 数据说明

- 数据来源：[舞阳复盘](https://www.wuylh.com/replayrobot/index.html)，接口：`/replayrobot/json/{date}p.json`
- 每日首次启动自动爬取并缓存到 `data/` 目录
- 休市日或非交易日自动回退显示最近一个交易日的数据
- 历史数据文件按日期命名：`data/YYYY-MM-DD.json`

## 开发

运行测试：

```bash
pytest tests/ -v --cov=fetcher --cov=processor --cov-report=term-missing
```
