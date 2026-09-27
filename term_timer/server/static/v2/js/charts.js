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
