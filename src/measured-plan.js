const NS = 'http://www.w3.org/2000/svg';
const SCALE = 1.05;

function svgEl(name, attrs = {}, text = null) {
  const el = document.createElementNS(NS, name);
  for (const [key, value] of Object.entries(attrs)) el.setAttribute(key, String(value));
  if (text !== null) el.textContent = text;
  return el;
}

function htmlEl(name, attrs = {}, text = null) {
  const el = document.createElement(name);
  for (const [key, value] of Object.entries(attrs)) {
    if (key === 'className') el.className = value;
    else el.setAttribute(key, value);
  }
  if (text !== null) el.textContent = text;
  return el;
}

function line(svg, x1, y1, x2, y2, className = 'survey-wall') {
  svg.append(svgEl('line', { x1, y1, x2, y2, class: className }));
}

function dimension(svg, x1, y1, x2, y2, label, offset = 0) {
  const dx = x2 - x1;
  const dy = y2 - y1;
  const length = Math.hypot(dx, dy) || 1;
  const nx = (-dy / length) * offset;
  const ny = (dx / length) * offset;
  const ax = x1 + nx;
  const ay = y1 + ny;
  const bx = x2 + nx;
  const by = y2 + ny;
  line(svg, ax, ay, bx, by, 'survey-dimension-line');
  line(svg, ax - (dy / length) * 5, ay + (dx / length) * 5, ax + (dy / length) * 5, ay - (dx / length) * 5, 'survey-dimension-tick');
  line(svg, bx - (dy / length) * 5, by + (dx / length) * 5, bx + (dy / length) * 5, by - (dx / length) * 5, 'survey-dimension-tick');
  svg.append(svgEl('text', {
    x: (ax + bx) / 2,
    y: (ay + by) / 2 - 6,
    class: 'survey-dimension-label'
  }, label));
}

function drawRoom(svg, area) {
  const x = area.x;
  const y = area.y;
  const width = area.widthCm * SCALE;
  const depth = area.depthCm * SCALE;
  svg.append(svgEl('rect', { x, y, width, height: depth, class: 'survey-room' }));
  svg.append(svgEl('text', { x: x + width / 2, y: y + depth / 2, class: 'survey-room-label' }, area.name));
  dimension(svg, x, y, x + width, y, `${area.widthCm} cm`, -20);
  dimension(svg, x, y, x, y + depth, `${area.depthCm} cm`, 20);

  if (area.openingChainCm) {
    let cursor = x;
    for (const value of area.openingChainCm) {
      const next = cursor + value * SCALE;
      line(svg, cursor, y + depth, next, y + depth, 'survey-opening-segment');
      dimension(svg, cursor, y + depth, next, y + depth, `${value}`, 17);
      cursor = next;
    }
    const end = x + width;
    line(svg, cursor, y + depth, end, y + depth, 'survey-unresolved');
    dimension(svg, cursor, y + depth, end, y + depth, `${area.unassignedCm} offen`, 17);
  }
}

function chainPoints(area) {
  let x = area.x;
  let y = area.y;
  const points = [[x, y]];
  area.segmentsCm.forEach((segment, index) => {
    const distance = segment * SCALE;
    switch (area.directions[index]) {
      case 'left': x -= distance; break;
      case 'up': y -= distance; break;
      case 'down': y += distance; break;
      default: x += distance;
    }
    points.push([x, y]);
  });
  return points;
}

function drawChain(svg, area) {
  const points = area.kind === 'wall_chain'
    ? [[area.x, area.y], [area.x, area.y + area.segmentsCm[0] * SCALE]]
    : chainPoints(area);
  svg.append(svgEl('polyline', {
    points: points.map((point) => point.join(',')).join(' '),
    class: 'survey-wall-chain'
  }));
  points.slice(0, -1).forEach((point, index) => {
    const next = points[index + 1];
    const horizontal = point[1] === next[1];
    dimension(svg, point[0], point[1], next[0], next[1], `${area.segmentsCm[index]} cm`, horizontal ? -13 : 13);
  });
  svg.append(svgEl('text', { x: area.x, y: area.y - 18, class: 'survey-section-label' }, area.name));
}

