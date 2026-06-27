const sceneData = JSON.parse(document.getElementById("scene-data").textContent);
const canvas = document.getElementById("scene");

const renderer = new THREE.WebGLRenderer({ canvas, antialias: true });
renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
renderer.setClearColor(0xf6f8fb, 1);

const scene = new THREE.Scene();
scene.fog = new THREE.Fog(0xf6f8fb, 35, 120);

const camera = new THREE.PerspectiveCamera(45, 1, 0.05, 1000);
const controls = createOrbitController(camera, renderer.domElement);

const raycaster = new THREE.Raycaster();
raycaster.params.Line.threshold = 0.12;
const pointer = new THREE.Vector2();
const nodeObjects = [];
const labelObjects = [];
const linkObjects = [];
const linkGroups = new Map();
const nodeGroups = new Map();
const neutralColor = new THREE.Color(0x94a3b8);
const highlightColor = new THREE.Color(0xfacc15);
let labelsVisible = false;
let linksVisible = true;
let linkOpacityScale = 1;
let clickTargetMode = "both";
let selection = null;
let pointerStart = null;

initStaticScene();
buildScene(sceneData);
initUi(sceneData);
resize();
applyCameraPreset(sceneData.layout.cameraPresets[0]);
animate();

window.addEventListener("resize", resize);
canvas.addEventListener("pointerdown", onPointerStart);
canvas.addEventListener("pointermove", onPointerMove);
canvas.addEventListener("pointerleave", () => setInfoItem(null));
canvas.addEventListener("click", onCanvasClick);

function initStaticScene() {
  scene.add(new THREE.HemisphereLight(0xffffff, 0xd8e2ef, 1.25));

  const key = new THREE.DirectionalLight(0xffffff, 1.35);
  key.position.set(9, 12, 8);
  scene.add(key);

  const fill = new THREE.DirectionalLight(0xbfd7ff, 0.8);
  fill.position.set(-8, 4, -6);
  scene.add(fill);

  const grid = new THREE.GridHelper(32, 32, 0xcbd5e1, 0xe2e8f0);
  grid.position.y = -0.03;
  grid.material.opacity = 0.55;
  grid.material.transparent = true;
  scene.add(grid);

  const axes = new THREE.AxesHelper(2);
  axes.position.set(-15, 0.02, -15);
  scene.add(axes);
}

function buildScene(data) {
  const routerGeometry = new THREE.SphereGeometry(1, 18, 12);
  const terminalGeometry = new THREE.BoxGeometry(1, 1, 1);

  data.links.forEach((link, index) => {
    if (!link.id) link.id = `${link.src}->${link.dst}:${index}`;
    const material = new THREE.LineBasicMaterial({
      color: link.style.color,
      transparent: true,
      opacity: link.style.opacity,
      depthWrite: false,
    });
    const points = linkPoints(link);
    const geometry = new THREE.BufferGeometry().setFromPoints(points);
    const object = new THREE.Line(geometry, material);
    object.renderOrder = 1;
    object.userData = {
      kind: "link",
      link,
      baseColor: new THREE.Color(link.style.color),
      baseOpacity: link.style.opacity,
      enabled: true,
    };
    scene.add(object);
    linkObjects.push(object);
    if (!linkGroups.has(link.group)) linkGroups.set(link.group, []);
    linkGroups.get(link.group).push(object);
  });

  for (const node of data.nodes) {
    const geometry = node.kind === "terminal" ? terminalGeometry : routerGeometry;
    const material = new THREE.MeshStandardMaterial({
      color: node.style.color,
      roughness: 0.48,
      metalness: 0.05,
      transparent: true,
      opacity: 1,
    });
    const mesh = new THREE.Mesh(geometry, material);
    mesh.position.fromArray(node.position);
    applyNodeScale(mesh, node, 1);
    mesh.userData = {
      kind: "node",
      node,
      baseColor: new THREE.Color(node.style.color),
      baseScale: mesh.scale.clone(),
    };
    scene.add(mesh);
    nodeObjects.push(mesh);
    if (!nodeGroups.has(node.group)) nodeGroups.set(node.group, []);
    nodeGroups.get(node.group).push(mesh);

    const label = makeLabel(node.label);
    label.position.copy(mesh.position);
    label.position.y += node.style.size * 1.8;
    label.visible = false;
    label.userData = { nodeId: node.id };
    scene.add(label);
    labelObjects.push(label);
  }
}

