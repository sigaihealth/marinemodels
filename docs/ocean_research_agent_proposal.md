# Ocean Research Agent Pilot Proposal

SIG.AI  |  Prepared for the Ocean Observatories Initiative and research collaborators  |  November 25, 2026

SIG.AI proposes a six-week pilot on ocean.sig.ai. A researcher will be able to ask a question about a coastal storm, examine the sensor measurements and plankton images behind the answer, and rerun the analysis in Jupyter. We request scheduled research compute from OOI and invite an ocean scientist to review the pilot independently.

**Compute request.** We request access to one GPU with 80 GB of device memory per scheduled job. Two 48 GB NVIDIA L40S GPUs on the same node are an alternative for jobs that split the model across devices. We will use the existing single L40S to measure memory use and runtime before sizing longer runs. The six-week pilot covers the research agent. A regional ocean forecasting model is a proposed follow-on.

## What the Pioneer observations can tell us

“Did plankton bloom during Winter Storm Gianna?” is the first question we want a researcher to try. At the Pioneer Mid-Atlantic Bight Central Surface Mooring off North Carolina, the Imaging FlowCytobot (IFCB) recorded 7.45 times as many image regions per milliliter in the afternoon sample as in the early morning sample. Nearby salinity measurements fell over the same period. [OOI event description](https://oceanobservatories.org/2026/09/ooi-plankton-imagery-and-co-located-environmental-data-now-ready-for-analysis/) · [Replay data and methods](https://github.com/sigaihealth/marinemodels#what-happened-on-february-1)

| February 1, 2026 (UTC) | Volume sampled | Image regions | Regions per mL | Practical salinity¹ |
| --- | --- | --- | --- | --- |
| 00:25:46 | 4.615 mL | 1,065 | 231 | 35.061 |
| 15:25:45 | 3.005 mL | 5,164 | 1,718 | 34.582 |

¹ Nearest conductivity, temperature and depth instrument reading. Salinity passed aggregate quality control (flag 1). Both image concentrations carried flag 2, meaning quality had not been evaluated.

The six-day replay has IFCB observations in 42 of 144 hourly bins. Image regions include plankton, aggregates and other particles. The difference in these two samples could reflect changes in any of those groups. To investigate a bloom, the agent would help a researcher draw a random sample of images across storm phases for expert review, compare volume-normalized plankton groups, and inspect chlorophyll and currents for evidence of growth or transport.

The replay, its Jupyter notebook and browser-based model trials are available today. The proposed work connects them into an investigation that another lab can reproduce. [Pioneer storm workspace](https://ocean.sig.ai/pioneer-storm.html) · [Marine Models repository](https://github.com/sigaihealth/marinemodels)

## The researcher workflow

**Choose the evidence.** A researcher opens the Pioneer event and asks a question. The agent shows the station, depth, UTC window, instruments and quality filters it intends to use. The researcher can change those choices or open each source sample.

**Run and inspect the analysis.** Tested Python functions align observations, retain time offsets, calculate particle concentrations from counts and sampled volumes, flag gaps, and plot results. The language model selects a tool and explains the returned values. Each quantitative claim links to a result row and its source samples. Interpretations identify the evidence that would distinguish competing explanations.

**Review images and compare models.** Use an IFCB model for Pioneer imagery. PlankScope users can compare the SIG.AI 101-class classifier with a compatible baseline on matching crops and shared label groups. Preserve instrument identity, image IDs, model revisions and expert annotations. Researchers can set low-confidence or ambiguous crops aside for review. The SIG.AI weights and inference source stay on a private service. [Plankton lab](https://ocean.sig.ai/plankton-lab.html) · [SIG.AI classifier](https://ocean.sig.ai/sigai-plankton.html)

**Repeat and share.** Each run returns a figure, a CSV, an executable notebook and a record of data versions, code revision, model versions, filters and random seed. A collaborator can rerun it, change one assumption and link the new result to the original. Contributors choose which runs, images and corrections to share and receive attribution. [Collaboration design](https://github.com/sigaihealth/marinemodels/blob/main/docs/research_collaboration.md)

## How the pilot will be judged

Before development, we will reserve a second event or deployment for a blind test. An ocean researcher will write 20 reference questions for that event covering calculations, data quality, image interpretation and questions the evidence cannot resolve. The reviewer will keep the questions and answers private until both agents are frozen. Both models will receive identical inputs. The following are proposed acceptance criteria.

| Measure | Proposed pilot target |
| --- | --- |
| Scientific answers | At least 18 of 20 answers satisfy the expert rubric. Every reported measurement in the scored set matches its reference calculation within the stated rounding tolerance and carries the correct unit. |
| Evidence and uncertainty | Every scored numerical claim links to its input records. All designated missing-data and unsupported-cause questions identify the limitation. Report counts for each question type. |
| Independent reproduction | A second researcher recreates the Gianna figure and numerical results and reruns the held-out event from the exported notebook and pinned inputs. |

## Work plan and GPU allocation

| Proposed timing | Work and deliverable |
| --- | --- |
| Weeks 1 and 2 | Package the Gianna analysis tools and data references. Agree on scoring rules and reserve an event with the scientific reviewer. Deliver a reproducible baseline notebook. |
| Weeks 3 and 4 | Add the browser question workflow, source-linked answers, image review and notebook export. Compare open-weight Qwen3-8B and Qwen3-32B using identical tools and evidence. |
| Weeks 5 and 6 | Freeze the agent, run the blind evaluation and independent reproduction, and document errors. Deliver the runnable pilot, benchmark results and measured compute report. |

SIG.AI would operate the browser application and private inference service. Investigators would launch scheduled OOI research jobs for model comparisons, batch image classification and any targeted fine-tuning. Retrieval, quality checks and reference calculations can run on CPUs. Browser visitors would use SIG.AI infrastructure. [Qwen3-8B model card](https://huggingface.co/Qwen/Qwen3-8B) · [Qwen3-32B model card](https://huggingface.co/Qwen/Qwen3-32B)

Qwen3-32B has 32.8 billion parameters. At two bytes per parameter its weights alone occupy about 66 GB, before memory for inputs and intermediate calculations. An 80 GB card would let us benchmark higher precision alongside a quantized run on the existing L40S. We will report peak device memory, input length, batch size, throughput and GPU-hours alongside answer quality. We will choose the smaller model if it meets the evaluation criteria at comparable quality. If expert review identifies a recurring error, we will test a small trainable adapter against the frozen model. In the two-card configuration each device has its own memory, and sharded runs exchange data over PCIe. [L40S specifications](https://www.nvidia.com/en-us/data-center/l40s/) · [Adapter training method](https://arxiv.org/abs/2305.14314)

## From storm replay to an ocean world model

The next scientific question is whether a researcher could have predicted freshening before a storm arrived. We propose to train a regional model that predicts temperature and salinity at observed stations and depths 6, 24 and 72 hours ahead. The model would use recent ocean observations and wind forecasts available at the time of issue. The agent would run the forecast, show its uncertainty and compare it with the measurements that subsequently arrived.

We would test on whole storms withheld from training, measure error and prediction-interval coverage by lead time, and compare against persistence (the last observed value). Recovered imagery could support a separate retrospective test of whether images improve predictions. We would seek a larger allocation only if measured forecast skill, memory and runtime justify it.
