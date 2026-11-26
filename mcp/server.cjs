const {createHash} = require("node:crypto");
const {McpServer} = require("@modelcontextprotocol/sdk/server/mcp.js");
const {z} = require("zod");
const catalog = require("../site/assets/model-catalog.json");
const archive = require("../site/assets/glonet-midatlantic-2024.json");
const {pioneer} = require("../world-model/evidence.json");
const whoi = require("../site/assets/whoi-coscinodiscus-reference.json");
const pelgas = require("../site/assets/pelgas-chaetognatha.json");
const {oc3m} = require("../site/assets/oc3m.mjs");
const classifier = require("./classifier.cjs");

const origin = "https://ocean.sig.ai";
const scoresURL = "https://raw.githubusercontent.com/sigaihealth/marinemodels/pioneer-storm-scores/state.json";
const reportURL = "https://github.com/sigaihealth/marinemodels/blob/pioneer-storm-scores/REPORT.md";
const methodsURL = "https://github.com/sigaihealth/marinemodels/tree/main/world-model/pioneer-fixed-confirmation";
const lanes = new Map(catalog.lanes.map(lane => [lane.id, lane]));
const datasets = [
  {id: "pioneer-gianna", title: pioneer.name + " · Winter Storm Gianna", instrument: "IFCB, CTD, fluorometer and meteorology",
    source: pioneer.sources.station, workspace: origin + "/pioneer_playback.html", tool: "get_pioneer_observations"},
  {id: "oceanbench-glonet", title: archive.title, instrument: "Ocean model grids",
    source: "https://github.com/mercator-ocean/oceanbench", workspace: origin + "/try-forecast.html", tool: "get_glonet_forecast"},
  {id: "pioneer-storm-scores", title: "Frozen six-hour Pioneer salinity forecast verification", instrument: "CTD, current meter, waves and astronomical tides",
    source: reportURL, workspace: origin + "/world-model.html#forecast", tool: "get_pioneer_storm_scores"},
  {id: "whoi-nes", title: whoi.dataset, instrument: "IFCB", license: whoi.license,
    source: whoi.doi, workspace: origin + "/sigai-plankton.html", tool: "classify_plankton", sample: "whoi"},
  {id: "pelgas", title: pelgas.dataset, instrument: "ZooScan", license: pelgas.license,
    source: pelgas.doi, workspace: origin + "/sigai-plankton.html", tool: "classify_plankton", sample: "pelgas"},
  {id: "ventana-v4277", title: "MBARI DeepSea-MOT · ROV Ventana V4277", instrument: "ROV camera",
    source: "https://huggingface.co/datasets/MBARI-org/DeepSea-MOT", workspace: origin + "/v4277.html"}
];

function result(data) {
  return {structuredContent: data, content: [{type: "text", text: JSON.stringify(data)}]};
}
function search(text, query) {
  return query.trim().toLowerCase().split(/\s+/).every(word => text.toLowerCase().includes(word));
}

