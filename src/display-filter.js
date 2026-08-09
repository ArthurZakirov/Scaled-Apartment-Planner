export const DISPLAY_OPTIONS = Object.freeze([
  Object.freeze({ id: 'labels', label: 'Raumtitel', selector: '.layer-labels' }),
  Object.freeze({ id: 'doors', label: 'Türschwenkflächen und -radien', selector: '.layer-doors' }),
  Object.freeze({ id: 'access', label: 'Bedien- und Zugriffszonen', selector: '.layer-access-zones' }),
  Object.freeze({ id: 'furniture', label: 'Möbel', selector: '.layer-furniture' })
]);

const DISPLAY_IDS = new Set(DISPLAY_OPTIONS.map((option) => option.id));

export function allDisplayLayers(visible = true) {
  return new Set(visible ? DISPLAY_OPTIONS.map((option) => option.id) : []);
}

export function parseDisplayState(searchParams) {
  const value = searchParams.get('display');
  if (value === null) return allDisplayLayers();
  if (value === 'none' || value === '') return allDisplayLayers(false);
  return new Set(value.split(',').filter((id) => DISPLAY_IDS.has(id)));
}

export function serializeDisplayState(visibleLayers) {
  const visible = DISPLAY_OPTIONS.filter((option) => visibleLayers.has(option.id)).map((option) => option.id);
  if (visible.length === DISPLAY_OPTIONS.length) return null;
  return visible.length ? visible.join(',') : 'none';
}

export function setDisplayStateInUrl(url, visibleLayers) {
  const nextUrl = new URL(url);
  const serialized = serializeDisplayState(visibleLayers);
  if (serialized === null) nextUrl.searchParams.delete('display');
  else nextUrl.searchParams.set('display', serialized);
  return nextUrl;
}

export function applyDisplayState(svg, visibleLayers) {
  for (const option of DISPLAY_OPTIONS) {
    const layer = svg.querySelector(option.selector);
    if (!layer) continue;
    const visible = visibleLayers.has(option.id);
    layer.classList.toggle('display-layer-hidden', !visible);
    layer.setAttribute('aria-hidden', String(!visible));
  }
}
