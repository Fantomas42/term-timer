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

// Daily charts: the fixed zones of the daily (DAILY_ZONE_EDGES) drawn as
// faint bands behind the times, without chartjs-plugin-annotation.
const ZONE_ROLES = ['zone-0', 'zone-1', 'zone-2', 'zone-3'];

// The zones of the daily as horizontal bands, faint, clipped to the
// chart area; each edge a thin line of the colour of the zone above it.
// edges: [20, 25, 30] in seconds, four zones.
function zoneBands(edges) {
  return {
    id: 'zoneBands',
    beforeDatasetsDraw(chart) {
      const { ctx, chartArea, scales } = chart;
      const bounds = [-Infinity, ...edges, Infinity];
      const clamp = (value) => Math.min(
        chartArea.bottom, Math.max(chartArea.top, value),
      );
      ctx.save();
      ZONE_ROLES.forEach((role, index) => {
        const low = Math.max(bounds[index], scales.y.min);
        const high = Math.min(bounds[index + 1], scales.y.max);
        if (low >= high) return;
        const top = clamp(scales.y.getPixelForValue(high));
        const bottom = clamp(scales.y.getPixelForValue(low));
        ctx.fillStyle = token(role);
        ctx.globalAlpha = 0.07;
        ctx.fillRect(chartArea.left, top, chartArea.right - chartArea.left,
                     bottom - top);
        if (index && bounds[index] > scales.y.min) {
          ctx.globalAlpha = 0.45;
          ctx.fillRect(chartArea.left, bottom, chartArea.right - chartArea.left,
                       1);
        }
      });
      ctx.restore();
    },
  };
}

// An axis tick: whole seconds, minutes past a minute.
const tick = (value) => (value < 60 ? `${value}` : seconds(value));

const day = (label) => new Date(`${label}T00:00:00`).toLocaleDateString(
  'en-GB', { day: 'numeric', month: 'short', year: 'numeric' },
);

// The best and the first attempt of every played day, on the zones.
// data: {labels: [iso day], best: [s], first: [s], edges, floor, ceiling,
//        clipped: points above the ceiling}
register('daily-times', (data) => ({
  type: 'line',
  data: {
    labels: data.labels,
    datasets: [
      { label: 'Best', data: data.best, borderColor: token('chart-1'),
        backgroundColor: token('chart-1'), borderWidth: 2, pointRadius: 2,
        pointHoverRadius: 5, tension: 0.2, order: 0 },
      { label: 'First attempt', data: data.first, showLine: false,
        pointRadius: 3, pointHoverRadius: 5, pointBorderWidth: 0,
        pointBackgroundColor: token('chart-3'), order: 1 },
    ],
  },
  options: {
    interaction: { mode: 'index', intersect: false },
    scales: {
      x: {
        grid: { display: false },
        ticks: {
          maxTicksLimit: 8, maxRotation: 0,
          callback(value) {
            return new Date(`${this.getLabelForValue(value)}T00:00:00`)
              .toLocaleDateString('en-GB', { day: 'numeric', month: 'short' });
          },
        },
      },
      y: { min: data.floor, max: data.ceiling,
           ticks: { stepSize: 5, callback: tick } },
    },
    plugins: {
      tooltip: {
        callbacks: {
          title: (items) => day(items[0].label),
          label: (item) => `${item.dataset.label} ${seconds(item.parsed.y)}`,
        },
      },
    },
  },
  plugins: [zoneBands(data.edges)],
}));

// The attempts of a day in order, each bar of its zone, the best one
// outlined.
// data: {labels, times: [s], zones: [0-3 | null], best, edges, ceiling}
register('daily-attempts', (data) => ({
  type: 'bar',
  data: {
    labels: data.labels,
    datasets: [{
      data: data.times,
      backgroundColor: data.zones.map((zone) => token(
        zone === null ? 'zone-dnf' : ZONE_ROLES[zone],
      )),
      borderColor: token('text'),
      borderWidth: data.times.map((_, index) => (index === data.best ? 2 : 0)),
    }],
  },
  options: {
    datasets: {
      bar: { borderRadius: 0, categoryPercentage: 0.8, barPercentage: 0.8 },
    },
    scales: {
      x: { grid: { display: false } },
      y: { min: 0, max: data.ceiling,
           ticks: { stepSize: 10, callback: tick } },
    },
    plugins: {
      tooltip: {
        callbacks: {
          title: (items) => `Attempt ${items[0].label}`,
          label: (item) => seconds(item.parsed.y),
        },
      },
    },
  },
  plugins: [zoneBands(data.edges)],
}));

// The time of each step, attempt by attempt, stacked into the solve.
// data: {labels, steps: [{label, data: [s | null]}]}
const STEP_ROLES = ['chart-3', 'chart-4', 'chart-5', 'chart-1'];
register('daily-steps', (data) => ({
  type: 'bar',
  data: {
    labels: data.labels,
    datasets: data.steps.map((step, index) => ({
      label: step.label,
      data: step.data,
      backgroundColor: token(STEP_ROLES[index % STEP_ROLES.length]),
    })),
  },
  options: {
    interaction: { mode: 'index', intersect: false },
    datasets: {
      bar: { borderRadius: 0, categoryPercentage: 0.7, barPercentage: 0.9 },
    },
    scales: {
      x: { stacked: true, grid: { display: false } },
      y: { stacked: true, beginAtZero: true, ticks: { callback: tick } },
    },
    plugins: {
      tooltip: {
        callbacks: {
          title: (items) => `Attempt ${items[0].label}`,
          label: (item) =>
            `${item.dataset.label} ${item.parsed.y.toFixed(2)} s`,
        },
      },
    },
  },
}));