function applyNodeScale(mesh, node, multiplier) {
  const scale = node.style.scale || [1, 1, 1];
  const size = Number(node.style.size || 0.1) * multiplier;
  mesh.scale.set(size * scale[0], size * scale[1], size * scale[2]);
}

function linkPoints(link) {
  const start = new THREE.Vector3().fromArray(link.sourcePosition);
  const end = new THREE.Vector3().fromArray(link.targetPosition);
  const curveHeight = Number(link.style.curveHeight || 0);
  if (curveHeight <= 0) {
    const sharedPlane = link.kind === "network" ? coordinatePlane(start, end) : null;
    if (sharedPlane) {
      return samePlaneCurvePoints(link, start, end, sharedPlane);
    }
    return [start, end];
  }

  const mid = start.clone().add(end).multiplyScalar(0.5);
  const distance = start.distanceTo(end);
  mid.y += Math.max(0.2, curveHeight * Math.max(1, distance * 0.18));
  const curve = new THREE.QuadraticBezierCurve3(start, mid, end);
  return curve.getPoints(16);
}

function coordinatePlane(start, end) {
  if (Math.abs(start.y - end.y) < 1e-6) return "xz";
  if (Math.abs(start.z - end.z) < 1e-6) return "xy";
  if (Math.abs(start.x - end.x) < 1e-6) return "yz";
  return null;
}

function samePlaneCurvePoints(link, start, end, plane) {
  const delta = end.clone().sub(start);
  const distance = planeDistance(delta, plane);
  if (distance < 1e-6) return [start, end];

  const normal = planeNormal(delta, plane).normalize();
  const direction = link.src < link.dst ? 1 : -1;
  const bend = Math.min(0.42, Math.max(0.08, distance * 0.12));
  const mid = start.clone().add(end).multiplyScalar(0.5);
  mid.addScaledVector(normal, bend * direction);
  const curve = new THREE.QuadraticBezierCurve3(start, mid, end);
  return curve.getPoints(12);
}

function planeDistance(delta, plane) {
  if (plane === "xy") return Math.hypot(delta.x, delta.y);
  if (plane === "xz") return Math.hypot(delta.x, delta.z);
  return Math.hypot(delta.y, delta.z);
}

function planeNormal(delta, plane) {
  if (plane === "xy") return new THREE.Vector3(-delta.y, delta.x, 0);
  if (plane === "xz") return new THREE.Vector3(-delta.z, 0, delta.x);
  return new THREE.Vector3(0, -delta.z, delta.y);
}

function makeLabel(text) {
  const canvas2d = document.createElement("canvas");
  const context = canvas2d.getContext("2d");
  const fontSize = 28;
  context.font = `${fontSize}px Inter, Arial, sans-serif`;
  const metrics = context.measureText(text);
  canvas2d.width = Math.ceil(metrics.width + 18);
  canvas2d.height = 42;
  context.font = `${fontSize}px Inter, Arial, sans-serif`;
  context.fillStyle = "rgba(255,255,255,0.9)";
  roundRect(context, 0, 0, canvas2d.width, canvas2d.height, 7);
  context.fill();
  context.fillStyle = "#172033";
  context.fillText(text, 9, 29);

  const texture = new THREE.CanvasTexture(canvas2d);
  texture.minFilter = THREE.LinearFilter;
  const material = new THREE.SpriteMaterial({ map: texture, transparent: true });
  const sprite = new THREE.Sprite(material);
  sprite.scale.set(canvas2d.width / 160, canvas2d.height / 160, 1);
  return sprite;
}

