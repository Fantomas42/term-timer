// Charts of the training pages: Chart.js + annotation plugin, colors read
// from the design tokens of style.css so that no color lives in the
// templates.

function trainingToken(name) {
    return getComputedStyle(document.documentElement)
        .getPropertyValue(name).trim();
}

function trainingFormatSeconds(value) {
    return value === null ? 'N/A' : `${value.toFixed(2)}s`;
}

function trainingAxis(title, extra) {
    return Object.assign({
        title: {
            display: Boolean(title),
            text: title,
            color: trainingToken('--text-secondary'),
        },
        ticks: {color: trainingToken('--text-secondary')},
        grid: {color: trainingToken('--chart-grid')},
    }, extra || {});
}

// Horizontal reference line, labelled at its right end.
function trainingLevel(value, label) {
    return {
        type: 'line',
        yMin: value,
        yMax: value,
        borderColor: trainingToken('--text-secondary'),
        borderWidth: 1,
        borderDash: [4, 4],
        label: {
            display: true,
            content: label,
            position: 'end',
            color: trainingToken('--text-primary'),
            backgroundColor: trainingToken('--card-bg'),
            font: {size: 11},
        },
    };
}

// Vertical marker at a position of a numeric horizontal axis.
function trainingMarker(value, label, token) {
    return {
        type: 'line',
        xMin: value,
        xMax: value,
        borderColor: trainingToken(token),
        borderWidth: 1,
        borderDash: [4, 4],
        label: {
            display: true,
            content: label,
            position: 'start',
            color: trainingToken('--text-primary'),
            backgroundColor: trainingToken('--card-bg'),
            font: {size: 11},
        },
    };
}

