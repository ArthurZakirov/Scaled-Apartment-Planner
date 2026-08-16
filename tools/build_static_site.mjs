import { cp, mkdir, readFile, rm, writeFile } from 'node:fs/promises';
import { join } from 'node:path';

const root = process.cwd();
const dist = join(root, 'dist');
const client = join(dist, 'client');

const readJson = async (path) => JSON.parse(await readFile(join(root, path), 'utf8'));
const writeJson = async (path, value) => {
  await writeFile(join(client, path), `${JSON.stringify(value)}\n`, 'utf8');
};

await rm(dist, { recursive: true, force: true });
await mkdir(join(client, 'data'), { recursive: true });
await mkdir(join(client, 'src'), { recursive: true });
await mkdir(join(client, 'calibration'), { recursive: true });
await mkdir(join(dist, 'server'), { recursive: true });

const [scenarioData, evaluations] = await Promise.all([
  readJson('data/layout-scenarios.json'),
  readJson('data/scenario-evaluations.json')
]);
const activeScenario = scenarioData.scenarios.find((scenario) => scenario.id === scenarioData.activeScenarioId);
const hostedDeskVariantId = activeScenario.selection.deskVariantId;
const hostedScenarios = scenarioData.scenarios.filter(
  (scenario) => scenario.selection.deskVariantId === hostedDeskVariantId
);
const hostedIds = new Set(hostedScenarios.map((scenario) => scenario.id));
const hostedResults = evaluations.results.filter((result) => hostedIds.has(result.id));
const hostedValidIds = evaluations.rankedValidScenarioIds.filter((id) => hostedIds.has(id));

const staticFiles = [
  'index.html',
  'calibration/index.html',
  'src/app.js',
  'src/display-filter.js',
  'src/furniture.js',
  'src/geometry.js',
  'src/styles.css',
  'data/apartment.json',
  'data/fixed-fixtures.json',
  'data/fixed-furnishings.json',
  'data/furniture-catalog.json',
  'data/layout-constraints.json',
  'data/layout-policy.json'
];
for (const path of staticFiles) {
  await cp(join(root, path), join(client, path));
}

await writeJson('data/layout-scenarios.json', {
  ...scenarioData,
  scenarioCount: hostedScenarios.length,
  scenarios: hostedScenarios
});
await writeJson('data/scenario-evaluations.json', {
  ...evaluations,
  scenarioCount: hostedResults.length,
  validCount: hostedValidIds.length,
  rankedValidScenarioIds: hostedValidIds,
  results: hostedResults
});

await writeFile(join(dist, 'server/index.js'), `export default {
  async fetch(request, env) {
    return env.ASSETS.fetch(request);
  }
};
`, 'utf8');

console.log(`Built ${hostedScenarios.length} selectable ${hostedDeskVariantId} layouts (${hostedValidIds.length} without conflicts) for hosting.`);
