# Distinguishing calanoid lookalikes from amphipods in ZooScan images

The OOI retrain **withdrew the false amphipod call** on the known PS126 calanoid and retained **2/2** previously recovered *Themisto*. On a fresh Barents–Kara cruise, calanoid false positives went from **126 to 6 among 360**, and ostracod false positives went from **1 to 1 among 107**. On earlier collections, 6 other correctly recognized *Themisto* lost the amphipod call.

This ZooScan comparison measures whether a specimen is called an amphipod. A successful rejection of a calanoid or ostracod can receive the broad output “other organism.” Recognition as an amphipod establishes neither the genus nor the species. Genus labels below come from the source investigators.

## Three earlier Fram Strait specimens

In 24 masked ZooScan crops from PS126 and MSM108, the PS126 calanoid showed a dark rounded body and one sharply angled projection. The two previously recovered *Themisto* showed multiple pale tapered projections. All three anchor images were familiar to the reviewer. Among the other eight expert calanoids, the reviewer called one an amphipod, recognized two as calanoids, gave a broader crustacean call on one and abstained on four. Of the six other *Themisto*, five received visual amphipod calls. The 21 comparison specimens were selected by shape, size and acquisition context. Investigator annotations remained the reference for every model comparison.

## Training on expert-labeled lookalikes

