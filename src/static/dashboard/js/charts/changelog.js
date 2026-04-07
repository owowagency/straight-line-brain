/* === Changelog Timeline === */

function renderChangelog(changelog) {
  const timeline = document.getElementById('changelog-timeline');
  if (!timeline) return;

  const items = changelog.items || [];
  if (items.length === 0) {
    timeline.innerHTML = '<div class="empty-state">Nog geen wijzigingen geregistreerd</div>';
    return;
  }

  timeline.innerHTML = '';
  items.slice(0, 20).forEach(item => {
    const action = item.action || 'other';
    let dotClass = 'other';
    if (action.includes('create') || action === 'publish') dotClass = 'create';
    else if (action.includes('update')) dotClass = 'update';
    else if (action.includes('delete')) dotClass = 'delete';
    else if (action.includes('synthesis')) dotClass = 'synthesis';

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
        ${item.change_summary ? `<div style="font-size:0.7rem;color:#64748b;margin-top:2px">${item.change_summary}</div>` : ''}
      </div>
    `;
    timeline.appendChild(el);
  });
}
