import { expandApartmentGeometry } from './geometry.js';

const isCalibration = window.location.pathname.includes('/calibration');
const base = isCalibration ? '..' : '.';
const NS = 'http://www.w3.org/2000/svg';

function svgEl(name, attrs = {}, text = null) {
  const el = document.createElementNS(NS, name);
  for (const [key, value] of Object.entries(attrs)) {
    if (value !== undefined && value !== null) el.setAttribute(key, String(value));
  }
  if (text !== null) el.textContent = text;
  return el;
}

function htmlEl(name, attrs = {}, text = null) {
  const el = document.createElement(name);
  for (const [key, value] of Object.entries(attrs)) {
    if (key === 'className') el.className = value;
    else if (key === 'html') el.innerHTML = value;
    else el.setAttribute(key, value);
  }
  if (text !== null) el.textContent = text;
  return el;
}

function resolveAsset(path) {
  return /^https?:\/\//i.test(path) ? path : `${base}/${path}`;
}

async function loadJson(path) {
  const response = await fetch(resolveAsset(path));
  if (!response.ok) throw new Error(`Could not load ${path}: ${response.status}`);
  return response.json();
}

function pointsAttr(points) {
  return points.map(([x, y]) => `${x},${y}`).join(' ');
}

function pointInPolygon(point, polygon) {
  const [x, y] = point;
  let inside = false;
  for (let i = 0, j = polygon.length - 1; i < polygon.length; j = i++) {
    const [xi, yi] = polygon[i];
    const [xj, yj] = polygon[j];
    const intersects = yi > y !== yj > y && x < ((xj - xi) * (y - yi)) / (yj - yi || 1e-9) + xi;
    if (intersects) inside = !inside;
  }
  return inside;
}

function orientation(a, b, c) {
  const value = (b[1] - a[1]) * (c[0] - b[0]) - (b[0] - a[0]) * (c[1] - b[1]);
  if (Math.abs(value) < 1e-7) return 0;
  return value > 0 ? 1 : 2;
}

function onSegment(a, b, c) {
  return (
    b[0] <= Math.max(a[0], c[0]) + 1e-7 &&
    b[0] + 1e-7 >= Math.min(a[0], c[0]) &&
    b[1] <= Math.max(a[1], c[1]) + 1e-7 &&
    b[1] + 1e-7 >= Math.min(a[1], c[1])
  );
}

function segmentsIntersect(p1, q1, p2, q2) {
  const o1 = orientation(p1, q1, p2);
  const o2 = orientation(p1, q1, q2);
  const o3 = orientation(p2, q2, p1);
  const o4 = orientation(p2, q2, q1);
  if (o1 !== o2 && o3 !== o4) return true;
  if (o1 === 0 && onSegment(p1, p2, q1)) return true;
  if (o2 === 0 && onSegment(p1, q2, q1)) return true;
  if (o3 === 0 && onSegment(p2, p1, q2)) return true;
  if (o4 === 0 && onSegment(p2, q1, q2)) return true;
  return false;
}

function polygonsIntersect(a, b) {
  for (let i = 0; i < a.length; i += 1) {
    const a1 = a[i];
    const a2 = a[(i + 1) % a.length];
    for (let j = 0; j < b.length; j += 1) {
      const b1 = b[j];
      const b2 = b[(j + 1) % b.length];
      if (segmentsIntersect(a1, a2, b1, b2)) return true;
    }
  }
  return pointInPolygon(a[0], b) || pointInPolygon(b[0], a);
}

function rotatePoint([x, y], angleDeg, [cx, cy] = [0, 0]) {
  const angle = (angleDeg * Math.PI) / 180;
  const dx = x - cx;
  const dy = y - cy;
  return [cx + dx * Math.cos(angle) - dy * Math.sin(angle), cy + dx * Math.sin(angle) + dy * Math.cos(angle)];
}