function roundRect(context, x, y, width, height, radius) {
  context.beginPath();
  context.moveTo(x + radius, y);
  context.arcTo(x + width, y, x + width, y + height, radius);
  context.arcTo(x + width, y + height, x, y + height, radius);
  context.arcTo(x, y + height, x, y, radius);
  context.arcTo(x, y, x + width, y, radius);
  context.closePath();
}

function initUi(data) {
  document.getElementById("system-name").textContent = data.system.name;
  document.getElementById("system-meta").innerHTML = [
    ["Topology", data.system.topology_type],
    ["Routing", data.system.routing],
    ["Routers", data.system.router_count],
    ["Nodes", data.system.terminal_count],
    ["Links", data.system.link_count],
  ].map(([key, value]) => `<div><strong>${key}:</strong> ${value}</div>`).join("");

  document.getElementById("layout-name").textContent =
    `${data.layout.name}: ${data.layout.description}`;

  const presets = document.getElementById("camera-presets");
  for (const preset of data.layout.cameraPresets) {
    const button = document.createElement("button");
    button.type = "button";
    button.textContent = preset.name;
    button.addEventListener("click", () => applyCameraPreset(preset));
    presets.appendChild(button);
  }

  document.getElementById("labels-toggle").addEventListener("change", (event) => {
    labelsVisible = event.target.checked;
    updateVisualState();
  });

  document.getElementById("links-toggle").addEventListener("change", (event) => {
    linksVisible = event.target.checked;
    updateVisualState();
  });

  document.getElementById("opacity-slider").addEventListener("input", (event) => {
    linkOpacityScale = Number(event.target.value);
    updateVisualState();
  });

  for (const button of document.querySelectorAll("#click-target-modes button")) {
    button.addEventListener("click", () => {
      setClickTargetMode(button.dataset.mode || "both");
    });
  }

  const filters = document.getElementById("link-filters");
  for (const group of data.legend.linkGroups) {
    const row = document.createElement("label");
    row.className = "filter";
    row.innerHTML = `
      <input type="checkbox" checked>
      <span class="swatch" style="background:${group.color}"></span>
      <span>${group.name}</span>
    `;
    const input = row.querySelector("input");
    input.addEventListener("change", () => {
      const objects = linkGroups.get(group.name) || [];
      for (const object of objects) object.userData.enabled = input.checked;
      updateVisualState();
    });
    filters.appendChild(row);
  }

  const legend = document.getElementById("legend");
  for (const group of [...data.legend.nodeGroups, ...data.legend.linkGroups]) {
    const row = document.createElement("div");
    row.className = "legend-row";
    row.innerHTML = `
      <span></span>
      <span class="swatch" style="background:${group.color}"></span>
      <span>${group.name}</span>
    `;
    legend.appendChild(row);
  }
  updateVisualState();
}

function applyCameraPreset(preset) {
  if (!preset) return;
  controls.setView(preset.position, preset.target);
}

function resize() {
  const rect = canvas.parentElement.getBoundingClientRect();
  camera.aspect = Math.max(1, rect.width) / Math.max(1, rect.height);
  camera.updateProjectionMatrix();
  renderer.setSize(rect.width, rect.height, false);
}

function animate() {
  requestAnimationFrame(animate);
  renderer.render(scene, camera);
}

function onPointerStart(event) {
  pointerStart = { x: event.clientX, y: event.clientY };
}

function onPointerMove(event) {
  if (selection) return;
  const hit = pickSceneItem(event);
  if (!hit) {
    setInfoItem(null);
    return;
  }
  setInfoItem(hit.userData);
}

