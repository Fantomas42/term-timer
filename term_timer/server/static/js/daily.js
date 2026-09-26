// Charts of the daily pages: Chart.js + annotation plugin, colors read from
// the design tokens of style.css so that no color lives in the templates.

function dailyToken(name) {
    return getComputedStyle(document.documentElement)
        .getPropertyValue(name).trim();
}

// Fixed zones drawn behind the times, one box between two edges.
function dailyZoneBands(edges) {
    const bands = {};

    for (let i = 0; i + 1 < edges.length; i++) {
        bands[`zone${i}`] = {
            type: 'box',
            yMin: edges[i],
            yMax: edges[i + 1],
            backgroundColor: dailyToken(`--daily-band-${i}`),
            borderWidth: 0,
            drawTime: 'beforeDatasetsDraw',
        };
    }

    return bands;
}

function dailyZoneColor(zone) {
    if (zone === null) {
        return dailyToken('--daily-zone-dnf');
    }
    return dailyToken(`--daily-zone-${zone}`);
}

function dailyFormatSeconds(value) {
    return value === null ? 'DNF' : `${value.toFixed(2)}s`;
}

function dailyAxis(title, extra) {
    return Object.assign({
        title: {
            display: Boolean(title),
            text: title,
            color: dailyToken('--text-secondary'),
        },
        ticks: {color: dailyToken('--text-secondary')},
        grid: {color: dailyToken('--chart-grid')},
    }, extra || {});
}

// Times of several days: one line per series over the fixed zones.
function dailyTimesChart(canvas, labels, series, edges, options) {
    const settings = Object.assign({compact: false}, options || {});
    const slots = ['--chart-series-1', '--chart-series-2'];

    return new Chart(canvas, {
        type: 'line',
        data: {
            labels: labels,
            datasets: series.map((item, index) => ({
                label: item.label,
                data: item.data,
                borderColor: dailyToken(slots[index]),
                backgroundColor: dailyToken(slots[index]),
                borderWidth: 2,
                pointRadius: settings.compact ? 3 : 4,
                pointHoverRadius: 6,
                pointHitRadius: 10,
                tension: 0.2,
                spanGaps: false,
            })),
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            interaction: {mode: 'index', intersect: false},
            plugins: {
                legend: {
                    display: series.length > 1,
                    labels: {color: dailyToken('--text-primary')},
                },
                tooltip: {
                    callbacks: {
                        label: (context) => `${context.dataset.label}: `
                            + dailyFormatSeconds(context.parsed.y),
                    },
                },
                annotation: {annotations: dailyZoneBands(edges)},
            },
            scales: {
                x: dailyAxis('', {display: !settings.compact}),
                y: dailyAxis(settings.compact ? '' : 'Seconds', {
                    display: !settings.compact,
                    suggestedMin: edges[0] - 2,
                    suggestedMax: edges[edges.length - 1] + 2,
                }),
            },
        },
    });
}

// Attempts of a single day: one bar per attempt, colored by its zone.
function dailyAttemptsChart(canvas, times, zones, edges) {
    return new Chart(canvas, {
        type: 'bar',
        data: {
            labels: times.map((_, index) => `#${index + 1}`),
            datasets: [{
                label: 'Time',
                data: times,
                backgroundColor: zones.map(dailyZoneColor),
                borderRadius: 4,
                maxBarThickness: 48,
            }],
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {display: false},
                tooltip: {
                    callbacks: {
                        label: (context) => dailyFormatSeconds(
                            context.parsed.y,
                        ),
                    },
                },
                annotation: {annotations: dailyZoneBands(edges)},
            },
            scales: {
                x: dailyAxis('Attempt'),
                y: dailyAxis('Seconds', {beginAtZero: true}),
            },
        },
    });
}

// Time spent on each step, stacked attempt by attempt.
function dailyStepsChart(canvas, steps) {
    const count = steps.length ? steps[0].data.length : 0;

    return new Chart(canvas, {
        type: 'bar',
        data: {
            labels: Array.from({length: count}, (_, index) => `#${index + 1}`),
            datasets: steps.map((step, index) => ({
                label: step.label,
                data: step.data,
                backgroundColor: dailyToken(`--chart-series-${index + 1}`),
                borderColor: dailyToken('--card-bg'),
                borderWidth: 2,
                maxBarThickness: 48,
            })),
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            interaction: {mode: 'index', intersect: false},
            plugins: {
                legend: {labels: {color: dailyToken('--text-primary')}},
                tooltip: {
                    callbacks: {
                        label: (context) => `${context.dataset.label}: `
                            + dailyFormatSeconds(context.parsed.y),
                    },
                },
            },
            scales: {
                x: dailyAxis('Attempt', {stacked: true}),
                y: dailyAxis('Seconds', {stacked: true, beginAtZero: true}),
            },
        },
    });
}

// Number of attempts of each day, kept on its own axis and chart.
function dailyCountChart(canvas, labels, counts) {
    return new Chart(canvas, {
        type: 'bar',
        data: {
            labels: labels,
            datasets: [{
                label: 'Attempts',
                data: counts,
                backgroundColor: dailyToken('--chart-series-1'),
                borderRadius: 4,
            }],
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {legend: {display: false}},
            scales: {
                x: dailyAxis(''),
                y: dailyAxis('Attempts', {
                    beginAtZero: true,
                    ticks: {
                        precision: 0,
                        color: dailyToken('--text-secondary'),
                    },
                }),
            },
        },
    });
}

// Copy the share card of a day, the way a Wordle result is shared.
function dailyCopyShare(button) {
    const text = document.getElementById(button.dataset.target).textContent;

    navigator.clipboard.writeText(text.trim()).then(() => {
        const label = button.innerHTML;
        button.innerHTML = '<i class="fas fa-clipboard"></i> Copied !';
        setTimeout(() => {
            button.innerHTML = label;
        }, 2000);
    });
}
