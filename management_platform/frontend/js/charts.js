/**
 * Highway Safety Analytics Charts (Chart.js Integration)
 */

let hourlyChartInstance = null;
let typeChartInstance = null;

function initAnalyticsCharts() {
    const hourlyCtx = document.getElementById('hourlyChart');
    const typeCtx = document.getElementById('typeChart');
    if (!hourlyCtx || !typeCtx) return;

    // Hourly Distribution Chart
    hourlyChartInstance = new Chart(hourlyCtx, {
        type: 'bar',
        data: {
            labels: ["00:00", "04:00", "08:00", "12:00", "16:00", "20:00"],
            datasets: [{
                label: 'Obstruction Incidents',
                data: [0, 0, 2, 4, 1, 0],
                backgroundColor: 'rgba(59, 130, 246, 0.65)',
                borderColor: '#3b82f6',
                borderWidth: 1,
                borderRadius: 4
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { display: false }
            },
            scales: {
                y: {
                    beginAtZero: true,
                    grid: { color: '#243044' },
                    ticks: { color: '#94a3b8' }
                },
                x: {
                    grid: { display: false },
                    ticks: { color: '#94a3b8' }
                }
            }
        }
    });

    // Hazard Type Doughnut Chart
    typeChartInstance = new Chart(typeCtx, {
        type: 'doughnut',
        data: {
            labels: ['Stalled Car', 'Debris', 'Slow Vehicle'],
            datasets: [{
                data: [70, 15, 15],
                backgroundColor: ['#ef4444', '#f59e0b', '#3b82f6'],
                borderWidth: 0
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    position: 'right',
                    labels: { color: '#cbd5e1', font: { size: 11 } }
                }
            }
        }
    });
}

function updateChartsData(analyticsData) {
    if (!analyticsData || !analyticsData.charts) return;
    const charts = analyticsData.charts;

    if (hourlyChartInstance && charts.hourly) {
        hourlyChartInstance.data.labels = charts.hourly.labels;
        hourlyChartInstance.data.datasets[0].data = charts.hourly.data;
        hourlyChartInstance.update('none');
    }

    if (typeChartInstance && charts.types) {
        typeChartInstance.data.labels = charts.types.labels;
        typeChartInstance.data.datasets[0].data = charts.types.data;
        typeChartInstance.update('none');
    }
}
