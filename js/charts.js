// js/charts.js

const DARK = {
  paper_bgcolor: '#1c2232',
  plot_bgcolor:  '#1c2232',
  font:          { color: '#fafafa', size: 12 },
  xaxis: { gridcolor: '#2e3650', linecolor: '#2e3650', color: '#8b95a8' },
  yaxis: { gridcolor: '#2e3650', linecolor: '#2e3650', color: '#8b95a8' },
  margin: { t: 30, b: 50, l: 50, r: 30 },
};

const CONFIG = { responsive: true, displayModeBar: false };

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

function renderLbRanking(elementId, lbStocks) {
  if (!lbStocks.length) {
    document.getElementById(elementId).innerHTML = '<p style="color:#8b95a8;text-align:center;padding:2rem">暂无连板股数据</p>';
    return;
  }
  const stocks = lbStocks.slice(0, 15).reverse();
  const maxDays = lbStocks[0].continuous_days;
  const colors = stocks.map(s => s.continuous_days === maxDays ? '#ff4b4b' : '#4c8bf5');

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
