# Does the Pioneer six-hour salinity gain hold on later storms?

This study keeps the November 2026 tide-and-current fit fixed. The first endpoint is the complete storm that began on November 24 at 15:00 UTC. A separate confirmation cohort consists of the **first three distinct qualifying storms after that event**, in chronological order. Event selection uses observed waves alone. Registering the study before those three storms allows each to test generalization to new conditions at Pioneer Central. [Live scorecard](https://github.com/sigaihealth/marinemodels/blob/pioneer-storm-scores/REPORT.md) · [Refresh history](https://github.com/sigaihealth/marinemodels/actions/workflows/pioneer-confirm.yml)

## Model and baseline

At each hourly issue time the fixed model predicts practical salinity at the same nominal 7 m sensor six hours later. It adds a correction learned from four Duck astronomical tide features and four colocated Pioneer current features to the latest available salinity. Persistence uses exactly the same initial salinity. The published coefficients, input scaling, feature order and lead are fixed. The inference command verifies the model file's SHA-256. The training window had 14,820 eligible rows. Its last training outcome is October 28, 2026 at 23:00 UTC. The model also contains the original temperature coefficients. Salinity is the prespecified comparison for this study. [Frozen fit](frozen_model.json) · [Original experiment](../pioneer-6h-tide-current/README.md)

The registered fit reproduced all 20 previously examined November forecasts to numerical precision. Those 20 entries are identified in the first-capture ledger. The report gives November's entire available score and a separate score for observations beyond those 20. November is reported separately from the three-storm confirmation. [Original predictions](../pioneer-6h-tide-current/results/predictions.csv) · [Registered November entries](initial_forecasts.csv)

## Storm definition and scoring rules

- Use hourly significant wave height from CDIP 192p1 near Oregon Inlet. At least two consecutive bins at or above 3 m define a qualifying run. The original detector merges runs whose successive peaks are less than 72 hours apart or whose expanded windows overlap. Issue windows include 12 hours before onset and 24 hours after the last qualifying hour. Use the event containing the registered November onset even if its peak changes.
- A wave window can close once observed coverage extends at least 72 hours past the last qualifying run, past the verification horizon, and wave sampling supports closure. A gap capable of concealing another event keeps the affected ordering uncertain. Sensor availability never determines which subsequent storms enter the cohort. Every selected event keeps its slot even if few or no forecasts can be verified.
- Pair both forecasts with the same QC-passing measured salinity six hours later on the same deployment. A full score requires all hourly pairs in a closed, sequence-confirmed window. Show the available pair count, expected hours, and partial scores while station data are delayed or missing. Irrecoverable gaps can leave a storm and the final result incomplete.
- For each storm compute mean absolute error (MAE) in practical salinity and gain equal to persistence MAE minus fixed-model MAE. Each subsequent storm has equal weight, regardless of duration. Call the gain sustained across this cohort only if all three are fully scored, their mean gain is positive, and at least two of three individual gains are positive. Ties count as zero gain. Three storms give a descriptive replication. The overlapping six-hour forecasts within a storm share observations.
- Generate predictions for eligible hours between storms as well, so a later wave peak can identify the event window without deciding which forecasts to issue. Keep each prediction and its first-recorded time. Delayed telemetry can put the first capture after target time. Those rows test the frozen model on independent events in replay; the score table also counts pairs recorded before their target time. The 20 legacy entries have unknown capture times.
- Run public-source ingestion and scoring every six hours. On each successful refresh, the results branch stores the model fingerprint, issue-level forecasts, verification measurements, current source extracts and provenance. Git history preserves previous publications as data providers revise observations. Once November and all three successors are fully scored, subsequent scheduled runs skip scoring.

## Reproduce a score

Python's standard library is sufficient for acquisition and forecasting. From the repository root run the following commands. Reuse the output directory across refreshes to preserve first-capture times. To continue the published ledger, use a checkout of the results branch as that directory.

```sh
study=world-model/pioneer-fixed-confirmation
python3 "$study/refresh_inputs.py" --out inputs --cache cache
python3 "$study/score.py" --data inputs --output scores
python3 -m unittest discover -s "$study"
```

To reconstruct a published run offline, check out the desired results commit, decompress its five observation CSV files into the input directory, and copy its refresh_provenance.json alongside them. Run the scorer against a copy of that commit's results directory. Hash checks bind the model, source preprocessing helpers, input snapshot and previously examined predictions. An optional independent coefficient audit, `python3 "$study/freeze_model.py"`, uses NumPy and the original experiment. The scheduled scorer only performs inference. [Data sources and coverage rules](REFRESH.md)
