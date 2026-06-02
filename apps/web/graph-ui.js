/** Wiki graph visualization (depends on app-shared.js). */
function refreshGraphIfActive() {
  const graphView = document.getElementById("view-graph");
  if (graphView && graphView.classList.contains("active")) {
    loadWikiGraph();
  }
}

function startGraphPolling() {
  if (graphTimer) clearInterval(graphTimer);
  graphTimer = setInterval(refreshGraphIfActive, 60000);
}

function setGraphView(view) {
  currentGraphView = view;
  try {
    localStorage.setItem(GRAPH_VIEW_STORAGE_KEY, view);
  } catch (_) {
    // ignore storage access errors
  }
  graphViewTopBtn.classList.toggle("active", view === "top");
  graphViewOrphanBtn.classList.toggle("active", view === "orphan");
  graphViewHubBtn.classList.toggle("active", view === "hub");
  renderGraphList();
}

function stopGraphAnimation() {
  if (graphAnimId) {
    cancelAnimationFrame(graphAnimId);
    graphAnimId = null;
  }
}

function matchesGraphFilter(node, degreeMap) {
  const key = graphFilterKeyword.trim().toLowerCase();
  const okKeyword = !key || String(node.id || "").toLowerCase().includes(key);
  const degree = degreeMap.get(node.id) || 0;
  return okKeyword && degree >= graphFilterMinDegree;
}

async function openWikiNode(path) {
  const data = await api(`/api/wiki-content?path=${encodeURIComponent(path)}`);
  docMeta.textContent = `wiki / ${data.path} (markdown)`;
  const breadcrumb = document.getElementById("docBreadcrumb");
  if (breadcrumb) breadcrumb.textContent = `wiki / ${data.path}`;
  if (typeof renderWikiMarkdown === "function") {
    renderWikiMarkdown(data.content || "", data.path);
  } else {
    docContent.innerHTML = renderSimpleMarkdown(data.content || "");
  }
  window.MindSyncWikiEditor?.setWikiContext?.(data.path);
  if (typeof switchView === "function") switchView("library");
  docNav.classList.add("hidden");
  matchCount.textContent = "0 / 0";
  currentMatchIndex = -1;
}

async function loadWikiGraph() {
  try {
    const g = await api("/api/wiki-graph");
    currentGraphData = g;
    graphSummary.textContent = `节点: ${g.node_count} | 边: ${g.edge_count}`;
    graphMeta.textContent = `孤儿页: ${g.orphans?.length || 0} | Hub页: ${g.hubs?.length || 0}`;
    renderGraph(g);
    renderGraphList();
  } catch (e) {
    currentGraphData = null;
    stopGraphAnimation();
    graphSummary.textContent = "节点: -- | 边: --";
    graphMeta.textContent = `图谱加载失败: ${e.message}`;
    graphCanvas.innerHTML = "";
    graphUnifiedList.innerHTML = "";
  }
}

function renderGraphList() {
  const g = currentGraphData;
  graphUnifiedList.innerHTML = "";
  const key = graphFilterKeyword.trim().toLowerCase();
  const byKeyword = (path) => !key || String(path || "").toLowerCase().includes(key);
  if (!g) {
    graphListTitle.textContent = "关键节点";
    return;
  }
  if (currentGraphView === "orphan") {
    const list = (g.orphans || []).filter(byKeyword);
    graphListTitle.textContent = `孤儿页 (${list.length})`;
    if (!list.length) {
      const li = document.createElement("li");
      li.textContent = "暂无孤儿页";
      graphUnifiedList.appendChild(li);
      return;
    }
    for (const path of list) {
      const li = document.createElement("li");
      li.innerHTML = `<span>${path}</span><button class="open-node-btn">打开</button>`;
      li.querySelector("button").onclick = async () => {
        try {
          await openWikiNode(path);
        } catch (e) {
          setStatus(`打开孤儿页失败: ${e.message}`);
        }
      };
      graphUnifiedList.appendChild(li);
    }
    return;
  }
  if (currentGraphView === "hub") {
    const list = (g.hubs || []).filter(byKeyword);
    graphListTitle.textContent = `Hub页 (${list.length})`;
    if (!list.length) {
      const li = document.createElement("li");
      li.textContent = "暂无Hub页";
      graphUnifiedList.appendChild(li);
      return;
    }
    for (const path of list) {
      const li = document.createElement("li");
      li.innerHTML = `<span>${path}</span><button class="open-node-btn">打开</button>`;
      li.querySelector("button").onclick = async () => {
        try {
          await openWikiNode(path);
        } catch (e) {
          setStatus(`打开Hub页失败: ${e.message}`);
        }
      };
      graphUnifiedList.appendChild(li);
    }
    return;
  }

  graphListTitle.textContent = "关键节点";
  const nodes = [...(g.nodes || [])]
    .filter((n) => {
      const degree = (n.in_degree || 0) + (n.out_degree || 0);
      return byKeyword(n.id) && degree >= graphFilterMinDegree;
    })
    .sort((a, b) => b.in_degree + b.out_degree - (a.in_degree + a.out_degree))
    .slice(0, 8);
  if (!nodes.length) {
    const li = document.createElement("li");
    li.textContent = "暂无关键节点";
    graphUnifiedList.appendChild(li);
    return;
  }
  for (const n of nodes) {
    const li = document.createElement("li");
    li.innerHTML = `<span>${n.id} (in:${n.in_degree}, out:${n.out_degree})</span><button class="open-node-btn">打开</button>`;
    li.querySelector("button").onclick = async () => {
      try {
        await openWikiNode(n.id);
      } catch (e) {
        setStatus(`打开节点失败: ${e.message}`);
      }
    };
    graphUnifiedList.appendChild(li);
  }
}

