/* === Cross-Reference Graph — D3.js Force-Directed === */

function renderCrossRefGraph(indexData) {
  const container = document.getElementById('graph-container');
  if (!container) return;

  container.innerHTML = '';

  const edges = indexData.cross_reference_graph || [];
  const categories = indexData.categories || [];

  // Build node map from categories
  const nodeMap = new Map();
  categories.forEach(cat => {
    (cat.entries || []).forEach(entry => {
      nodeMap.set(entry.id, {
        id: entry.id,
        label: entry.title,
        type: cat.type,
        related_count: entry.related_count || 0,
      });
    });
  });

  if (nodeMap.size === 0) {
    container.innerHTML = '<div class="empty-state">Nog geen cross-referenties beschikbaar</div>';
    return;
  }

  // Filter edges to only include known nodes, cap at 200 edges
  const validEdges = edges
    .filter(e => nodeMap.has(e.source) && nodeMap.has(e.target))
    .slice(0, 200);

  // Only include nodes that appear in edges (for a cleaner graph)
  const connectedIds = new Set();
  validEdges.forEach(e => { connectedIds.add(e.source); connectedIds.add(e.target); });

  // If no edges, show all nodes as standalone
  let nodes;
  if (connectedIds.size === 0) {
    nodes = Array.from(nodeMap.values()).slice(0, 50);
  } else {
    nodes = Array.from(nodeMap.values()).filter(n => connectedIds.has(n.id));
  }

  const rect = container.getBoundingClientRect();
  const width = rect.width || 600;
  const height = rect.height || 400;

  const svg = d3.select(container)
    .append('svg')
    .attr('width', width)
    .attr('height', height);

  const g = svg.append('g');

  // Zoom
  svg.call(d3.zoom()
    .scaleExtent([0.3, 5])
    .on('zoom', (event) => g.attr('transform', event.transform)));

  // Force simulation
  const simulation = d3.forceSimulation(nodes)
    .force('link', d3.forceLink(validEdges).id(d => d.id).distance(80).strength(0.3))
    .force('charge', d3.forceManyBody().strength(-120))
    .force('center', d3.forceCenter(width / 2, height / 2))
    .force('collision', d3.forceCollide().radius(20))
    .alphaDecay(0.03);

  // Edges
  const link = g.append('g')
    .selectAll('line')
    .data(validEdges)
    .enter()
    .append('line')
    .attr('stroke', 'rgba(0,220,255,0.06)')
    .attr('stroke-width', d => Math.max(1, (d.score || 0.5) * 3));

  // Nodes
  const node = g.append('g')
    .selectAll('g')
    .data(nodes)
    .enter()
    .append('g')
    .style('cursor', 'grab')
    .call(d3.drag()
      .on('start', dragStart)
      .on('drag', dragging)
      .on('end', dragEnd));

  node.append('circle')
    .attr('r', d => Math.max(5, Math.min(12, 4 + (d.related_count || 0))))
    .attr('fill', d => TYPE_COLORS[d.type] || '#6B7F99')
    .attr('fill-opacity', 0.85)
    .attr('stroke', 'rgba(0,220,255,0.15)')
    .attr('stroke-width', 1);

  // Labels for nodes with connections
  node.append('text')
    .text(d => d.label?.length > 20 ? d.label.substring(0, 18) + '...' : d.label)
    .attr('x', 14)
    .attr('y', 4)
    .attr('font-size', '9px')
    .attr('fill', '#B8C5D6')
    .attr('pointer-events', 'none');

  // Hover interactions
  node.on('mouseenter', function(event, d) {
    d3.select(this).select('circle').attr('fill-opacity', 1).attr('stroke-width', 2);
    // Highlight connected edges
    link.attr('stroke', l =>
      (l.source.id === d.id || l.target.id === d.id) ? TYPE_COLORS[d.type] || '#33E5FF' : 'rgba(0,220,255,0.03)'
    ).attr('stroke-opacity', l =>
      (l.source.id === d.id || l.target.id === d.id) ? 1 : 0.3
    );
  })
  .on('mouseleave', function() {
    d3.select(this).select('circle').attr('fill-opacity', 0.85).attr('stroke-width', 1);
    link.attr('stroke', 'rgba(0,220,255,0.06)').attr('stroke-opacity', 1);
  });

  // Tick
  simulation.on('tick', () => {
    link
      .attr('x1', d => d.source.x)
      .attr('y1', d => d.source.y)
      .attr('x2', d => d.target.x)
      .attr('y2', d => d.target.y);

    node.attr('transform', d => `translate(${d.x},${d.y})`);
  });

  // Drag functions
  function dragStart(event, d) {
    if (!event.active) simulation.alphaTarget(0.3).restart();
    d.fx = d.x;
    d.fy = d.y;
  }

  function dragging(event, d) {
    d.fx = event.x;
    d.fy = event.y;
  }

  function dragEnd(event, d) {
    if (!event.active) simulation.alphaTarget(0);
    d.fx = null;
    d.fy = null;
  }
}
