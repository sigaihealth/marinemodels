# Pioneer six-hour salinity confirmation

The November event and the next three distinct wave-defined storms use the same frozen tide-and-current model. Persistence carries the latest measured salinity forward. Lower mean absolute error (MAE) is better. A positive gain favors the fixed model.

Wave coverage through **2026-11-26T03:00:00Z**. Latest usable CTD **2026-11-25T04:00:00Z**. Latest usable currents **2026-11-25T04:00:00Z**.

| Storm (UTC onset) | Status | Verified / window hours | Persistence MAE | Fixed model MAE | Gain |
|---|---|---:|---:|---:|---:|
| November · 2026-11-24 | wave window open or unconfirmed | 20 / 49 | 0.4510 | 0.4306 | 0.0204 |
| Next 1 | Awaiting a qualifying event | — | — | — | — |
| Next 2 | Awaiting a qualifying event | — | — | — | — |
| Next 3 | Awaiting a qualifying event | — | — | — | — |

**November follow-up.** 26 forecasts have been saved for this window. 6 still await a usable verification. 0 verified hours are additional to the 20 examined when the model was frozen. On those additional hours persistence MAE is — and fixed-model MAE is —. The open-window denominator can grow until the storm closes.

**Independent follow-up.** 0/3 subsequent storms fully scored. The three-storm result is pending.

Each reported MAE uses identical, QC-passing verification hours for the two forecasts. A full score requires a closed, sequence-confirmed wave window and all issue–target pairs. Per-storm rows with missing observations remain visible. Overlapping hourly forecasts are not independent storms. Predictions are retained on first capture; observations can arrive late. The ledger records capture time to distinguish backfills from predictions saved before target time.

[Registered protocol and model](https://github.com/sigaihealth/marinemodels/tree/main/world-model/pioneer-fixed-confirmation) · [Per-storm scores](per_storm.csv) · [Paired verifying observations](verified.csv) · [Forecast ledger](predictions.csv) · [Run history](https://github.com/sigaihealth/marinemodels/actions/workflows/pioneer-confirm.yml)
