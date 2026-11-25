# Testing SIG.AI's plankton classifier across six collections

The SIG.AI classifier ranks 101 categories for a microscope crop. Researchers assembled 13,930 distinct expert-annotated images from six collections to see where its first choice agrees with a human label, and whether training on its errors improves that choice. The held-out images represent 28 categories. The other 73 still need suitable reference images. [Try the public classifier](https://ocean.sig.ai/sigai-plankton.html)

## Held-out results

The fitting data identified 23 categories for targeted improvement. Training ran on CUDA. The settings were frozen before opening the test images. Each test crop went through the same ONNX graph and CPU execution provider used by the hosted classifier.

| Test data | Mapped images | Original first choice correct | Correction gated by original category | Correction gated by acquisition source |
| --- | ---: | ---: | ---: | ---: |
| Held-out acquisitions from the four fitting collections | 2,060 | 0.3% | 6.7% | 25.1% |
| Baltic and North Sea collections reserved in full | 1,194 | 2.3% | 2.3% | 2.3% |
| Northeast U.S. Shelf IFCB | 634 | 0.5% | 19.7% | 30.4% |
| Naples IFCB | 44 | 2.3% | 18.2% | 29.5% |
| Northern Red Sea IFCB | 36 | 0.0% | 2.8% | 38.9% |
| Bay of Biscay ZooScan | 1,346 | 0.1% | 0.4% | 22.1% |
| Baltic ZooScan | 419 | 0.0% | 0.0% | 0.0% |
| North Sea VPR | 775 | 3.6% | 3.6% | 3.6% |

On the four represented collections, the source-specific correction increased macro-F1 from 0.007 to 0.390. It corrected 512 original first choices and displaced 0 correct first choices. Across the full test, it changed the original top label on 5 of 377 unmapped controls. Those controls have no assigned native truth for judging the replacement.

For the two external collections, source-specific mode retained the original model by design. This verifies its fallback behavior. Generalization to new instruments and to native PlankScope field conditions still requires independent expert labels. Two external collections provide limited evidence about variability between regions.

In the public trial, researchers can request the source-specific ranking alongside the original suggestions for a crop from one of the four fitting collections. Uploaded crops require the researcher to identify their actual collection. The original-category-gated experiment remains available in the private OOI research notebook. [Browser trial](https://ocean.sig.ai/sigai-plankton.html)

## Which categories improved?

These counts use held-out acquisitions from the four represented collections. Each fraction is the number whose first choice agreed with the mapped expert label.

| Group | Original classifier | Source-specific comparison |
| --- | ---: | ---: |
| Radiolarians | 2/35 | 24/35 |
| Fish eggs | 0/82 | 38/82 |
| *Phaeocystis* | 0/147 | 54/147 |
| Barnacle nauplii | 0/88 | 1/88 |

The source-specific comparison improved recall for 23 of the 25 categories represented in this part of the test. Two were tied. Accuracy remained low for barnacle nauplii and *Leptocylindrus* (17/196). On the Baltic held-out collection the baseline identified 0/419 mapped specimens. This is an important limitation for interpreting a prediction on an unfamiliar instrument.

The previous four-group Northeast Shelf reference panel answers a different question and can refer an image to expert review. On the 954 new WHOI crops it offered 390 suggestions, of which 331 matched a source annotation. It referred 564 crops for review. It issued a four-group suggestion on 56 of the 489 crops known to fall outside the panel.

## Sampling and evaluation

| Instrument and collection | Fit | Development | Test |
| --- | ---: | ---: | ---: |
| Imaging FlowCytobot, Northeast U.S. Shelf | 3,059 | 641 | 954 |
| Imaging FlowCytobot, Gulf of Naples | 181 | 40 | 44 |
| Imaging FlowCytobot, Northern Red Sea | 149 | 29 | 36 |
| ZooScan, Bay of Biscay | 4,982 | 1,218 | 1,378 |
| ZooScan, Baltic Sea | 0 | 0 | 444 |
| Video Plankton Recorder, Belgian North Sea | 0 | 0 | 775 |
| **Total** | **8,371** | **1,928** | **3,631** |

The final comparison uses every original category as a possible answer. It scores 3,254 images with a mapped reference label. Another 377 annotated crops act as controls because their source labels have no defensible match in the tested vocabulary. Precision applies to this sampled mix. The class frequencies differ from those of any particular ocean survey.

Among the 3,254 mapped test cases, 1,835 have direct matches, 1,032 have finer labels that support a broader target, and 387 use a historical name or an operational category as a proxy. For example, a Tomopteridae identification supports the broader polychaete category. Historical and operational bins still need confirmation against the original PlankScope labeling guide.

Entire acquisition groups stayed together, and the test excludes all 1,642 acquisition bins from two earlier project experiments. SHA-256 checks excluded repeated images and repeated decoded pixels across splits. The original model's historical training inventory is unavailable, so overlap with that earlier training remains unknown. All sampled Baltic and Belgian images were reserved for the independent transfer test. Each contributes one independent domain to the transfer analysis.

The OOI NVIDIA L40S was used to learn a correction to the rankings from frozen image features. The fitting set determined the weak classes. The development set determined when the correction could change an identification. One option requires the original model's top choice to be among the fitted categories. A second option requires a known acquisition source. The latter keeps the original order on sources outside the four used in fitting. Each comparison uses the same held-out images, with classes equally weighted in macro-F1. Unmapped controls are reported separately.

## Image sources

- WHOI Northeast Shelf IFCB images and annotations by Heidi M. Sosik, Emily E. Peacock, Sidney Batchelder and Joe Futrelle. [WHOI dataset](https://doi.org/10.57967/hf/10839)
- Gulf of Naples MedPlanktonSet by M. S. Mente, E. Houliez, E. Scalco, L. Roselli and D. Sarno. [Dataset](https://doi.org/10.5281/zenodo.15471023) · [Data paper](https://doi.org/10.1038/s41597-025-05973-y)
- Northern Red Sea IFCB library by Herdís G. R. Steinsdóttir, Miguel J. Frada and Derya Akkaynak. [Dataset](https://doi.org/10.5281/zenodo.20716677)
- PELGAS Bay of Biscay ZooScan by Nina Grandrémy and colleagues. [Dataset](https://doi.org/10.17882/94052) · [Data paper](https://essd.copernicus.org/articles/16/1265/2024/)
- SYKE Baltic ZooScan by Joona Kareinen, Annaliina Skyttä and colleagues. [Dataset and attribution](https://doi.org/10.23729/fa115087-2698-4aa5-aedd-11e260b9694d)
- Belgian North Sea LifeWatch Video Plankton Recorder learning set from the Flanders Marine Institute (VLIZ). [Dataset and attribution](https://doi.org/10.14284/607)

The data providers release these collections under [Creative Commons Attribution 4.0](https://creativecommons.org/licenses/by/4.0/). Selected JPEGs were decoded to lossless PNGs. The study records source object identifiers, mapping rules, original collection information and image hashes.