// Timings of a case in attempt order, with rolling averages, the best
// single and the best Ao12 ever (the peak) as reference levels.
function trainingAttemptsChart(canvas, curve) {
    const levels = {best: trainingLevel(curve.best, 'Best')};
    if (curve.peak !== null) {
        levels.peak = trainingLevel(curve.peak, 'Best Ao12');
    }

    const series = [
        {label: 'Time', data: curve.times, token: '--chart-series-1'},
        {label: 'Ao5', data: curve.ao5, token: '--chart-series-2'},
        {label: 'Ao12', data: curve.ao12, token: '--chart-series-3'},
    ];

    return new Chart(canvas, {
        type: 'line',
        data: {
            labels: curve.labels,
            datasets: series.map((item, index) => ({
                label: item.label,
                data: item.data,
                borderColor: trainingToken(item.token),
                backgroundColor: trainingToken(item.token),
                borderWidth: index ? 2 : 0,
                showLine: index > 0,
                pointRadius: index ? 0 : 3,
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
                    labels: {color: trainingToken('--text-primary')},
                },
                tooltip: {
                    callbacks: {
                        title: (items) => `Attempt #${items[0].label}`,
                        label: (context) => `${context.dataset.label}: `
                            + trainingFormatSeconds(context.parsed.y),
                    },
                },
                annotation: {annotations: levels},
            },
            scales: {
                x: trainingAxis('Attempt (undated, in order)'),
                y: trainingAxis('Seconds', {beginAtZero: true}),
            },
        },
    });
}

// Recall probability since the last review, today and the due date
// marked on the time axis. FSRS counts whole elapsed days: steps.
function trainingForgettingChart(canvas, forgetting) {
    return new Chart(canvas, {
        type: 'line',
        data: {
            datasets: [{
                label: 'Recall probability',
                data: forgetting.points,
                borderColor: trainingToken('--chart-series-1'),
                backgroundColor: trainingToken('--chart-series-1'),
                borderWidth: 2,
                pointRadius: 0,
                pointHitRadius: 10,
                stepped: 'after',
            }, {
                label: 'Today',
                data: [{x: forgetting.today, y: forgetting.retention}],
                borderColor: trainingToken('--card-bg'),
                backgroundColor: trainingToken('--text-primary'),
                borderWidth: 2,
                pointRadius: 5,
                pointHoverRadius: 7,
                showLine: false,
            }],
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            interaction: {mode: 'nearest', intersect: false},
            plugins: {
                legend: {display: false},
                tooltip: {
                    callbacks: {
                        title: (items) => (
                            `Day ${items[0].parsed.x.toFixed(1)}`
                        ),
                        label: (context) => `${context.dataset.label}: `
                            + `${context.parsed.y.toFixed(0)}%`,
                    },
                },
                annotation: {
                    annotations: {
                        due: trainingMarker(
                            forgetting.due, 'Due', '--warning',
                        ),
                    },
                },
            },
            scales: {
                x: trainingAxis('Days since last review', {type: 'linear'}),
                y: trainingAxis('Recall %', {min: 0, max: 100}),
            },
        },
    });
}

// Tint selector of the academy step grid: the chosen tint is set on the
// root element, the stylesheet does the rest. Remembered per browser.
function trainingTintSelector(root) {
    const buttons = root.querySelectorAll('[data-tint-choice]');

    function choose(tint) {
        root.dataset.tint = tint;
        buttons.forEach((button) => {
            button.setAttribute(
                'aria-pressed', String(button.dataset.tintChoice === tint),
            );
        });
    }

    try {
        const saved = localStorage.getItem('academy-tint');
        if (saved && root.querySelector(`[data-tint-choice="${saved}"]`)) {
            choose(saved);
        }
    } catch (error) {
        // Storage unavailable: keep the default tint.
    }

    buttons.forEach((button) => {
        button.addEventListener('click', () => {
            choose(button.dataset.tintChoice);
            try {
                localStorage.setItem('academy-tint', button.dataset.tintChoice);
            } catch (error) {
                // Storage unavailable: the choice lasts for the page only.
            }
        });
    });
}

// Reviews to come, one stacked bar per day, one color per step.
function trainingForecastChart(canvas, labels, series) {
    return new Chart(canvas, {
        type: 'bar',
        data: {
            labels: labels,
            datasets: series.map((item) => ({
                label: item.label,
                data: item.data,
                backgroundColor: trainingToken(item.token),
                borderColor: trainingToken('--card-bg'),
                borderWidth: 2,
                borderRadius: 4,
                maxBarThickness: 48,
            })),
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            interaction: {mode: 'index', intersect: false},
            plugins: {
                legend: {
                    display: series.length > 1,
                    labels: {color: trainingToken('--text-primary')},
                },
            },
            scales: {
                x: trainingAxis('', {stacked: true}),
                y: trainingAxis('Reviews', {
                    stacked: true,
                    beginAtZero: true,
                    ticks: {
                        precision: 0,
                        color: trainingToken('--text-secondary'),
                    },
                }),
            },
        },
    });
}

// Flashcards of the due cases: one card at a time, its answer hidden
// until revealed. Space reveals, arrows move. Nothing is sent anywhere.
function trainingFlashcards(root) {
    const cards = Array.from(root.querySelectorAll('.flashcard'));
    const progress = root.querySelector('.flashcard-progress');
    let current = 0;

    function show(index) {
        current = Math.max(0, Math.min(cards.length - 1, index));
        cards.forEach((card, position) => {
            card.hidden = position !== current;
        });
        progress.textContent = `${current + 1} / ${cards.length}`;
    }

    function reveal() {
        cards[current].querySelector('.flashcard-answer').hidden = false;
    }

    const actions = {
        previous: () => show(current - 1),
        next: () => show(current + 1),
        reveal: reveal,
    };

    root.querySelectorAll('[data-flashcard]').forEach((button) => {
        button.addEventListener('click', actions[button.dataset.flashcard]);
    });

    document.addEventListener('keydown', (event) => {
        if (event.key === ' ') {
            event.preventDefault();
            reveal();
        } else if (event.key === 'ArrowRight') {
            actions.next();
        } else if (event.key === 'ArrowLeft') {
            actions.previous();
        }
    });
}
