# Six-hour Pioneer temperature and salinity hindcast

This first comparison predicts the hourly near-surface CTD state at the Pioneer Mid-Atlantic Bight Central Surface Mooring six hours after each issue time. The instrument is nominally at 7 m. The reference is the QC-passing, time-aligned CTD observation. All CTD lags, the issue-time measurement and its verifying observation must belong to the same instrument deployment. Practical salinity is dimensionless on PSS-78.

## Split and scoring

Use April 2024 through October 2026, with November 1, 2025 at 00 UTC as the chronological split. Fit on all eligible earlier hours. Purge a minimum of 72 hours between the last training target and the split. Exclude any training data that fall within a wave-defined storm crossing the split. Gianna was previously explored and helped motivate the study. A chronological holdout tests transfer to later events, while a future storm is still needed for prospective validation. Score the frozen models only on storms whose complete windows start in the test period and end before November 1, 2026. Assign forecasts to storms by issue time. The verifying observation may be up to six hours beyond the event window. Identify regional storms from Oregon Inlet significant wave heights of at least 3 m for at least two consecutive hourly bins. Join nearby peaks separated by less than 72 hours and overlapping event windows. Windows include the 12 hours before onset through 24 hours after the last qualifying hour. See [weather processing](sources/WEATHER.md) for exact aggregation and grouping. Storm selection uses wave observations alone. Report data coverage for every held-out event, including events with zero eligible issues.

Compare four predictions on exactly the same issue times and targets in each split:

1. **Persistence** carries the last temperature and salinity forward six hours.
2. **Mooring history** estimates a correction to persistence using the current state, 3-, 6- and 12-hour changes and annual sine and cosine.
3. **History + winds and waves** adds wind components, a wind-speed interaction for each component, significant wave height and its square, and six-hour changes in wind components and wave height.
4. **History + winds, waves and SST maps** also adds temperature differences between the map and the mooring, spatial spread, east–west and north–south map contrasts, and map age. In any retrospective analysis, use only a map whose archive availability precedes the issue time.

Fit the same ridge regression to the six-hour change for each learned model. Standardize inputs on training hours only. Use a fixed ridge penalty of 0.01 times the training sample count and an unpenalized intercept. Do not tune on test storms. Only use observed input histories through the issue time. For station and buoy records, timestamps identify measurements, with historical telemetry latency unverified. Cap the age of a satellite map at 30 days. Require finite fields across all three learned feature sets for the paired comparison.

The primary score is mean absolute error (MAE), averaged equally across held-out storms with at least one eligible observation. Also report pooled hourly MAE, RMSE, bias, and each storm's errors. For paired differences in storm MAE, bootstrap whole storms with replacement (5,000 draws, fixed seed). Count wins per target. Whole-storm resampling preserves hourly dependence within events. Sample sizes, spatial footprints and calendar coverage limit how far skill estimates can be generalized.
