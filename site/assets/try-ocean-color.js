import {oc3m, wavelengths} from "./oc3m.mjs";

const fields = wavelengths.map(nm => document.getElementById("rrs" + nm));
const estimate = document.getElementById("estimate");
const numerator = document.getElementById("numerator");
const ratioDisplay = document.getElementById("ratio");
const logRatioDisplay = document.getElementById("log-ratio");
const status = document.getElementById("result-status");
const origin = document.getElementById("input-origin");
const download = document.getElementById("export-result");
let illustrative = true;
let record = null;

function calculate() {
  record = null;
  download.disabled = true;
  const values = fields.map(field => field.valueAsNumber);
  const result = oc3m(values);
  fields.forEach((field, i) => field.setAttribute("aria-invalid", String(result.invalid[i])));
  origin.textContent = illustrative
    ? "Illustrative inputs (no station or observation date)."
    : "User-entered reflectance. Observation provenance has not been verified.";
  if (result.error) {
    estimate.textContent = numerator.textContent = ratioDisplay.textContent = logRatioDisplay.textContent = "—";
    status.textContent = result.error;
    return;
  }
  const {chlorophyll_a_mg_m3: chlorophyll, selected_blue_wavelengths_nm: selected,
    max_blue_to_green_ratio: ratio, log10_ratio: x, output_clamped: clamped} = result.record;
  estimate.textContent = Number(chlorophyll.toPrecision(4)).toString();
  numerator.textContent = selected.join(" and ") + " nm";
  ratioDisplay.textContent = Number(ratio.toPrecision(5)).toString();
  logRatioDisplay.textContent = Number(x.toPrecision(5)).toString();
  status.textContent = clamped
    ? "The polynomial reached the OCSSW output limit shown above."
    : "Calculated with the MODIS OC3M coefficients from R2022.";
  record = {
    ...result.record,
    input_origin: illustrative ? "illustrative synthetic example" : "user-entered values, provenance unverified",
    sources: ["atbd", "implementation", "limits"].map(id => document.getElementById(id).href)
  };
  download.disabled = false;
}

for (const field of fields) {
  field.addEventListener("input", () => {
    illustrative = false;
    calculate();
  });
}
document.getElementById("reset-inputs").addEventListener("click", () => {
  fields.forEach(field => { field.value = field.defaultValue; });
  illustrative = true;
  calculate();
});
download.addEventListener("click", () => {
  if (!record) return;
  const report = { ...record, exported_at_utc: new Date().toISOString() };
  const blob = new Blob([JSON.stringify(report, null, 2) + "\n"], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = "modis-oc3m-r2022-result.json";
  document.body.append(link);
  link.click();
  link.remove();
  window.setTimeout(() => URL.revokeObjectURL(url), 1000);
});
calculate();
