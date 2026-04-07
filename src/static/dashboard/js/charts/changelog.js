/* === Enhanced Changelog Timeline with Filters === */

let changelogFiltersInitialized = false;

function initChangelogFilters() {
  if (changelogFiltersInitialized) return;
  changelogFiltersInitialized = true;

  // Populate type filter
  const typeSelect = document.getElementById('cl-filter-type');
  if (typeSelect && typeSelect.options.length <= 1) {
    Object.entries(TYPE_LABELS).forEach(([key, label]) => {
      const opt = document.createElement('option');
      opt.value = key;
      opt.textContent = label;
      typeSelect.appendChild(opt);
    });
  }

  // Attach filter listeners
  document.getElementById('cl-filter-type')?.addEventListener('change', reloadChangelog);
  document.getElementById('cl-filter-period')?.addEventListener('change', reloadChangelog);
}

async function reloadChangelog() {
  const timeline = document.getElementById('changelog-timeline');
  if (!timeline) return;

  const typeFilter = document.getElementById('cl-filter-type')?.value || '';
  const periodFilter = document.getElementById('cl-filter-period')?.value || '';

  // Build query params
  const params = new URLSearchParams({ limit: '50' });
  if (typeFilter) params.set('entry_type', typeFilter);
  if (periodFilter) {
    const since = new Date(Date.now() - parseInt(periodFilter) * 86400000);
    params.set('since', since.toISOString().split('T')[0]);
  }

  timeline.innerHTML = '<div class="empty-state"><div class="loading-spinner"></div></div>';

  try {
    const data = await API.get(`/api/v1/brain/changelog?${params}`);
    renderChangelog(data);
  } catch (err) {
    timeline.innerHTML = `<div class="empty-state">Kon changelog niet laden: ${err.message}</div>`;
  }
}

function renderChangelog(changelog) {
  const timeline = document.getElementById('changelog-timeline');
  if (!timeline) return;

  const items = changelog.items || [];
  if (items.length === 0) {
    timeline.innerHTML = '<div class="empty-state">Geen wijzigingen gevonden</div>';
    return;
  }

  timeline.innerHTML = '';
  items.slice(0, 50).forEach(item => {
    const action = item.action || 'other';
    let dotClass = 'other';
    if (action.includes('create') || action === 'publish') dotClass = 'create';
    else if (action.includes('update')) dotClass = 'update';
    else if (action.includes('delete')) dotClass = 'delete';
    else if (action.includes('synthesis')) dotClass = 'synthesis';
    else if (action === 'approved') dotClass = 'create';
    else if (action === 'rejected') dotClass = 'delete';

    const el = document.createElement('div');
    el.className = 'changelog-item';
    el.innerHTML = `
      <div class="cl-dot ${dotClass}"></div>
      <div class="cl-content">
        <div class="cl-title">${item.entry_title || 'Onbekend'}</div>
        <div class="cl-meta">
          <span class="cl-action ${dotClass}">${action}</span>
          <span>${TYPE_LABELS[item.entry_type] || item.entry_type || ''}</span>
          <span>${item.triggered_by || ''}</span>
          <span>${formatDate(item.created_at)}</span>
        </div>
        ${item.change_summary ? `<div class="cl-summary">${item.change_summary}</div>` : ''}
      </div>
    `;
    timeline.appendChild(el);
  });
}
