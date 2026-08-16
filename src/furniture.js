function indexFamilies(catalog) {
  return new Map(catalog.families.map((family) => [family.id, family]));
}

export function normalizeScenarioId(scenarioId) {
  return scenarioId
    ?.replace(/pax-(150|175|200)-low/, 'pax-$1')
    .replace(/malm-(140|160|180)/, 'new-bed-$1') ?? null;
}

function resolveScenarioObject(placement, families) {
  const family = families.get(placement.templateId);
  if (!family) throw new Error(`Unknown furniture template: ${placement.templateId}`);
  const variant = family.variants.find((item) => item.id === placement.variantId);
  if (!variant) throw new Error(`Unknown variant ${placement.variantId} for ${family.id}`);

  const resolved = {
    id: placement.id,
    templateId: family.id,
    variantId: variant.id,
    type: family.type,
    name: variant.label,
    sourceUrl: variant.sourceUrl ?? family.sourceUrl ?? null,
    confidence: variant.confidence ?? family.confidence,
    dimensionsCm: structuredClone(variant.dimensionsCm),
    positionPx: structuredClone(placement.positionPx),
    render: structuredClone(variant.render)
  };

  for (const key of ['mattressCm', 'modules', 'heightRangeCm']) {
    if (variant[key] !== undefined) resolved[key] = structuredClone(variant[key]);
  }
  for (const key of ['requiresAnchoring', 'safetyNote', 'doorType', 'planningDepthCm', 'estimateNote', 'headEdge', 'accessEdge', 'accessLabel', 'accessDepthCm', 'bodyDimensionsCm', 'doorSweepRadiusCm', 'doorOpeningDegrees', 'planningNote']) {
    if (family[key] !== undefined) resolved[key] = structuredClone(family[key]);
  }
  if (placement.intentionalDoorBlocks) {
    resolved.intentionalDoorBlocks = [...placement.intentionalDoorBlocks];
  }
  return resolved;
}

export function resolveScenarioData(scenarioData, catalog, selectedScenarioId = null) {
  const families = indexFamilies(catalog);
  const layouts = scenarioData.scenarios.map((scenario) => ({
    ...structuredClone(scenario),
    objects: scenario.objects.map((placement) => resolveScenarioObject(placement, families))
  }));
  const canonicalScenarioId = normalizeScenarioId(selectedScenarioId);
  const requested = canonicalScenarioId && layouts.some((layout) => layout.id === canonicalScenarioId)
    ? canonicalScenarioId
    : scenarioData.activeScenarioId;
  return { activeLayoutId: requested, layouts };
}

export function layoutsForDesk(layouts, deskVariantId) {
  return layouts.filter((layout) => layout.selection.deskVariantId === deskVariantId);
}

// Backward-compatible export for old imports. User-facing layouts intentionally
// include invalid evaluations so the user can inspect and challenge the rule.
export function validLayoutsForDesk(layouts, _evaluations, deskVariantId) {
  return layoutsForDesk(layouts, deskVariantId);
}

export function evaluationSummary(evaluation) {
  if (!evaluation || evaluation.valid) return null;
  const reasons = evaluation.reasons ?? [];
  const wallLimit = reasons.find((reason) => reason.includes('exceeds the') && reason.includes('wall segment'));
  if (wallLimit) {
    const maximum = wallLimit.match(/exceeds the ([\d.]+) cm/)?.[1];
    const selected = evaluation.id.match(/pax-(100|150|175|200)/)?.[1];
    return selected && maximum ? `PAX ${selected} cm > Wand ${maximum} cm` : 'PAX länger als Wandabschnitt';
  }
  if (reasons.some((reason) => reason.includes('overlap'))) return 'Möbel überschneiden sich';
  if (reasons.some((reason) => reason.includes('door') || reason.includes('Door'))) return 'Türnutzung eingeschränkt';
  if (reasons.some((reason) => reason.includes('access') || reason.includes('work zone'))) return 'Bedien- oder Arbeitszone blockiert';
  if (reasons.some((reason) => reason.includes('interior') || reason.includes('wall'))) return 'außerhalb der nutzbaren Innenkontur';
  return 'Konflikt laut aktueller Prüfung';
}

