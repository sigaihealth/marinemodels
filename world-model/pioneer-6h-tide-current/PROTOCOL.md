# Tide and current test at Pioneer

**Question.** Do the astronomical tide at Duck, the observed horizontal current at the Pioneer Central Surface Mooring, or both reduce six-hour temperature or practical salinity error relative to carrying the latest CTD observation forward? Fit on CPU using NumPy. A single station, early deployments and a short fresh observation window constrain the interpretation.

## Storm selection before comparing errors

Retain the previous Oregon Inlet buoy definition (at least two consecutive hourly bins of significant wave height ≥3 m, 72-hour peak separation with overlapping windows merged, starting 12 hours before onset and ending 24 hours after the last qualifying hour). The follow-up period starts November 1, 2026 UTC. Use data known through November 26 at 02 UTC. Later events can merge across the boundary. Report any event that has started without a confirmed ending as **provisional**, use only issues with an actual verifying observation, and keep it separate from the completed-storm average.

For a completed archival comparison, reconstruct the exact issue times used in the previous wind/wave/SST fit and test. Mark each CTD timestamp consumed as input or target (offsets −12, −6, −3, 0 and +6 hours). Include every historical wave-defined window having **zero** overlap with those times over the window and its subsequent six verifying hours. This selection uses timestamps and completeness, without examining forecast errors. Report unscorable windows as well. Archival tests are strictly forward in time for their own fit. They are distinct from storms occurring after the previous study period.

## Forecasts and timing

The primary comparison uses the same issue hours, target hours, and earlier training rows in every arm. Each target is the six-hour change from the current CTD reading. Use persistence (zero change) and three linear corrections:

- **Tide** uses predicted tide height now, its change over the previous three hours, and its changes from now to three and six hours ahead. Duck hourly astronomical predictions are in metres relative to MLLW. The future terms are computed astronomical tides. No future water-level observation is used.
- **Currents** uses eastward and northward observed velocity at issue time and the mean of each component over the three most recent hourly bins. All current and CTD measurements must come from the same deployment. The newest eligible native current observation ends at least 15 minutes before issue. Require complete current bins, without interpolation.
- **Tide + currents** uses both feature sets. Train all three as ridge corrections to persistence with training-only feature means and standard deviations, no intercept or estimated average drift, and a fixed penalty of 0.01 times the number of training hours. There is no hyperparameter or model selection on the held-out windows. Centering imposes zero correction at mean training conditions.

The nominal issue and verification times are six hours apart. CTD measurements must have passing quality flags for both targets, be within the original 15-minute freshness limit, and belong to the same deployment. Source observation timestamps are available. The exact time of historical telemetry delivery is unknown. Today's astronomical constituent tables also do not preserve an issue timestamp per predicted value. Results therefore represent a hindcast.

## Folds and scores

Use expanding training records. For each archival storm, require that each training target is strictly earlier than the start of its window minus 72 hours. Freeze the November fit at November 1 with the same 72-hour purge, even when a provisional window begins later. Also exclude all historical test windows from **every** fit, including their target and lag footprints. Fit a fold only when there are at least 72 complete earlier training hours. Report each fold's actual training size. The April 2024 test is near initial deployment and consequently has a short calibration history.

Compute MAE for each model, target and event, then average the completed, scorable events equally. Report bias, RMSE, hours, per-storm wins and paired differences versus persistence. Compare the joint model with each single extension. Report the ongoing event separately. The small number of independent storms does not support a population significance claim. The deployment run uses frozen source extracts, independent of the publication of final figures.
