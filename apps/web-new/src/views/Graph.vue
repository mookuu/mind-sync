<template>
  <div class="view-pane">
    <div class="view-header">
      <h2>🕸 Wiki 图谱</h2>
      <p class="subtle">Wiki 页面之间的链接关系图（拖动节点，滚轮缩放）</p>
    </div>
    <div class="graph-meta">
      <span class="meta-item">{{ stats.nodeCount }} 节点</span>
      <span class="meta-item">{{ stats.edgeCount }} 条链接</span>
      <span v-if="stats.orphanCount" class="meta-item warn">{{ stats.orphanCount }} 孤儿页</span>
      <span v-if="stats.hubCount" class="meta-item info">{{ stats.hubCount }} 枢纽页</span>
      <span v-if="stats.brokenCount" class="meta-item danger">{{ stats.brokenCount }} 断链</span>
    </div>
    <div class="graph-canvas-wrap">
      <canvas
        ref="canvasEl"
        class="graph-canvas"
        @mousedown="onMouseDown"
        @mousemove="onMouseMove"
        @mouseup="onMouseUp"
        @mouseleave="onMouseUp"
        @wheel.prevent="onWheel"
      ></canvas>
      <div v-if="tooltip" class="graph-tooltip" :style="tooltipStyle">
        <div class="tooltip-path">{{ tooltip.id }}</div>
        <div class="tooltip-type">{{ tooltip.docType }}</div>
        <div class="tooltip-deg">↗{{ tooltip.outDeg }} ↙{{ tooltip.inDeg }}</div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted, onUnmounted } from "vue";
import api from "../api/index.js";

const canvasEl = ref(null);
const tooltip = ref(null);
const tooltipStyle = ref({});

const stats = reactive({ nodeCount: 0, edgeCount: 0, orphanCount: 0, hubCount: 0, brokenCount: 0 });

// Force simulation state
let simNodes = [];
let simEdges = [];
let simRunning = false;
let simFrameId = null;
let dragNode = null;
let dragOffset = { x: 0, y: 0 };
let mousePos = { x: 0, y: 0 };
let viewTransform = { x: 0, y: 0, scale: 1 };

const NODE_RADIUS = 8;
const REPULSION = 8000;
const ATTRACTION = 0.005;
const DAMPING = 0.9;
const CENTER_GRAVITY = 0.01;

function initSimulation(data) {
  const nodes = data.nodes || [];
  const edges = data.edges || [];

  stats.nodeCount = nodes.length;
  stats.edgeCount = edges.length;
  stats.orphanCount = (data.orphans || []).length;
  stats.hubCount = (data.hubs || []).length;
  stats.brokenCount = (data.broken_links || []).length;

  // Create simulation nodes
  simNodes = nodes.map((n, i) => ({
    id: n.id,
    docType: n.doc_type,
    inDeg: n.in_degree,
    outDeg: n.out_degree,
    isHub: n.is_hub,
    isOrphan: n.is_orphan,
    x: (Math.random() - 0.5) * 400,
    y: (Math.random() - 0.5) * 300,
    vx: 0,
    vy: 0,
    radius: n.is_hub ? 14 : NODE_RADIUS,
  }));

  const nodeMap = new Map(simNodes.map((n) => [n.id, n]));
  simEdges = edges
    .filter((e) => nodeMap.has(e.source) && nodeMap.has(e.target))
    .map((e) => ({ source: nodeMap.get(e.source), target: nodeMap.get(e.target) }));

  // Center the view
  const canvas = canvasEl.value;
  if (canvas) {
    viewTransform.x = canvas.width / 2;
    viewTransform.y = canvas.height / 2;
  }

  startSimulation();
}

function startSimulation() {
  if (simRunning) return;
  simRunning = true;
  simulateStep();
}

function stopSimulation() {
  simRunning = false;
  if (simFrameId) {
    cancelAnimationFrame(simFrameId);
    simFrameId = null;
  }
}