export function formatEvaluationReason(reason) {
  const names = {
    'ikea-pax-divider': 'PAX',
    'sleeping-bed': 'Bett',
    'owned-bedside-cabinet': 'Kommode',
    'vernal-l-desk': 'VERNAL-Schreibtisch',
    'kesser-minifridge': 'KESSER-Kühlschrank',
    'bosch-kgn36vict': 'Bosch-Kühlschrank',
    'door-balcony-upper': 'oberen Balkontür',
    'door-balcony-lower': 'unteren Balkontür',
    'door-loggia-bedroom': 'Loggiatür im Schlafbereich',
    'door-loggia-living': 'Loggiatür im Wohnbereich',
    'kitchen-bottom-run': 'untere Küchenzeile',
    'kitchen-return': 'Küchenrücklauf',
    'kitchen-hob': 'Kochfeld',
    'kitchen-chair-lower': 'unterer Küchenstuhl'
  };
  const readable = (id) => names[id] ?? id;
  const wallLimit = reason.match(/Wardrobe .* exceeds the ([\d.]+) cm fixed balcony-wall segment\./);
  if (wallLimit) return `Der PAX ist länger als der verfügbare ${wallLimit[1]}-cm-Wandabschnitt. Wähle für diese Position PAX 150 cm.`;
  const overlap = reason.match(/Furniture overlap: (.+?) ↔ (.+?) \([\d.]+px²\)\./);
  if (overlap) return `${readable(overlap[1])} und ${readable(overlap[2])} überschneiden sich physisch.`;
  const outside = reason.match(/(.+) leaves the approximate interior\./);
  if (outside) return `${readable(outside[1].replace(/^Furniture /, ''))} ragt aus der geschätzten nutzbaren Innenkontur.`;
  const accessOutside = reason.match(/(.+) access for (.+) leaves the apartment interior\./);
  if (accessOutside) return `Die Bedienzone von ${readable(accessOutside[2])} ragt aus der Wohnung.`;
  const accessBlocked = reason.match(/(.+) access for (.+) is blocked by (.+)\./);
  if (accessBlocked) return `Die Bedienzone von ${readable(accessBlocked[2])} wird durch ${readable(accessBlocked[3].replace(/^fixed fixture /, ''))} blockiert.`;
  const wardrobeBlocked = reason.match(/Wardrobe access is blocked by (.+)\./);
  if (wardrobeBlocked) return `Der Zugriff vor dem PAX wird durch ${readable(wardrobeBlocked[1])} blockiert.`;
  const wardrobeDoor = reason.match(/Wardrobe access conflicts with (.+)\./);
  if (wardrobeDoor) return `Die PAX-Zugriffsfläche überschneidet den Schwenkbereich der ${readable(wardrobeDoor[1])}.`;
  const deskBlocked = reason.match(/Desk chair\/work zone is blocked by (.+)\./);
  if (deskBlocked) return `Die Stuhl- und Arbeitszone des VERNAL wird durch ${readable(deskBlocked[1])} blockiert.`;
  const fixedOverlap = reason.match(/Furniture (.+) overlaps fixed (?:fixture|furnishing) (.+)\./);
  if (fixedOverlap) return `${readable(fixedOverlap[1])} überschneidet ${readable(fixedOverlap[2])}.`;
  if (reason === 'At least one Loggia door must remain usable.') return 'Mindestens eine der beiden Loggiatüren muss als Durchgang nutzbar bleiben.';
  if (reason === 'At least one Balkon door must remain usable.') return 'Mindestens eine der beiden Balkontüren muss als Durchgang nutzbar bleiben.';
  const door = reason.match(/Door (.+) opens only to ([\d.]+)%/);
  if (door) return `${readable(door[1])} lässt sich nur zu ${door[2]} % öffnen.`;
  return reason;
}

export function findLayoutForSelection(layouts, activeLayout, overrides) {
  const selection = { ...activeLayout.selection, ...overrides };
  return layouts.find((layout) =>
    layout.selection.arrangementId === selection.arrangementId &&
    layout.selection.bedVariantId === selection.bedVariantId &&
    layout.selection.paxVariantId === selection.paxVariantId &&
    layout.selection.paxAccessDepthCm === selection.paxAccessDepthCm &&
    layout.selection.deskVariantId === selection.deskVariantId &&
    layout.selection.deskPlacementId === selection.deskPlacementId &&
    layout.selection.minifridgePlacementId === selection.minifridgePlacementId &&
    layout.selection.fridgeVariantId === selection.fridgeVariantId
  );
}

export function findLayoutForArrangement(layouts, activeLayout, arrangementId) {
  const candidates = layouts.filter((layout) => (
    layout.selection.arrangementId === arrangementId
    && layout.selection.bedVariantId === activeLayout.selection.bedVariantId
    && layout.selection.paxVariantId === activeLayout.selection.paxVariantId
    && layout.selection.deskVariantId === activeLayout.selection.deskVariantId
  ));
  return candidates.sort((first, second) => {
    const score = (layout) => (
      (layout.selection.paxAccessDepthCm === activeLayout.selection.paxAccessDepthCm ? 100 : 0)
      + (layout.selection.deskPlacementId === activeLayout.selection.deskPlacementId ? 20 : 0)
      + (layout.selection.minifridgePlacementId === activeLayout.selection.minifridgePlacementId ? 10 : 0)
      + (layout.selection.fridgeVariantId === activeLayout.selection.fridgeVariantId ? 5 : 0)
      - Math.abs(layout.selection.paxAccessDepthCm - activeLayout.selection.paxAccessDepthCm) / 10
    );
    return score(second) - score(first);
  })[0];
}

const SELECTION_AXES = [
  'arrangementId',
  'bedVariantId',
  'paxVariantId',
  'paxAccessDepthCm',
  'deskPlacementId',
  'minifridgePlacementId',
  'fridgeVariantId'
];

export function recommendAlternativeLayouts(layouts, evaluations, activeLayout, limit = 3) {
  const evaluationById = new Map(evaluations.results.map((item) => [item.id, item]));
  return layouts
    .filter((layout) => evaluationById.get(layout.id)?.valid)
    .map((layout) => ({
      layout,
      evaluation: evaluationById.get(layout.id),
      changedAxes: SELECTION_AXES.filter((axis) => layout.selection[axis] !== activeLayout.selection[axis])
    }))
    .filter((candidate) => candidate.changedAxes.length > 0)
    .sort((first, second) => (
      first.changedAxes.length - second.changedAxes.length
      || second.evaluation.score - first.evaluation.score
      || first.layout.id.localeCompare(second.layout.id)
    ))
    .slice(0, limit);
}
