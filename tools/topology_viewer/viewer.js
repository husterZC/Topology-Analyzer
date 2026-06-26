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
const pointer = new THREE.Vector2();
const nodeObjects = [];
const labelObjects = [];
const linkObjects = [];
const linkGroups = new Map();
const nodeGroups = new Map();

initStaticScene();
buildScene(sceneData);
initUi(sceneData);
resize();
applyCameraPreset(sceneData.layout.cameraPresets[0]);
animate();

window.addEventListener("resize", resize);
canvas.addEventListener("pointermove", onPointerMove);
canvas.addEventListener("pointerleave", () => setHover(null));

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
  const nodeGeometry = new THREE.SphereGeometry(1, 18, 12);

  for (const link of data.links) {
    const material = new THREE.LineBasicMaterial({
      color: link.style.color,
      transparent: true,
      opacity: link.style.opacity,
      depthWrite: false,
    });
    const points = linkPoints(link);
    const geometry = new THREE.BufferGeometry().setFromPoints(points);
    const object = new THREE.Line(geometry, material);
    object.userData = { kind: "link", link, baseOpacity: link.style.opacity };
    scene.add(object);
    linkObjects.push(object);
    if (!linkGroups.has(link.group)) linkGroups.set(link.group, []);
    linkGroups.get(link.group).push(object);
  }

  for (const node of data.nodes) {
    const material = new THREE.MeshStandardMaterial({
      color: node.style.color,
      roughness: 0.48,
      metalness: 0.05,
    });
    const mesh = new THREE.Mesh(nodeGeometry, material);
    mesh.position.fromArray(node.position);
    mesh.scale.setScalar(node.style.size);
    mesh.userData = { kind: "node", node };
    scene.add(mesh);
    nodeObjects.push(mesh);
    if (!nodeGroups.has(node.group)) nodeGroups.set(node.group, []);
    nodeGroups.get(node.group).push(mesh);

    const label = makeLabel(node.label);
    label.position.copy(mesh.position);
    label.position.y += node.style.size * 1.8;
    label.visible = false;
    scene.add(label);
    labelObjects.push(label);
  }
}

function linkPoints(link) {
  const start = new THREE.Vector3().fromArray(link.sourcePosition);
  const end = new THREE.Vector3().fromArray(link.targetPosition);
  const curveHeight = Number(link.style.curveHeight || 0);
  if (curveHeight <= 0) return [start, end];

  const mid = start.clone().add(end).multiplyScalar(0.5);
  const distance = start.distanceTo(end);
  mid.y += Math.max(0.2, curveHeight * Math.max(1, distance * 0.18));
  const curve = new THREE.QuadraticBezierCurve3(start, mid, end);
  return curve.getPoints(16);
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
    ["Terminals", data.system.terminal_count],
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
    for (const label of labelObjects) label.visible = event.target.checked;
  });

  document.getElementById("links-toggle").addEventListener("change", (event) => {
    for (const link of linkObjects) link.visible = event.target.checked;
  });

  document.getElementById("opacity-slider").addEventListener("input", (event) => {
    const scale = Number(event.target.value);
    for (const link of linkObjects) {
      link.material.opacity = link.userData.baseOpacity * scale;
    }
  });

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
      for (const object of objects) object.visible = input.checked;
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

function onPointerMove(event) {
  const rect = canvas.getBoundingClientRect();
  pointer.x = ((event.clientX - rect.left) / rect.width) * 2 - 1;
  pointer.y = -((event.clientY - rect.top) / rect.height) * 2 + 1;
  raycaster.setFromCamera(pointer, camera);
  const hits = raycaster.intersectObjects(nodeObjects, false);
  setHover(hits.length ? hits[0].object.userData.node : null);
}

function setHover(node) {
  const card = document.getElementById("hover-card");
  if (!node) {
    card.textContent = "Hover a router";
    return;
  }
  const meta = Object.entries(node.metadata || {})
    .filter(([key]) => ["coord", "group", "subgroup", "position", "bits", "layer_role", "router"].includes(key))
    .map(([key, value]) => `<div>${key}: ${Array.isArray(value) ? value.join(".") : value}</div>`)
    .join("");
  card.innerHTML = `<strong>${node.id}</strong><div>${node.group}</div>${meta}`;
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