function onCanvasClick(event) {
  if (pointerStart) {
    const dx = event.clientX - pointerStart.x;
    const dy = event.clientY - pointerStart.y;
    if (Math.hypot(dx, dy) > 4) return;
  }
  if (selection) {
    selection = null;
    updateVisualState();
    setInfoItem(null);
    return;
  }
  const hit = pickSceneItem(event);
  if (!hit) return;
  if (hit.userData.kind === "link") {
    selectLink(hit.userData.link);
  } else if (hit.userData.kind === "node") {
    selectNode(hit.userData.node);
  }
}

function pickSceneItem(event) {
  const rect = canvas.getBoundingClientRect();
  pointer.x = ((event.clientX - rect.left) / rect.width) * 2 - 1;
  pointer.y = -((event.clientY - rect.top) / rect.height) * 2 + 1;
  raycaster.setFromCamera(pointer, camera);
  const targets = [];
  if (clickTargetMode === "both" || clickTargetMode === "router") {
    targets.push(...nodeObjects.filter((object) => object.userData.node.kind !== "terminal"));
  }
  if (clickTargetMode === "both" || clickTargetMode === "link") {
    targets.push(...linkObjects.filter((object) => object.visible));
  }
  if (!targets.length) return null;
  const hits = raycaster.intersectObjects(targets, false);
  return hits.length ? hits[0].object : null;
}

function setClickTargetMode(mode) {
  clickTargetMode = ["both", "router", "link"].includes(mode) ? mode : "both";
  for (const button of document.querySelectorAll("#click-target-modes button")) {
    button.setAttribute("aria-pressed", String(button.dataset.mode === clickTargetMode));
  }
  if (selection) {
    selection = null;
    updateVisualState();
  }
  setInfoItem(null);
}

function selectLink(link) {
  selection = {
    kind: "link",
    selectedNodeIds: new Set([link.src, link.dst]),
    activeNodeIds: new Set([link.src, link.dst]),
    activeLinkIds: new Set([link.id]),
  };
  updateVisualState();
  setInfoItem({ kind: "link", link });
}

function selectNode(node) {
  const activeNodeIds = new Set([node.id]);
  const activeLinkIds = new Set();
  for (const object of linkObjects) {
    const link = object.userData.link;
    if (link.src !== node.id && link.dst !== node.id) continue;
    activeLinkIds.add(link.id);
    activeNodeIds.add(link.src);
    activeNodeIds.add(link.dst);
  }
  selection = {
    kind: "node",
    selectedNodeIds: new Set([node.id]),
    activeNodeIds,
    activeLinkIds,
  };
  updateVisualState();
  setInfoItem({ kind: "node", node });
}

function updateVisualState() {
  for (const object of nodeObjects) {
    const node = object.userData.node;
    const isSelected = selection?.selectedNodeIds.has(node.id) || false;
    const isActive = !selection || selection.activeNodeIds.has(node.id);
    object.material.color.copy(isActive ? object.userData.baseColor : neutralColor);
    object.material.opacity = isActive ? 1 : 0.18;
    const scale = isSelected ? 1.6 : isActive && selection ? 1.15 : 1;
    object.scale.copy(object.userData.baseScale).multiplyScalar(scale);
    object.renderOrder = isSelected ? 10 : 2;
  }

  for (const object of linkObjects) {
    const link = object.userData.link;
    const enabled = linksVisible && object.userData.enabled;
    const isActive = !selection || selection.activeLinkIds.has(link.id);
    object.visible = enabled;
    object.material.color.copy(isActive ? object.userData.baseColor : neutralColor);
    object.material.opacity = isActive
      ? Math.min(1, object.userData.baseOpacity * linkOpacityScale)
      : 0.08;
    if (selection && isActive) {
      object.material.color.copy(highlightColor);
      object.material.opacity = 0.95;
      object.renderOrder = 20;
    } else {
      object.renderOrder = 1;
    }
  }

  for (const label of labelObjects) {
    const nodeId = label.userData.nodeId;
    const isSelected = selection?.selectedNodeIds.has(nodeId) || false;
    label.visible = labelsVisible || isSelected;
  }
}

