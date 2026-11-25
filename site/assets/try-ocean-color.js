"use strict";

const coefficients = [0.26294, -2.64669, 1.28364, 1.08209, -1.76828];
const wavelengths = [443, 488, 547];
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
  const invalid = values.map((value, index) =>
    !Number.isFinite(value) || (index === 0 ? value <= -0.001 : value <= 0)
  );
  fields.forEach((field, i) => field.setAttribute("aria-invalid", String(invalid[i])));
  origin.textContent = illustrative
    ? "Illustrative inputs (no station or observation date)."
    : "User-entered reflectance. Observation provenance has not been verified.";
  const [blue, cyan, green] = values;
  const ratio = Math.max(blue, cyan) / green;
  let problem = "";
  if (invalid.some(Boolean)) {
    problem = "Check the highlighted bands. Enter finite values above −0.001 at 443 nm and above zero at 488 and 547 nm.";
  } else if (!(ratio > 0.21 && ratio < 30)) {
    problem = "The blue-to-green ratio falls outside the model domain. It must be greater than 0.21 and less than 30.";
  }
  if (problem) {
    estimate.textContent = numerator.textContent = ratioDisplay.textContent = logRatioDisplay.textContent = "—";
    status.textContent = problem;
    return;
  }
  const x = Math.log10(ratio);
  const [a0, a1, a2, a3, a4] = coefficients;
  const rawChlorophyll = 10 ** (a0 + x * (a1 + x * (a2 + x * (a3 + x * a4))));
  const chlorophyll = Math.min(1000, Math.max(0.001, rawChlorophyll));
  const selected = blue === cyan ? [443, 488] : [blue > cyan ? 443 : 488];
  estimate.textContent = Number(chlorophyll.toPrecision(4)).toString();
  numerator.textContent = selected.join(" and ") + " nm";
  ratioDisplay.textContent = Number(ratio.toPrecision(5)).toString();
  logRatioDisplay.textContent = Number(x.toPrecision(5)).toString();
  status.textContent = chlorophyll !== rawChlorophyll
    ? "The polynomial reached the OCSSW output limit shown above."
    : "Calculated with the MODIS OC3M coefficients from R2022.";
  record = {
    model: "NASA MODIS OC3M band-ratio component",
    coefficient_version: "R2022, NASA OB.DAAC chlorophyll-a ATBD, 2023-11-06, Table 1",
    coefficients_ascending: coefficients,
    input_origin: illustrative ? "illustrative synthetic example" : "user-entered values, provenance unverified",
    rrs_sr_inverse: Object.fromEntries(wavelengths.map((nm, i) => [nm, values[i]])),
    selected_blue_wavelengths_nm: selected,
    max_blue_to_green_ratio: ratio,
    log10_ratio: x,
    chlorophyll_a_mg_m3: chlorophyll,
    output_clamped: chlorophyll !== rawChlorophyll,
    product_scope: "Band-ratio component only. The operational chlor_a product includes an additional color-index algorithm.",
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
