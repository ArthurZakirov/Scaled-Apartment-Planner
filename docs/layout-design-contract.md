# Layout design contract

## Purpose

The planner is an exploratory decision tool, not a gatekeeper. It must faithfully render what the user selected and then explain whether the result is recommended, usable with trade-offs, not recommended, or dimensionally impossible.

## Separation of responsibilities

1. **Scenario generator** creates every supported combination of independent selection axes.
2. **Layout renderer** displays the exact requested combination without replacing unrelated selections.
3. **Constraint evaluator** measures physical overlaps, boundaries, door usability, operating zones, and circulation.
4. **UI adviser** translates those measurements into concrete explanations and visual warnings.
5. **Hard blockers** are reserved for combinations that cannot be represented from the product and wall dimensions at all.

## Interaction rules

- Every generated option remains selectable, even when its current evaluation is invalid.
- A selection changes only its own axis.
- Invalid URLs remain on the requested scenario instead of redirecting to a nearby valid one.
- Dropdowns may annotate a choice as `Konflikt anzeigen`, but must not disable it.
- The plan highlights affected furniture or operating zones in red.
- The status panel lists the evaluator's concrete reasons; generic `nicht passend` text is insufficient.
- A newly added configuration may not make a previously reachable scenario unreachable.

## Affordance-aware validation

Validation models ordinary use rather than rectangle packing alone:

- entering and leaving through required doors;
- opening furniture, drawers, and appliances in their actual direction;
- reaching storage and using desk/table chair zones;
- walking between functional zones;
- allowing mutually exclusive door swings to overlap when simultaneous operation is unnecessary;
- preferring wall contact and useful circulation when several placements are possible.

Exact personal tolerances remain explicit data. Defaults are recommendations and must be explained rather than disguised as immutable geometry.

## Regression contract

Automated checks must prove that:

- every generated scenario can be selected by URL;
- every control axis can reach its generated alternatives without mutating another axis;
- invalid scenarios remain present in the user-facing scenario set;
- every invalid evaluation has at least one concrete reason;
- valid/recommended scenarios continue satisfying the physical rules;
- canonical layouts receive visual inspection after geometry changes.
