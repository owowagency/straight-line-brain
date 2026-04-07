/* === Digitaal Brein Dashboard — App Core === */

const TYPE_LABELS = {
  bedrijfsprofiel: 'Bedrijfsprofiel',
  propositie: 'Propositie',
  icp: 'Klantprofielen (ICP)',
  dienst: 'Diensten',
  tone_of_voice: 'Schrijfstijl',
  werkwijze: 'Werkwijze',
  brand: 'Merk',
  synthese: 'Synthese',
  inzicht: 'Inzichten',
  overig: 'Overig',
};

const TYPE_COLORS = {
  bedrijfsprofiel: '#6366f1',
  propositie: '#3b82f6',
  icp: '#14b8a6',
  dienst: '#22c55e',
  tone_of_voice: '#f59e0b',
  werkwijze: '#f97316',
  brand: '#ec4899',
  synthese: '#a855f7',
  inzicht: '#06b6d4',
  overig: '#64748b',
};

/* === API Client === */
const API = {
  getHeaders() {
    const headers = { 'Content-Type': 'application/json' };
    const key = document.getElementById('api-key-input')?.value?.trim();
    if (key) headers['X-API-Key'] = key;
    return headers;
  },

  async get(path) {
    const res = await fetch(path, { headers: this.getHeaders() });
    if (!res.ok) throw new Error(`API ${res.status}: ${res.statusText}`);
    return res.json();
  },

  async post(path, body = {}) {
    const res = await fetch(path, {
      method: 'POST',
      headers: this.getHeaders(),
      body: JSON.stringify(body),
    });
    if (!res.ok) throw new Error(`API ${res.status}: ${res.statusText}`);
    return res.json();
  },
};

/* === Tab Routing === */
function switchView(viewName) {
  document.querySelectorAll('.view').forEach(v => v.hidden = true);
  document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));

  const target = document.getElementById(`${viewName}-view`);
  const btn = document.querySelector(`.tab-btn[data-view="${viewName}"]`);
  if (target) target.hidden = false;
  if (btn) btn.classList.add('active');

  location.hash = viewName;

  if (viewName === 'live') {
    loadLiveData();
  }
}

document.querySelectorAll('.tab-btn').forEach(btn => {
  btn.addEventListener('click', () => switchView(btn.dataset.view));
});

// Init from hash
const initView = location.hash === '#live' ? 'live' : 'framework';
switchView(initView);

// Refresh button
document.getElementById('refresh-btn')?.addEventListener('click', () => loadLiveData());
document.getElementById('retry-btn')?.addEventListener('click', () => loadLiveData());

/* === Utility === */
function formatDate(dateStr) {
  const d = new Date(dateStr);
  const now = new Date();
  const diff = now - d;
  if (diff < 3600000) return `${Math.floor(diff / 60000)}m geleden`;
  if (diff < 86400000) return `${Math.floor(diff / 3600000)}u geleden`;
  if (diff < 604800000) return `${Math.floor(diff / 86400000)}d geleden`;
  return d.toLocaleDateString('nl-NL', { day: 'numeric', month: 'short' });
}
