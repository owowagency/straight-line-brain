/* === Framework View — Knowledge Type Cards === */

const TYPE_DESCRIPTIONS = {
  bedrijfsprofiel: 'Kernidentiteit, missie en visie van de organisatie',
  propositie: 'Waardepropositie en onderscheidend vermogen',
  icp: 'Ideal Customer Profiles per segment',
  dienst: 'Dienstenaanbod met specificaties',
  tone_of_voice: 'Schrijfstijl en communicatierichtlijnen',
  werkwijze: 'Methodologie en procesaanpak',
  brand: 'Merkidentiteit en visuele richtlijnen',
  synthese: 'Auto-gegenereerde samenvattingen en vergelijkingen',
  inzicht: 'Vastgelegde kennis uit vragen en analyses',
  overig: 'Overige kennisbronnen en documenten',
};

const TYPE_ICONS = {
  bedrijfsprofiel: '<svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M3 21h18M3 7v14M21 7v14M7 11h2M7 15h2M15 11h2M15 15h2M9 21v-4h6v4M12 3l9 4H3l9-4z"/></svg>',
  propositie: '<svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M12 2l3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77l-6.18 3.25L7 14.14 2 9.27l6.91-1.01L12 2z"/></svg>',
  icp: '<svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M17 21v-2a4 4 0 00-4-4H5a4 4 0 00-4 4v2M9 11a4 4 0 100-8 4 4 0 000 8zM23 21v-2a4 4 0 00-3-3.87M16 3.13a4 4 0 010 7.75"/></svg>',
  dienst: '<svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="1.5"><rect x="2" y="3" width="20" height="14" rx="2"/><path d="M8 21h8M12 17v4"/></svg>',
  tone_of_voice: '<svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M21 15a2 2 0 01-2 2H7l-4 4V5a2 2 0 012-2h14a2 2 0 012 2z"/></svg>',
  werkwijze: '<svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M14.7 6.3a1 1 0 000 1.4l1.6 1.6a1 1 0 001.4 0l3.77-3.77a6 6 0 01-7.94 7.94l-6.91 6.91a2.12 2.12 0 01-3-3l6.91-6.91a6 6 0 017.94-7.94l-3.76 3.76z"/></svg>',
  brand: '<svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M20.59 13.41l-7.17 7.17a2 2 0 01-2.83 0L2 12V2h10l8.59 8.59a2 2 0 010 2.82zM7 7h.01"/></svg>',
  synthese: '<svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M12 3L2 9l10 6 10-6-10-6z"/><path d="M2 17l10 6 10-6M2 13l10 6 10-6" opacity="0.5"/></svg>',
  inzicht: '<svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="1.5"><circle cx="12" cy="12" r="10"/><path d="M9.09 9a3 3 0 015.83 1c0 2-3 3-3 3M12 17h.01"/></svg>',
  overig: '<svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/></svg>',
};

(function renderTypeCards() {
  const grid = document.getElementById('types-grid');
  if (!grid) return;

  const types = Object.keys(TYPE_LABELS);
  types.forEach(type => {
    const color = TYPE_COLORS[type] || '#6B7F99';
    const card = document.createElement('div');
    card.className = 'type-card';
    card.style.setProperty('--card-color', color);
    card.innerHTML = `
      <div class="type-icon" style="background:${color}20; color:${color}">
        ${TYPE_ICONS[type] || ''}
      </div>
      <h4>${TYPE_LABELS[type]}</h4>
      <p>${TYPE_DESCRIPTIONS[type] || ''}</p>
    `;
    grid.appendChild(card);
  });
})();
