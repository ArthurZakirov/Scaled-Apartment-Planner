import { expandApartmentGeometry } from './geometry.js';
import { findLayoutForArrangement, findLayoutForSelection, normalizeScenarioId, resolveScenarioData, validLayoutsForDesk } from './furniture.js';
import {
  DISPLAY_OPTIONS,
  allDisplayLayers,
  applyDisplayState,
  parseDisplayState,
  setDisplayStateInUrl
} from './display-filter.js';

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

function fixedFurnishingElement(item) {
  if (item.shape !== 'side_chair' || item.openSide !== 'west') {
    throw new Error(`Unsupported fixed furnishing: ${item.id}`);
  }
  const right = item.x + item.widthPx;
  const bottom = item.y + item.depthPx;
  const group = svgEl('g', {
    class: `fixed-furnishing fixed-furnishing-${item.type}`,
    'data-id': item.id
  });
  group.append(svgEl('path', {
    d: `M ${item.x} ${item.y} H ${right} V ${bottom} H ${item.x}`,
    class: 'fixed-furnishing-outline'
  }));
  return group;
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

function deskWorkZonePolygon(object, cmPerPixel, dimensionsCm) {
  const { width, mainTopDepth, returnDepth } = object.dimensionsCm;
  const deskWidth = width / cmPerPixel;
  const mainDepth = mainTopDepth / cmPerPixel;
  const returnWidth = returnDepth / cmPerPixel;
  const zoneWidth = dimensionsCm.width / cmPerPixel;
  const zoneDepth = dimensionsCm.depth / cmPerPixel;
  const innerX = object.positionPx.handedness === 'left' ? returnWidth : deskWidth - returnWidth;
  const startX = object.positionPx.handedness === 'left' ? innerX : innerX - zoneWidth;
  const local = [
    [startX, mainDepth],
    [startX + zoneWidth, mainDepth],
    [startX + zoneWidth, mainDepth + zoneDepth],
    [startX, mainDepth + zoneDepth]
  ];
  const [x, y] = object.positionPx.topLeft;
  return local.map(([px, py]) => rotatePoint([x + px, y + py], object.positionPx.rotationDeg, [x, y]));
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

function doorRevealPolygon(door, cmPerPixel) {
  if (!door.revealDepthCm) return null;
  const [hx, hy] = door.hinge;
  const [cx, cy] = door.closedPoint;
  const edge = [cx - hx, cy - hy];
  const length = Math.hypot(edge[0], edge[1]);
  let normal = [-edge[1] / length, edge[0] / length];
  const openVector = [door.openPoint[0] - hx, door.openPoint[1] - hy];
  if (normal[0] * openVector[0] + normal[1] * openVector[1] < 0) normal = [-normal[0], -normal[1]];
  const depthPx = door.revealDepthCm / cmPerPixel;
  const offset = [normal[0] * depthPx, normal[1] * depthPx];
  return [[hx, hy], [cx, cy], [cx + offset[0], cy + offset[1]], [hx + offset[0], hy + offset[1]]];
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

function appendAccessIndicator(group, polygon, label, kind) {
  const [start, end] = polygon;
  const midpoint = [(start[0] + end[0]) / 2, (start[1] + end[1]) / 2];
  const centroid = polygon.reduce((sum, [x, y]) => [sum[0] + x / polygon.length, sum[1] + y / polygon.length], [0, 0]);
  const edge = [end[0] - start[0], end[1] - start[1]];
  const length = Math.hypot(edge[0], edge[1]);
  let normal = [-edge[1] / length, edge[0] / length];
  const towardCenter = (centroid[0] - midpoint[0]) * normal[0] + (centroid[1] - midpoint[1]) * normal[1];
  if (towardCenter > 0) normal = [-normal[0], -normal[1]];
  const tip = [midpoint[0] + normal[0] * 19, midpoint[1] + normal[1] * 19];
  const side = [-normal[1], normal[0]];
  const arrow = [
    tip,
    [tip[0] - normal[0] * 6 + side[0] * 3.5, tip[1] - normal[1] * 6 + side[1] * 3.5],
    [tip[0] - normal[0] * 6 - side[0] * 3.5, tip[1] - normal[1] * 6 - side[1] * 3.5]
  ];
  group.append(svgEl('line', {
    x1: midpoint[0], y1: midpoint[1], x2: tip[0], y2: tip[1], class: `access-arrow access-arrow-${kind}`
  }));
  group.append(svgEl('polygon', { points: pointsAttr(arrow), class: `access-arrowhead access-arrowhead-${kind}` }));
  group.append(svgEl('text', {
    x: tip[0] + normal[0] * 7,
    y: tip[1] + normal[1] * 7,
    class: `access-label access-label-${kind}`
  }, label));
}

function accessZonePolygon(polygon, depthPx) {
  const [start, end] = polygon;
  const midpoint = [(start[0] + end[0]) / 2, (start[1] + end[1]) / 2];
  const centroid = polygon.reduce((sum, [x, y]) => [sum[0] + x / polygon.length, sum[1] + y / polygon.length], [0, 0]);
  const edge = [end[0] - start[0], end[1] - start[1]];
  const length = Math.hypot(edge[0], edge[1]);
  let normal = [-edge[1] / length, edge[0] / length];
  if ((centroid[0] - midpoint[0]) * normal[0] + (centroid[1] - midpoint[1]) * normal[1] > 0) {
    normal = [-normal[0], -normal[1]];
  }
  return [
    start,
    end,
    [end[0] + normal[0] * depthPx, end[1] + normal[1] * depthPx],
    [start[0] + normal[0] * depthPx, start[1] + normal[1] * depthPx]
  ];
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

    const pillowCount = object.mattressCm.width >= 120 ? 2 : 1;
    const pillowDepth = 28 / cmPerPixel;
    const pillowAreaWidth = mattressWidth * .78;
    const pillowGap = 5 / cmPerPixel;
    const pillowWidth = (pillowAreaWidth - pillowGap * (pillowCount - 1)) / pillowCount;
    const pillowY = cy - mattressDepth / 2 + pillowDepth / 2 + 5 / cmPerPixel;
    for (let index = 0; index < pillowCount; index += 1) {
      const pillowX = cx - pillowAreaWidth / 2 + pillowWidth / 2 + index * (pillowWidth + pillowGap);
      const pillow = [
        [pillowX - pillowWidth / 2, pillowY - pillowDepth / 2],
        [pillowX + pillowWidth / 2, pillowY - pillowDepth / 2],
        [pillowX + pillowWidth / 2, pillowY + pillowDepth / 2],
        [pillowX - pillowWidth / 2, pillowY + pillowDepth / 2]
      ].map((point) => rotatePoint(point, object.positionPx.rotationDeg, [cx, cy]));
      group.append(svgEl('polygon', { points: pointsAttr(pillow), class: 'pillow' }));
    }
    const headMidpoint = [(inner[0][0] + inner[1][0]) / 2, (inner[0][1] + inner[1][1]) / 2];
    group.append(svgEl('text', { x: headMidpoint[0], y: headMidpoint[1] - 5, class: 'head-label' }, 'Kopf'));
  }

  if (object.type === 'wardrobe') {
    const [frontStart, frontEnd] = polygon;
    group.append(svgEl('line', {
      x1: frontStart[0], y1: frontStart[1], x2: frontEnd[0], y2: frontEnd[1],
      class: 'wardrobe-opening-edge'
    }));
    appendAccessIndicator(group, polygon, 'Zugriff', 'wardrobe');
  }

  if (object.type === 'storage') appendAccessIndicator(group, polygon, object.accessLabel ?? 'Schubladen', 'storage');
  if (object.type === 'appliance') {
    const [frontStart, frontEnd] = polygon;
    group.append(svgEl('line', {
      x1: frontStart[0], y1: frontStart[1], x2: frontEnd[0], y2: frontEnd[1],
      class: 'appliance-door-edge'
    }));
    appendAccessIndicator(group, polygon, object.accessLabel ?? 'Tür', 'appliance');
  }

  const centroid = polygon.reduce((sum, [x, y]) => [sum[0] + x / polygon.length, sum[1] + y / polygon.length], [0, 0]);
  group.append(svgEl('text', { x: centroid[0], y: centroid[1] - 3, class: 'furniture-label' }, object.render.label));
  group.append(svgEl('text', { x: centroid[0], y: centroid[1] + 10, class: 'furniture-id' }, object.id));
  return { group, polygon };
}

function buildSvg(apartment, fixtures, fixedFurnishings, furniture, constraints, evaluation, calibration) {
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

  const revealLayer = svgEl('g', { class: 'layer layer-door-reveals' });
  for (const door of apartment.doors) {
    const reveal = doorRevealPolygon(door, apartment.scale.cmPerPixel);
    if (reveal) revealLayer.append(svgEl('polygon', {
      points: pointsAttr(reveal),
      class: 'door-reveal',
      'data-id': `${door.id}-reveal`
    }));
  }
  svg.append(revealLayer);

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
  for (const item of fixedFurnishings.furnishings) {
    furnitureLayer.append(fixedFurnishingElement(item));
  }
  const furniturePolygons = [];
  for (const object of activeLayout.objects) {
    const rendered = makeFurnitureGroup(object, apartment.scale.cmPerPixel);
    furniturePolygons.push({ id: object.id, polygon: rendered.polygon, object, group: rendered.group });
  }

  const accessLayer = svgEl('g', { class: 'layer layer-access-zones' });
  for (const item of furniturePolygons.filter((entry) => entry.object.type === 'wardrobe')) {
    const depthCm = activeLayout.selection.paxAccessDepthCm ?? constraints.wardrobeAccessDepthCm;
    if (depthCm <= 0) continue;
    const zone = accessZonePolygon(item.polygon, depthCm / apartment.scale.cmPerPixel);
    accessLayer.append(svgEl('polygon', {
      points: pointsAttr(zone),
      class: 'wardrobe-access-zone',
      'data-id': `${item.id}-access-zone`
    }));
    const center = zone.reduce((sum, [x, y]) => [sum[0] + x / zone.length, sum[1] + y / zone.length], [0, 0]);
    accessLayer.append(svgEl('text', { x: center[0], y: center[1], class: 'wardrobe-access-zone-label' }, `${depthCm} cm Zugriff`));
  }
  for (const item of furniturePolygons.filter((entry) => entry.object.type === 'storage' && entry.object.accessLabel)) {
    const depthCm = item.object.accessDepthCm || constraints.storageAccessDepthCm;
    const zone = accessZonePolygon(item.polygon, depthCm / apartment.scale.cmPerPixel);
    accessLayer.append(svgEl('polygon', {
      points: pointsAttr(zone),
      class: 'storage-access-zone',
      'data-id': `${item.id}-access-zone`
    }));
    const center = zone.reduce((sum, [x, y]) => [sum[0] + x / zone.length, sum[1] + y / zone.length], [0, 0]);
    accessLayer.append(svgEl('text', { x: center[0], y: center[1], class: 'storage-access-zone-label' }, `${depthCm} cm Schubladen`));
  }
  for (const item of furniturePolygons.filter((entry) => entry.object.type === 'appliance' && entry.object.accessLabel)) {
    const depthCm = item.object.accessDepthCm || constraints.applianceAccessDepthCm;
    const zone = accessZonePolygon(item.polygon, depthCm / apartment.scale.cmPerPixel);
    accessLayer.append(svgEl('polygon', {
      points: pointsAttr(zone),
      class: 'appliance-access-zone',
      'data-id': `${item.id}-access-zone`
    }));
    const center = zone.reduce((sum, [x, y]) => [sum[0] + x / zone.length, sum[1] + y / zone.length], [0, 0]);
    accessLayer.append(svgEl('text', { x: center[0], y: center[1], class: 'appliance-access-zone-label' }, `${depthCm} cm Bedienzone`));
  }
  for (const item of furniturePolygons.filter((entry) => entry.object.type === 'desk')) {
    const zone = deskWorkZonePolygon(item.object, apartment.scale.cmPerPixel, constraints.deskWorkZoneCm);
    accessLayer.append(svgEl('polygon', {
      points: pointsAttr(zone),
      class: 'desk-work-zone',
      'data-id': `${item.id}-work-zone`
    }));
    const center = zone.reduce((sum, [x, y]) => [sum[0] + x / zone.length, sum[1] + y / zone.length], [0, 0]);
    accessLayer.append(svgEl('text', { x: center[0], y: center[1], class: 'desk-work-zone-label' }, '60 × 60 cm Stuhlzone'));
  }
  svg.append(accessLayer);

  for (const item of furniturePolygons) {
    furnitureLayer.append(item.group);
  }
  svg.append(furnitureLayer);

  const furnitureCollisions = [];
  for (let firstIndex = 0; firstIndex < furniturePolygons.length; firstIndex += 1) {
    for (let secondIndex = firstIndex + 1; secondIndex < furniturePolygons.length; secondIndex += 1) {
      const first = furniturePolygons[firstIndex];
      const second = furniturePolygons[secondIndex];
      if (polygonsIntersect(first.polygon, second.polygon)) {
        furnitureCollisions.push([first.id, second.id]);
      }
    }
  }

  const doorLayer = svgEl('g', { class: 'layer layer-doors' });
  const doorResults = [];
  for (const door of apartment.doors) {
    const zone = doorSwingPolygon(door);
    const openingFraction = evaluation.doorOpeningFractions[door.id] ?? 1;
    const minimumOpeningFraction = constraints.doorPolicies.minimumOpeningFractionByDoor[door.id] ?? 1;
    const blockingObjects = evaluation.doorOpeningLimitedBy[door.id] ?? [];
    const blocked = openingFraction < minimumOpeningFraction;
    doorResults.push({ door, blocked, blockingObjects, openingFraction, minimumOpeningFraction });

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

  return { svg, activeLayout, doorResults, furniturePolygons, furnitureCollisions };
}

function selectScenario(scenarioId) {
  const url = new URL(window.location.href);
  url.searchParams.set('scenario', scenarioId);
  window.location.assign(url);
}

function renderDisplayControls(svg) {
  const section = htmlEl('fieldset', { className: 'display-controls control-section' });
  section.append(htmlEl('legend', {}, 'Anzeige'));

  const popoverId = `display-options-${isCalibration ? 'calibration' : 'main'}`;
  const toggle = htmlEl('button', {
    type: 'button',
    className: 'display-toggle',
    'aria-expanded': 'false',
    'aria-controls': popoverId
  });
  const toggleLabel = htmlEl('span', {}, 'Ebenen auswählen');
  const toggleStatus = htmlEl('span', { className: 'display-toggle-status', 'aria-hidden': 'true' });
  toggle.append(toggleLabel, toggleStatus);

  const popover = htmlEl('div', {
    id: popoverId,
    className: 'display-popover',
    role: 'group',
    'aria-label': 'Sichtbare Ebenen',
    hidden: ''
  });
  const checkboxById = new Map();
  let visibleLayers = parseDisplayState(new URLSearchParams(window.location.search));

  const sync = () => {
    applyDisplayState(svg, visibleLayers);
    for (const option of DISPLAY_OPTIONS) checkboxById.get(option.id).checked = visibleLayers.has(option.id);
    toggleStatus.textContent = `${visibleLayers.size} von ${DISPLAY_OPTIONS.length}`;
    toggle.setAttribute('aria-label', `Anzeigeebenen auswählen, ${visibleLayers.size} von ${DISPLAY_OPTIONS.length} sichtbar`);
  };

  const commit = (nextVisibleLayers) => {
    visibleLayers = nextVisibleLayers;
    const nextUrl = setDisplayStateInUrl(window.location.href, visibleLayers);
    if (nextUrl.href !== window.location.href) window.history.pushState(null, '', nextUrl);
    sync();
  };

  for (const option of DISPLAY_OPTIONS) {
    const label = htmlEl('label', { className: 'display-option' });
    const checkbox = htmlEl('input', { type: 'checkbox', value: option.id });
    checkbox.checked = visibleLayers.has(option.id);
    checkbox.addEventListener('change', () => {
      const next = new Set(visibleLayers);
      if (checkbox.checked) next.add(option.id);
      else next.delete(option.id);
      commit(next);
    });
    checkboxById.set(option.id, checkbox);
    label.append(checkbox, htmlEl('span', {}, option.label));
    popover.append(label);
  }

  const actions = htmlEl('div', { className: 'display-actions' });
  const showAll = htmlEl('button', { type: 'button' }, 'Alles anzeigen');
  showAll.addEventListener('click', () => commit(allDisplayLayers()));
  const hideAll = htmlEl('button', { type: 'button' }, 'Alles ausblenden');
  hideAll.addEventListener('click', () => commit(allDisplayLayers(false)));
  actions.append(showAll, hideAll);
  popover.append(actions);

  const close = () => {
    popover.hidden = true;
    toggle.setAttribute('aria-expanded', 'false');
  };
  toggle.addEventListener('click', () => {
    const isOpen = !popover.hidden;
    if (isOpen) close();
    else {
      popover.hidden = false;
      toggle.setAttribute('aria-expanded', 'true');
      popover.querySelector('input')?.focus();
    }
  });
  section.addEventListener('keydown', (event) => {
    if (event.key === 'Escape' && !popover.hidden) {
      close();
      toggle.focus();
    }
  });
  document.addEventListener('click', (event) => {
    if (!section.contains(event.target)) close();
  });
  window.addEventListener('popstate', () => {
    visibleLayers = parseDisplayState(new URLSearchParams(window.location.search));
    sync();
  });

  section.append(toggle, popover);
  sync();
  return section;
}

function renderScenarioNavigation(furniture, activeLayout, evaluations) {
  const navigation = htmlEl('div', { className: 'scenario-navigation' });
  const position = htmlEl('div', { className: 'scenario-position' });
  position.append(htmlEl('strong', {}, 'Schlafbereich-Experiment'));
  position.append(htmlEl('small', {}, `${furniture.layouts.length} geometrisch mögliche Kombinationen · Schreibtischgröße bleibt unverändert`));
  navigation.append(position);
  return navigation;
}

function renderBedroomControls(furniture, activeLayout) {
  const controls = htmlEl('div', { className: 'bedroom-controls' });
  const dimensions = htmlEl('fieldset', { className: 'control-section' });
  dimensions.append(htmlEl('legend', {}, 'Möbel & Maße'));
  const positions = htmlEl('fieldset', { className: 'control-section' });
  positions.append(htmlEl('legend', {}, 'Möbelpositionen'));
  const currentBed = activeLayout.selection.bedVariantId === 'current-bed-90';
  let controlIndex = 0;

  const addSelect = (section, labelText, value, options, onChange, disabled = false, wide = false) => {
    const id = `bedroom-control-${controlIndex++}`;
    const label = htmlEl('label', wide ? { className: 'wide-control' } : {});
    label.setAttribute('for', id);
    label.append(htmlEl('span', { className: 'control-label' }, labelText));
    const selectAttrs = { id, name: id };
    if (disabled) selectAttrs.disabled = '';
    const select = htmlEl('select', selectAttrs);
    for (const option of options) {
      const attrs = { value: option.value };
      if (option.value === value) attrs.selected = '';
      if (option.disabled) attrs.disabled = '';
      select.append(htmlEl('option', attrs, option.disabled ? `${option.label} · nicht passend` : option.label));
    }
    select.addEventListener('change', () => onChange(select.value));
    label.append(select);
    section.append(label);
  };

  const findBedroomLayout = (overrides) => findLayoutForSelection(furniture.layouts, activeLayout, overrides);
  const findArrangementLayout = (arrangementId) => findLayoutForArrangement(furniture.layouts, activeLayout, arrangementId);

  addSelect(dimensions, 'Bettart', currentBed ? 'current' : 'new', [
    { value: 'current', label: 'Mein aktuelles Bett', disabled: !findBedroomLayout({ bedVariantId: 'current-bed-90' }) },
    { value: 'new', label: 'Neues Bett', disabled: !findBedroomLayout({ bedVariantId: 'new-bed-90' }) }
  ], (value) => {
    const bedVariantId = value === 'current'
      ? 'current-bed-90'
      : currentBed ? 'new-bed-90' : activeLayout.selection.bedVariantId;
    const target = findBedroomLayout({ bedVariantId });
    if (target) selectScenario(target.id);
  });

  const mattressWidth = currentBed ? '90' : activeLayout.selection.bedVariantId.replace('new-bed-', '');
  addSelect(dimensions, 'Matratzenbreite', mattressWidth, ['90', '120', '140', '160', '180'].map((width) => ({
    value: width,
    label: `${width} cm`,
    disabled: !findBedroomLayout({ bedVariantId: `new-bed-${width}` })
  })), (width) => {
    const target = findBedroomLayout({ bedVariantId: `new-bed-${width}` });
    if (target) selectScenario(target.id);
  }, currentBed);

  const paxWidth = activeLayout.selection.paxVariantId.replace('pax-', '');
  addSelect(dimensions, 'PAX-Breite', paxWidth, ['100', '150', '175', '200'].map((width) => ({
    value: width,
    label: `${width} cm`,
    disabled: !findBedroomLayout({ paxVariantId: `pax-${width}` })
  })), (width) => {
    const target = findBedroomLayout({ paxVariantId: `pax-${width}` });
    if (target) selectScenario(target.id);
  });

  const paxAccessDepth = activeLayout.selection.paxAccessDepthCm ?? 45;
  const paxAccessOptions = [
    { value: '0', label: '0 cm · offen/Schiebetür, keine Reserve' },
    { value: '30', label: '30 cm · kompakte Zugriffsreserve' },
    { value: '45', label: '45 cm · offene Front (Standard)' },
    { value: '60', label: '60 cm · komfortabler Zugriff' }
  ].map((option) => ({
    ...option,
    disabled: !findBedroomLayout({ paxAccessDepthCm: Number(option.value) })
  }));
  addSelect(dimensions, 'Freiraum vor PAX', String(paxAccessDepth), paxAccessOptions, (depth) => {
    const target = findBedroomLayout({ paxAccessDepthCm: Number(depth) });
    if (target) selectScenario(target.id);
  }, false, true);

  if (!currentBed) dimensions.append(htmlEl('p', {}, 'Geschätztes Bettgestell: Matratzenbreite + 16 cm, Länge ca. 209 cm.'));

  const arrangementOptions = [
    { value: 'divider', label: 'Raumteiler quer' },
    { value: 'bath-wall-bed-shifted', label: 'PAX an Badwand' },
    { value: 'bath-wall-both-rotated', label: 'Beide gedreht' },
    { value: 'east-wall-wardrobe', label: 'PAX an Balkonwand' },
    { value: 'kitchen-wall-wardrobe', label: 'PAX an Küchenwand' }
  ].map((option) => ({
    ...option,
    disabled: !findArrangementLayout(option.value)
  }));
  addSelect(positions, 'Schlafbereich-Anordnung', activeLayout.selection.arrangementId, arrangementOptions, (arrangementId) => {
    const target = findArrangementLayout(arrangementId);
    if (target) selectScenario(target.id);
  }, false, true);

  const deskPlacementOptions = [
    { value: 'upper-loggia-corner', label: 'Oben an Loggia/Balkon' },
    { value: 'lower-balcony-corner', label: 'Unten an Balkon/Südwand' },
    { value: 'living-room-centre', label: 'Mitte im Wohnbereich' },
    { value: 'balcony-between-doors', label: 'An Balkonwand zwischen Türen' },
    { value: 'kitchen-balcony-corner', label: 'Im Küchen-/Balkoneck' }
  ].map((option) => ({
    ...option,
    disabled: !findBedroomLayout({ deskPlacementId: option.value })
  }));
  addSelect(positions, 'Schreibtischposition', activeLayout.selection.deskPlacementId, deskPlacementOptions, (deskPlacementId) => {
    const target = findBedroomLayout({ deskPlacementId });
    if (target) selectScenario(target.id);
  }, false, true);

  const minifridgePlacementOptions = [
    { value: 'endcap-extension', label: 'A · hinter der Endkappe' },
    { value: 'kitchen-back-wall', label: 'B · bündig zur Küchenrückwand' }
  ].map((option) => ({
    ...option,
    disabled: !findBedroomLayout({ minifridgePlacementId: option.value })
  }));
  addSelect(positions, 'Kühlschrankposition', activeLayout.selection.minifridgePlacementId, minifridgePlacementOptions, (minifridgePlacementId) => {
    const target = findBedroomLayout({ minifridgePlacementId });
    if (target) selectScenario(target.id);
  }, false, true);

  controls.append(dimensions, positions);
  return controls;
}

function renderFurnitureSummary(activeLayout) {
  const summary = htmlEl('div', { className: 'scenario-objects' });
  for (const object of activeLayout.objects) {
    const row = htmlEl('div', { className: 'scenario-object' });
    row.append(htmlEl('strong', {}, object.type === 'storage' ? object.name : object.render.label));
    if (object.modules) {
      const depthCm = activeLayout.selection.paxAccessDepthCm ?? 45;
      const accessText = depthCm === 0 ? 'keine zusätzliche Zugriffsreserve' : `${depthCm} cm Zugriffsreserve`;
      row.append(htmlEl('small', {}, `${object.modules.length} PAX-Module · Stellfläche ${object.dimensionsCm.width.toFixed(1)} × ${object.dimensionsCm.depth.toFixed(0)} cm · ${accessText}`));
    }
    else if (object.mattressCm) row.append(htmlEl('small', {}, `${object.estimateNote ? 'Geschätzte ' : ''}Stellfläche ${object.dimensionsCm.width} × ${object.dimensionsCm.depth} cm · Kopfseite markiert`));
    else if (object.type === 'storage') row.append(htmlEl('small', {}, `${object.dimensionsCm.width} × ${object.dimensionsCm.depth} × ${object.dimensionsCm.height} cm · Schubladenseite markiert`));
    else if (object.type === 'appliance') row.append(htmlEl('small', {}, `${object.dimensionsCm.width} × ${object.dimensionsCm.depth} × ${object.dimensionsCm.height} cm · Türseite markiert · ${object.accessDepthCm} cm Bedienzone`));
    else row.append(htmlEl('small', {}, `Stellfläche ${object.dimensionsCm.width} × ${object.dimensionsCm.depth} cm`));
    summary.append(row);
  }
  return summary;
}

function renderScenarioMetrics(evaluation) {
  const accessLabel = evaluation.bedPaxGapCm >= 60
    ? `${evaluation.bedPaxGapCm.toFixed(1)} cm · gut`
    : evaluation.bedPaxGapCm >= 45
      ? `${evaluation.bedPaxGapCm.toFixed(1)} cm · knapp`
      : `${evaluation.bedPaxGapCm.toFixed(1)} cm · zu eng`;
  const metrics = htmlEl('div', { className: 'scenario-metrics' });
  const entries = [
    ['Bewertung', `${evaluation.score.toFixed(1)} / 100`],
    ['Bett–PAX', accessLabel],
    ['PAX-Zugriffsreserve', `${evaluation.wardrobeAccessDepthCm} cm`],
    ['Freie Fläche', `ca. ${evaluation.freeFloorAreaM2.toFixed(1)} m²`],
    ['Loggia-Türen', `${evaluation.usableLoggiaDoors} von 2 · min. 1`]
  ];
  for (const [label, value] of entries) {
    const item = htmlEl('div', { className: 'scenario-metric' });
    item.append(htmlEl('small', {}, label));
    item.append(htmlEl('strong', {}, value));
    metrics.append(item);
  }
  return metrics;
}

function renderStatusPanel(apartment, furniture, activeLayout, evaluation, evaluations, doorResults, furnitureCollisions, svg) {
  const panel = htmlEl('aside', { className: 'status-panel' });
  panel.append(renderScenarioNavigation(furniture, activeLayout, evaluations));
  panel.append(renderBedroomControls(furniture, activeLayout));
  panel.append(renderDisplayControls(svg));
  panel.append(htmlEl('h2', {}, 'Aktuelles Szenario'));
  panel.append(htmlEl('div', { className: 'layout-name' }, activeLayout.name));
  const arrangement = htmlEl('div', { className: 'arrangement-summary' });
  arrangement.append(htmlEl('strong', {}, activeLayout.arrangementLabel ?? 'PAX quer als Raumteiler'));
  arrangement.append(htmlEl('small', {}, activeLayout.kitchenExposure === 'low'
    ? 'PAX-Rückwand zeigt zur Küche · geringere direkte Küchenexposition'
    : 'PAX-Öffnung zeigt stärker zum Wohnraum · Lüftung oder textiler Schutz sinnvoll'));
  panel.append(arrangement);
  const requiresEngineeredSupport = activeLayout.installationStatus === 'requires_engineered_solution';
  const validityClass = !evaluation.valid ? 'invalid' : requiresEngineeredSupport ? 'caution' : 'valid';
  const validityLabel = !evaluation.valid
    ? 'Diese Kombination passt geometrisch nicht'
    : requiresEngineeredSupport
      ? 'Nur geometrisch passend · Befestigung ungelöst'
      : 'Geometrisch und funktional nutzbar';
  const validity = htmlEl('div', { className: `scenario-validity ${validityClass}` });
  validity.append(htmlEl('span', { className: 'status-dot' }));
  validity.append(htmlEl('strong', {}, validityLabel));
  panel.append(validity);
  if (!evaluation.valid) {
    const invalid = htmlEl('div', { className: 'notice danger' });
    invalid.append(htmlEl('strong', {}, 'Warum sie nicht passt'));
    invalid.append(htmlEl('span', {}, evaluation.reasons.some((reason) => reason.includes('overlap'))
      ? 'Mindestens zwei Möbel überschneiden sich. Probiere eine andere Orientierung, Bett- oder PAX-Breite.'
      : evaluation.reasons.some((reason) => reason.includes('door'))
        ? 'Mindestens eine feste Türregel wird verletzt.'
        : 'Mindestens ein Möbelstück liegt außerhalb der geschätzten Wohnungsfläche.'));
    panel.append(invalid);
  }
  panel.append(renderScenarioMetrics(evaluation));
  panel.append(renderFurnitureSummary(activeLayout));

  const pax = activeLayout.objects.find((object) => object.requiresAnchoring);
  if (pax) {
    const wallCandidate = activeLayout.installationStatus === 'manufacturer_wall_mount_candidate';
    const anchoring = htmlEl('div', { className: `notice ${wallCandidate ? 'safety' : 'danger'}` });
    anchoring.append(htmlEl('strong', {}, wallCandidate ? 'Wandmontage grundsätzlich möglich' : 'Nicht freistehend verwenden'));
    anchoring.append(htmlEl('span', {}, activeLayout.recommendation ?? 'Vor dem Kauf ist eine sichere und fachlich geprüfte Verankerung erforderlich.'));
    panel.append(anchoring);
  }

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
    const policyText = result.door.policy === 'must_remain_usable'
      ? 'muss nutzbar bleiben'
      : result.door.policy === 'group_requirement'
        ? 'mindestens eine Tür dieser Gruppe muss frei bleiben'
        : 'darf blockiert werden';
    const openingPercent = Math.round(result.openingFraction * 100);
    const openingText = result.openingFraction < 1
      ? `${openingPercent} % öffnbar${result.blocked ? ` · begrenzt durch ${result.blockingObjects.join(', ')}` : ' · ausreichend'}`
      : '100 % öffnbar';
    row.append(htmlEl('small', {}, `${openingText} · ${policyText}`));
    list.append(row);
  }
  panel.append(list);

  const collision = htmlEl('div', { className: `collision-summary ${furnitureCollisions.length ? 'blocked' : 'clear'}` });
  collision.append(htmlEl('span', { className: 'status-dot' }));
  collision.append(htmlEl('strong', {}, furnitureCollisions.length ? `${furnitureCollisions.length} Möbelkollision(en)` : 'Keine Möbelkollisionen'));
  panel.append(collision);

  const notes = htmlEl('div', { className: 'layout-notes' });
  notes.append(htmlEl('h3', {}, 'Absicht dieses Layouts'));
  const ul = htmlEl('ul');
  activeLayout.notes.forEach((note) => ul.append(htmlEl('li', {}, note)));
  notes.append(ul);
  panel.append(notes);

  return panel;
}

function renderCalibrationControls(svg) {
  const controls = htmlEl('div', { className: 'calibration-controls' });
  const opacityControls = htmlEl('fieldset', { className: 'calibration-opacity-controls' });
  opacityControls.append(htmlEl('legend', {}, 'Kalibrierung'));

  const refLabel = htmlEl('label');
  refLabel.append(htmlEl('span', {}, 'Original'));
  const refRange = htmlEl('input', { type: 'range', min: '0', max: '1', step: '0.05', value: '0.55' });
  refRange.addEventListener('input', () => document.documentElement.style.setProperty('--reference-opacity', refRange.value));
  refLabel.append(refRange);
  opacityControls.append(refLabel);

  const vectorLabel = htmlEl('label');
  vectorLabel.append(htmlEl('span', {}, 'Vektor'));
  const vectorRange = htmlEl('input', { type: 'range', min: '0.1', max: '1', step: '0.05', value: '0.85' });
  vectorRange.addEventListener('input', () => document.documentElement.style.setProperty('--vector-opacity', vectorRange.value));
  vectorLabel.append(vectorRange);
  opacityControls.append(vectorLabel);

  const link = htmlEl('a', { href: `../${window.location.search}` }, 'Zur normalen Ansicht');
  opacityControls.append(link);
  controls.append(opacityControls, renderDisplayControls(svg));
  return controls;
}

async function main() {
  const root = document.querySelector('#app');
  try {
    const [apartmentSource, fixtures, fixedFurnishings, catalog, scenarioData, evaluations, constraints] = await Promise.all([
      loadJson('data/apartment.json'),
      loadJson('data/fixed-fixtures.json'),
      loadJson('data/fixed-furnishings.json'),
      loadJson('data/furniture-catalog.json'),
      loadJson('data/layout-scenarios.json'),
      loadJson('data/scenario-evaluations.json'),
      loadJson('data/layout-constraints.json')
    ]);
    const apartment = expandApartmentGeometry(apartmentSource);
    const requestedScenario = new URLSearchParams(window.location.search).get('scenario');
    const normalizedScenario = normalizeScenarioId(requestedScenario);
    const scenariosById = new Map(scenarioData.scenarios.map((scenario) => [scenario.id, scenario]));
    const validIds = new Set(evaluations.results.filter((result) => result.valid).map((result) => result.id));
    const requestedLayout = scenariosById.get(normalizedScenario);
    let selectedScenario = validIds.has(normalizedScenario) ? normalizedScenario : null;
    if (!selectedScenario && requestedLayout) {
      const requestedBed = requestedLayout.selection.bedVariantId;
      const requestedIsCurrent = requestedBed === 'current-bed-90';
      const requestedWidth = Number(requestedBed.replace('new-bed-', '')) || 90;
      const candidates = scenarioData.scenarios.filter((scenario) =>
        validIds.has(scenario.id) && scenario.selection.deskVariantId === requestedLayout.selection.deskVariantId
      );
      candidates.sort((first, second) => {
        const score = (scenario) => {
          const bed = scenario.selection.bedVariantId;
          const isCurrent = bed === 'current-bed-90';
          const width = Number(bed.replace('new-bed-', '')) || 90;
          return (scenario.selection.arrangementId === requestedLayout.selection.arrangementId ? 1000 : 0)
            + (scenario.selection.paxAccessDepthCm === requestedLayout.selection.paxAccessDepthCm ? 2000 : 0)
            + (scenario.selection.minifridgePlacementId === requestedLayout.selection.minifridgePlacementId ? 1500 : 0)
            + (scenario.selection.deskPlacementId === requestedLayout.selection.deskPlacementId ? 500 : 0)
            + (scenario.selection.paxVariantId === requestedLayout.selection.paxVariantId ? 100 : 0)
            + (isCurrent === requestedIsCurrent ? 20 : 0)
            - Math.abs(width - requestedWidth);
        };
        return score(second) - score(first);
      });
      selectedScenario = candidates[0]?.id ?? null;
    }
    selectedScenario ??= validIds.has(scenarioData.activeScenarioId)
      ? scenarioData.activeScenarioId
      : evaluations.rankedValidScenarioIds[0];
    if (requestedScenario && requestedScenario !== selectedScenario) {
      const canonicalUrl = new URL(window.location.href);
      canonicalUrl.searchParams.set('scenario', selectedScenario);
      window.history.replaceState(null, '', canonicalUrl);
    }
    const resolvedFurniture = resolveScenarioData(scenarioData, catalog, selectedScenario);
    const selectedLayout = resolvedFurniture.layouts.find((layout) => layout.id === selectedScenario);
    const fixedDeskVariantId = selectedLayout.selection.deskVariantId;
    const furniture = {
      ...resolvedFurniture,
      layouts: validLayoutsForDesk(resolvedFurniture.layouts, evaluations, fixedDeskVariantId),
      activeLayoutId: selectedScenario
    };
    const activeEvaluation = evaluations.results.find((result) => result.id === furniture.activeLayoutId);

    const header = htmlEl('header', { className: 'app-header' });
    const titleWrap = htmlEl('div');
    titleWrap.append(htmlEl('p', { className: 'eyebrow' }, 'Scaled Apartment Planner'));
    titleWrap.append(htmlEl('h1', {}, isCalibration ? 'Kalibrierungsansicht' : 'Wohnung 264 · Layout-Experiment'));
    header.append(titleWrap);
    const nav = htmlEl('nav');
    nav.append(htmlEl('a', { href: `${isCalibration ? '../' : './calibration/'}${window.location.search}` }, isCalibration ? 'Plan öffnen' : 'Kalibrierung öffnen'));
    header.append(nav);
    root.append(header);

    const workspace = htmlEl('main', { className: isCalibration ? 'workspace calibration-workspace' : 'workspace' });
    const canvas = htmlEl('section', { className: 'canvas-card reconstructed-card' });
    const rendered = buildSvg(apartment, fixtures, fixedFurnishings, furniture, constraints, activeEvaluation, isCalibration);
    if (isCalibration) root.append(renderCalibrationControls(rendered.svg));
    canvas.append(rendered.svg);
    workspace.append(canvas);

    if (!isCalibration) {
      workspace.append(renderStatusPanel(apartment, furniture, rendered.activeLayout, activeEvaluation, evaluations, rendered.doorResults, rendered.furnitureCollisions, rendered.svg));
    }

    root.append(workspace);

    const footer = htmlEl('footer', { className: 'app-footer' });
    footer.append(htmlEl('span', {}, 'Gebäudegeometrie, feste Einbauten und lose Möbel sind getrennte Datenebenen.'));
    footer.append(htmlEl('code', {}, `Szenario: ${rendered.activeLayout.id}`));
    root.append(footer);
  } catch (error) {
    console.error(error);
    root.append(htmlEl('div', { className: 'fatal-error' }, error.message));
  }
}

main();