function simulateStep() {
  if (!simRunning) return;

  const nodes = simNodes;
  const edges = simEdges;
  const area = 600 * 500;

  // Repulsion (Barnes-Hut approximation — full pairwise for simplicity)
  for (let i = 0; i < nodes.length; i++) {
    for (let j = i + 1; j < nodes.length; j++) {
      let dx = nodes[j].x - nodes[i].x;
      let dy = nodes[j].y - nodes[i].y;
      let dist = Math.sqrt(dx * dx + dy * dy) || 1;
      let force = REPULSION / (dist * dist);
      let fx = (dx / dist) * force;
      let fy = (dy / dist) * force;
      nodes[i].vx -= fx;
      nodes[i].vy -= fy;
      nodes[j].vx += fx;
      nodes[j].vy += fy;
    }
  }

  // Attraction along edges
  for (const e of edges) {
    let dx = e.target.x - e.source.x;
    let dy = e.target.y - e.source.y;
    let dist = Math.sqrt(dx * dx + dy * dy) || 1;
    let force = dist * ATTRACTION;
    let fx = (dx / dist) * force;
    let fy = (dy / dist) * force;
    e.source.vx += fx;
    e.source.vy += fy;
    e.target.vx -= fx;
    e.target.vy -= fy;
  }

  // Center gravity
  for (const n of nodes) {
    n.vx -= n.x * CENTER_GRAVITY;
    n.vy -= n.y * CENTER_GRAVITY;
  }

  // Apply velocity + damping
  let maxVelocity = 0;
  for (const n of nodes) {
    n.vx *= DAMPING;
    n.vy *= DAMPING;
    n.x += n.vx;
    n.y += n.vy;
    let speed = Math.sqrt(n.vx * n.vx + n.vy * n.vy);
    maxVelocity = Math.max(maxVelocity, speed);
  }

  render();

  // Continue until settled
  if (maxVelocity > 0.1) {
    simFrameId = requestAnimationFrame(simulateStep);
  } else {
    simRunning = false;
    simFrameId = null;
  }
}

function render() {
  const canvas = canvasEl.value;
  if (!canvas) return;
  const ctx = canvas.getContext("2d");
  const { x: ox, y: oy, scale: s } = viewTransform;

  ctx.clearRect(0, 0, canvas.width, canvas.height);

  // Edges
  ctx.strokeStyle = "var(--border-muted, #e0e0e0)";
  ctx.lineWidth = 1;
  ctx.globalAlpha = 0.5;
  for (const e of simEdges) {
    ctx.beginPath();
    ctx.moveTo(e.source.x * s + ox, e.source.y * s + oy);
    ctx.lineTo(e.target.x * s + ox, e.target.y * s + oy);
    ctx.stroke();
  }
  ctx.globalAlpha = 1;

  // Nodes
  for (const n of simNodes) {
    const cx = n.x * s + ox;
    const cy = n.y * s + oy;
    const r = n.radius * s;

    // Glow for hubs
    if (n.isHub) {
      ctx.beginPath();
      ctx.arc(cx, cy, r + 4, 0, Math.PI * 2);
      ctx.fillStyle = "var(--accent-bg, #ebf4ff)";
      ctx.fill();
    }

    ctx.beginPath();
    ctx.arc(cx, cy, r, 0, Math.PI * 2);

    // Color by type
    if (n.docType === "summary") ctx.fillStyle = "var(--success-fg, #166534)";
    else if (n.docType === "query") ctx.fillStyle = "var(--accent-emphasis, #2563eb)";
    else ctx.fillStyle = "var(--fg-muted, #6b6b6b)";

    ctx.fill();

    // Label for hubs
    if (n.isHub && s > 0.6) {
      ctx.fillStyle = "var(--fg-default, #1a1a1a)";
      ctx.font = `${Math.max(10, 11 * s)}px sans-serif`;
      ctx.fillText(n.id.split("/").pop().replace(".md", ""), cx + r + 4, cy + 4);
    }
  }
}

function resizeCanvas() {
  const canvas = canvasEl.value;
  if (!canvas) return;
  const parent = canvas.parentElement;
  canvas.width = parent.clientWidth;
  canvas.height = parent.clientHeight;
  render();
}

