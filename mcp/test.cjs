const {after, before, test} = require("node:test");
const assert = require("node:assert/strict");
const {createServer} = require("node:http");
const {createHash} = require("node:crypto");
const {readFileSync} = require("node:fs");
const {Client} = require("@modelcontextprotocol/sdk/client/index.js");
const {StreamableHTTPClientTransport} = require("@modelcontextprotocol/sdk/client/streamableHttp.js");
const {makeHandler} = require("./handler.cjs");
const {samples, sampleHashes} = require("../site/assets/plankton-examples.mjs");
const catalog = require("../site/assets/model-catalog.json");
const archive = require("../site/assets/glonet-midatlantic-2024.json");
const {pioneer} = require("../world-model/evidence.json");

const example = readFileSync(require.resolve("../site/assets/whoi-coscinodiscus-reference.png"));
const upstream = [];
const state = {model_sha256: "a".repeat(64), ctd_through: "2026-11-25T04:00:00Z", storms: [{paired: 20}], study_complete: false};
async function fixtureFetch(url, opts) {
  upstream.push({url, method: opts.method || "GET"});
  if (url === "https://ocean.sig.ai/assets/whoi-coscinodiscus-reference.png") return new Response(example);
  if (url === "https://ocean.sig.ai/api/plankton/predict") {
    assert.deepEqual(Buffer.from(opts.body), example);
    assert.equal(opts.method, "POST");
    assert.equal(opts.headers["Content-Type"], "image/png");
    return Response.json({model: "SIG.AI Plankton Classifier", version: "fixture", score_type: "softmax",
      image_sha256: sampleHashes.whoi, candidates: [{label: "one", score: 0.6}, {label: "two", score: 0.3}, {label: "three", score: 0.1}],
      extra_private_field: "must not be returned"});
  }
  if (url === "https://raw.githubusercontent.com/sigaihealth/marinemodels/pioneer-storm-scores/state.json") return Response.json(state);
  throw new Error("Unexpected upstream route");
}

let http, url, client;
before(async () => {
  http = createServer(makeHandler(fixtureFetch));
  await new Promise(resolve => http.listen(0, "127.0.0.1", resolve));
  url = new URL("http://127.0.0.1:" + http.address().port + "/api/mcp");
  client = new Client({name: "ocean-integration-test", version: "1.0"});
  await client.connect(new StreamableHTTPClientTransport(url));
});
after(async () => {
  if (client) await client.close();
  if (http) await new Promise(resolve => http.close(resolve));
});
async function call(name, args = {}) {
  const response = await client.callTool({name, arguments: args});
  assert.ok(!response.isError, response.content[0]?.text);
  assert.deepEqual(JSON.parse(response.content[0].text), response.structuredContent);
  return response.structuredContent;
}

test("MCP handshake, tool discovery, dataset directory and source links", async () => {
  const {tools} = await client.listTools();
  assert.equal(tools.length, 8);
  const {resources} = await client.listResources();
  const data = JSON.parse((await client.readResource({uri: resources[0].uri})).contents[0].text);
  assert.deepEqual(data, (await call("list_datasets")).datasets);
  assert.deepEqual((await call("list_datasets", {query: "ZooScan"})).datasets.map(d => d.id), ["pelgas"]);
});

test("model search keeps lanes, access and trial links, with repeatable pages", async () => {
  const first = await call("search_models", {limit: 1});
  const second = await call("search_models", {offset: first.next_offset, limit: 1});
  assert.equal(first.total, catalog.models.length);
  assert.notEqual(first.records[0].name, second.records[0].name);
  const glonet = await call("search_models", {lane: "ocean-physics", query: "GLONET"});
  const record = glonet.records.find(r => r.name === "GLONET");
  assert.equal(record.source, catalog.models.find(m => m.name === "GLONET").source);
  assert.equal(record.actionUrl, "https://ocean.sig.ai/try-forecast.html");
});

test("Gianna replay retains sensor times, QC and missing wind, including empty dates", async () => {
  const day = await call("get_pioneer_observations", {utc_date: "2026-02-01", limit: 1});
  const {sample_url, ...row} = day.records[0];
  assert.deepEqual(row, pioneer.samples.find(r => r.time.startsWith("2026-02-01")));
  assert.equal(row.windMs, null);
  assert.ok(sample_url.includes(row.binId));
  assert.deepEqual((await call("get_pioneer_observations", {utc_date: "2000-01-01"})).records, []);
});

