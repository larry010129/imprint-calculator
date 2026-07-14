(function () {
  'use strict';

  const rangeForm = document.getElementById('dashboard-range-form');
  if (rangeForm) {
    rangeForm.querySelectorAll('select, input[type="date"]').forEach((field) => {
      field.addEventListener('change', () => rangeForm.submit());
    });
  }

  const chartEl = document.getElementById('cms-trends-chart');
  const dataEl = document.getElementById('dashboard-chart-data');
  const activeEl = document.getElementById('dashboard-chart-active');
  if (!chartEl || !dataEl || typeof Chart === 'undefined') return;

  let trends = [];
  let activeKey = '';
  try {
    trends = JSON.parse(dataEl.textContent || '[]');
    activeKey = JSON.parse(activeEl?.textContent || '""');
  } catch (_) {
    return;
  }

  function chartLabel(key, fallback) {
    const lang = localStorage.getItem('appLang') || 'zh';
    const table = typeof translations !== 'undefined' ? translations[lang] : null;
    return (table && table[key]) || fallback;
  }

  function chartColors() {
    const isDark = document.body.classList.contains('dark-theme');
    return {
      gridColor: isDark ? 'rgba(255,255,255,0.08)' : 'rgba(0,0,0,0.08)',
      textColor: isDark ? '#8b8b96' : '#6d6a64',
    };
  }

  const labels = trends.map((item) => item.label || item.month);
  const orderTotals = trends.map((item) => item.order_total ?? item.orders);
  const revenue = trends.map((item) => item.revenue);
  const orderCounts = trends.map((item) => item.orders);
  const completedCounts = trends.map((item) => item.completed_orders ?? 0);
  const activeIndex = trends.findIndex((item) => (item.key || item.month) === activeKey);

  function cumulative(values) {
    let running = 0;
    return values.map((value) => {
      running += value;
      return running;
    });
  }

  function setActiveButton(group, activeBtn) {
    group.querySelectorAll('button').forEach((other) => {
      const active = other === activeBtn;
      other.setAttribute('aria-pressed', active ? 'true' : 'false');
      other.classList.toggle('bg-gray-900', active);
      other.classList.toggle('text-white', active);
      other.classList.toggle('dark:bg-white', active);
      other.classList.toggle('dark:text-gray-900', active);
      other.classList.toggle('bg-white', !active);
      other.classList.toggle('dark:bg-[#14141a]', !active);
      other.classList.toggle('text-gray-700', !active);
      other.classList.toggle('dark:text-gray-300', !active);
    });
  }

  const viewToggle = document.getElementById('cms-trend-view-toggle');
  const metricToggle = document.getElementById('cms-trend-metric-toggle');
  let trendView = 'period';
  let trendMetric = 'amount';

  let chartInstance = null;

  function buildChart() {
    const { gridColor, textColor } = chartColors();
    const isCount = trendMetric === 'count';
    const ordersLabel = isCount
      ? chartLabel('admin_dashboard_chart_orders_count', '訂單數量')
      : chartLabel('admin_dashboard_chart_orders', '訂單總額');
    const revenueLabel = isCount
      ? chartLabel('admin_dashboard_chart_revenue_count', '完成訂單數量')
      : chartLabel('admin_dashboard_chart_revenue', '完成訂單總額');
    const cumulativeSuffix = chartLabel('admin_dashboard_view_cumulative_suffix', '（累計）');

    const orderSeries = isCount ? orderCounts : orderTotals;
    const revenueSeries = isCount ? completedCounts : revenue;
    const orderData = trendView === 'cumulative' ? cumulative(orderSeries) : orderSeries;
    const revenueData = trendView === 'cumulative' ? cumulative(revenueSeries) : revenueSeries;
    const suffix = trendView === 'cumulative' ? cumulativeSuffix : '';

    const formatValue = (value) => (isCount
      ? Number(value).toLocaleString()
      : 'NT$ ' + Number(value).toLocaleString());

    if (chartInstance) {
      chartInstance.destroy();
    }

    chartInstance = new Chart(chartEl, {
      type: 'line',
      data: {
        labels,
        datasets: [
          {
            label: ordersLabel + suffix,
            data: orderData,
            borderColor: 'rgb(59, 130, 246)',
            backgroundColor: 'rgba(59, 130, 246, 0.1)',
            tension: 0.35,
            yAxisID: 'y',
          },
          {
            label: revenueLabel + suffix,
            data: revenueData,
            borderColor: 'rgb(34, 168, 88)',
            backgroundColor: 'rgba(34, 168, 88, 0.1)',
            tension: 0.35,
            yAxisID: 'y',
          },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        interaction: { mode: 'index', intersect: false },
        plugins: {
          legend: {
            labels: { color: textColor, usePointStyle: true },
          },
          tooltip: {
            callbacks: {
              label(context) {
                const value = context.parsed.y;
                return `${context.dataset.label}: ${formatValue(value)}`;
              },
            },
          },
        },
        scales: {
          x: {
            ticks: { color: textColor, maxRotation: 45, minRotation: 0 },
            grid: { color: gridColor },
          },
          y: {
            position: 'left',
            beginAtZero: true,
            ticks: {
              color: textColor,
              callback(value) {
                return formatValue(value);
              },
            },
            grid: { color: gridColor },
          },
        },
      },
    });

    if (activeIndex >= 0) {
      chartEl.setAttribute('aria-description', `目前選取區間 ${activeKey}`);
    }
  }

  if (viewToggle) {
    viewToggle.querySelectorAll('[data-trend-view]').forEach((btn) => {
      btn.addEventListener('click', () => {
        if (btn.dataset.trendView === trendView) return;
        trendView = btn.dataset.trendView;
        setActiveButton(viewToggle, btn);
        buildChart();
      });
    });
  }

  if (metricToggle) {
    metricToggle.querySelectorAll('[data-trend-metric]').forEach((btn) => {
      btn.addEventListener('click', () => {
        if (btn.dataset.trendMetric === trendMetric) return;
        trendMetric = btn.dataset.trendMetric;
        setActiveButton(metricToggle, btn);
        buildChart();
      });
    });
  }

  buildChart();
  document.addEventListener('langchange', buildChart);
})();