The two development sources supplied 518 new investigator-validated scans. These included 300 calanoids (210 selected for compact shape and pale projections, plus 90 ordinary examples), 130 *Themisto*, 58 ostracods and 30 additional controls. The investigators identified 189 to order Calanoida and 111 to one of five families. Source identity, validation date, net, acquisition and image fingerprints were recorded. Each program supplied 150 calanoids. Both had contributed other specimens to earlier training. Of the 64 physical nets, 36 were new to registered development material. Conservative image screening excluded two near matches from the 520 original selections. [APERO Thalassa BIONESS](https://ecotaxa.obs-vlfr.fr/prj/11638) · [Tara Microbiomes WP2](https://ecotaxa.obs-vlfr.fr/prj/20784)

In a separate masked audit of fitting scans, 2 of 16 shape-selected calanoids and 0 of 16 ordinary calanoids clearly had the compact silhouette and sparse projections. Seven of 32 additional high-ranked examples had those features. Other images had elongated bodies, visible limbs or insufficient detail to assess the outline.

The private OOI NVIDIA L40S fit used 3,608 accepted source images, including 3,214 with out-of-fold predictions from six collections. The retrain used the scanner image and an enlarged view of the dark body and nearby appendages. A decision of amphipod could be withdrawn in favor of other organism. The preceding faint-appendage alternative was the comparison model. Researchers compared candidates trained from source cruises alone with a candidate that also incorporated the three familiar Fram Strait specimens. The selected model used the PS126 calanoid and both Fram Strait Themisto as three labeled visual examples. Their replay outcomes are in-sample. The source-only comparator retained the PS126 false positive and retained 2/2 known Themisto recoveries. Both the comparison models and the selection rule were frozen before scoring the fresh panels.

In the validation folds, the selected retrain corrected 169/179 baseline calanoid false positives and withdrew 0 correct amphipod calls among 1020. The source-only comparator corrected 169 calanoid errors and withdrew 0 correct calls on the same examples. These data were used for selection.

## Fresh cruise and independent genus check

The Arctic cruise ran from Murmansk to Dudinka in 2013. The 30 sampled nets spanned 15 stations from June 30 to July 19, between 71.0° and 79.4° N. It was a separate leg of the same Tara Polar Circle program and vessel used for earlier Arctic tests. The registered test included 360 Calanoida, 107 Ostracoda, 46 Hyperiidea and 60 other controls. Calanoids were sampled across nets without model scores or shape selection. One station supplied 101 of the 107 ostracods. The investigators labeled Arctic amphipods to suborder Hyperiidea. Two genus-confirmed Iroise Sea vouchers provided a separate check from May 3, 2012 and July 6, 2016. The field archive documented both WP2 net events. The vessels for those events were unverified. Across the two panels 575 of 575 registered images received predictions. Identity and image checks covered 15,543 previously registered organisms and 25,440 scanner reference crops, respectively. No fresh specimen matched an earlier one under the registered exact or perceptual criteria. The original 101-class model’s complete training inventory is unavailable. [Campaign registry](https://doi.org/10.1594/PANGAEA.842191) · [Station registry](https://doi.org/10.1594/PANGAEA.842237) · [Iroise Sea survey archive](https://ipt.gbif.org/resource?r=dasid_6511)

The fresh Arctic test recognized 44/46 broader hyperiids, compared with 44/46 previously. Among the separate Iroise Sea vouchers the two models recognized 2/2 and 2/2 *Themisto* respectively. Only 44 Arctic hyperiids and 2 Iroise *Themisto* were eligible to change. These panels cannot by themselves establish genus-wide retention or a change in performance across vessels.

Among scored Arctic specimens, calanoids came from 15 stations, ostracods from 3 stations and hyperiids from 12 stations. The withdrawn calanoid calls came from 15 stations. Specimens collected in the same net or station share collection conditions, so the image totals should not be interpreted as independent cruises. Leaving out each Arctic station in turn gave a calanoid false-positive reduction ranging from 31.8 to 34.5 percentage points. Of the six remaining calanoid errors, three came from station 169 and one each from stations 172, 173 and 178.

Among 28 explicitly labeled larvae on the Arctic cruise, the preceding model recognized 17 as larvae and the retrain recognized 17.

| Collection | Investigator group | Scored | Eligible | Earlier amphipod calls | Source-only comparator | Selected retrain | Withdrawn | Added |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Iroise Sea vouchers | Genus Themisto | 2 | 2 | 2 | 2 | 2 | 0 | 0 |
| Barents and Kara seas | Calanoids | 360 | 126 | 126 | 6 | 6 | 120 | 0 |
| Barents and Kara seas | Ostracods | 107 | 1 | 1 | 1 | 1 | 0 | 0 |
| Barents and Kara seas | Suborder Hyperiidea | 46 | 44 | 44 | 44 | 44 | 0 | 0 |
| Barents and Kara seas | Other controls | 60 | 16 | 16 | 4 | 4 | 12 | 0 |
| Earlier collections pooled | Calanoids | 642 | 170 | 170 | 6 | 5 | 165 | 0 |
| Earlier collections pooled | Ostracods | 1356 | 2 | 2 | 1 | 1 | 1 | 0 |
| Earlier collections pooled | Suborder Hyperiidea | 140 | 117 | 117 | 117 | 117 | 0 | 0 |
| Earlier collections pooled | Genus Themisto | 964 | 757 | 757 | 751 | 751 | 6 | 0 |
| Earlier collections pooled | Other controls | 403 | 76 | 76 | 51 | 51 | 25 | 0 |

The source-only retrain and the model that learned from the three Fram Strait examples gave identical predictions on all 575 fresh specimens. They differed on exactly one of the 3,505 earlier specimens, the PS126 calanoid itself. The source-cruise training therefore accounts for the observed fresh-cruise improvement. The extra three examples corrected one known case.

“Eligible” counts specimens whose preceding model decisions allowed the retrain to act. The difference between two totals can conceal simultaneous gains and losses. The last two columns count those paired changes separately.

## Replay on earlier collections

The 3,505 previously evaluated images were scored again with the frozen candidate. Their six historical model decisions were checked specimen by specimen against the preceding study. The remaining baseline ostracod error in earlier collections was counted against the candidate. Of the 56 original PS121/PS131 ostracod false positives, **1** still received amphipod calls. The rounded PS131 *Themisto* received **amphipod**. The retrain added 0 ostracod false positives and corrected 1 earlier ostracod false positive.

Of 757 previously recognized Themisto on all earlier collections, 6 lost the amphipod call. The preceding model had 170 false amphipod calls among 642 calanoids. The retrain retained 5 of those false calls. The earlier cruise results include the three development cases. The newly missed investigator-confirmed Themisto came from PS126 (2), PS136 (1), PS80 (3). In descriptive review, the three PS80 animals had pale, curved bodies with visible segmentation. One PS126 crop had a large white gap in the silhouette. The other PS126 animal and the PS136 animal showed dark compact profiles with projections at one end. These observations suggest more than one error pattern.

[Results by cruise](https://github.com/sigaihealth/marinemodels/blob/main/docs/zooscan_calanoid_cruises.csv) · [Results by investigator taxon](https://github.com/sigaihealth/marinemodels/blob/main/docs/zooscan_calanoid_taxa.csv) · [Arctic results by station](https://github.com/sigaihealth/marinemodels/blob/main/docs/zooscan_calanoid_stations.csv)

The research notebook on OOI supports side-by-side comparisons on archived scans and new ZooScan uploads. The public classifier continues to serve its existing production version.
