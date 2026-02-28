# GitHub Pages 部署设计

日期: 2026-02-28

## 目标

将现有 Streamlit 看板重构为纯静态 Vanilla JS + Plotly.js 页面，部署到 GitHub Pages（公开仓库），并通过 GitHub Actions 每天自动抓取最新涨停数据。

## 方案选择

选择方案 A：单分支，代码与数据同仓库。结构最简单，main 分支统一管理所有文件。

## 项目结构

```
daily-review/
├── index.html                    ← 看板入口页
├── js/
│   ├── app.js                    ← 主逻辑（加载数据、日期切换）
│   ├── charts.js                 ← 所有 Plotly 图表渲染
│   └── utils.js                  ← 工具函数（格式化等）
├── css/
│   └── style.css                 ← 样式
├── data/
│   ├── index.json                ← 日期索引 ["2026-02-28", "2026-02-27", ...]
│   └── YYYY-MM-DD.json           ← 每日原始数据（现有 JSON 格式，原样保存）
├── .github/
│   └── workflows/
│       └── fetch.yml             ← 每天定时抓取脚本
│
│── fetcher.py / processor.py     ← 保留，本地开发仍可用
└── app.py / tests/               ← 保留
```

## 数据流

```
每天 16:00 北京时间
→ GitHub Actions 触发
→ 调用 wuylh.com API 抓取当日数据
→ 存入 data/YYYY-MM-DD.json
→ 更新 data/index.json（头部插入新日期）
→ git commit + push 到 main 分支
→ GitHub Pages 自动重新部署（约 1-2 分钟生效）
```

## 前端布局

```
┌─────────────────────────────────────────────┐
│  每日复盘看板          日期选择: [2026-02-28 ▼] │
├─────────────────────────────────────────────┤
│  涨停 N家  │ 开板 N家  │ 封板率 N%  │ 最高 N板  │
├─────────────────────────────────────────────┤
│  连板股排行（横向柱状图）  │  题材热度（横向柱状图）  │
├─────────────────────────────────────────────┤
│        近10日情绪趋势（折线图，可多选指标）        │
├─────────────────────────────────────────────┤
│              连板梯队（柱状图）                │
└─────────────────────────────────────────────┘
```

### 交互功能

- 顶部日期下拉框：读取 `data/index.json`，切换查看历史数据
- 情绪趋势图：多选框筛选指标（复刻现有 Streamlit 版交互）
- 所有图表使用 Plotly.js CDN，无需构建工具

### 样式

- 深色背景（与现有 Streamlit 暗色主题一致）
- 纯 CSS，无 UI 框架依赖

## GitHub Actions 工作流（fetch.yml）

```
触发条件:
  - 定时: 每天 08:00 UTC（北京时间 16:00，A 股收盘后）
  - 手动触发: workflow_dispatch（支持在 GitHub 页面手动运行）

执行步骤:
  1. Checkout 仓库（含历史，用于 push）
  2. 安装 Python 3.12 + requests
  3. 运行抓取脚本，生成 data/YYYY-MM-DD.json
  4. 更新 data/index.json
  5. git commit + git push

异常处理:
  - 非交易日（API 无数据）→ 跳过，不创建空文件
  - 文件已存在 → 跳过（幂等，手动触发安全）
```

## GitHub Pages 配置

- 仓库可见性：Public
- Pages Source：main 分支，根目录 `/`
- 访问地址：`https://{username}.github.io/daily-review/`

## 保留内容

现有 Python 代码完整保留，本地 Streamlit 开发流程不受影响：
- `fetcher.py` / `processor.py` / `app.py`
- `tests/`
- `start.bat`
- `requirements.txt` / `requirements-dev.txt`