function furniturePolygon(object, cmPerPixel) {
  if (object.render.shape === 'l_desk') {
    const { width, depth, mainTopDepth, returnDepth } = object.dimensionsCm;
    const w = width / cmPerPixel;
    const d = depth / cmPerPixel;
    const main = mainTopDepth / cmPerPixel;
    const ret = returnDepth / cmPerPixel;
    const [x, y] = object.positionPx.topLeft;
    let local;
    if (object.positionPx.handedness === 'left') {
      local = [[0, 0], [w, 0], [w, main], [ret, main], [ret, d], [0, d]];
    } else {
      local = [[0, 0], [w, 0], [w, d], [w - ret, d], [w - ret, main], [0, main]];
    }
    return local.map(([px, py]) => rotatePoint([x + px, y + py], object.positionPx.rotationDeg, [x, y]));
  }

  const { width, depth } = object.dimensionsCm;
  const w = width / cmPerPixel;
  const d = depth / cmPerPixel;
  const [cx, cy] = object.positionPx.center;
  const local = [[cx - w / 2, cy - d / 2], [cx + w / 2, cy - d / 2], [cx + w / 2, cy + d / 2], [cx - w / 2, cy + d / 2]];
  return local.map((point) => rotatePoint(point, object.positionPx.rotationDeg, [cx, cy]));
}

function doorSwingPolygon(door, segments = 24) {
  const [hx, hy] = door.hinge;
  const angle1 = Math.atan2(door.closedPoint[1] - hy, door.closedPoint[0] - hx);
  const angle2 = Math.atan2(door.openPoint[1] - hy, door.openPoint[0] - hx);
  let delta = angle2 - angle1;
  while (delta > Math.PI) delta -= Math.PI * 2;
  while (delta < -Math.PI) delta += Math.PI * 2;
  const radius = Math.max(
    Math.hypot(door.closedPoint[0] - hx, door.closedPoint[1] - hy),
    Math.hypot(door.openPoint[0] - hx, door.openPoint[1] - hy)
  );
  const points = [[hx, hy]];
  for (let i = 0; i <= segments; i += 1) {
    const angle = angle1 + (delta * i) / segments;
    points.push([hx + radius * Math.cos(angle), hy + radius * Math.sin(angle)]);
  }
  return points;
}

function arcPath(door) {
  const [hx, hy] = door.hinge;
  const r = Math.max(
    Math.hypot(door.closedPoint[0] - hx, door.closedPoint[1] - hy),
    Math.hypot(door.openPoint[0] - hx, door.openPoint[1] - hy)
  );
  const v1 = [door.closedPoint[0] - hx, door.closedPoint[1] - hy];
  const v2 = [door.openPoint[0] - hx, door.openPoint[1] - hy];
  const cross = v1[0] * v2[1] - v1[1] * v2[0];
  const sweep = cross > 0 ? 1 : 0;
  return `M ${door.closedPoint[0]} ${door.closedPoint[1]} A ${r} ${r} 0 0 ${sweep} ${door.openPoint[0]} ${door.openPoint[1]}`;
}

function makeFurnitureGroup(object, cmPerPixel) {
  const group = svgEl('g', { class: `furniture furniture-${object.type}`, 'data-id': object.id });
  const polygon = furniturePolygon(object, cmPerPixel);
  group.append(svgEl('polygon', { points: pointsAttr(polygon), class: 'furniture-footprint' }));

  if (object.render.shape === 'bed') {
    const mattressWidth = object.mattressCm.width / cmPerPixel;
    const mattressDepth = object.mattressCm.depth / cmPerPixel;
    const [cx, cy] = object.positionPx.center;
    const inner = [
      [cx - mattressWidth / 2, cy - mattressDepth / 2],
      [cx + mattressWidth / 2, cy - mattressDepth / 2],
      [cx + mattressWidth / 2, cy + mattressDepth / 2],
      [cx - mattressWidth / 2, cy + mattressDepth / 2]
    ].map((point) => rotatePoint(point, object.positionPx.rotationDeg, [cx, cy]));
    group.append(svgEl('polygon', { points: pointsAttr(inner), class: 'mattress' }));
  }

  const centroid = polygon.reduce((sum, [x, y]) => [sum[0] + x / polygon.length, sum[1] + y / polygon.length], [0, 0]);
  group.append(svgEl('text', { x: centroid[0], y: centroid[1] - 3, class: 'furniture-label' }, object.render.label));
  group.append(svgEl('text', { x: centroid[0], y: centroid[1] + 10, class: 'furniture-id' }, object.id));
  return { group, polygon };
}

