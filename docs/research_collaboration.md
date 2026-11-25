# SIG.AI Ocean research platform

A researcher should be able to open an example, run a model, inspect where a result came from, and invite someone to reproduce or challenge it. The contributor should get something concrete back, such as a second instrument's comparison, a corrected label, a citable replication or credit on a benchmark. Pioneer is the first case study. Its 24 paired predictions establish that two classifiers accept the same images. Independent labels are needed to measure their accuracy.

## What researchers can do now

The public workspace organizes nine scientific tasks. The plankton trial runs WHOI's published model in the visitor's browser. The ocean-color trial calculates chlorophyll from reflectance. The physics explorer displays a subset of a published GLONET forecast. Each describes its execution mode. A PlankScope owner can import private classifier outputs and match them to WHOI by image checksum. The public contribution form accepts links, citations, requests and corrections. Contributors choose whether to invite a credited listing or independent replication. [Task workspace](https://ocean.sig.ai/model-catalog.html) · [PlankScope connector](https://ocean.sig.ai/plankscope.html) · [Research contributions](https://ocean.sig.ai/collaborate.html)

## Four records that can travel between labs

| Shareable record | Minimum useful contents | What a collaborator can return |
| --- | --- | --- |
| Dataset or instrument sample | Owner, version or DOI, access terms, UTC, instrument, region at permitted precision, depth, units, QC and stable sample IDs. For imaging, include volume and crop checksum where known. | Corrected metadata, independently reviewed labels or a comparable sample from a different deployment. |
| Model or instrument adapter | Task, owner, version, input schema, preprocessing, outputs, separate code and checkpoint terms, a known failure and one runnable example. | A reproduction on the example and a cross-instrument test using the same input contract. |
| Run | Input identifiers and hashes, model and preprocessing revisions, execution environment, parameters, completion status, output URI and optional compute usage. | A linked rerun, a baseline comparison, or a failure with evidence. |
| Finding or review | A narrow claim, linked observations and runs, uncertainty, review status, contributor roles and the question still open. | A replication, counterexample, correction or request for a blinded review. Corrections should supersede an earlier version and preserve its history. |

Reuse established archives and identifiers. Hugging Face cards already describe datasets and models. Existing version DOIs can identify releases. For marine occurrence records, map the sampling event and measurements to Darwin Core and OBIS conventions when applicable. A cropped particle can remain unresolved. A classifier's suggestion alone should never create a verified occurrence record. [Hugging Face dataset cards](https://huggingface.co/docs/hub/datasets-cards) · [Zenodo records](https://help.zenodo.org/docs/deposit/about-records/) · [OBIS guidance](https://manual.obis.org/darwin_core.html)

## PlankScope as an ecosystem participant

PlankScope fits at acquisition, inference and review. Its camera workflow can detect objects, and the standalone crop classifier can score existing regions. Keep the raw frame ID distinct from the crop ID and identify the detector that produced each crop. Pair models by original crop checksum. Include sample volume, units and sampling effort before interpreting image counts as concentrations. An expert's correction is a new annotation with provenance. Retraining requires a separate, explicit data-use grant.

The present integration exchanges prediction files locally. A proposed instrument adapter would let an operator choose a sample or batch, preview a manifest, and share approved thumbnails, results or references to restricted material. Sending data and allowing model training are separate choices. Model owners could also provide an approved inference endpoint while keeping weights on their own infrastructure.

## How OOI compute could fit

OOI describes JupyterHub as per-user research environments co-located with ocean observations. Our research session exposed a 32-CPU quota, 187 GiB RAM and one NVIDIA L40S with 46,068 MiB VRAM. These are observations from one allocation. Public traffic, uptime, unattended jobs and sharing a worker across researchers require discussion with OOI. The current public trials make no calls to a personal OOI session. [OOI access and setup guide](https://ooifb.org/wp-content/uploads/2024/10/ooi_jupyterhub_access_and_setup-1.pdf)

1. **Research pilot.** Use the authorized Jupyter session for investigator-launched batch inference on OOI data. Keep raw observations near the archive. Export a versioned run manifest and a small, approved result to SIG.AI. Profile one complete sample before requesting sustained GPU hours.
2. **Collaborator jobs.** After operator agreement, let authenticated labs submit a task and versioned dataset reference to a SIG.AI queue. An approved worker claims a time-limited job, validates the requested model and data access, stages inputs, and returns outputs to lab-scoped storage. Use an idempotent run ID and checkpoint completed batches so interrupted allocations can resume. Track GPU seconds, peak memory, queue time and failures by task.
3. **Public, low-latency inference.** Keep small models in the browser where possible. Operate a separately budgeted SIG.AI inference service for models needing a warm GPU or a public availability commitment. Cache approved public examples by input hash and model revision. Apply file limits, expiry, per-user quotas and a compute budget. A service-approved OOI worker could remain one of several backends.

Size deployments by model and task. A single microscope crop, a regional scene and a ten-day global forecast have different memory, latency and data-transfer requirements. Offer a precomputed example when an entire forecast is too expensive to generate interactively. Label measured hardware and resource limits per runnable deployment.

## How a new release earns a Run button

A maintainer pins the checkpoint and runtime, verifies the rights for the intended hosting mode, and supplies a small example with an expected result. Test it on the target worker for output parity, peak memory, latency and input limits. Then expose the version with its actual mode: on-device inference, queued research job, provider-hosted demo or archived output. When a newer checkpoint appears, test it alongside the current version before changing the default. Retain the old revision for reproducibility. A model with inaccessible weights can still have a research record and an owner contact or official release link.

Start by routing cheap, bounded jobs to the browser. For a future queued run the UI should show the chosen input, model revision, estimated wait and file visibility before submission. On completion, return a downloadable result, an evidence link and an optional invitation to share a finding. One-click reuse of a public example should work without giving a third party access to someone else's instrument or credentials.

## Collaboration incentives and release sequence

Start with a defined exchange: an instrument team contributes a versioned sample, a model team returns predictions, and a reviewer supplies a blind label with uncertainty. Credit all three roles. Invite a second lab to rerun the comparison on a different instrument. Publish both failures and successful replications, with separate credit for data collection, software, annotation and review.

Next, add lab workspaces with drafts, reviewer invitations, access expiry and owner-approved publishing. A lab should be able to list a public description and keep files in its chosen repository. Keep embargoed files, precise sensitive locations and private model weights out of public contributions. Collect separate opt-ins for inference, redistribution and training. Verify checkpoint, code, data and dependency terms before adding a model to shared hosting. [Zenodo access and embargo options](https://help.zenodo.org/docs/about/whats-changed/)

Measure time to first successful result, fraction of shared runs independently reproduced, datasets reused by another lab, reviews returned to a contributor and compute cost per successful run. Test the workflow with one instrument team, one outside dataset owner and one independent reviewer before expanding the hosted fleet.
