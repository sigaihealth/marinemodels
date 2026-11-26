"""Apply the fixed November Pioneer model without training or external dependencies."""
import hashlib
import json
import math
from pathlib import Path


MODEL_NAME = "pioneer-6h-tide-current-2026-11"
MODEL_SHA256 = "f8c2fa186b81b6fcc53b801b54d35cdc68f1891f48636f9b4458fd29e964a683"
FEATURES = (
    "tide_now_m", "tide_now_minus_lag3_m", "tide_lead3_minus_now_m",
    "tide_lead6_minus_now_m", "u_now_ms", "v_now_ms", "u_3h_mean_ms", "v_3h_mean_ms",
)
TARGETS = ("temperature_c", "salinity")


def load_model(path=None):
    path = Path(path) if path is not None else Path(__file__).with_name("frozen_model.json")
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != MODEL_SHA256:
        raise ValueError("Frozen Pioneer model checksum differs from the registered artifact")
    return json.loads(raw)


def feature_vector(tide_minus3, tide_now, tide_plus3, tide_plus6, currents):
    """Tide heights are astronomical predictions. Currents are issue-safe hourly means."""
    if len(currents) != 3 or any(len(pair) != 2 for pair in currents):
        raise ValueError("Supply (eastward, northward) currents for hours t-2, t-1 and t")
    return (tide_now, tide_now-tide_minus3, tide_plus3-tide_now, tide_plus6-tide_now,
            *currents[-1], sum(pair[0] for pair in currents)/3, sum(pair[1] for pair in currents)/3)


def predict(model, features, initial):
    """Return temperature (degrees C) and practical salinity for t+6 hours."""
    if len(features) != len(FEATURES) or len(initial) != len(TARGETS):
        raise ValueError("Expected eight predictors and two issue-time station readings")
    if not all(math.isfinite(v) for v in (*features, *initial)):
        raise ValueError("Forecast inputs must all be finite")
    z = [(v-mean)/scale for v, mean, scale in zip(features,model["means"],model["scales"])]
    return tuple(initial[k] + sum(v*b[k] for v,b in zip(z,model["coefficients"]))
                 for k in range(len(TARGETS)))
