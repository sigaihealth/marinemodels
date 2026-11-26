# SIG.AI Ocean MCP

Connect a research agent to **https://ocean.sig.ai/api/mcp** using Streamable HTTP. The public server requires no account or API key. In Codex, run the following command and start a new session.

```sh
codex mcp add sigai-ocean --url https://ocean.sig.ai/api/mcp
```

Other MCP clients can use the same URL in their remote-server configuration. Clients negotiate the protocol version during initialization. Native clients can connect directly. Requests made by browser scripts must originate from the Ocean site.

The official MCP Registry lists the server as `io.github.sigaihealth/ocean`. [Registry listing](https://registry.modelcontextprotocol.io/?q=io.github.sigaihealth%2Focean)

## Research tools

| Tool | Example arguments | What the agent receives |
| --- | --- | --- |
| `list_datasets` | `{"query":"IFCB"}` | Matching collections, instruments, source links and available tool names. The same directory is available at the MCP resource `ocean://workspace/datasets`. |
| `search_models` | `{"lane":"ocean-physics","query":"GLONET"}` | Model records with inputs, licenses, evaluation protocols, access status and trial links where available. |
| `get_pioneer_observations` | `{"utc_date":"2026-02-01","limit":1}` | Co-located measurements and IFCB acquisition times from the Gianna replay, with units, quality flags and source archive links. |
| `get_glonet_forecast` | `{"reference_date":"2024-07-02","site":"central","depth_m":0.494025,"variable":"so"}` | Ten daily forecasts at the selected grid cell and depth, alongside GLO12 persistence. These are archived 2024 runs. |
| `get_pioneer_storm_scores` | `{}` | The latest published six-hour salinity verification, including model hash, observation cutoffs, paired hours, pending data and the published report. |
| `estimate_chlorophyll` | `{"rrs443":0.006,"rrs488":0.008,"rrs547":0.004}` | The NASA MODIS OC3M band-ratio estimate in mg/m³, coefficients and source. The inputs here are illustrative. |
| `classify_plankton` | `{"sample":"whoi"}` | The hosted 101-class model's three candidates, scores, model version, input checksum and source. This tool uses the shared ranking. |

Model and observation searches support `offset` and `limit`, with `next_offset` when more results are available. The schemas returned by `tools/list` include the supported lanes, forecast dates, depths, sites and variables.

For an image you have permission to process, pass `png_base64` instead of `sample`. Use plain padded base64 of one opaque grayscale or RGB PNG up to 2 MiB. The public examples are `early`, `late`, `whoi` and `pelgas`. Classification sends the image to SIG.AI for in-memory prediction. The agent client can retain its inputs or outputs. Training contributions are available separately through the browser. Model weights and private research storage stay on the hosting service. [Data and privacy](https://ocean.sig.ai/data-and-privacy.html#uploads)

## Run locally

From this directory, use Node 22.12 or later and npm.

```sh
npm ci
npm test
npm start
```

The local endpoint is `http://127.0.0.1:8787/api/mcp`. Catalogs, science calculations, archived forecasts and Gianna observations use the repository's published data. The classifier calls the fixed SIG.AI prediction endpoint. Storm verification reads the public results branch on each call and includes the retrieved record's SHA-256. Deploy the hosted function with the site's existing staging command in the [repository guide](../README.md).

For example, ask your agent to find the first February 1 Gianna sample, report its practical salinity and quality flag, and link its original IFCB bin. Or ask it to compare July GLONET salinity against persistence at the central surface grid cell and cite the dated source arrays.
