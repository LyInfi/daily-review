// js/app.js

let state = {
  daily:  [...DAILY_DEFAULT],
  timing: [...TIMING_DEFAULT],
  volume: [...VOLUME_DEFAULT],
  history: [],
};

async function fetchJSON(url) {
  const resp = await fetch(url);
  if (!resp.ok) throw new Error(`HTTP ${resp.status}: ${url}`);
  return resp.json();
}

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

  sel.value = dates[0];
  sel.addEventListener('change', () => loadAndRender(sel.value));
  await loadAndRender(dates[0]);
}

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

function renderAll(data) {
  const stats    = getSummaryStats(data);
  const lbStocks = getLbStocks(data.limit_up || []);
  const topics   = getTopicCounts(data.limit_up || []);
  const ladder   = getContinuousLadder(data.limit_up || []);
  const history  = getHistory(data);
  state.history  = history;

  document.getElementById('data-caption').textContent =
    `数据日期：${data.date || ''}　　抓取时间：${data.fetched_at || ''}`;

  renderCards(stats);
  renderLbRanking('chart-lb',    lbStocks);
  renderTopicHeat('chart-topic', topics);
  renderLadder('chart-ladder',   ladder);

  if (history.length >= 2) {
    renderDailyTrend('chart-daily',  history, state.daily);
    renderTimingDist('chart-timing', history, state.timing);
    renderBreadth('chart-breadth',   history);
    renderVolume('chart-volume',     history, state.volume);
    document.getElementById('section-history').style.display = '';
  } else {
    document.getElementById('section-history').style.display = 'none';
  }
}

function renderCards(stats) {
  const displayZt = stats.zt_all > 0 ? stats.zt_all : stats.limit_up_count;
  setCard('card-zt',     '涨停家数（全市场）', displayZt);
  setCard('card-broken', '开板家数',           stats.limit_broken_count);
  setCard('card-seal',   '封板率',             stats.seal_rate + '%');
  setCard('card-max',    '最高连板',           `${stats.max_continuous}板`, stats.max_continuous_name);
  setCard('card-topic',  '最强题材',           stats.top_topic);
}

function setCard(id, label, value, sub) {
  const el = document.getElementById(id);
  el.querySelector('.card-label').textContent = label;
  el.querySelector('.card-value').textContent = value;
  const subEl = el.querySelector('.card-sub');
  if (subEl) subEl.textContent = sub || '';
}

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

function showLoading(on) {
  document.getElementById('loading').style.display = on ? '' : 'none';
}

function showError(msg) {
  const el = document.getElementById('warning-banner');
  el.textContent = '⚠️ ' + msg;
  el.style.display = '';
}

document.addEventListener('DOMContentLoaded', () => {
  buildMultiselect('ms-daily',  DAILY_METRICS,  DAILY_DEFAULT,  'daily',
    renderDailyTrend, 'chart-daily');
  buildMultiselect('ms-timing', TIMING_METRICS, TIMING_DEFAULT, 'timing',
    renderTimingDist, 'chart-timing');
  buildMultiselect('ms-volume', VOLUME_METRICS, VOLUME_DEFAULT, 'volume',
    renderVolume,     'chart-volume');

  initDateSelect();
});
