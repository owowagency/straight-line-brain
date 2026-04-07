/* === Embedding Map — D3.js Scatter Plot with Zoom === */

function renderEmbeddingMap(data) {
  const container = document.getElementById('embedding-container');
  if (!container) return;

  container.innerHTML = '';

  const points = data.points || [];
  if (points.length === 0) {
    container.innerHTML = '<div class="empty-state">Nog geen embeddings beschikbaar</div>';
    return;
  }

  const rect = container.getBoundingClientRect();
  const width = rect.width || 600;
  const height = rect.height || 400;
  const margin = 20;

  // Create SVG
  const svg = d3.select(container)
    .append('svg')
    .attr('width', width)
    .attr('height', height);

  // Scales — coords are normalized to [-1, 1]
  const xScale = d3.scaleLinear()
    .domain([-1.1, 1.1])
    .range([margin, width - margin]);

  const yScale = d3.scaleLinear()
    .domain([-1.1, 1.1])
    .range([height - margin, margin]);

  // Group for zoom
  const g = svg.append('g');

  // Zoom behavior
  const zoom = d3.zoom()
    .scaleExtent([0.5, 10])
    .on('zoom', (event) => g.attr('transform', event.transform));

  svg.call(zoom);

  // Draw points
  g.selectAll('circle')
    .data(points)
    .enter()
    .append('circle')
    .attr('cx', d => xScale(d.x))
    .attr('cy', d => yScale(d.y))
    .attr('r', 5)
    .attr('fill', d => TYPE_COLORS[d.type] || '#64748b')
    .attr('fill-opacity', 0.8)
    .attr('stroke', 'rgba(255,255,255,0.1)')
    .attr('stroke-width', 0.5)
    .style('cursor', 'pointer')
    .on('mouseenter', function(event, d) {
      d3.select(this).attr('r', 8).attr('fill-opacity', 1);
      showTooltip(event, d, container);
    })
    .on('mouseleave', function() {
      d3.select(this).attr('r', 5).attr('fill-opacity', 0.8);
      hideTooltip(container);
    });

  // Legend
  const legendDiv = document.createElement('div');
  legendDiv.className = 'embedding-legend';
  const typesPresent = [...new Set(points.map(p => p.type))];
  typesPresent.forEach(type => {
    const item = document.createElement('span');
    item.className = 'legend-item';
    item.innerHTML = `<span class="legend-dot" style="background:${TYPE_COLORS[type] || '#64748b'}"></span>${TYPE_LABELS[type] || type}`;
    legendDiv.appendChild(item);
  });
  container.appendChild(legendDiv);
}

function showTooltip(event, d, container) {
  let tooltip = container.querySelector('.embedding-tooltip');
  if (!tooltip) {
    tooltip = document.createElement('div');
    tooltip.className = 'embedding-tooltip';
    container.appendChild(tooltip);
  }

  tooltip.innerHTML = `
    <div class="tt-type">${TYPE_LABELS[d.type] || d.type}</div>
    <div>${d.label}</div>
  `;
  tooltip.classList.add('visible');

  const rect = container.getBoundingClientRect();
  const x = event.clientX - rect.left + 12;
  const y = event.clientY - rect.top - 10;
  tooltip.style.left = `${Math.min(x, rect.width - 200)}px`;
  tooltip.style.top = `${y}px`;
}

function hideTooltip(container) {
  const tooltip = container.querySelector('.embedding-tooltip');
  if (tooltip) tooltip.classList.remove('visible');
}
