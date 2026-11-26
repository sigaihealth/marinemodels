# Satellite sea-surface temperature inputs

The daily fields are NASA JPL MUR v4.1 foundation sea-surface temperature in °C. MUR merges satellite and in-situ observations in a spatial analysis. Its map values can span cloud gaps. A map has a different depth and sampling interval from the moored CTD. [NASA PO.DAAC collection](https://podaac.jpl.nasa.gov/dataset/MUR-JPL-L4-GLOB-v4.1) · [NOAA ERDDAP subset service](https://coastwatch.pfeg.noaa.gov/erddap/griddap/jplMURSST41.html)

## Shelf map

Each daily 09 UTC map samples a fixed five-by-five grid centered at 35.95° N, 75.12° W. The longitude bounds are −75.42° and −74.82°, and the latitude bounds are 35.65° and 36.25°. The spacing is 0.15°, or every fifteenth native MUR cell along each axis. The 25 cells cover approximately 54 km east–west and 67 km north–south at this latitude. The source resolution is 0.01°. The stencil trades spatial detail for a fixed view of the shelf within this first benchmark.

The feature file contains the center temperature, mean temperature, population standard deviation, mean east-edge minus mean west-edge temperature, and mean north-edge minus mean south-edge temperature. Edge differences have units of °C over the stencil. Means use finite water pixels. Features require at least 20 finite cells and edge differences require three values per edge.

## Historical availability

The 09 UTC time in the filename describes the map. It does not establish when its values were available. The archived final product undergoes revisions. For each map the build retrieves its matching NASA Earthdata granule and records its end of observation coverage, production time, provider insert or update time and CMR metadata revision time. The latest of those times becomes `available_time`. Only a map satisfying `available_time <= forecast_issue_time` can be used. If several maps qualify, take the one with the greatest nominal `map_time`, then apply the analysis's maximum age. Map times and availability times can have different orders. Administrative metadata updates can delay eligibility and reduce retrospective coverage. This rule is conservative for the final version. It cannot reconstruct faster historical near-real-time versions overwritten by the publisher. [NASA granule metadata for February 1, 2026](https://cmr.earthdata.nasa.gov/search/granules.umm_json?collection_concept_id=C1996881146-POCLOUD&temporal=2026-02-01T09%3A00%3A00Z%2C2026-02-01T09%3A00%3A01Z)

The NOAA ERDDAP map values are joined to the NASA granules by product, version and nominal timestamp. `source_file_md5` is NASA's recorded checksum for the full source netCDF. The provenance file records separate SHA-256 digests for the NOAA monthly subsets, the NASA metadata responses, and the delivered CSVs. Whole NASA netCDF files are not required for this build. A direct check for the February 1 map shows a NASA production time on February 10 at 07:18 UTC. [Public NASA checksum for the archived source file](https://archive.podaac.earthdata.nasa.gov/podaac-ops-cumulus-public/MUR-JPL-L4-GLOB-v4.1/20260201090000-JPL-L4_GHRSST-SSTfnd-MUR-GLOB-v02.0-fv04.1.nc.md5)

## Reproducing the inputs

Run `python3 fetch_sst.py --output ./sst-output` with Python 3.9 or newer. The default request starts March 1, 2024 and ends October 31, 2026 UTC. An initial month is included to support lookback at the start of the CTD series. Monthly HTTP responses are cached under `sst-cache/`. Run in a new output directory to check a newer archive revision. The build validates the daily inventory and cell coordinates before writing `sst_map_cells.csv.gz`, `sst_daily.csv` and `sst_provenance.json`.
