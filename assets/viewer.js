import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';

const segments = 5;
const light = new THREE.Color('#bce1d4');
const dark = new THREE.Color('#167861');
const position = new THREE.Vector3();
const direction = new THREE.Vector3();
const vertical = new THREE.Vector3(0, 1, 0);
const quaternion = new THREE.Quaternion();
const scale = new THREE.Vector3();
const matrix = new THREE.Matrix4();

function hollowTube() {
  const angle = new THREE.Path();
  const outline = new THREE.Shape();
  outline.absarc(0, 0, 1, 0, Math.PI * 2, false);
  angle.absarc(0, 0, .9, 0, Math.PI * 2, true);
  outline.holes.push(angle);
  const geometry = new THREE.ExtrudeGeometry(outline, { depth: 1, bevelEnabled: false, curveSegments: 6 });
  geometry.translate(0, 0, -.5);
  geometry.rotateX(-Math.PI / 2);
  return geometry;
}

function createView(name, results, geometry) {
  const model = results[name];
  const host = document.getElementById(name + '-view');
  const details = document.getElementById(name + '-inspect');
  const renderer = new THREE.WebGLRenderer({ antialias: true });
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 1.6));
  renderer.setClearColor('#0e2224');
  renderer.domElement.setAttribute('aria-label', name + ' frame and tube stress');
  host.append(renderer.domElement);
  const scene = new THREE.Scene();
  scene.add(new THREE.HemisphereLight('#effff7', '#6a8b83', 2.0));
  const lightSource = new THREE.DirectionalLight('#f4fff7', 1.45);
  lightSource.position.set(-6, -7, 12);
  scene.add(lightSource);
  const camera = new THREE.PerspectiveCamera(37, 1, .1, 180);
  camera.up.set(0, 0, 1);
  const controls = new OrbitControls(camera, renderer.domElement);
  controls.minDistance = 6;
  controls.maxDistance = 90;
  controls.target.set(0, 0, 1.35);
  camera.position.set(10.5, -19.5, 11.5);
  controls.update();
  controls.saveState();

  const span = results.dimensions.span_m;
  const width = results.dimensions.width_m;
  const thickness = results.dimensions.deck_thickness_m;
  const grid = new THREE.GridHelper(24, 24, '#344c4e', '#274145');
  grid.rotateX(Math.PI / 2);
  grid.position.z = -.45;
  scene.add(grid);
  const deck = new THREE.Mesh(new THREE.BoxGeometry(span, width, thickness), new THREE.MeshStandardMaterial({
    color: '#a7c4b9', transparent: true, opacity: .23, depthWrite: false
  }));
  deck.position.z = -thickness / 2;
  scene.add(deck);

  const tubes = new THREE.InstancedMesh(geometry, new THREE.MeshStandardMaterial({
    color: '#ffffff', roughness: .86
  }), results.mesh.elements * segments);
  // Vertices move when the slider or mode animation runs, so keep culling conservative.
  tubes.frustumCulled = false;
  tubes.boundingSphere = new THREE.Sphere(new THREE.Vector3(0, 0, 1.5), 13);
  tubes.instanceMatrix.setUsage(THREE.DynamicDrawUsage);
  scene.add(tubes);
  const limit = results.plate.limit_mpa;
  const paint = new THREE.Color();
  const origins = model.nodes.map(([x, y, z]) => new THREE.Vector3(x - span / 2, y, z));
  const translations = key => model[key].map(row => new THREE.Vector3(...row.slice(0, 3)));
  const rotations = key => model[key].map(row => new THREE.Vector3(...row.slice(3, 6)));
  const staticU = translations('static');
  const staticR = rotations('static');
  const modeU = translations('mode');
  const modeR = rotations('mode');

  const elements = results.mesh.edges.map(([a, b], index) => {
    const axis = new THREE.Vector3().subVectors(origins[b], origins[a]);
    const length = axis.length();
    axis.divideScalar(length);
    const member = results.mesh.owner[index];
    const radius = model.radii_m[member];
    const [s0, s1] = model.stress_mpa[index];
    for (let segment = 0; segment < segments; segment += 1) {
      const t = (segment + .5) / segments;
      const stress = (1 - t) * s0 + t * s1;
      tubes.setColorAt(index * segments + segment, paint.copy(light).lerp(dark, Math.min(1, stress / limit / 1.5)));
    }
    const points = [];
    for (let segment = 0; segment <= segments; segment += 1) {
      const t = segment / segments;
      const t2 = t * t;
      const t3 = t2 * t;
      const n0 = 1 - 3 * t2 + 2 * t3;
      const n1 = 3 * t2 - 2 * t3;
      const d0 = length * (t - 2 * t2 + t3);
      const d1 = length * (-t2 + t3);
      function interpolate(U, R) {
        // Transverse rotations give Hermite slopes θ × axis. Axial motion is linear.
        return new THREE.Vector3()
          .addScaledVector(U[a], n0).addScaledVector(U[b], n1)
          .addScaledVector(new THREE.Vector3().crossVectors(R[a], axis), d0)
          .addScaledVector(new THREE.Vector3().crossVectors(R[b], axis), d1)
          .addScaledVector(axis, (1 - t - n0) * U[a].dot(axis) + (t - n1) * U[b].dot(axis));
      }
      points.push({ origin: new THREE.Vector3().lerpVectors(origins[a], origins[b], t),
        static: interpolate(staticU, staticR), mode: interpolate(modeU, modeR) });
    }
    return { member, radius, s0, s1, points };
  });
  const exceeded = elements.filter(element => Math.max(element.s0, element.s1) > limit);
  const markers = new THREE.InstancedMesh(new THREE.SphereGeometry(1, 12, 8),
    new THREE.MeshBasicMaterial({ color: '#ffb47a' }), exceeded.length);
  markers.frustumCulled = false;
  scene.add(markers);
  const at = (target, sample, staticFactor, modeFactor) => target.copy(sample.origin)
    .addScaledVector(sample.static, staticFactor).addScaledVector(sample.mode, modeFactor);
  const start = new THREE.Vector3();
  const end = new THREE.Vector3();
  const identity = new THREE.Quaternion();

  function deform(staticFactor, modeFactor) {
    elements.forEach((element, index) => {
      at(start, element.points[0], staticFactor, modeFactor);
      for (let segment = 0; segment < segments; segment += 1) {
        at(end, element.points[segment + 1], staticFactor, modeFactor);
        direction.subVectors(end, start);
        const length = direction.length();
        position.addVectors(start, end).multiplyScalar(.5);
        quaternion.setFromUnitVectors(vertical, direction.divideScalar(length));
        scale.set(element.radius, length, element.radius);
        tubes.setMatrixAt(index * segments + segment, matrix.compose(position, quaternion, scale));
        start.copy(end);
      }
    });
    tubes.instanceMatrix.needsUpdate = true;
    exceeded.forEach((element, index) => {
      const sample = element.s0 > element.s1 ? element.points[0] : element.points[segments];
      at(position, sample, staticFactor, modeFactor);
      scale.setScalar(1.3 * element.radius);
      markers.setMatrixAt(index, matrix.compose(position, identity, scale));
    });
    markers.instanceMatrix.needsUpdate = true;
  }

  const raycaster = new THREE.Raycaster();
  const pointer = new THREE.Vector2();
  let previous = -1;
  function pick(event) {
    const box = renderer.domElement.getBoundingClientRect();
    pointer.set(2 * (event.clientX - box.left) / box.width - 1, 1 - 2 * (event.clientY - box.top) / box.height);
    raycaster.setFromCamera(pointer, camera);
    const hit = raycaster.intersectObject(tubes)[0];
    if (!hit) return;
    const index = Math.floor(hit.instanceId / segments);
    if (index === previous) return;
    previous = index;
    const { member, radius, s0, s1 } = elements[index];
    const peak = Math.max(s0, s1);
    details.textContent = results.mesh.labels[member] + ' ' + (member + 1) + ' · element ' + (index + 1) +
      ' · radius ' + (radius * 1000).toFixed(1) + ' mm · ' + peak.toFixed(2) +
      ' MPa · ' + (peak > limit ? 'Fatigue limit exceeded' : 'Within fatigue limit');
  }
  renderer.domElement.addEventListener('pointermove', event => { if (event.buttons === 0) pick(event); });
  renderer.domElement.addEventListener('click', pick);

  function render() { renderer.render(scene, camera); }
  const resize = new ResizeObserver(() => {
    camera.aspect = host.clientWidth / host.clientHeight;
    // Maintain the same horizontal framing when the viewport becomes narrow.
    camera.fov = THREE.MathUtils.radToDeg(2 * Math.atan(Math.tan(THREE.MathUtils.degToRad(37 / 2)) *
      Math.max(1, 1.27 / camera.aspect)));
    camera.updateProjectionMatrix();
    renderer.setSize(host.clientWidth, host.clientHeight, false);
    render();
  });
  resize.observe(host);
  return { camera, controls, deform, render };
}

