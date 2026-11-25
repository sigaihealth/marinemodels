# Marine Models

Marine Models explores how open ocean observations can support local models and digital twins. The first pilot replays Winter Storm Gianna at OOI's Pioneer Mid-Atlantic Bight Central Surface Mooring (`CP10CNSM`) off North Carolina. The [research brief](docs/ocean_digital_twin_research.md) covers five model ideas, complementary datasets, and the validation questions each project would need to answer.

## Run the Pioneer event replay

The sensor download and offline playback builder use Python 3.10 or newer. The image sampler also uses Pillow. To execute the analysis notebook, use a Python 3 kernel with pandas and Matplotlib, and install Jupyter nbconvert. Run these commands in a local shell or the OOI JupyterHub terminal.

```sh
git clone https://github.com/sigaihealth/marinemodels.git
cd marinemodels
run_dir="$HOME/data/pioneer-gianna"
python3 ooi_replay.py --output-dir "$run_dir"
python3 pioneer_images.py --output-dir "$run_dir/ifcb"
python3 pioneer_playback.py "$run_dir"
PIONEER_REPLAY_DIR="$run_dir" jupyter nbconvert --to notebook --execute \
  --output-dir "$run_dir" --output pioneer_storm_replay.ipynb pioneer_storm_replay.ipynb
```

Open `pioneer_playback.html` from the output directory in a browser. The file embeds its observations and image crops, so it also works offline. Use the slider to select an hour or the two sample buttons to inspect imagery. In JupyterLab, open the executed `pioneer_storm_replay.ipynb` in the data directory for the source-resolution comparison, sampling offsets, and four-panel figure.

The default window runs from January 29, 2026 at 00:00 UTC up to February 4 at 00:00 UTC. The two download commands expect new output directories. If a completed download is already present, proceed with the remaining commands. The sensor downloader also accepts `--start` and `--end` for other windows up to 31 days. The image sampler and the event comparisons in the notebook are specific to February 1.

The pilot brings together IFCB image-region counts and sampled volume, fluorometer chlorophyll, CTD salinity, and buoy air pressure. It uses recovered observations and telemetry to align measurements in time for a historical replay. IFCB image regions per milliliter can include particles. Images are available after recovery through OOI’s IFCB archive for visual comparison and future image models. [OOI’s Gianna case study and image links](https://oceanobservatories.org/2026/09/ooi-plankton-imagery-and-co-located-environmental-data-now-ready-for-analysis/)

- `plims.csv`, `fluorometer.csv`, `ctd.csv`, and `meteorology.csv` contain source observations, timestamps, and aggregate QC flags.
- `replay.csv` contains hourly UTC medians, counts of contributing observations, and counts of contributing flag-2 observations. Values with flag 1 (pass) or 2 (not evaluated) can contribute. Missing observations produce blank values and are never interpolated.
- `summary.json` records the exact source queries, units, coverage, QC counts, platform DOI, and retrieval time. A window with no observations eligible for the replay returns an error.
- `ifcb/` contains 24 unclassified image crops, a contact sheet, and a manifest with the original URLs, sample volumes, selection method, and SHA-256 checksums. Twelve crops were selected at evenly spaced positions within each sample's sorted list of image targets. The contact sheet resizes each crop independently.
- `pioneer_storm.png` shows the six-day time series. IFCB observations are available in 42 of the 144 hourly bins in this replay.

## What happened on February 1

The 00:25:46 UTC sample contained 1,065 image regions in 4.615 mL (231 ROIs/mL). At 15:25:45 UTC there were 5,164 in 3.005 mL (1,718 ROIs/mL), a 7.45-fold difference. The buoy recorded its lowest pressure that day at 08:34 UTC, 995.02 mbar. The nearest CTD measurements to the two image samples showed practical salinity falling from 35.061 to 34.582. Both ROI concentrations and the pressure minimum carried aggregate QC flag 2 (not evaluated). The matched salinity values carried flag 1 (pass).

The higher count coincided with fresher water at the mooring. ROI counts include plankton, aggregates, and other suspended particles. Distinguishing a community shift from changes in transported or resuspended material requires classifying a larger image sample. [OOI event description and original samples](https://oceanobservatories.org/2026/09/ooi-plankton-imagery-and-co-located-environmental-data-now-ready-for-analysis/)

## Research directions

### Classify the recovered gallery

The pilot uses the frozen WHOI Northeast Shelf IFCB classifier on CPU. Its suggestions require a local expert audit before they can support estimates of plankton composition. Run from the repository directory with NumPy, Pillow 9.1 or newer, and ONNX Runtime installed. The script verifies the model, labels, and gallery image checksums.

```sh
weights="$HOME/data/models/whoi-nes-v2.4"
run_dir="$HOME/data/pioneer-gianna"
base="https://huggingface.co/sosiklab/NES-plankton-IFCB-classifier-2022/resolve/71bc362e8c75014c27692a8f10637d36f411962e"
mkdir -p "$weights"
curl -fL "$base/20220209_Jan2022_NES_2.4.onnx" -o "$weights/20220209_Jan2022_NES_2.4.onnx"
curl -fL "$base/labels.json" -o "$weights/labels.json"
python3 pioneer_classify_gallery.py --ifcb-dir "$run_dir/ifcb" --weights-dir "$weights" \
  --output "$run_dir/pioneer_whoi_predictions_rerun.csv"
```

Each row gives the three highest-scoring labels for one original image. The output path must be new. [WHOI model card](https://huggingface.co/sosiklab/NES-plankton-IFCB-classifier-2022)

### Model ideas

- [Pioneer plankton recognition and scientific interpretation](docs/pioneer_plankton_models.md) outlines a local image-label audit, volume-normalized community estimates, cited event reports, and three follow-on experiments.
- Compare persistence against sensor-only predictions and then test whether earlier image features improve accuracy on held-out deployments. Use data availability timestamps before evaluating a live forecast.
- Use the Oregon or Washington shelf for a separate near-bottom oxygen forecast. Validate against OOI measurements and compare with regional forecasts and gliders where time and depth overlap.
- Use CoastWatch, NASA PACE, NDBC, IOOS, and regional model products for spatial and weather context. The research brief links the source datasets and explains where their footprints and time coverage differ.

## Data attribution

The source data are from the NSF Ocean Observatories Initiative, funded under NSF Cooperative Agreement No. 2244833 and managed by the Woods Hole Oceanographic Institution OOI Program Office. The Pioneer station platform DOI is `10.58046/OOI-CP10CNSM`. Cite the instrument or product, date range, repository, and access date for each analysis. External datasets have their own access and reuse terms. [OOI citation guidance](https://oceanobservatories.org/how-to-use-acknowledge-and-cite-data/)