function buildSvg(apartment, fixtures, furniture, calibration) {
  const [vx, vy, vw, vh] = apartment.coordinateSystem.viewBox;
  const svg = svgEl('svg', {
    viewBox: `${vx} ${vy} ${vw} ${vh}`,
    class: calibration ? 'floorplan calibration-floorplan' : 'floorplan',
    role: 'img',
    'aria-label': calibration ? 'Kalibrierungsansicht des Wohnungsgrundrisses' : 'Vektorisierter Wohnungsgrundriss'
  });

  if (calibration) {
    const { cropPx, naturalSizePx, image } = apartment.source;
    svg.append(svgEl('image', {
      href: resolveAsset(image),
      x: -cropPx.x,
      y: -cropPx.y,
      width: naturalSizePx[0],
      height: naturalSizePx[1],
      class: 'reference-image'
    }));
  }

  const spaces = svgEl('g', { class: 'layer layer-spaces' });
  for (const space of apartment.spaces) {
    spaces.append(svgEl('polygon', {
      points: pointsAttr(space.points),
      class: `space space-${space.type}`,
      'data-id': space.id
    }));
  }
  svg.append(spaces);

  const niches = svgEl('g', { class: 'layer layer-niches' });
  for (const niche of apartment.niches ?? []) {
    niches.append(svgEl('polygon', {
      points: pointsAttr(niche.points),
      class: 'niche',
      'data-id': niche.id
    }));
  }
  svg.append(niches);

  const balustrades = svgEl('g', { class: 'layer layer-balustrades' });
  for (const balustrade of apartment.balustrades) {
    balustrades.append(svgEl(balustrade.closed ? 'polygon' : 'polyline', {
      points: pointsAttr(balustrade.points),
      class: 'balustrade'
    }));
  }
  svg.append(balustrades);

  const walls = svgEl('g', { class: 'layer layer-walls' });
  for (const wall of apartment.walls) {
    walls.append(svgEl('line', {
      x1: wall.start[0], y1: wall.start[1], x2: wall.end[0], y2: wall.end[1],
      'stroke-width': wall.thicknessPx,
      class: `wall wall-${wall.kind}`,
      'data-id': wall.id
    }));
  }
  svg.append(walls);

  const windows = svgEl('g', { class: 'layer layer-windows' });
  for (const windowItem of apartment.windows) {
    windows.append(svgEl('line', {
      x1: windowItem.start[0], y1: windowItem.start[1], x2: windowItem.end[0], y2: windowItem.end[1],
      class: 'window-line',
      'data-id': windowItem.id
    }));
  }
  svg.append(windows);

  const fixtureLayer = svgEl('g', { class: 'layer layer-fixtures' });
  for (const fixture of fixtures.fixtures) {
    fixtureLayer.append(svgEl('rect', {
      x: fixture.x, y: fixture.y, width: fixture.widthPx, height: fixture.depthPx,
      class: `fixture fixture-${fixture.type}`,
      'data-id': fixture.id
    }));
    if (fixture.type === 'sink') {
      fixtureLayer.append(svgEl('rect', { x: fixture.x + 5, y: fixture.y + 5, width: fixture.widthPx - 10, height: fixture.depthPx - 10, class: 'fixture-detail' }));
    }
    if (fixture.type === 'hob') {
      fixtureLayer.append(svgEl('circle', { cx: fixture.x + 8, cy: fixture.y + 10, r: 5, class: 'fixture-detail' }));
      fixtureLayer.append(svgEl('circle', { cx: fixture.x + 16, cy: fixture.y + 23, r: 5, class: 'fixture-detail' }));
    }
  }
  svg.append(fixtureLayer);

  const activeLayout = furniture.layouts.find((layout) => layout.id === furniture.activeLayoutId);
  const furnitureLayer = svgEl('g', { class: 'layer layer-furniture' });
  const furniturePolygons = [];
  for (const object of activeLayout.objects) {
    const rendered = makeFurnitureGroup(object, apartment.scale.cmPerPixel);
    furnitureLayer.append(rendered.group);
    furniturePolygons.push({ id: object.id, polygon: rendered.polygon, object });
  }
  svg.append(furnitureLayer);

  const doorLayer = svgEl('g', { class: 'layer layer-doors' });
  const doorResults = [];
  for (const door of apartment.doors) {
    const zone = doorSwingPolygon(door);
    const blockingObjects = furniturePolygons.filter((item) => polygonsIntersect(zone, item.polygon));
    const blocked = blockingObjects.length > 0;
    doorResults.push({ door, blocked, blockingObjects: blockingObjects.map((item) => item.id) });

    doorLayer.append(svgEl('polygon', {
      points: pointsAttr(zone),
      class: `door-zone ${door.policy} ${blocked ? 'blocked' : 'clear'}`,
      'data-id': `${door.id}-zone`
    }));
    doorLayer.append(svgEl('line', {
      x1: door.hinge[0], y1: door.hinge[1], x2: door.openPoint[0], y2: door.openPoint[1],
      class: 'door-leaf',
      'data-id': door.id
    }));
    doorLayer.append(svgEl('path', { d: arcPath(door), class: 'door-arc' }));
    doorLayer.append(svgEl('circle', { cx: door.hinge[0], cy: door.hinge[1], r: 2.5, class: 'door-hinge' }));
  }
  svg.append(doorLayer);

  const labels = svgEl('g', { class: 'layer layer-labels' });
  for (const label of apartment.labels) {
    labels.append(svgEl('text', { x: label.position[0], y: label.position[1], class: 'room-label' }, label.text));
  }
  svg.append(labels);

  if (calibration) {
    const annotations = svgEl('g', { class: 'layer layer-annotations' });
    apartment.spaces.forEach((space) => {
      space.points.forEach(([x, y], index) => {
        annotations.append(svgEl('circle', { cx: x, cy: y, r: 4, class: 'vertex-marker' }));
        annotations.append(svgEl('text', { x: x + 6, y: y - 6, class: 'vertex-label' }, `${space.id}:${index}`));
      });
    });
    apartment.walls.forEach((wall) => {
      const x = (wall.start[0] + wall.end[0]) / 2;
      const y = (wall.start[1] + wall.end[1]) / 2;
      annotations.append(svgEl('text', { x, y, class: 'wall-id' }, wall.id));
    });
    svg.append(annotations);
  }

  return { svg, activeLayout, doorResults, furniturePolygons };
}

