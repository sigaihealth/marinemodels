# Marine Models

Marine Models explores how open ocean observations can support local models and digital twins. The first pilot replays Winter Storm Gianna at OOI's Pioneer Mid-Atlantic Bight Central Surface Mooring (`CP10CNSM`) off North Carolina. The [research brief](docs/ocean_digital_twin_research.md) covers five model ideas, complementary datasets, and the validation questions each project would need to answer.

## Run the Pioneer event replay

The replay uses Python 3.10 or newer and public OOI ERDDAP endpoints. Clone the repository and run the replay from a local shell or the OOI JupyterHub terminal.

```sh
git clone https://github.com/sigaihealth/marinemodels.git
cd marinemodels
python3 ooi_replay.py --output-dir ../pioneer-gianna
```

To keep the output in your JupyterHub data directory, use `--output-dir "$HOME/data/pioneer-gianna"`. Choose a new output directory for each run. The default replay window runs from January 29, 2026 at 00:00 UTC up to February 4 at 00:00 UTC. Set `--start` and `--end` to UTC dates to request another window of up to 31 days. The start date is inclusive and the end date is exclusive.

The pilot brings together IFCB image-region counts and sampled volume, fluorometer chlorophyll, CTD salinity, and buoy air pressure. It uses recovered observations and telemetry to align measurements in time for a historical replay. IFCB image regions per milliliter can include particles. Images are available after recovery through OOI’s IFCB archive for visual comparison and future image models. [OOI’s Gianna case study and image links](https://oceanobservatories.org/2026/09/ooi-plankton-imagery-and-co-located-environmental-data-now-ready-for-analysis/)

- `plims.csv`, `fluorometer.csv`, `ctd.csv`, and `meteorology.csv` contain source observations, timestamps, and aggregate QC flags.
- `replay.csv` contains hourly UTC medians, counts of contributing observations, and counts of contributing flag-2 observations. Values with flag 1 (pass) or 2 (not evaluated) can contribute. Missing observations produce blank values and are never interpolated.
- `summary.json` records the exact source queries, units, coverage, QC counts, platform DOI, and retrieval time. A window with no observations eligible for the replay returns an error.

## Research directions

- Compare persistence against sensor-only predictions and then test whether earlier image features improve accuracy on held-out deployments. Use data availability timestamps before evaluating a live forecast.
- Use the Oregon or Washington shelf for a separate near-bottom oxygen forecast. Validate against OOI measurements and compare with regional forecasts and gliders where time and depth overlap.
- Use CoastWatch, NASA PACE, NDBC, IOOS, and regional model products for spatial and weather context. The research brief links the source datasets and explains where their footprints and time coverage differ.

## Data attribution

The source data are from the NSF Ocean Observatories Initiative, funded under NSF Cooperative Agreement No. 2244833 and managed by the Woods Hole Oceanographic Institution OOI Program Office. The Pioneer station platform DOI is `10.58046/OOI-CP10CNSM`. Cite the instrument or product, date range, repository, and access date for each analysis. External datasets have their own access and reuse terms. [OOI citation guidance](https://oceanobservatories.org/how-to-use-acknowledge-and-cite-data/)
