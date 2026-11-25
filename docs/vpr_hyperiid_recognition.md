# Arctic amphipods across three imaging instruments

The SIG.AI Plankton Classifier’s research model still missed the five *Themisto abyssorum* images from a July 20 Healy encounter. All five passed the bubble screen and were classified as “other organism.” The VPR-only retraining introduced five false amphipod calls and recovered no true amphipods in 1,810 evaluation images. A separate ZooScan model improved recognition on two newly reserved Arctic cruises from **155/306 to 230/306** expert-labeled *Themisto*. False amphipod calls on controls rose from **68/310 to 88/310**.

## What happened on Healy

JAMSTEC experts identified all six diagnostic crops as *T. abyssorum*. Five were taken within one second on July 20, so they may show one animal. All three models recognized the single crop from July 14. This amounts to one of two encounter windows detected, even though the image-level recall was only one in six. The model produces the broad “amphipod” class. Species and genus names throughout this report come from the reference annotations. [Healy VPR source](https://ecotaxa.obs-vlfr.fr/api/projects/3177) · [Previous error study](https://github.com/sigaihealth/marinemodels/blob/main/docs/vpr_healy_error_study.md)

An AI reviewer in this chat scored two anonymized sheets before seeing the expert keys. It identified all six diagnostic amphipods, called none of 22 controls amphipods and abstained on five images. The reviewer described a rounded, dark red front and a pale, bent rear on the five missed frames. On a second sheet of historical fitting and development images, it identified seven of eight amphipods, mislabeled one of 20 controls (*Calanus hyperboreus*, a copepod), and abstained on nine images. The reviewer had prior familiarity with the collection. None of these provisional labels supplied training or evaluation targets.

The VPR-only model ranked three copepods above every July 20 amphipod and promoted all three. A lower cutoff could recover some amphipods but would retain all three false calls. That ordering identifies a problem with how the model distinguishes lookalikes.

## Training and native VPR checks

The search covered 107 public EcoTaxa VPR projects and 85 taxa in the hyperiid branch. It found 25 validated hyperiid records from three previously studied cruises. Six additional collections supplied 403 expert-labeled hyperiids and 256 controls from other instruments. Two Arctic *Polarstern* net collections supplied 265 ZooScan *Themisto* images, including 18 *T. abyssorum* and 37 *T. libellula*. Four UVP collections supplied 97 *Hyperia*, 32 other Hyperiidea, seven *Scina* and two *Phronima*. The auxiliary model used all 403 targets and 245 controls. Eleven large krill control images exceeded the input-size limit. [PS106/2](https://doi.org/10.1594/PANGAEA.971716) · [PS122](https://doi.org/10.1594/PANGAEA.968968) · [EXPORTS](https://ecotaxa.obs-vlfr.fr/api/projects/1286) · [APERO](https://ecotaxa.obs-vlfr.fr/api/projects/9622) · [SOLACE](https://ecotaxa.obs-vlfr.fr/api/projects/4034) · [BOWHEAD](https://ecotaxa.obs-vlfr.fr/api/projects/14019)

An OOI NVIDIA L40S trained a VPR-only model from 5,487 images and a mixed model from all 6,135 eligible images. Both could change “other organism” to “amphipod” and preserved every already predicted bubble and larva. Model selection on 1,482 development images favored the VPR-only model. The mixed model reported below uses its best configuration from that same frozen development comparison.

| VPR collection and outcome | Previous | VPR-only | Mixed |
| --- | ---: | ---: | ---: |
| Healy, amphipods identified on the two known acquisitions | 1/6 | 1/6 | 1/6 |
| Healy, historical bubble recall | 49/50 | 49/50 | 49/50 |
| Healy, other organisms called amphipods | 0/25 | 3/25 | 0/25 |
| Healy, additional bubble recall | 29/30 | 29/30 | 29/30 |
| Healy, additional copepods called amphipods | 1/32 | 2/32 | 1/32 |
| Canadian historical larvae retained as organisms | 239/250 | 239/250 | 239/250 |
| Canadian historical larvae classified as larvae | 125/250 | 125/250 | 125/250 |
| Canadian additional larvae retained as organisms | 38/40 | 38/40 | 38/40 |
| Canadian additional larvae classified as larvae | 30/40 | 30/40 | 30/40 |
| Hamburg, reference amphipods identified | 95/95 | 95/95 | 95/95 |
| Hokuto, other organisms called amphipods | 10/222 | 11/222 | 10/222 |

The mixed model recovered one expert-labeled *Primno* on an older Japanese cruise. It also changed two Canadian larvae from “other organism” to “amphipod,” a molluscan veliger and a nemertean pilidium. Both still passed the bubble screen. The VPR-only model introduced neither error. [MR17-07C expert records](https://ecotaxa.obs-vlfr.fr/api/projects/3108) · [Canadian VPR annotations](https://ecotaxa.obs-vlfr.fr/api/projects/10429)

A fresh VPR source from Meteor cruise M153 supplied six identified examples from one published figure. All three recognized the single *T. gaudichaudii* and falsely called two of five controls amphipods. One selected amphipod from the Benguela Upwelling System cannot establish recall for an Arctic cruise. The new source supplied no confirmed bubbles. [Meteor cruise account](https://www.biologie.uni-hamburg.de/einrichtungen/imf/aktuelles/2020-11-30-meteor-cruise.html) · [SPACES II newsletter, figure 5](https://www.emsafrica.org/fileadmin/spaces/Downloads/SPACES_II_newsletter_November_2020.pdf)

## Four independent instrument-transfer tests

ZooScan images show net-collected, laboratory-scanned specimens. The Underwater Vision Profiler (UVP) images organisms in the water using different optics from the Video Plankton Recorder (VPR). All 854 transfer images received predictions. Controls were selected from labeled organisms and larvae around the positive cases. The rates apply to these deliberately enriched panels. On the five original new cruises together, the mixed correction added 30 true amphipod calls and 28 false calls over the previous model. Each cell below shows target amphipods identified, then controls falsely called amphipods.

| Cruise and instrument | Previous | VPR-only | Mixed |
| --- | ---: | ---: | ---: |
| Polarstern PS80, ZooScan | 141/235 · 33/311 | 141/235 · 33/311 | 161/235 · 53/311 |
| Polarstern PS85, ZooScan | 29/39 · 23/55 | 29/39 · 23/55 | 34/39 · 28/55 |
| Discovery DY180, UVP6 | 36/64 · 8/120 | 36/64 · 8/120 | 39/64 · 11/120 |
| Palmer NBP18-02, UVP5 HD | 4/10 · 1/20 | 4/10 · 1/20 | 6/10 · 1/20 |

Of the mixed model’s 30 additional correct calls on the original five new cruises, 28 had explicit hyperiid labels and two had only an order label. Fifteen of its 28 additional false calls were larval krill from PS80 and PS85. On Discovery DY180, nine positives had a genus-level *Themisto* label and 55 were labeled only to order Amphipoda. On the two Fram Strait cruises, the positives were *Themisto* identified to genus or species. Palmer NBP18-02 supplied *Hyperia* and used the same UVP5 HD instrument serial as an earlier training cruise, with different casts, dates and ship. [Discovery BIO-Carbon](https://bio-carbon.ac.uk/bio-carbon-data) · [PS80](https://doi.org/10.1594/PANGAEA.992956) · [PS85](https://doi.org/10.1594/PANGAEA.992966) · [Palmer GO-SHIP cruise](https://cchdo.ucsd.edu/cruise/320620180309)

## Two new Arctic cruises for the ZooScan follow-up

After viewing the four original transfer results, we trained separate ZooScan and UVP models. Each candidate and cutoff was chosen by withholding one training cruise at a time. The earlier test panels became historical replays. Only the two additional ZooScan cruises, PS78 in 2011 and PS136 in 2023, remained prospective. They contributed 306 source-confirmed *Themisto* and 310 controls. Most controls came from the same acquisition as a positive. We removed 12 duplicate entries from PS78 before scoring. All 616 supplied images were scored.

| Fresh ZooScan cruise | Expert *Themisto* recognized | Controls called amphipods | Eligible / supplied |
| --- | ---: | ---: | ---: |
| PS136 | 70/195 → 138/195 | 40/195 → 54/195 | 390/390 |
| PS78 | 85/111 → 92/111 | 28/115 → 34/115 | 226/226 |

PS136 supplied 68 of the 75 additional detections across 16 net samples. The seven PS78 gains came from six samples. Across both cruises, 53 gains were *T. abyssorum*, 20 were genus-only *Themisto*, and two were *T. libellula*. Ostracods accounted for 15 of the 20 new false calls. Sample-level resampling gives a descriptive 95% interval for the recall gain of +19.8 to +44.2 percentage points on PS136 and +2.2 to +11.8 on PS78. We resampled complete net samples 20,000 times within each cruise to keep related images together. Neither cruise supplied verified bubbles or explicit larvae. [PS78 validated scans](https://ecotaxa.obs-vlfr.fr/prj/2771) · [PS136 validated scans](https://ecotaxa.obs-vlfr.fr/prj/11688)

A replay on the two previously scored UVP cruises exposed a tradeoff. On Discovery DY180 the UVP-specific classifier recovered 12 more amphipods but added 31 false calls among 120 controls. On Palmer it recovered three more and added two false calls among 20 controls. The study has no new prospective UVP cruise for this follow-up.

The public browser serves the existing 101-class classifier. These results document private OOI research models. Aggregate data include the decisions by cruise and expert taxon, with paired sample-level resampling intervals for the two new scanner cruises. [Three-model results by expert taxon](https://github.com/sigaihealth/marinemodels/blob/main/docs/vpr_hyperiid_taxa.csv) · [Two-cruise ZooScan results by expert taxon](https://github.com/sigaihealth/marinemodels/blob/main/docs/vpr_hyperiid_scanner_taxa.csv) · [Three-model results by cruise](https://github.com/sigaihealth/marinemodels/blob/main/docs/vpr_hyperiid_results.csv) · [Two-cruise ZooScan results](https://github.com/sigaihealth/marinemodels/blob/main/docs/vpr_hyperiid_scanner.csv)