function renderStatusPanel(apartment, activeLayout, doorResults) {
  const panel = htmlEl('aside', { className: 'status-panel' });
  panel.append(htmlEl('h2', {}, 'Aktueller Versuch'));
  panel.append(htmlEl('div', { className: 'layout-name' }, activeLayout.name));

  const scale = htmlEl('div', { className: 'notice warning' });
  scale.append(htmlEl('strong', {}, 'Maßstab aus Eingangstür abgeleitet'));
  scale.append(htmlEl('span', {}, `${apartment.scale.cmPerPixel.toFixed(2)} cm/px – Eingangstür als 100-cm-Anker bestätigt; restliche Maße bleiben Näherungen.`));
  panel.append(scale);

  const list = htmlEl('div', { className: 'door-list' });
  for (const result of doorResults) {
    const row = htmlEl('div', { className: `door-status ${result.blocked ? 'blocked' : 'clear'} ${result.door.policy}` });
    const title = htmlEl('div', { className: 'door-status-title' });
    title.append(htmlEl('span', { className: 'status-dot' }));
    title.append(htmlEl('strong', {}, result.door.name));
    row.append(title);
    const policyText = result.door.policy === 'must_remain_usable' ? 'muss nutzbar bleiben' : 'darf blockiert werden';
    row.append(htmlEl('small', {}, `${result.blocked ? `blockiert durch ${result.blockingObjects.join(', ')}` : 'frei'} · ${policyText}`));
    list.append(row);
  }
  panel.append(list);

  const notes = htmlEl('div', { className: 'layout-notes' });
  notes.append(htmlEl('h3', {}, 'Absicht dieses Layouts'));
  const ul = htmlEl('ul');
  activeLayout.notes.forEach((note) => ul.append(htmlEl('li', {}, note)));
  notes.append(ul);
  panel.append(notes);

  return panel;
}