function drawKitchen(svg, area) {
  const x = area.x;
  const y = area.y;
  const width = area.widthCm * SCALE;
  const depth = area.depthCm * SCALE;
  svg.append(svgEl('path', {
    d: `M ${x} ${y} V ${y + depth} H ${x + width} V ${y}`,
    class: 'survey-room-detail'
  }));
  svg.append(svgEl('text', { x: x + width / 2, y: y + depth / 2, class: 'survey-room-label' }, area.name));
  dimension(svg, x, y, x + width, y, `${area.widthCm} cm Durchgang`, -15);
}

export function buildMeasuredSurveySvg(survey) {
  const svg = svgEl('svg', {
    viewBox: '0 0 760 680',
    class: 'floorplan measured-floorplan',
    role: 'img',
    'aria-label': 'Maßstäbliche Aufmaß-Skizze der bei der Besichtigung gemessenen Teilbereiche'
  });
  svg.append(svgEl('text', { x: 38, y: 28, class: 'survey-title' }, 'Aufmaß · 1 Einheit = 1 cm'));
  svg.append(svgEl('text', { x: 38, y: 45, class: 'survey-subtitle' }, 'Durchgezogen = gemessen · gestrichelt = noch nicht eindeutig verbunden'));

  for (const area of survey.measuredAreas) {
    if (area.kind === 'room') drawRoom(svg, area);
    else if (area.kind === 'room_detail') drawKitchen(svg, area);
    else drawChain(svg, area);
  }
  return svg;
}

function confidenceText(confidence) {
  if (confidence === 'measured') return 'vor Ort gemessen';
  if (confidence === 'partially_measured') return 'teilweise gemessen';
  return 'Maßfolge gemessen, Zuordnung noch offen';
}

export function buildMeasuredSurveyPanel(survey, resolveAsset) {
  const panel = htmlEl('aside', { className: 'status-panel measured-panel' });
  panel.append(htmlEl('h2', {}, 'Grundrissbasis'));
  panel.append(htmlEl('div', { className: 'layout-name' }, 'Besichtigungsmaße · ohne Möbel'));
  const notice = htmlEl('div', { className: 'notice safety' });
  notice.append(htmlEl('strong', {}, 'Echte Maße, keine globale Bildskalierung'));
  notice.append(htmlEl('span', {}, survey.sourceNote));
  panel.append(notice);

  const list = htmlEl('div', { className: 'survey-area-list' });
  for (const area of survey.measuredAreas) {
    const details = htmlEl('details', { className: 'survey-area' });
    const summary = htmlEl('summary');
    summary.append(htmlEl('strong', {}, area.name));
    summary.append(htmlEl('small', {}, confidenceText(area.confidence)));
    details.append(summary);
    const ul = htmlEl('ul');
    area.dimensions.forEach((item) => ul.append(htmlEl('li', {}, item)));
    details.append(ul);
    list.append(details);
  }
  panel.append(list);

  const open = htmlEl('div', { className: 'notice warning' });
  open.append(htmlEl('strong', {}, 'Noch zu messen oder eindeutig zuzuordnen'));
  const openList = htmlEl('ul', { className: 'survey-open-list' });
  survey.openMeasurements.forEach((item) => openList.append(htmlEl('li', {}, item)));
  open.append(openList);
  panel.append(open);

  panel.append(htmlEl('h3', { className: 'survey-photo-heading' }, 'Besichtigungsfotos'));
  const gallery = htmlEl('div', { className: 'survey-gallery' });
  for (const photo of survey.photos) {
    const link = htmlEl('a', { href: resolveAsset(photo.file), target: '_blank', rel: 'noreferrer' });
    link.append(htmlEl('img', { src: resolveAsset(photo.file), alt: photo.label }));
    link.append(htmlEl('span', {}, photo.label));
    gallery.append(link);
  }
  panel.append(gallery);
  return panel;
}