function createServer(fetcher = fetch) {
  const server = new McpServer({name: "sigai-ocean", version: "1.0.0"}, {
    instructions: "Cite source URLs and identify the instrument, site and dates. Model suggestions, archived forecasts and measured observations have different evidentiary status."
  });
  function tool(name, title, description, inputSchema, execute, openWorldHint = false) {
    server.registerTool(name, {title, description, inputSchema: z.strictObject(inputSchema),
      annotations: {readOnlyHint: true, destructiveHint: false, openWorldHint}},
    async args => result(await execute(args)));
  }
  const query = z.string().trim().max(120).default("");
  const pagination = {
    offset: z.number().int().min(0).default(0),
    limit: z.number().int().min(1).max(12).default(5)
  };
  function page(rows, offset, limit) {
    return {total: rows.length, offset, next_offset: offset + limit < rows.length ? offset + limit : null,
      records: rows.slice(offset, offset + limit)};
  }

  tool("list_datasets", "Find Ocean datasets", "Find public collections by title, instrument or ID, with sources and available Ocean tools.",
    {query}, ({query}) => ({datasets: datasets.filter(d => search([d.id, d.title, d.instrument].join(" "), query)),
      source: origin + "/collaborate.html#agent-access"}));

  tool("search_models", "Search Ocean models", "Find models and their licenses, availability, benchmarks and trial links within a scientific task lane.",
    {query, lane: z.enum(catalog.lanes.map(lane => lane.slug)).optional(), ...pagination}, ({query, lane, offset, limit}) => {
      const rows = catalog.models.filter(m => {
        const group = lanes.get(m.lane);
        return (!lane || lane === group.slug) && search([m.name, m.task, m.input, m.output, group.name, m.accessGroup].join(" "), query);
      }).map(m => {
        const group = lanes.get(m.lane);
        return {...m, lane: group.slug, workspace: origin + "/model-catalog.html#" + group.slug,
          ...(m.actionUrl ? {actionUrl: new URL(m.actionUrl, origin).href} : {})};
      });
      return {catalog_verified: catalog.verified, lanes: catalog.lanes.map(l => l.slug), ...page(rows, offset, limit),
        source: origin + "/assets/model-catalog.json"};
    });

  tool("get_pioneer_observations", "Read Pioneer storm observations", "Read Gianna acquisitions and their matched sensor values with original UTC times, quality flags and missing values. Filter by a UTC date or page through the six-day replay.",
    {utc_date: z.iso.date().optional(), ...pagination}, ({utc_date, offset, limit}) => {
      const rows = pioneer.samples.filter(s => !utc_date || s.time.startsWith(utc_date)).map(s => ({
        ...s, sample_url: pioneer.sampleUrlTemplate.replace("{binId}", s.binId)
      }));
      return {event: pioneer.event, station: pioneer.station, start_utc: pioneer.startUtc, end_exclusive_utc: pioneer.endExclusiveUtc,
        units: pioneer.units, qc: pioneer.qc, matching: pioneer.matching, interpretation: pioneer.interpretation,
        ...page(rows, offset, limit), sources: pioneer.sources, workspace: origin + "/pioneer_playback.html"};
    });

  tool("get_glonet_forecast", "Compare archived GLONET and persistence", "Return ten dated daily forecasts and the matched GLO12 persistence baseline from an archived OceanBench run. Depth is in metres.",
    {reference_date: z.enum(archive.forecasts.map(f => f.referenceDate)), site: z.enum(archive.sites.map(s => s.id)),
      depth_m: z.union(archive.depths.map(d => z.literal(d))), variable: z.enum(Object.keys(archive.variables))},
    ({reference_date, site, depth_m, variable}) => {
      const run = archive.forecasts.find(f => f.referenceDate === reference_date);
      const series = run.profiles[site][String(depth_m)][variable];
      return {title: archive.title, reference_date, site: archive.sites.find(s => s.id === site), depth_m,
        variable: archive.variables[variable].name, units: archive.variables[variable].units, grid: archive.grid,
        baseline: archive.baseline, time: archive.time, precision: archive.precision, provider: archive.provider,
        daily: run.dates.map((date, i) => ({date, lead_days: i + 1, forecast: series.forecast[i], persistence: series.persistence})),
        sources: run.sources, workspace: origin + "/try-forecast.html"};
    });

  tool("get_pioneer_storm_scores", "Read the latest published Pioneer storm scores", "Read the frozen six-hour salinity model's latest published verification, including paired hours, observations still missing and gain over persistence.",
    {}, async () => {
      const response = await fetcher(scoresURL, {redirect: "error", cache: "no-store", signal: AbortSignal.timeout(9000)});
      if (!response.ok) throw new Error("The published verification record is temporarily unavailable.");
      const raw = await response.text();
      const state = JSON.parse(raw);
      if (!Array.isArray(state.storms) || !state.model_sha256 || !state.ctd_through || typeof state.study_complete !== "boolean") {
        throw new Error("The published verification record has an unexpected format.");
      }
      return {target: "Practical salinity (PSS-78, dimensionless)", lead_hours: 6,
        gain_definition: "Persistence MAE minus frozen-model MAE on paired observations. Positive gain favors the model.",
        ...state, retrieved_at_utc: new Date().toISOString(), record_sha256: createHash("sha256").update(raw).digest("hex"),
        source: scoresURL, report: reportURL, methods: methodsURL};
    }, true);

  tool("estimate_chlorophyll", "Estimate chlorophyll from MODIS reflectance", "Calculate NASA's R2022 OC3M band-ratio estimate from three remote-sensing reflectances in inverse steradians.",
    {rrs443: z.number(), rrs488: z.number(), rrs547: z.number()}, ({rrs443, rrs488, rrs547}) => {
      const value = oc3m([rrs443, rrs488, rrs547]);
      if (value.error) throw new Error(value.error);
      return {...value.record, input_origin: "caller-supplied reflectance", source: origin + "/try-ocean-color.html",
        reference: "https://oceandata.sci.gsfc.nasa.gov/files/atbd/atbd-obdaac-chlorophyll-a.pdf"};
    });

  tool("classify_plankton", "Classify one plankton crop", "Send one public example or one permitted PNG to SIG.AI's hosted shared 101-class classifier. It processes the image in memory and returns three provisional candidates. The call does not contribute the image for training.",
    classifier.inputSchema, args => classifier.classify(args, fetcher), true);

  const resourceURI = "ocean://workspace/datasets";
  server.registerResource("datasets", resourceURI, {title: "Ocean research datasets", mimeType: "application/json",
    description: "Dataset sources and the Ocean tools that can use them."}, async () => ({
    contents: [{uri: resourceURI, mimeType: "application/json", text: JSON.stringify(datasets)}]
  }));
  return server;
}
module.exports = {createServer};