// Dashed horizontal levels, labelled at their right end.
function levels(items) {
  return {
    id: 'levels',
    afterDatasetsDraw(chart) {
      const { ctx, chartArea, scales } = chart;
      ctx.save();
      ctx.strokeStyle = token('chart-marker');
      ctx.fillStyle = token('chart-marker');
      ctx.setLineDash([4, 4]);
      ctx.textAlign = 'right';
      ctx.font = `600 ${window.Chart.defaults.font.size}px ${fontFamily()}`;
      // The labels alternate above and under their line: close levels
      // would otherwise print over each other.
      const size = window.Chart.defaults.font.size;
      items.filter((item) => item.value).forEach((item, index) => {
        const y = scales.y.getPixelForValue(item.value);
        ctx.beginPath();
        ctx.moveTo(chartArea.left, y);
        ctx.lineTo(chartArea.right, y);
        ctx.stroke();
        ctx.fillText(item.label, chartArea.right, index % 2
          ? y + size + 3 : y - 5);
      });
      ctx.restore();
    },
  };
}

// The attempts of a trained case in order, their rolling Ao5 and Ao12,
// the best single and the best Ao12 as levels. Undated: x counts
// attempts.
// data: {labels, times: [s], ao5: [s|null], ao12: [s|null], best, peak}
register('training-attempts', (data) => ({
  type: 'line',
  data: {
    labels: data.labels,
    datasets: [
      { label: 'Ao5', data: data.ao5, borderColor: token('chart-1'),
        borderWidth: 2, pointRadius: 0, tension: 0.25 },
      { label: 'Ao12', data: data.ao12, borderColor: token('chart-3'),
        borderWidth: 2, pointRadius: 0, tension: 0.25 },
      { label: 'Attempt', data: data.times, showLine: false,
        pointRadius: 2.5, pointBackgroundColor: token('chart-dot'),
        pointBorderWidth: 0 },
    ],
  },
  options: {
    interaction: { mode: 'index', intersect: false },
    layout: { padding: { top: 18 } },
    scales: {
      x: { grid: { display: false }, ticks: { maxTicksLimit: 8 },
           title: { display: true, text: 'attempt' } },
      y: { beginAtZero: true, ticks: { maxTicksLimit: 5, callback: seconds } },
    },
    plugins: {
      tooltip: {
        filter: (item) => item.parsed.y != null,
        callbacks: {
          title: (items) => `Attempt #${items[0].label}`,
          label: (item) => `${item.dataset.label} ${seconds(item.parsed.y)}`,
        },
      },
    },
  },
  plugins: [levels([
    { value: data.best, label: `BEST ${seconds(data.best)}` },
    { value: data.peak, label: `BEST AO12 ${seconds(data.peak)}` },
  ])],
}));

// The recall probability of a case since its last review: FSRS counts
// whole days, hence the steps. The dot is now, the marker the due date.
// data: {points: [{x, y}], today, due, retention}
register('training-forgetting', (data) => ({
  type: 'line',
  data: {
    datasets: [
      { label: 'Recall', data: data.points, borderColor: token('chart-1'),
        borderWidth: 2, pointRadius: 0, pointHitRadius: 8, stepped: 'after' },
      { label: 'Now', data: [{ x: data.today, y: data.retention }],
        showLine: false, pointRadius: 5, pointHoverRadius: 7,
        pointBackgroundColor: token('text'), pointBorderWidth: 0 },
    ],
  },
  options: {
    interaction: { mode: 'nearest', intersect: false },
    scales: {
      x: { type: 'linear', min: 0, grid: { display: false },
           title: { display: true, text: 'days since the last review' } },
      y: { min: 0, max: 100, ticks: { callback: (value) => `${value}%` } },
    },
    plugins: {
      tooltip: {
        callbacks: {
          title: (items) => `Day ${items[0].parsed.x.toFixed(1)}`,
          label: (item) =>
            `${item.dataset.label} ${item.parsed.y.toFixed(0)}%`,
        },
      },
    },
  },
  plugins: [markerLines([{ x: data.due, label: 'DUE' }])],
}));

// The reviews to come day by day, one stacked series per step, the
// overdue ones first. Each step keeps the colour role the view gave it,
// whatever the others do.
// data: {labels, series: [{label, role, data}]}
register('training-forecast', (data) => ({
  type: 'bar',
  data: {
    labels: data.labels,
    datasets: data.series.map((series) => ({
      label: series.label,
      data: series.data,
      backgroundColor: token(series.role),
    })),
  },
  options: {
    interaction: { mode: 'index', intersect: false },
    datasets: {
      bar: { borderRadius: 0, categoryPercentage: 0.7, barPercentage: 0.9 },
    },
    scales: {
      x: { stacked: true, grid: { display: false } },
      y: { stacked: true, beginAtZero: true, ticks: { precision: 0 } },
    },
    plugins: {
      tooltip: {
        filter: (item) => item.parsed.y > 0,
        callbacks: {
          label: (item) => `${item.dataset.label} ${item.parsed.y}`,
        },
      },
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
