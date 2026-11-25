# ZooScan ostracods and Arctic amphipod recognition

On two Arctic cruises held out before training, the retrained classifier corrected **106 ostracod false amphipod calls** and retained **2/3 of the *Themisto* detections added by the preceding ZooScan model**. Overall *Themisto* detection went from 127/138 to 126/138. The correction also resolved 15 of the 15 historical ostracod errors that prompted the experiment.

## Two untouched Arctic cruises

We registered PS121 (2019) and PS131 (2022) as whole-cruise test panels before fitting. Investigators’ source records identify individual samples, dates, stations, validation status and the taxon assigned to each image. Both cruises sampled the Arctic Fram Strait in the same long-term HAUSGARTEN monitoring program used for training. We intentionally selected ostracods, *Themisto* and other organism controls. The class frequencies describe this test panel. All 616 registered test images are accounted for, with 616 scored. [PS121 data and methods](https://doi.org/10.1594/PANGAEA.993017) · [PS131 data and methods](https://doi.org/10.1594/PANGAEA.993020)

The three counts in each column follow the model history, from the original classifier through the preceding ZooScan model to this retrain. All models output the broad amphipod group. *Themisto* and ostracod names come from the investigators’ annotations.

| Cruise | *Themisto* identified | Ostracods called amphipods | Other controls called amphipods | Scanner gains on *Themisto* kept |
| --- | ---: | ---: | ---: | ---: |
| PS121 | 88/94 → 89/94 → 89/94 | 29/159 → 76/159 → 29/159 | 27/80 → 31/80 → 30/80 | 1/1 |
| PS131 | 36/44 → 38/44 → 37/44 | 27/159 → 86/159 → 27/159 | 23/80 → 25/80 → 23/80 | 1/2 |

Across the two cruises, ostracod false calls went from 162/318 (50.9%) to 56/318 (17.6%). Of the 106 ostracod errors introduced by the preceding ZooScan correction, 106 were withdrawn. The original classifier’s 56 ostracod false calls fall outside the correction’s scope. Other controls include copepods, euphausiids and 20 explicitly labeled larval krill. The new cruises supplied no verified bubble controls. Several images share a net sample. The supporting cruise table includes descriptive 95% intervals for paired changes in call rates from 20,000 resamples of complete net samples within each cruise. For the two new cruises we grouped observations by the investigators’ normalized sample names across EcoTaxa projects.

The 47 PS121 ostracod corrections came from 26 distinct net samples. The 59 PS131 corrections came from 13. The lost PS131 positive was identified to *Themisto* genus. Only three true amphipod calls had been added by the preceding scanner on these two cruises, so this test gives a limited estimate of how often such gains survive. All 20 krill larvae passed the bubble screen in both models. Thirteen were correctly called larvae and four were called amphipods by both.

## What the 15 errors looked like

The earlier ZooScan model introduced 20 false amphipod calls on Arctic cruises PS78 and PS136. Fifteen were expert-validated ostracods, four from PS78 and eleven from PS136. We reviewed all fifteen alongside 15 expert-labeled *Themisto* and 15 other crustaceans chosen from the same cruises. Controls were matched by acquisition or net sample where available, then by approximate crop size. We removed the standard 18-pixel scale footer and preserved the specimen pixels and orientation. The chat reviewer saw shuffled numbered panels and recorded 45 labels, confidence ratings and visible features before opening the expert key. The images came from a previously studied collection.

| Expert group (15 images each) | Called ostracod | Called amphipod | Called other crustacean | Abstained |
| --- | ---: | ---: | ---: | ---: |
| Ostracods newly misclassified by the earlier model | 12 | 0 | 0 | 3 |
| *Themisto* | 1 | 9 | 1 | 4 |
| Other crustaceans | 3 | 4 | 3 | 5 |

The typical ostracod call described a smooth, oval outline with a continuous or paired rim enclosing a darker center. Seven of twelve ostracod calls had high confidence. The three abstentions had straight or incomplete-looking outlines. Checking the source renders showed white space around the specimens even before the footer was removed. The upstream cause of those outlines is unknown. One *Themisto* and three other crustaceans also looked sufficiently shell-like to receive an ostracod call. The expert labels supply all numerical training and test targets. Public morphology references describe how the ostracod carapace encloses most of the body and how amphipod appendages and body segments are arranged. [Ostracod morphology](https://sat-zooplankton.linnaeus.naturalis.nl/linnaeus_ng/app/views/introduction/topic.php?epi=23&id=740) · [Amphipod morphology](https://ns-zooplankton.linnaeus.naturalis.nl/linnaeus_ng/app/views/highertaxa/taxon.php?cat=TAB_DESCRIPTION&id=131468) · [Original two-cruise ZooScan study](https://github.com/sigaihealth/marinemodels/blob/main/docs/vpr_hyperiid_recognition.md)

## Expert training data and model selection

Four additional *Polarstern* cruises contributed 800 expert-labeled ostracods, 525 *Themisto* and 192 control organisms. The original verified annotation and sample record accompany each crop. Two taxonomy entries, Ostracoda and “Ostracoda X,” share explicit Ostracoda ancestry. We used 1514/1517 new crops and 394 earlier ZooScan training crops after preprocessing. All 800 new ostracods entered fitting. Three new *T. libellula* and eleven earlier krill controls exceeded the four-megapixel input limit. All four new cruises and the two untouched test cruises have disjoint specimen IDs and source and decoded image hashes. A visual-similarity check flagged two ostracod crops that closely resembled earlier images. We excluded both before scoring and found zero exact matches across the 616 final cases and 11,571 earlier observations. [PS93.2](https://doi.org/10.1594/PANGAEA.993009) · [PS99.2](https://doi.org/10.1594/PANGAEA.993010) · [PS107](https://doi.org/10.1594/PANGAEA.993012) · [PS114](https://doi.org/10.1594/PANGAEA.993016)

OOI’s NVIDIA L40S fitted a ZooScan-only correction. The model can withdraw an amphipod designation added by the preceding ZooScan model and restore the original “other organism” decision. This protects amphipods already detected by the original model, and all previously predicted bubbles and larvae. We withheld one of the four new training cruises at a time to choose the correction and cutoff. The prospective trials check whether gains in the held-out training cruises transfer to different cruises.

## Replay of earlier cruises

Every original and preceding model decision on a previously scored input was reproduced by observation ID. The retrain resolved 4/4 of the historical ostracod errors from PS78 and 11/11 from PS136. Across PS78 and PS136, the correction kept 66 of the earlier 75 additional *Themisto* detections. All nine losses were on PS136, including four *T. abyssorum* and five genus-level *Themisto*. These images supplied the motivating error examples and have a diagnostic role. A withdrawn call becomes “other organism.” It gives no automated species identification.

| Cruise | *Themisto* identified | Ostracods called amphipods | Other controls called amphipods | Scanner gains on *Themisto* kept |
| --- | ---: | ---: | ---: | ---: |
| PS136 | 70/195 → 138/195 → 129/195 | 5/37 → 16/37 → 5/37 | 35/158 → 38/158 → 35/158 | 59/68 |
| PS78 | 85/111 → 92/111 → 92/111 | 1/18 → 5/18 → 1/18 | 27/97 → 29/97 → 28/97 | 7/7 |
| PS80 | 141/235 → 179/235 → 178/235 | 2/70 → 5/70 → 2/70 | 31/241 → 32/241 → 32/241 | 37/38 |
| PS85 | 29/39 → 34/39 → 33/39 | 0/5 → 0/5 → 0/5 | 23/50 → 28/50 → 26/50 | 4/5 |

The public SIG.AI page provides aggregate research results and the existing 101-class classifier. The private OOI workspace contains expert-labeled crops, the blinded review, fitted checkpoints, per-case predictions and interactive research inference. [Cruise counts and paired intervals](https://github.com/sigaihealth/marinemodels/blob/main/docs/zooscan_ostracod_cruises.csv) · [Results by expert taxon](https://github.com/sigaihealth/marinemodels/blob/main/docs/zooscan_ostracod_taxa.csv)
