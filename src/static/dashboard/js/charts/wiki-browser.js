/* === Wiki Browser === */

let wikiFiles = null;
let wikiLoaded = false;
let currentWikiFile = null;

// Configure marked
if (typeof marked !== 'undefined') {
  marked.setOptions({ breaks: true, gfm: true });
}

async function loadWikiData(forceReload) {
  if (wikiLoaded && !forceReload) return;

  const loading = document.getElementById('wiki-loading');
  const error = document.getElementById('wiki-error');
  const layout = document.getElementById('wiki-layout');

  loading.hidden = false;
  error.hidden = true;
  layout.hidden = true;

  try {
    const data = await API.post('/api/v1/brain/wiki-export');
    wikiFiles = data.files || {};
    wikiLoaded = true;

    if (Object.keys(wikiFiles).length === 0) {
      loading.hidden = true;
      error.hidden = false;
      document.getElementById('wiki-error-message').textContent =
        'Het brein bevat nog geen content om te exporteren.';
      return;
    }

    buildWikiSidebar(wikiFiles);
    navigateToWikiFile('index.md');

    loading.hidden = true;
    layout.hidden = false;
  } catch (err) {
    loading.hidden = true;
    error.hidden = false;
    document.getElementById('wiki-error-message').textContent =
      `Kon wiki niet laden: ${err.message}`;
  }
}

function buildWikiSidebar(files) {
  const sidebar = document.getElementById('wiki-sidebar');
  if (!sidebar) return;
  sidebar.innerHTML = '';

  const filenames = Object.keys(files);

  // Special files first
  const specialFiles = ['index.md', 'changelog.md'];
  const specialGroup = document.createElement('div');
  specialGroup.className = 'wiki-tree-group';
  specialGroup.innerHTML = '<div class="wiki-tree-label">Navigatie</div>';

  specialFiles.forEach(f => {
    if (!files[f]) return;
    const item = document.createElement('div');
    item.className = 'wiki-tree-item';
    item.dataset.file = f;
    item.textContent = f === 'index.md' ? 'Inhoudsopgave' : 'Wijzigingslog';
    specialGroup.appendChild(item);
  });
  sidebar.appendChild(specialGroup);

  // Group remaining files by directory (type)
  const grouped = {};
  filenames.forEach(f => {
    if (specialFiles.includes(f)) return;
    const parts = f.split('/');
    if (parts.length >= 2) {
      const dir = parts[0];
      if (!grouped[dir]) grouped[dir] = [];
      grouped[dir].push(f);
    }
  });

  // Sort groups by TYPE_LABELS order
  const typeOrder = Object.keys(TYPE_LABELS);
  const sortedDirs = Object.keys(grouped).sort((a, b) => {
    const ai = typeOrder.indexOf(a);
    const bi = typeOrder.indexOf(b);
    return (ai === -1 ? 999 : ai) - (bi === -1 ? 999 : bi);
  });

  sortedDirs.forEach(dir => {
    const group = document.createElement('div');
    group.className = 'wiki-tree-group';
    group.innerHTML = `<div class="wiki-tree-label">${TYPE_LABELS[dir] || dir}</div>`;

    grouped[dir].sort().forEach(f => {
      // Extract display name from filename: "type/slug.md" -> "slug" -> prettify
      const slug = f.split('/').pop().replace('.md', '').replace(/-/g, ' ');
      const displayName = slug.charAt(0).toUpperCase() + slug.slice(1);

      const item = document.createElement('div');
      item.className = 'wiki-tree-item';
      item.dataset.file = f;
      item.textContent = displayName;
      item.title = displayName;
      group.appendChild(item);
    });

    sidebar.appendChild(group);
  });
}

function navigateToWikiFile(filename) {
  const content = document.getElementById('wiki-content');
  if (!content || !wikiFiles) return;

  const md = wikiFiles[filename];
  if (!md) {
    content.innerHTML = '<div class="empty-state">Bestand niet gevonden</div>';
    return;
  }

  currentWikiFile = filename;

  // Convert [[path|title]] wiki links to clickable anchors BEFORE marked parsing
  const processed = md.replace(/\[\[([^\]|]+)\|([^\]]+)\]\]/g, (match, path, title) => {
    const file = path.endsWith('.md') ? path : path + '.md';
    return `<a class="wiki-link" data-file="${file}">${title}</a>`;
  });

  // Parse markdown to HTML
  content.innerHTML = typeof marked !== 'undefined' ? marked.parse(processed) : processed;

  // Update active state in sidebar
  document.querySelectorAll('.wiki-tree-item').forEach(item => {
    item.classList.toggle('active', item.dataset.file === filename);
  });

  // Scroll content to top
  content.scrollTop = 0;
}

// Sidebar click delegation
document.getElementById('wiki-sidebar')?.addEventListener('click', (e) => {
  const item = e.target.closest('.wiki-tree-item');
  if (item?.dataset.file) navigateToWikiFile(item.dataset.file);
});

// Wiki content link delegation
document.getElementById('wiki-content')?.addEventListener('click', (e) => {
  const link = e.target.closest('.wiki-link');
  if (link) {
    e.preventDefault();
    const file = link.dataset.file;
    if (file && wikiFiles && wikiFiles[file]) {
      navigateToWikiFile(file);
    }
  }
});

// Refresh button
document.getElementById('wiki-refresh-btn')?.addEventListener('click', () => {
  wikiLoaded = false;
  loadWikiData(true);
});

// Retry button
document.getElementById('wiki-retry-btn')?.addEventListener('click', () => {
  wikiLoaded = false;
  loadWikiData(true);
});
