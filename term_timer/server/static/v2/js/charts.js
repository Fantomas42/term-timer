// V2 charts: every canvas[data-chart] is drawn by the builder its kind
// names, from the JSON block data-chart-data points to. Colours and fonts
// come from the theme custom properties, never from here. Needs Chart.js
// 3.7.1 loaded before this module.

const root = document.documentElement;

export const token = (name) =>
  getComputedStyle(root).getPropertyValue(`--${name}`).trim();

const builders = {};

export function register(kind, build) {
  builders[kind] = build;
}

function fontFamily() {
  return token('font-mono').split(',')[0].replace(/"/g, '');
}

function applyTheme(Chart) {
  Chart.defaults.color = token('chart-axis');
  Chart.defaults.borderColor = token('chart-grid');
  Chart.defaults.font.family = fontFamily();
  Chart.defaults.font.size = parseFloat(getComputedStyle(root).fontSize) * 0.7;
  Chart.defaults.maintainAspectRatio = false;
  Chart.defaults.plugins.legend.display = false;
  Chart.defaults.plugins.tooltip.backgroundColor = token('tooltip-bg');
  Chart.defaults.plugins.tooltip.titleColor = token('tooltip-text');
  Chart.defaults.plugins.tooltip.bodyColor = token('tooltip-text');
  Chart.defaults.plugins.tooltip.cornerRadius = 0;
  Chart.defaults.plugins.tooltip.displayColors = false;
}

// Dashed vertical markers with their label, alternating heights so that
// close steps do not overlap.
function markerLines(markers) {
  return {
    id: 'markerLines',
    afterDatasetsDraw(chart) {
      const { ctx, chartArea, scales } = chart;
      const size = window.Chart.defaults.font.size;
      ctx.save();
      ctx.strokeStyle = token('chart-marker');
      ctx.fillStyle = token('chart-marker');
      ctx.lineWidth = 1;
      ctx.setLineDash([3, 3]);
      ctx.textAlign = 'right';
      ctx.font = `600 ${size}px ${fontFamily()}`;
      markers.forEach((marker, index) => {
        const x = scales.x.getPixelForValue(marker.x);
        ctx.beginPath();
        ctx.moveTo(x, chartArea.top);
        ctx.lineTo(x, chartArea.bottom);
        ctx.stroke();
        const line = size * 1.3;
        ctx.fillText(marker.label, x - 4, chartArea.top + line * (1 + index % 2));
      });
      ctx.restore();
    },
  };
}

// Cumulative time of each move, the steps marked.
// data: {points: [{x, y}], steps: [{x, label}]}
register('moves-timing', (data) => ({
  type: 'scatter',
  data: {
    datasets: [{
      data: data.points,
      showLine: true,
      borderColor: token('chart-1'),
      backgroundColor: token('chart-1'),
      borderWidth: 2,
      pointRadius: 0,
      pointHoverRadius: 5,
      pointHitRadius: 8,
    }],
  },
  options: {
    scales: {
      x: {
        type: 'linear', min: 0, max: data.points.length + 1,
        grid: { display: false }, title: { display: true, text: 'move' },
      },
      y: { min: 0, title: { display: true, text: 'seconds' } },
    },
    plugins: {
      tooltip: {
        callbacks: {
          title: (items) => `Move #${items[0].parsed.x}`,
          label: (item) => `${item.parsed.y.toFixed(2)} s`,
        },
      },
    },
  },
  plugins: [markerLines(data.steps)],
}));

// TPS and eTPS of each step, side by side.
// data: {steps: [{label, tps, etps}]}
register('steps-tps', (data) => ({
  type: 'bar',
  data: {
    labels: data.steps.map((step) => step.label),
    datasets: [
      { label: 'TPS', data: data.steps.map((step) => step.tps),
        backgroundColor: token('chart-2') },
      { label: 'eTPS', data: data.steps.map((step) => step.etps),
        backgroundColor: token('chart-1') },
    ],
  },
  options: {
    datasets: {
      bar: { borderRadius: 0, categoryPercentage: 0.7, barPercentage: 0.9 },
    },
    plugins: {
      tooltip: {
        callbacks: {
          label: (item) => `${item.dataset.label} ${item.parsed.y.toFixed(2)}`,
        },
      },
    },
    scales: { x: { grid: { display: false } }, y: { beginAtZero: true } },
  },
}));

// Recognition then execution of each step, stacked into its total.
// data: {steps: [{label, recognition, execution}]}, in seconds
register('steps-recognition', (data) => ({
  type: 'bar',
  data: {
    labels: data.steps.map((step) => step.label),
    datasets: [
      { label: 'Recognition', data: data.steps.map((step) => step.recognition),
        backgroundColor: token('chart-2') },
      { label: 'Execution', data: data.steps.map((step) => step.execution),
        backgroundColor: token('chart-1') },
    ],
  },
  options: {
    datasets: {
      bar: { borderRadius: 0, categoryPercentage: 0.7, barPercentage: 0.9 },
    },
    plugins: {
      tooltip: {
        callbacks: {
          label: (item) =>
            `${item.dataset.label} ${item.parsed.y.toFixed(2)} s`,
        },
      },
    },
    scales: {
      x: { stacked: true, grid: { display: false } },
      y: { stacked: true, beginAtZero: true,
           title: { display: true, text: 'seconds' } },
    },
  },
}));

// Fluency of each step, from 0 to 100.
// data: {steps: [{label, fluency}]}
register('steps-fluency', (data) => ({
  type: 'line',
  data: {
    labels: data.steps.map((step) => step.label),
    datasets: [{
      label: 'Fluency',
      data: data.steps.map((step) => step.fluency),
      borderColor: token('chart-1'),
      backgroundColor: token('chart-1'),
      borderWidth: 2,
      pointRadius: 3,
      pointHoverRadius: 5,
    }],
  },
  options: {
    plugins: {
      tooltip: {
        callbacks: { label: (item) => `Fluency ${item.parsed.y}%` },
      },
    },
    scales: {
      x: { grid: { display: false } },
      y: { min: 0, max: 100, title: { display: true, text: '%' } },
    },
  },
}));

// A time in seconds as it is read: 28.84, 1:02.35, DNF for none.
function seconds(value) {
  if (value == null) return 'DNF';
  if (value < 60) return value.toFixed(2);
  const minutes = Math.floor(value / 60);
  return `${minutes}:${(value - minutes * 60).toFixed(2).padStart(5, '0')}`;
}

// A dashed horizontal reference in acid, labelled at its right end.
function reference(value, label) {
  return {
    id: 'reference',
    afterDatasetsDraw(chart) {
      if (!value) return;
      const { ctx, chartArea, scales } = chart;
      const y = scales.y.getPixelForValue(value);
      ctx.save();
      ctx.strokeStyle = token('accent');
      ctx.fillStyle = token('accent');
      ctx.setLineDash([4, 4]);
      ctx.beginPath();
      ctx.moveTo(chartArea.left, y);
      ctx.lineTo(chartArea.right, y);
      ctx.stroke();
      ctx.textAlign = 'right';
      ctx.font = `700 ${window.Chart.defaults.font.size}px ${fontFamily()}`;
      ctx.fillText(label, chartArea.right, y - 5);
      ctx.restore();
    },
  };
}

// The last solves as dots, their Ao12 as the line, the best Ao12 dashed.
// data: {points: [s], ao12: [s], best: s}
register('form', (data) => ({
  type: 'line',
  data: {
    labels: data.points.map((_, index) => index + 1),
    datasets: [
      { label: 'Ao12', data: data.ao12, borderColor: token('chart-1'),
        borderWidth: 2, pointRadius: 0, spanGaps: true, tension: 0.25 },
      { label: 'Solve', data: data.points, showLine: false, pointRadius: 2.5,
        pointBackgroundColor: token('chart-dot'), pointBorderWidth: 0 },
    ],
  },
  options: {
    layout: { padding: { top: 18 } },
    scales: {
      x: { display: false },
      y: { ticks: { maxTicksLimit: 4, callback: seconds } },
    },
    plugins: {
      tooltip: {
        callbacks: {
          title: () => '',
          label: (item) => `${item.dataset.label} ${seconds(item.parsed.y)}`,
        },
      },
    },
  },
  plugins: [reference(data.best, `PB AO12 ${seconds(data.best)}`)],
}));

// Every solve on the calendar, coloured by its series, the rolling
// average on top. x counts the days since start.
// data: {start, days, points: [{x, y, k}], line: [{x, y}], floor,
//        ceiling, kinds: [{key, label, role}], labels: {key: label}}
register('career', (data) => {
  const colours = Object.fromEntries(
    data.kinds.map((kind) => [kind.key, token(kind.role)]),
  );
  const start = new Date(`${data.start}T00:00:00`);
  const day = (offset) => {
    const moment = new Date(start);
    moment.setDate(moment.getDate() + offset);
    return moment;
  };
  return {
    type: 'scatter',
    data: {
      datasets: [
        { label: 'Ao100', data: data.line, showLine: true, order: 0,
          borderColor: token('text'), borderWidth: 2, pointRadius: 0,
          tension: 0.3 },
        { label: 'Solve', data: data.points, order: 1, pointRadius: 2,
          pointBorderWidth: 0,
          pointBackgroundColor: data.points.map((point) => colours[point.k]) },
      ],
    },
    options: {
      scales: {
        x: {
          type: 'linear', min: 0, max: data.days, grid: { display: false },
          ticks: {
            maxTicksLimit: 12,
            callback: (offset) => day(offset).toLocaleDateString(
              'en-GB', { month: 'short', year: '2-digit' },
            ),
          },
        },
        y: { min: data.floor, max: data.ceiling,
             ticks: { maxTicksLimit: 6, callback: seconds } },
      },
      plugins: {
        tooltip: {
          callbacks: {
            title: (items) => day(items[0].parsed.x).toLocaleDateString('en-GB'),
            label: (item) => (item.datasetIndex
              ? `${data.labels[item.raw.k]} ${seconds(item.parsed.y)}`
              : `Ao100 ${seconds(item.parsed.y)}`),
          },
        },
      },
    },
  };
});

// The times of a session as dots and their rolling averages, the second
// one (Ao12 by default) in acid.
// data: {indices, times: [s], series: [{label, data}], ceiling}
const TREND_ROLES = ['chart-3', 'chart-1', 'chart-4', 'chart-5'];
register('trend', (data) => ({
  type: 'line',
  data: {
    labels: data.indices,
    datasets: [
      { label: 'Time', data: data.times, showLine: false, pointRadius: 2,
        pointBorderWidth: 0, pointBackgroundColor: token('chart-dot') },
      ...data.series.map((series, index) => ({
        label: series.label, data: series.data, pointRadius: 0,
        borderWidth: index === 1 ? 2.5 : 1.5, spanGaps: true, tension: 0.2,
        borderColor: token(TREND_ROLES[index % TREND_ROLES.length]),
      })),
    ],
  },
  options: {
    interaction: { mode: 'index', intersect: false },
    scales: {
      x: { grid: { display: false }, ticks: { maxTicksLimit: 10 } },
      y: { suggestedMax: data.ceiling, ticks: { callback: seconds } },
    },
    plugins: {
      tooltip: {
        callbacks: {
          title: (items) => `Solve #${items[0].label}`,
          label: (item) => `${item.dataset.label} ${seconds(item.parsed.y)}`,
        },
      },
    },
  },
}));

// Solves per time bucket, the most frequent one in acid.
// data: {labels, counts, mode}
register('distribution', (data) => ({
  type: 'bar',
  data: {
    labels: data.labels,
    datasets: [{
      data: data.counts,
      backgroundColor: data.labels.map((label) => token(
        label === data.mode ? 'chart-1' : 'chart-2',
      )),
    }],
  },
  options: {
    datasets: {
      bar: { borderRadius: 0, categoryPercentage: 0.92, barPercentage: 1 },
    },
    scales: {
      x: { grid: { display: false } },
      y: { beginAtZero: true, ticks: { maxTicksLimit: 5 } },
    },
    plugins: {
      tooltip: { callbacks: { label: (item) => `${item.parsed.y} solves` } },
    },
  },
}));

export function draw(canvas) {
  const build = builders[canvas.dataset.chart];
  if (!build) {
    console.error(`Unknown chart kind: ${canvas.dataset.chart}`);
    return null;
  }
  const source = document.getElementById(canvas.dataset.chartData);
  return new window.Chart(canvas, build(JSON.parse(source.textContent)));
}

if (window.Chart) {
  applyTheme(window.Chart);
  document.querySelectorAll('canvas[data-chart]').forEach(draw);
} else {
  console.error('Chart.js is not loaded: charts are not drawn');
}
