function offsetNormal(start, end, depthPx, offsetSide) {
  const dx = end[0] - start[0];
  const dy = end[1] - start[1];
  const length = Math.hypot(dx, dy);
  if (!Number.isFinite(length) || length === 0) {
    throw new Error('Parametric wall profile requires a non-zero baseline.');
  }

  const direction = offsetSide === 'left' ? -1 : 1;
  return [direction * (-dy / length) * depthPx, direction * (dx / length) * depthPx];
}

export function deriveRectangularWallProfile(profile) {
  const start = [...profile.baselineStart];
  const end = [...profile.baselineEnd];
  const [offsetX, offsetY] = offsetNormal(start, end, profile.depthPx, profile.offsetSide);
  const farStart = [start[0] + offsetX, start[1] + offsetY];
  const farEnd = [end[0] + offsetX, end[1] + offsetY];
  const common = { kind: profile.kind, derivedFrom: profile.id };

  return {
    niche: {
      id: profile.nicheId,
      type: profile.nicheType,
      points: [start, end, farEnd, farStart],
      confidence: profile.confidence,
      note: profile.note,
      derivedFrom: profile.id
    },
    walls: [
      {
        ...common,
        id: profile.wallIds.baseline,
        start,
        end,
        thicknessPx: profile.baselineThicknessPx
      },
      {
        ...common,
        id: profile.wallIds.endCap,
        start: end,
        end: farEnd,
        thicknessPx: profile.wallThicknessPx
      },
      {
        ...common,
        id: profile.wallIds.farSide,
        start: farEnd,
        end: farStart,
        thicknessPx: profile.wallThicknessPx
      }
    ]
  };
}

export function expandApartmentGeometry(apartment) {
  const walls = [...apartment.walls];
  const niches = [...(apartment.niches ?? [])];

  for (const profile of apartment.wallProfiles ?? []) {
    const derived = deriveRectangularWallProfile(profile);
    walls.push(...derived.walls);
    niches.push(derived.niche);
  }

  return { ...apartment, walls, niches };
}