export function startViewer(results) {
  const geometry = hollowTube();
  const views = ['initial', 'optimized'].map(name => createView(name, results, geometry));
  let syncing = false;
  views.forEach((view, index) => view.controls.addEventListener('change', () => {
    if (syncing) return;
    syncing = true;
    const other = views[1 - index];
    other.camera.position.copy(view.camera.position);
    other.controls.target.copy(view.controls.target);
    other.controls.update();
    view.render();
    other.render();
    syncing = false;
  }));

  const slider = document.getElementById('exaggeration');
  const scaleLabel = document.getElementById('exaggeration-value');
  const animation = document.getElementById('animate-mode');
  let playing = false;
  let startTime = 0;
  let frame = 0;
  function update(modeFactor = 0) {
    scaleLabel.textContent = slider.value + '×';
    views.forEach(view => {
      view.deform(Number(slider.value), modeFactor);
      view.render();
    });
  }
  function animate(time) {
    if (!playing) return;
    update(.35 * Math.sin((time - startTime) * 2 * Math.PI / 2400));
    frame = requestAnimationFrame(animate);
  }
  slider.addEventListener('input', () => update());
  animation.addEventListener('click', () => {
    playing = !playing;
    animation.setAttribute('aria-pressed', String(playing));
    animation.textContent = playing ? 'Pause buckling mode' : 'Play buckling mode';
    if (playing) {
      startTime = performance.now();
      frame = requestAnimationFrame(animate);
    } else {
      cancelAnimationFrame(frame);
      update();
    }
  });
  document.getElementById('reset-camera').addEventListener('click', () => views[0].controls.reset());
  update();
  views.forEach(view => view.render());
}
