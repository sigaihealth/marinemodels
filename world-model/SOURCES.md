# Ocean world model evidence

## Pioneer event replay

The [weather and satellite guide](pioneer-weather-satellite.md) documents winds, waves, currents, tides, sea-surface temperature and ocean color available for the six-day replay.

The NSF Ocean Observatories Initiative’s Pioneer Mid-Atlantic Bight Central Surface Mooring (CP10CNSM) is approximately 45 km east of Nags Head, North Carolina, on a shelf about 30 m deep. Its Imaging FlowCytobot intake is at 7 m. SIG.AI matched the 42 recovered microscope acquisitions spanning January 29 through February 3, 2026 with the co-located CTD, fluorometer and surface weather streams. The six-day interval contains 123,609 image regions. An image region can depict a cell, colony, chain, or debris. The plotted particle concentration uses the instrument’s count per analyzed milliliter. [OOI storm report](https://oceanobservatories.org/2026/09/ooi-plankton-imagery-and-co-located-environmental-data-now-ready-for-analysis/) · [Platform DOI](https://doi.org/10.58046/OOI-CP10CNSM) · [Recovered IFCB archive](https://ifcb-data.oceanobservatories.org/timeline?dataset=PioneerMABMoored)

The public IFCB export supplies the native bin ID, second-resolved acquisition time, analyzed volume, original region count and instrument depth. Its 42 bins match 42 telemetered ROI concentration measurements one-to-one. The staging script verifies the reported concentration against the archival region count divided by analyzed volume. The environmental join takes the nearest finite eligible reading within 360 seconds of the *recovered* acquisition time. The 42 air-pressure matches range from 5 seconds before to 18 seconds after the IFCB sampling time. All 42 CTD and fluorometer samples lag the IFCB by 235 to 258 seconds. Each record stores the actual measurement and acquisition times. The plot spaces samples by elapsed time. The event’s 995.02 mbar minimum comes from the full weather stream at 08:34 UTC February 1.

The OOI aggregated flags for air pressure, sample volume and ROI concentration are 2 (not evaluated). Temperature, practical salinity and the fluorometer’s chlorophyll-a estimates have flag 1 (pass) among the matched records. Each of the 8,640 eastward and northward wind measurements in this station stream is missing across the event, so vector components and derived wind speed remain null. Any examples of wind-driven mixing or ecological change shown alongside the replay remain mechanism hypotheses. [Station meteorology](https://erddap.dataexplorer.oceanobservatories.org/erddap/info/ooi-cp10cnsm-sbd11-06-metbka000/index.html) · [CTD](https://erddap.dataexplorer.oceanobservatories.org/erddap/info/ooi-cp10cnsm-rid27-03-ctdbpc000/index.html) · [Fluorometer](https://erddap.dataexplorer.oceanobservatories.org/erddap/info/ooi-cp10cnsm-rid27-02-flortd000/index.html) · [IFCB telemetry](https://erddap.dataexplorer.oceanobservatories.org/erddap/info/ooi-cp10cnsm-rid27-07-plimsa000/index.html)

## MBARI detector trial

The Pacific case uses MBARI’s ROV Ventana dive V4277 on February 19, 2020. In 600 Benthic Difficult frames, 94 annotated animals contribute 28,708 appearances. At one-to-one intersection-over-union of at least 0.50, Megalodon reached 91 animals and 18,926 appearances. Ecotype reached 51 animals and 3,472 appearances. These are measures of localization coverage. The Atlantic mooring and Pacific transect supply separate observation examples. [Frozen trial, model versions, credits and scores](https://github.com/sigaihealth/marinemodels/tree/367cf3cd6ccfffdc3aeb54a724180d7cf604b1c5/transect/v4277) · [MBARI DeepSea-MOT](https://huggingface.co/datasets/MBARI-org/DeepSea-MOT)

## Rebuild the Pioneer evidence

From the repository root, run these commands with Python 3.11 or later. The first run downloads five public CSV responses to a temporary directory. Reusing the cache replays those same responses. Use a fresh temporary directory to check the upstream services again.

```sh
world_evidence_dir=$(mktemp -d)
python3 world-model/build_evidence.py --cache "$world_evidence_dir/cache" --out "$world_evidence_dir/evidence.json"
cmp "$world_evidence_dir/evidence.json" world-model/evidence.json
```

The committed snapshot has SHA-256 `a5a6124dc1805dcb047a5a16532ea7cc2cfe27317ba8e02a5cd325b2aa5f7c71`. Its `pioneer.sources` object records the ERDDAP data queries and the IFCB archive export. Each row in `pioneer.samples` contains the source bin, acquisition and sensor times, values, and quality flags. The builder checks the recovered and telemetered counts and volumes and raises an error if the event inventory changes. The Ventana detector results can be reproduced using the separately versioned [V4277 workflow](../transect/v4277/README.md).

## Conceptual illustration

SIG.AI created the coastal water-column illustration using image generation. The water, terrain and organisms depict a hypothetical ocean section. The paths and labels identify mechanisms to investigate. The Pioneer measurements and V4277 detector results appear separately in the evidence panels. [Explore the ocean world model](https://ocean.sig.ai/world-model.html) · [Download the labeled illustration](https://ocean.sig.ai/assets/ocean-world-model.png)