function setInfoItem(item) {
  const card = document.getElementById("hover-card");
  if (!item) {
    card.textContent = "No selection";
    return;
  }
  if (item.kind === "link") {
    const link = item.link;
    const meta = Object.entries(link.metadata || {})
      .map(([key, value]) => `<div>${key}: ${formatValue(value)}</div>`)
      .join("");
    card.innerHTML = `<strong>${link.src} -> ${link.dst}</strong><div>${link.group}</div>${meta}`;
    return;
  }
  const node = item.node;
  const shownKeys = [
    "coord",
    "group",
    "subgroup",
    "position",
    "bits",
    "layer_role",
    "router",
    "attached_router",
    "terminal_index",
  ];
  const meta = Object.entries(node.metadata || {})
    .filter(([key]) => shownKeys.includes(key))
    .map(([key, value]) => `<div>${key}: ${formatValue(value)}</div>`)
    .join("");
  card.innerHTML = `<strong>${node.id}</strong><div>${node.group}</div>${meta}`;
}

function formatValue(value) {
  return Array.isArray(value) ? value.join(".") : value;
}

function createOrbitController(cameraObject, element) {
  const target = new THREE.Vector3();
  const spherical = new THREE.Spherical();
  const offset = new THREE.Vector3();
  const state = {
    pointerId: null,
    mode: "rotate",
    x: 0,
    y: 0,
  };

  element.addEventListener("contextmenu", (event) => event.preventDefault());
  element.addEventListener("pointerdown", onPointerDown);
  element.addEventListener("pointermove", onPointerDrag);
  element.addEventListener("pointerup", onPointerEnd);
  element.addEventListener("pointercancel", onPointerEnd);
  element.addEventListener("wheel", onWheel, { passive: false });

  function setView(position, focus) {
    cameraObject.position.fromArray(position);
    target.fromArray(focus);
    syncSpherical();
    updateCamera();
  }

  function syncSpherical() {
    offset.copy(cameraObject.position).sub(target);
    spherical.setFromVector3(offset);
    spherical.radius = Math.max(0.4, spherical.radius);
  }

  function updateCamera() {
    spherical.makeSafe();
    spherical.radius = Math.min(Math.max(spherical.radius, 0.4), 400);
    offset.setFromSpherical(spherical);
    cameraObject.position.copy(target).add(offset);
    cameraObject.lookAt(target);
  }

  function onPointerDown(event) {
    state.pointerId = event.pointerId;
    state.mode = event.button === 2 || event.shiftKey ? "pan" : "rotate";
    state.x = event.clientX;
    state.y = event.clientY;
    syncSpherical();
    element.setPointerCapture(event.pointerId);
  }

  function onPointerDrag(event) {
    if (state.pointerId !== event.pointerId) return;
    const dx = event.clientX - state.x;
    const dy = event.clientY - state.y;
    state.x = event.clientX;
    state.y = event.clientY;
    if (state.mode === "pan") {
      pan(dx, dy);
    } else {
      spherical.theta -= dx * 0.006;
      spherical.phi -= dy * 0.006;
    }
    updateCamera();
  }

  function onPointerEnd(event) {
    if (state.pointerId !== event.pointerId) return;
    state.pointerId = null;
    element.releasePointerCapture(event.pointerId);
  }

  function onWheel(event) {
    event.preventDefault();
    syncSpherical();
    spherical.radius *= Math.exp(event.deltaY * 0.001);
    updateCamera();
  }

  function pan(dx, dy) {
    const distance = Math.max(1, cameraObject.position.distanceTo(target));
    const scale = distance * 0.0015;
    const right = new THREE.Vector3().setFromMatrixColumn(cameraObject.matrix, 0);
    const up = new THREE.Vector3().setFromMatrixColumn(cameraObject.matrix, 1);
    target.addScaledVector(right, -dx * scale);
    target.addScaledVector(up, dy * scale);
  }

  return { setView };
}
