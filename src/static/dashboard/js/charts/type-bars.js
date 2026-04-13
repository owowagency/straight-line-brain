/* === Knowledge Type Bar Chart — Chart.js === */

let typesChart = null;

function renderTypeBars(overview) {
  const canvas = document.getElementById('types-chart');
  if (!canvas || !overview.types) return;

  const types = overview.types;
  const labels = types.map(t => TYPE_LABELS[t.type] || t.type);
  const data = types.map(t => t.count);
  const colors = types.map(t => TYPE_COLORS[t.type] || css('--text-dim'));

  if (typesChart) {
    typesChart.data.labels = labels;
    typesChart.data.datasets[0].data = data;
    typesChart.data.datasets[0].backgroundColor = colors;
    typesChart.update();
    return;
  }

  typesChart = new Chart(canvas, {
    type: 'bar',
    data: {
      labels,
      datasets: [{
        data,
        backgroundColor: colors,
        borderRadius: 6,
        borderSkipped: false,
        maxBarThickness: 40,
      }],
    },
    options: {
      indexAxis: 'y',
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { display: false },
        tooltip: {
          backgroundColor: css('--bg-card'),
          borderColor: css('--border'),
          borderWidth: 1,
          titleFont: { size: 12 },
          bodyFont: { size: 11 },
          callbacks: {
            label: (ctx) => ` ${ctx.raw} entries`,
          },
        },
      },
      scales: {
        x: {
          beginAtZero: true,
          ticks: { color: css('--text-dim'), precision: 0 },
          grid: { color: css('--accent-04') },
        },
        y: {
          ticks: { color: css('--text-muted'), font: { size: 12 } },
          grid: { display: false },
        },
      },
    },
  });
}