test("archived GLONET series matches the exact native levels, dates and baseline", async () => {
  const params = {reference_date: "2024-07-02", site: "central", depth_m: 0.494025, variable: "so"};
  const data = await call("get_glonet_forecast", params);
  const run = archive.forecasts.find(f => f.referenceDate === params.reference_date);
  const series = run.profiles.central["0.494025"].so;
  assert.deepEqual(data.daily.map(row => row.date), run.dates);
  assert.deepEqual(data.daily.map(row => row.forecast), series.forecast);
  assert.ok(data.daily.every(row => row.persistence === series.persistence));
  assert.equal(data.units, "dimensionless");
  assert.equal((await client.callTool({name: "get_glonet_forecast", arguments: {...params, depth_m: 100}})).isError, true);
});

test("frozen scores report observation cutoffs and checksum of the exact source", async () => {
  const result = await call("get_pioneer_storm_scores");
  assert.deepEqual(result.storms, state.storms);
  assert.equal(result.ctd_through, state.ctd_through);
  assert.equal(result.record_sha256, createHash("sha256").update(JSON.stringify(state)).digest("hex"));
});

test("OC3M covers valid reflectance, ties and the strict ratio boundary", async () => {
  const equal = await call("estimate_chlorophyll", {rrs443: 0.004, rrs488: 0.004, rrs547: 0.004});
  assert.equal(equal.chlorophyll_a_mg_m3, 10 ** 0.26294);
  assert.deepEqual(equal.selected_blue_wavelengths_nm, [443, 488]);
  const edge = await client.callTool({name: "estimate_chlorophyll", arguments: {rrs443: 30, rrs488: 3, rrs547: 1}});
  assert.equal(edge.isError, true);
});

test("single PNG inference uses only the prediction service and never echoes image bytes", async () => {
  const before = upstream.length;
  const sample = await call("classify_plankton", {sample: "whoi"});
  const own = await call("classify_plankton", {png_base64: example.toString("base64")});
  assert.equal(sample.image_sha256, sampleHashes.whoi);
  assert.equal(sample.input.roi, samples.whoi.roi);
  assert.deepEqual(sample.candidates, own.candidates);
  assert.equal(own.extra_private_field, undefined);
  assert.ok(!JSON.stringify(own).includes(example.toString("base64")));
  assert.deepEqual(upstream.slice(before).map(r => r.url), [
    "https://ocean.sig.ai/assets/whoi-coscinodiscus-reference.png",
    "https://ocean.sig.ai/api/plankton/predict", "https://ocean.sig.ai/api/plankton/predict"]);
  for (const args of [{}, {sample: "whoi", png_base64: "eA=="}, {png_base64: "eA=="}, {url: "https://example.org/crop.png"}]) {
    assert.equal((await client.callTool({name: "classify_plankton", arguments: args})).isError, true);
  }
  assert.equal(upstream.length, before + 3);
});

test("HTTP endpoint rejects unsupported methods and unrelated browser origins", async () => {
  assert.equal((await fetch(url)).status, 405);
  const rejected = await fetch(url, {method: "POST", headers: {origin: "https://example.org"}});
  assert.equal(rejected.status, 403);
  assert.match(rejected.headers.get("cache-control"), /no-store/);
});

test("source atlas search filters by kind, licence and link status, and pages repeatably", async () => {
  const atlas = require("../site/assets/ocean-sources.json");
  const all = await call("search_sources", {limit: 12});
  assert.equal(all.total, atlas.length);
  assert.ok(all.lanes.includes("plankton-imaging"));
  const ifcb = await call("search_sources", {query: "IFCB", kind: "dataset", licence: "open", limit: 12});
  assert.ok(ifcb.total > 0);
  for (const r of ifcb.records) {
    assert.equal(r.kind, "dataset");
    assert.equal(r.licence_group, "Open");
    assert.match(r.workspace, /^https:\/\/ocean\.sig\.ai\/ocean-sources\.html#/);
  }
  const broken = await call("search_sources", {link_status: "broken", limit: 12});
  assert.equal(broken.total, atlas.filter(s => s.check?.status === "broken").length);
  const next = await call("search_sources", {offset: 5, limit: 5});
  assert.equal(next.records[0].name, (await call("search_sources", {limit: 12})).records[5].name);
  const summary = JSON.parse((await client.readResource({uri: "ocean://workspace/sources"})).contents[0].text);
  assert.equal(summary.total, atlas.length);
  assert.equal(summary.lanes.reduce((n, lane) => n + lane.count, 0), atlas.length);
});
