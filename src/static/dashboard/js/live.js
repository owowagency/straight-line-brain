/* === Live Brain View — Data Loading & Panel Orchestration === */

let liveDataLoaded = false;
let liveData = {};

async function loadLiveData() {
  const loading = document.getElementById('live-loading');
  const error = document.getElementById('live-error');
  const grid = document.getElementById('dashboard-grid');
  const refreshBtn = document.getElementById('refresh-btn');

  loading.hidden = false;
  error.hidden = true;
  grid.style.opacity = '0.3';
  refreshBtn?.classList.add('spinning');

  try {
    const [overview, lint, index, changelog] = await Promise.all([
      API.get('/api/v1/stats/overview'),
      API.post('/api/v1/brain/lint'),
      API.get('/api/v1/brain/index'),
      API.get('/api/v1/brain/changelog'),
    ]);

    liveData = { overview, lint, index, changelog };
    liveDataLoaded = true;

    // Render all panels
    renderHealthGauge(lint);
    renderStats(overview, lint);
    renderTypeBars(overview);
    renderCoverage(lint);
    renderIssues(lint);
    renderChangelog(changelog);
    renderCrossRefGraph(index);

    // Embeddings loaded separately (can be slow)
    loadEmbeddings('entries');

    loading.hidden = true;
    grid.style.opacity = '1';
  } catch (err) {
    loading.hidden = true;
    grid.style.opacity = '1';
    error.hidden = false;
    document.getElementById('error-message').textContent =
      `Kon geen verbinding maken met de API: ${err.message}`;
  } finally {
    refreshBtn?.classList.remove('spinning');
  }
}

async function loadEmbeddings(kind) {
  const container = document.getElementById('embedding-container');
  container.innerHTML = '<div class="empty-state"><div class="loading-spinner"></div><p>Embeddings berekenen...</p></div>';

  try {
    const data = await API.get(`/api/v1/stats/embeddings?kind=${kind}`);
    renderEmbeddingMap(data);
  } catch (err) {
    container.innerHTML = `<div class="empty-state">Kon embeddings niet laden: ${err.message}</div>`;
  }
}

// Embedding kind selector
document.getElementById('embedding-kind')?.addEventListener('change', (e) => {
  loadEmbeddings(e.target.value);
});

/* === Stats Panel === */
function renderStats(overview, lint) {
  document.getElementById('stat-entries').textContent = overview.total_entries || 0;
  document.getElementById('stat-chunks').textContent = overview.total_chunks || 0;
  document.getElementById('stat-types').textContent = overview.types?.length || 0;
  document.getElementById('stat-issues').textContent = lint.total_issues || 0;
}

/* === Coverage Panel === */
function renderCoverage(lint) {
  const grid = document.getElementById('coverage-grid');
  if (!grid || !lint.coverage) return;

  grid.innerHTML = '';
  const entries = Object.entries(lint.coverage);
  entries.forEach(([key, info]) => {
    const ok = info.ok !== false && info.count > 0;
    const item = document.createElement('div');
    item.className = 'coverage-item';
    item.innerHTML = `
      <span class="coverage-dot ${ok ? 'ok' : 'missing'}"></span>
      <span>${info.label || TYPE_LABELS[key] || key}</span>
      <span class="coverage-count">${info.count || 0}</span>
    `;
    grid.appendChild(item);
  });
}

/* === Issues Panel === */
function renderIssues(lint) {
  const list = document.getElementById('issues-list');
  if (!list) return;

  const issues = lint.issues || [];
  if (issues.length === 0) {
    list.innerHTML = '<div class="no-issues">Geen aandachtspunten gevonden</div>';
    return;
  }

  list.innerHTML = '';
  issues.slice(0, 15).forEach(issue => {
    const severity = issue.severity || 'info';
    const item = document.createElement('div');
    item.className = 'issue-item';
    item.innerHTML = `
      <span class="issue-badge ${severity}">${severity}</span>
      <span class="issue-text">${issue.message || ''}</span>
    `;
    list.appendChild(item);
  });
}