function renderCalibrationControls() {
  const controls = htmlEl('div', { className: 'calibration-controls' });
  controls.append(htmlEl('strong', {}, 'Kalibrierung'));

  const refLabel = htmlEl('label');
  refLabel.append(htmlEl('span', {}, 'Original'));
  const refRange = htmlEl('input', { type: 'range', min: '0', max: '1', step: '0.05', value: '0.55' });
  refRange.addEventListener('input', () => document.documentElement.style.setProperty('--reference-opacity', refRange.value));
  refLabel.append(refRange);
  controls.append(refLabel);

  const vectorLabel = htmlEl('label');
  vectorLabel.append(htmlEl('span', {}, 'Vektor'));
  const vectorRange = htmlEl('input', { type: 'range', min: '0.1', max: '1', step: '0.05', value: '0.85' });
  vectorRange.addEventListener('input', () => document.documentElement.style.setProperty('--vector-opacity', vectorRange.value));
  vectorLabel.append(vectorRange);
  controls.append(vectorLabel);

  const link = htmlEl('a', { href: '../' }, 'Zur normalen Ansicht');
  controls.append(link);
  return controls;
}

async function main() {
  const root = document.querySelector('#app');
  try {
    const [apartmentSource, fixtures, furniture] = await Promise.all([
      loadJson('data/apartment.json'),
      loadJson('data/fixed-fixtures.json'),
      loadJson('data/furniture.json')
    ]);
    const apartment = expandApartmentGeometry(apartmentSource);

    const header = htmlEl('header', { className: 'app-header' });
    const titleWrap = htmlEl('div');
    titleWrap.append(htmlEl('p', { className: 'eyebrow' }, 'Scaled Apartment Planner'));
    titleWrap.append(htmlEl('h1', {}, isCalibration ? 'Kalibrierungsansicht' : 'Wohnung 264 · Layout-Experiment'));
    header.append(titleWrap);
    const nav = htmlEl('nav');
    nav.append(htmlEl('a', { href: isCalibration ? '../' : './calibration/' }, isCalibration ? 'Plan öffnen' : 'Kalibrierung öffnen'));
    header.append(nav);
    root.append(header);

    if (isCalibration) root.append(renderCalibrationControls());

    const workspace = htmlEl('main', { className: isCalibration ? 'workspace calibration-workspace' : 'workspace' });
    const planStack = htmlEl('div', { className: 'plan-stack' });
    const canvas = htmlEl('section', { className: 'canvas-card reconstructed-card' });
    const rendered = buildSvg(apartment, fixtures, furniture, isCalibration);
    canvas.append(rendered.svg);
    planStack.append(canvas);

    if (!isCalibration) {
      const referenceCard = htmlEl('section', { className: 'reference-card' });
      referenceCard.append(htmlEl('h2', {}, 'Originalgrundriss'));
      referenceCard.append(htmlEl('p', { className: 'reference-caption' }, 'Unveränderte Referenzansicht zum direkten Vergleich mit der Rekonstruktion oben.'));
      referenceCard.append(htmlEl('img', {
        src: './reference/floorplan-reference-upload.png',
        alt: 'Originaler Wohnungsgrundriss',
        class: 'reference-plan'
      }));
      planStack.append(referenceCard);
    }

    workspace.append(planStack);
    if (!isCalibration) workspace.append(renderStatusPanel(apartment, rendered.activeLayout, rendered.doorResults));
    root.append(workspace);

    const footer = htmlEl('footer', { className: 'app-footer' });
    footer.append(htmlEl('span', {}, 'Gebäudegeometrie, feste Einbauten und lose Möbel sind getrennte Datenebenen.'));
    footer.append(htmlEl('code', {}, `Layout: ${rendered.activeLayout.id}`));
    root.append(footer);
  } catch (error) {
    console.error(error);
    root.append(htmlEl('div', { className: 'fatal-error' }, error.message));
  }
}

main();
