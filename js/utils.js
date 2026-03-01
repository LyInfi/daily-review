// js/utils.js
// 复刻 processor.py 的数据处理逻辑

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

function getLbStocks(stocks) {
  return stocks
    .filter(s => (s.continuous_days || 0) >= 2)
    .sort((a, b) => b.continuous_days - a.continuous_days);
}

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

function getHistory(data) {
  const h10d = data.history_10d || [];
  return h10d.slice().sort((a, b) => a.date.localeCompare(b.date));
}

function formatAmount(val) {
  if (!val) return '0';
  if (val >= 1e8) return (val / 1e8).toFixed(1) + '亿';
  if (val >= 1e4) return (val / 1e4).toFixed(1) + '万';
  return String(val);
}