function renderGraph(g) {
  stopGraphAnimation();
  const allNodes = (g.nodes || []).slice(0, 90);
  const allNodeIds = new Set(allNodes.map((n) => n.id));
  const allEdges = (g.edges || [])
    .filter((e) => allNodeIds.has(e.source) && allNodeIds.has(e.target))
    .slice(0, 220);

  const degreeMap = new Map();
  for (const n of allNodes) degreeMap.set(n.id, 0);
  for (const e of allEdges) {
    degreeMap.set(e.source, (degreeMap.get(e.source) || 0) + 1);
    degreeMap.set(e.target, (degreeMap.get(e.target) || 0) + 1);
  }

  const filteredNodes = allNodes.filter((n) => matchesGraphFilter(n, degreeMap));
  const filteredNodeIds = new Set(filteredNodes.map((n) => n.id));
  const filteredEdges = allEdges.filter((e) => filteredNodeIds.has(e.source) && filteredNodeIds.has(e.target));

  const canvas = document.createElement("canvas");
  canvas.className = "graph-canvas-el";
  canvas.width = Math.max(graphCanvas.clientWidth || 900, 320);
  canvas.height = 260;
  graphCanvas.innerHTML = "";
  graphCanvas.appendChild(canvas);
  const ctx = canvas.getContext("2d");
  if (!ctx) return;

  const nodeMap = new Map();
  const nodes = filteredNodes.map((n) => {
    const item = {
      id: n.id,
      in_degree: n.in_degree || 0,
      out_degree: n.out_degree || 0,
      x: Math.random() * canvas.width,
      y: Math.random() * canvas.height,
      vx: 0,
      vy: 0,
      r: 6,
      fixed: false,
    };
    nodeMap.set(item.id, item);
    return item;
  });
  const edges = filteredEdges
    .map((e) => ({ source: nodeMap.get(e.source), target: nodeMap.get(e.target) }))
    .filter((e) => e.source && e.target);

  graphRenderState = { nodes, edges, degreeMap };
  if (!nodes.length) {
    ctx.fillStyle = "#94a3b8";
    ctx.font = "13px Arial";
    ctx.fillText("当前过滤条件下无节点", 12, 24);
    return;
  }

  const centerX = canvas.width / 2;
  const centerY = canvas.height / 2;
  let dragged = null;
  let hovered = null;
  let panning = false;
  let mouseDownMoved = false;
  let panStartX = 0;
  let panStartY = 0;
  let panOriginX = 0;
  let panOriginY = 0;
  let dragStartX = 0;
  let dragStartY = 0;
  const view = {
    scale: 1,
    offsetX: 0,
    offsetY: 0,
  };

  function worldToCanvas(wx, wy) {
    return {
      x: wx * view.scale + view.offsetX,
      y: wy * view.scale + view.offsetY,
    };
  }

  function canvasToWorld(cx, cy) {
    return {
      x: (cx - view.offsetX) / view.scale,
      y: (cy - view.offsetY) / view.scale,
    };
  }

  function pickNode(worldX, worldY) {
    for (let i = nodes.length - 1; i >= 0; i -= 1) {
      const n = nodes[i];
      const dx = n.x - worldX;
      const dy = n.y - worldY;
      if (dx * dx + dy * dy <= (n.r + 4) * (n.r + 4)) return n;
    }
    return null;
  }

  function pointerPos(evt) {
    const rect = canvas.getBoundingClientRect();
    return {
      x: ((evt.clientX - rect.left) / rect.width) * canvas.width,
      y: ((evt.clientY - rect.top) / rect.height) * canvas.height,
    };
  }

  canvas.onmousedown = (evt) => {
    const p = pointerPos(evt);
    const world = canvasToWorld(p.x, p.y);
    dragged = pickNode(world.x, world.y);
    mouseDownMoved = false;
    dragStartX = p.x;
    dragStartY = p.y;
    if (dragged) {
      dragged.fixed = true;
      dragged.x = world.x;
      dragged.y = world.y;
      dragged.vx = 0;
      dragged.vy = 0;
      return;
    }
    panning = true;
    panStartX = p.x;
    panStartY = p.y;
    panOriginX = view.offsetX;
    panOriginY = view.offsetY;
  };

  canvas.onmousemove = (evt) => {
    const p = pointerPos(evt);
    const world = canvasToWorld(p.x, p.y);
    hovered = pickNode(world.x, world.y);
    if (Math.abs(p.x - dragStartX) + Math.abs(p.y - dragStartY) > 2) {
      mouseDownMoved = true;
    }
    if (dragged) {
      dragged.x = world.x;
      dragged.y = world.y;
      return;
    }
    if (panning) {
      view.offsetX = panOriginX + (p.x - panStartX);
      view.offsetY = panOriginY + (p.y - panStartY);
    }
  };

  canvas.onmouseup = async (evt) => {
    const p = pointerPos(evt);
    const world = canvasToWorld(p.x, p.y);
    const released = dragged;
    if (dragged) {
      dragged.fixed = false;
      dragged = null;
    }
    panning = false;
    const clicked = pickNode(world.x, world.y);
    if (clicked && clicked === released && !mouseDownMoved) {
      try {
        await openWikiNode(clicked.id);
      } catch (e) {
        setStatus(`打开图谱节点失败: ${e.message}`);
      }
    }
  };
  canvas.onmouseleave = () => {
    hovered = null;
    panning = false;
  };

  canvas.onwheel = (evt) => {
    evt.preventDefault();
    const p = pointerPos(evt);
    const before = canvasToWorld(p.x, p.y);
    const ratio = evt.deltaY < 0 ? 1.1 : 0.9;
    view.scale = Math.max(0.35, Math.min(3.2, view.scale * ratio));
    const after = worldToCanvas(before.x, before.y);
    view.offsetX += p.x - after.x;
    view.offsetY += p.y - after.y;
  };

  function tick() {
    const repulsion = 1300;
    const spring = 0.02;
    const rest = 85;
    const damping = 0.86;
    const centerPull = 0.0035;

    for (let i = 0; i < nodes.length; i += 1) {
      const a = nodes[i];
      for (let j = i + 1; j < nodes.length; j += 1) {
        const b = nodes[j];
        let dx = a.x - b.x;
        let dy = a.y - b.y;
        const d2 = dx * dx + dy * dy + 0.01;
        const f = repulsion / d2;
        const inv = 1 / Math.sqrt(d2);
        dx *= inv;
        dy *= inv;
        if (!a.fixed) {
          a.vx += dx * f;
          a.vy += dy * f;
        }
        if (!b.fixed) {
          b.vx -= dx * f;
          b.vy -= dy * f;
        }
      }
    }

    for (const e of edges) {
      const dx = e.target.x - e.source.x;
      const dy = e.target.y - e.source.y;
      const dist = Math.sqrt(dx * dx + dy * dy) + 0.001;
      const f = (dist - rest) * spring;
      const ux = dx / dist;
      const uy = dy / dist;
      if (!e.source.fixed) {
        e.source.vx += ux * f;
        e.source.vy += uy * f;
      }
      if (!e.target.fixed) {
        e.target.vx -= ux * f;
        e.target.vy -= uy * f;
      }
    }

    for (const n of nodes) {
      if (!n.fixed) {
        n.vx += (centerX - n.x) * centerPull;
        n.vy += (centerY - n.y) * centerPull;
        n.vx *= damping;
        n.vy *= damping;
        n.x += n.vx;
        n.y += n.vy;
        n.x = Math.max(8, Math.min(canvas.width - 8, n.x));
        n.y = Math.max(8, Math.min(canvas.height - 8, n.y));
      }
    }

    const neighbors = new Set();
    if (hovered) {
      neighbors.add(hovered.id);
      for (const e of edges) {
        if (e.source.id === hovered.id) neighbors.add(e.target.id);
        if (e.target.id === hovered.id) neighbors.add(e.source.id);
      }
    }

    ctx.clearRect(0, 0, canvas.width, canvas.height);
    for (const e of edges) {
      const s = worldToCanvas(e.source.x, e.source.y);
      const t = worldToCanvas(e.target.x, e.target.y);
      const active = hovered && (e.source.id === hovered.id || e.target.id === hovered.id);
      ctx.beginPath();
      ctx.strokeStyle = active ? "#60a5fa" : "#475569";
      ctx.lineWidth = active ? 1.9 : 1;
      ctx.moveTo(s.x, s.y);
      ctx.lineTo(t.x, t.y);
      ctx.stroke();
    }

    for (const n of nodes) {
      const p = worldToCanvas(n.x, n.y);
      const isHover = hovered && n.id === hovered.id;
      const isNeighbor = hovered && neighbors.has(n.id);
      ctx.beginPath();
      ctx.fillStyle = isHover ? "#f59e0b" : isNeighbor ? "#60a5fa" : "#3b82f6";
      ctx.arc(p.x, p.y, n.r * Math.max(1, Math.min(1.8, view.scale * 0.9)), 0, Math.PI * 2);
      ctx.fill();
      if (view.scale >= 0.7 || isHover) {
        const short = n.id.length > 18 ? `${n.id.slice(0, 18)}...` : n.id;
        ctx.fillStyle = isHover ? "#fde68a" : "#cbd5e1";
        ctx.font = "10px Arial";
        ctx.fillText(short, p.x + 9, p.y + 4);
      }
    }
    graphAnimId = requestAnimationFrame(tick);
  }
  tick();
}
