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
  for (const key of ['requiresAnchoring', 'safetyNote', 'doorType', 'planningDepthCm', 'estimateNote', 'headEdge', 'accessEdge', 'accessLabel', 'accessDepthCm']) {
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

export function validLayoutsForDesk(layouts, evaluations, deskVariantId) {
  const validIds = new Set(evaluations.results.filter((result) => result.valid).map((result) => result.id));
  return layouts.filter((layout) =>
    layout.selection.deskVariantId === deskVariantId && validIds.has(layout.id)
  );
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
    layout.selection.minifridgePlacementId === selection.minifridgePlacementId
  );
}

export function findLayoutForArrangement(layouts, activeLayout, arrangementId) {
  return layouts.find((layout) => (
    layout.selection.arrangementId === arrangementId
    && layout.selection.bedVariantId === activeLayout.selection.bedVariantId
    && layout.selection.paxVariantId === activeLayout.selection.paxVariantId
    && layout.selection.paxAccessDepthCm === activeLayout.selection.paxAccessDepthCm
    && layout.selection.deskVariantId === activeLayout.selection.deskVariantId
    && layout.selection.minifridgePlacementId === activeLayout.selection.minifridgePlacementId
  ));
}
