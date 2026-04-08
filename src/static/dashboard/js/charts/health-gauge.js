/* === Health Gauge — Chart.js Doughnut === */

let healthChart = null;

function renderHealthGauge(lint) {
  const canvas = document.getElementById('health-gauge');
  const scoreEl = document.getElementById('gauge-score');
  if (!canvas) return;

  const score = lint.score ?? 0;
  scoreEl.textContent = Math.round(score);

  // Color based on score
  let color;
  if (score >= 80) color = getComputedStyle(document.documentElement).getPropertyValue('--green').trim();
  else if (score >= 50) color = getComputedStyle(document.documentElement).getPropertyValue('--amber').trim();
  else color = getComputedStyle(document.documentElement).getPropertyValue('--red').trim();

  scoreEl.style.color = color;

  if (healthChart) {
    healthChart.data.datasets[0].data = [score, 100 - score];
    healthChart.data.datasets[0].backgroundColor = [color, 'rgba(0,220,255,0.04)'];
    healthChart.update();
    return;
  }

  healthChart = new Chart(canvas, {
    type: 'doughnut',
    data: {
      datasets: [{
        data: [score, 100 - score],
        backgroundColor: [color, 'rgba(0,220,255,0.04)'],
        borderWidth: 0,
      }],
    },
    options: {
      cutout: '78%',
      rotation: -135,
      circumference: 270,
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { display: false },
        tooltip: { enabled: false },
      },
    },
  });
}