function worldPos(e) {
  const rect = canvasEl.value.getBoundingClientRect();
  return {
    x: (e.clientX - rect.left - viewTransform.x) / viewTransform.scale,
    y: (e.clientY - rect.top - viewTransform.y) / viewTransform.scale,
  };
}

function hitTest(wx, wy) {
  for (const n of simNodes) {
    const dx = n.x - wx;
    const dy = n.y - wy;
    if (dx * dx + dy * dy < (n.radius + 4) * (n.radius + 4)) return n;
  }
  return null;
}

function onMouseDown(e) {
  const w = worldPos(e);
  const hit = hitTest(w.x, w.y);
  if (hit) {
    dragNode = hit;
    dragOffset.x = hit.x - w.x;
    dragOffset.y = hit.y - w.y;
    stopSimulation();
  }
}

function onMouseMove(e) {
  mousePos = { x: e.clientX, y: e.clientY };
  const rect = canvasEl.value.getBoundingClientRect();
  const wx = (e.clientX - rect.left - viewTransform.x) / viewTransform.scale;
  const wy = (e.clientY - rect.top - viewTransform.y) / viewTransform.scale;

  if (dragNode) {
    dragNode.x = wx + dragOffset.x;
    dragNode.y = wy + dragOffset.y;
    render();
    return;
  }

  // Tooltip on hover
  const hit = hitTest(wx, wy);
  if (hit) {
    tooltip.value = {
      id: hit.id,
      docType: hit.docType,
      outDeg: hit.outDeg,
      inDeg: hit.inDeg,
    };
    tooltipStyle.value = {
      left: (e.clientX - rect.left + 14) + "px",
      top: (e.clientY - rect.top - 10) + "px",
    };
    canvasEl.value.style.cursor = "pointer";
  } else {
    tooltip.value = null;
    canvasEl.value.style.cursor = "default";
  }
}

function onMouseUp() {
  if (dragNode) {
    // Resume simulation with slight push
    dragNode = null;
    if (!simRunning) startSimulation();
  }
}

function onWheel(e) {
  const delta = e.deltaY > 0 ? 0.9 : 1.1;
  viewTransform.scale = Math.min(3, Math.max(0.2, viewTransform.scale * delta));
  render();
}

onMounted(async () => {
  window.addEventListener("resize", resizeCanvas);
  try {
    const data = await api("/api/wiki-graph");
    initSimulation(data);
    resizeCanvas();
  } catch {
    // graph unavailable
  }
});

onUnmounted(() => {
  stopSimulation();
  window.removeEventListener("resize", resizeCanvas);
});
</script>

<style scoped>
.graph-meta {
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
  margin-bottom: 8px;
}
.meta-item {
  font-size: 0.8rem;
  color: var(--fg-muted);
  padding: 2px 8px;
  background: var(--bg-muted);
  border-radius: var(--radius);
}
.meta-item.warn { color: var(--warning-fg); background: var(--warning-bg); }
.meta-item.info { color: var(--accent-fg); background: var(--accent-bg); }
.meta-item.danger { color: var(--danger-fg); background: var(--danger-bg); }

.graph-canvas-wrap {
  position: relative;
  border: 1px solid var(--border-default);
  border-radius: var(--radius);
  overflow: hidden;
  height: calc(100vh - var(--topbar-height) - 160px);
  min-height: 400px;
}
.graph-canvas {
  width: 100%;
  height: 100%;
  display: block;
}
.graph-tooltip {
  position: absolute;
  background: var(--bg-card);
  border: 1px solid var(--border-default);
  border-radius: var(--radius);
  padding: 8px 12px;
  font-size: 0.8rem;
  box-shadow: var(--shadow-md);
  pointer-events: none;
  z-index: 10;
  max-width: 280px;
}
.tooltip-path {
  font-weight: 600;
  word-break: break-all;
  font-size: 0.82rem;
}
.tooltip-type {
  color: var(--fg-muted);
  font-size: 0.75rem;
  margin-top: 2px;
}
.tooltip-deg {
  color: var(--fg-subtle);
  font-size: 0.75rem;
  margin-top: 2px;
}
</style>
