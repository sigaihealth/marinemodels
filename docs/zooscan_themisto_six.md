# Recovering Themisto after the ZooScan calanoid retrain

The OOI candidate recovered **all six** known *Themisto* after learning from them. On a previously unseen July Greenland Sea leg, it recovered one additional expert-labeled *T. abyssorum*, raising recognition from **56/63 to 57/63**. The model trained without the six also recovered that animal. Across all **1,623 new images**, the two retrained models made the same broad decisions. The full candidate introduced **no new calanoid or ostracod errors**. Existing errors persisted on 12/660 calanoids and 1/643 ostracods. The decision rule allowed 174 calanoids and zero ostracods to change, so independent evidence about ostracod risk is limited.

## What the six scans have in common

The three PS80 images show pale, curled animals with appendages close to the body. One PS126 image has a conspicuous cutout in the outline. The second PS126 specimen and the PS136 specimen have a dark, compact body with a few visible projections. Their investigator labels include *Themisto* and *T. abyssorum*. Similar outlines also occur in calanoid copepods. We reviewed the six images knowing their prior errors. The investigators supplied the reference labels.

To test this overlap, the training set gained 500 validated ZooScan images from 89 previously sampled nets across 191 acquisitions. APERO and the southern Tara Microbiomes program supplied 219 new *Themisto*, 150 calanoids, 101 ostracods and 30 other crustaceans. The *Themisto* included 73 ranked for pale, curved bodies, 50 for compact shapes and 26 for clipped-looking edges, along with 70 ordinary specimens. Ten of 30 expert-labeled *Themisto* in a masked, enriched review closely resembled the targets. The review also identified an expert-labeled metridinid copepod with an angular cutout and a pale, curled euchaetid copepod. These selected counts describe the review set. [APERO Thalassa BIONESS](https://ecotaxa.obs-vlfr.fr/prj/11638) · [Tara Microbiomes WP2](https://ecotaxa.obs-vlfr.fr/prj/20784)

## How the comparison was made

The private OOI NVIDIA L40S ran the retraining and evaluation on 4,108 accepted fitting scans. The model used posture, body detail and local contrast to estimate amphipod evidence. It could restore an amphipod call only where the previous calanoid model had withdrawn one. Both comparators used training folds and 323 known, correctly withdrawn historical non-amphipod calls to calibrate their operating point, including 285 calanoids and one ostracod. Correctly rejected historical controls therefore helped tune the decision and cannot independently validate protection against false positives. Both models were frozen before fresh scores were read.

The first comparator learned from the source collections and historical negative controls. The second could also learn from the six labeled *Themisto*. Its 6/6 result is an in-sample check. The comparator trained without the six recovered 4/6. In the separate 4/6 analysis, each known specimen was removed from the positive examples and the operating point was recalculated. These six correlated, retrospectively selected examples provide a limited measure of transfer.

## Untouched Greenland–Labrador cruise

The 500 investigator-labeled images came from 11 nets and 22 acquisitions at all three sampled stations of Tara's October 20–November 10, 2013 voyage from Ilulissat to Quebec. The 500 image records matched the expedition team's date, station and coordinates. This voyage, its nets and stations were distinct from the earlier research cohorts. Earlier tests used other voyages from the same Tara expedition and vessel. The PELGAS and Point B genus checks below are separate. [Tara campaign registry](https://doi.pangaea.de/10.1594/PANGAEA.842191) · [Tara station registry](https://doi.pangaea.de/10.1594/PANGAEA.842237)

| Expert group and outcome | Scored | Eligible to change | Previous | Without the six | With the six | Added |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Calanoids called amphipods | 300 | 69 | 6 | 6 | 6 | 0 |
| Ostracods called amphipods | 128 | 0 | 0 | 0 | 0 | 0 |
| Hyperiids recognized | 22 | 0 | 20 | 20 | 20 | 0 |
| Other organisms called amphipods | 50 | 18 | 0 | 0 | 0 | 0 |

Only 87/500 fresh decisions were eligible to change under the model's rule. The opportunity set included 69 calanoids, 0 ostracods and 0 hyperiids. The other controls were identified at the broader copepod level. The Arctic field annotations identified amphipods only to Hyperiidea. The genus-level behavior of the candidate on this cruise remains unknown.

## Additional genus-confirmed specimens

**Bay of Biscay PELGAS.** The previous model recognized 8/13, the model without the six recognized 8/13, and the candidate recognized 8/13. 0 were eligible to change.

**Villefranche Point B.** The previous model recognized 1/1, the model without the six recognized 1/1, and the candidate recognized 1/1. 0 were eligible to change.

The 13 PELGAS genus labels came from seven annual R/V Thalassa surveys. Each reference image was matched to its original field-table ROI, date, net and coordinates. All 13 physical nets supplied different images to an older 101-class benchmark. The single Villefranche voucher matched its original April 23, 2014 WP2 sampling event. In all, the 514 new images passed source identity and decoded-pixel checks, with no exact or conservative perceptual matches across 26,515 comparison images. The complete training inventory of the original base classifier is unavailable. [PELGAS quantitative field archive](https://doi.org/10.17882/94052) · [Sampling and expert annotation methods](https://doi.org/10.5194/essd-16-1265-2024) · [Villefranche field archive](https://doi.org/10.14284/473) · [Expert genus vouchers](https://ecotaxa.obs-vlfr.fr/prj/1040)

## Independent Greenland Sea leg with genus-level labels

The Greenland–Labrador cruise contained no genus-level amphipod labels, and none of its hyperiids could change under the recovery rule. With the comparisons already frozen, we registered two more tests. Both used taxonomy, sampling dates and stations to select images before reading their predictions.

The first followed Polarstern's **July 2012 Greenland Sea leg ARK-XXVII/2**. We linked 63 expert-labeled *Themisto* from 19 new nets to five independent field station records using dates and coordinates. The same cruise name, PS80, covers a June–early July leg that supplied three training examples. All 546 previously registered PS80 images were from that earlier leg. The July leg also supplied 27 calanoid and 34 ostracod controls. Recognition here means the classifier returned the broad amphipod class on an image that experts identified as *Themisto*. [July field events and taxonomy](https://doi.pangaea.de/10.1594/PANGAEA.992965) · [Earlier PS80 field events](https://doi.pangaea.de/10.1594/PANGAEA.992956)

| Expert group and outcome | Scored | Eligible to change | Previous | Without the six | With the six | Added |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Themisto recognized | 63 | 1 | 56 | 57 | 57 | 1 |
| Calanoids called amphipods | 27 | 10 | 1 | 1 | 1 | 0 |
| Ostracods called amphipods | 34 | 0 | 0 | 0 | 0 | 0 |

Of the 63 scored *Themisto*, 1 could change. Both retrained models recovered the same investigator-confirmed *T. abyssorum*. The six remaining misses fell outside the set of decisions the retrain could change. The sample was enriched for expert-labeled organisms and cannot estimate their natural abundance.

The complete Arctic challenge also included 19 earlier-leg PS80 controls and independently selected images from previously used PS126, PS131 and PS136 cruises. Together it contained 377 registered scans, with 377 accepted. The table includes the July leg above. The per-cruise CSV separates the two legs and lists the remaining controls.

| Expert group and outcome | Scored | Eligible to change | Previous | Without the six | With the six | Added |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Themisto recognized | 63 | 1 | 56 | 57 | 57 | 1 |
| Calanoids called amphipods | 160 | 51 | 4 | 4 | 4 | 0 |
| Ostracods called amphipods | 154 | 0 | 0 | 0 | 0 | 0 |

## Four more Tara cruises

Two new Arctic voyages covered Dudinka to Pevek and Pevek to Tuktoyaktuk. Two southern voyages covered Buenos Aires to Ushuaia and Ushuaia to Puerto Williams. We reserved complete station lists and a sampling cap for each expert class before scoring. The investigators labeled the amphipods as Hyperiidea. The four cruises enrolled 748 images after duplicate checks. The service scored 732, excluding 16 hyperiid images over the four-megapixel input limit. These exclusions count towards image coverage. They have no model prediction. [Cruise registry](https://doi.pangaea.de/10.1594/PANGAEA.842191) · [Station registry](https://doi.pangaea.de/10.1594/PANGAEA.842237)

| Expert group and outcome | Scored | Eligible to change | Previous | Without the six | With the six | Added |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Hyperiids recognized | 171 | 4 | 115 | 115 | 115 | 0 |
| Calanoids called amphipods | 200 | 54 | 2 | 2 | 2 | 0 |
| Ostracods called amphipods | 361 | 0 | 1 | 1 | 1 | 0 |

The previous model and the candidate both recognized 115/171 broad hyperiids. The rule could change 4 hyperiid decisions, 54 calanoid decisions and 0 ostracod decisions. The 2 calanoid errors and 1 ostracod error already occurred in the previous model. The absence of eligible ostracods limits what these four cruises can establish about the risk of restoring such an error.

## Historical replay

We reproduced the previous model's decisions for all 4,080 historical scans. The candidate changed six. The replay includes the six positive examples and the historical controls used in calibration.

| Expert group and outcome | Scored | Eligible to change | Previous | Without the six | With the six | Added |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Themisto recognized | 966 | 6 | 753 | 757 | 759 | 6 |
| Hyperiids recognized | 186 | 0 | 161 | 161 | 161 | 0 |
| Calanoids called amphipods | 1002 | 285 | 11 | 11 | 11 | 0 |
| Ostracods called amphipods | 1463 | 1 | 2 | 2 | 2 | 0 |
| Other organisms called amphipods | 463 | 37 | 55 | 55 | 55 | 0 |

With the positive examples from each target cruise withheld together, 4/6 were recovered. Previously corrected negatives from those cruises still contributed to threshold calibration, so this is a retrospective sensitivity check.

The two earlier PS126 and MSM108 *Themisto* recoveries were retained on 2/2. The previously corrected PS126 calanoid remained classified as **other organism**. The experimental model runs in the authenticated OOI research notebook.

[Download per-cruise counts](zooscan_themisto_six_cruises.csv) and [per-station counts](zooscan_themisto_six_stations.csv).
