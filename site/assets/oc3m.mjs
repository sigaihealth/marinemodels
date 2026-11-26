export const wavelengths = [443, 488, 547];
const coefficients = [0.26294, -2.64669, 1.28364, 1.08209, -1.76828];

export function oc3m(values) {
  const invalid = values.map((value, i) => !Number.isFinite(value) || (i === 0 ? value <= -0.001 : value <= 0));
  if (invalid.some(Boolean)) {
    return {invalid, error: "Check the highlighted bands. Enter finite values above −0.001 at 443 nm and above zero at 488 and 547 nm."};
  }
  const [blue, cyan, green] = values;
  const ratio = Math.max(blue, cyan) / green;
  if (!(ratio > 0.21 && ratio < 30)) {
    return {invalid, error: "The blue-to-green ratio falls outside the model domain. It must be greater than 0.21 and less than 30."};
  }
  const x = Math.log10(ratio);
  const [a0, a1, a2, a3, a4] = coefficients;
  const raw = 10 ** (a0 + x * (a1 + x * (a2 + x * (a3 + x * a4))));
  const chlorophyll = Math.min(1000, Math.max(0.001, raw));
  return {invalid, record: {
    model: "NASA MODIS OC3M band-ratio component",
    coefficient_version: "R2022, NASA OB.DAAC chlorophyll-a ATBD, 2023-11-06, Table 1",
    coefficients_ascending: coefficients,
    rrs_sr_inverse: Object.fromEntries(wavelengths.map((nm, i) => [nm, values[i]])),
    selected_blue_wavelengths_nm: blue === cyan ? [443, 488] : [blue > cyan ? 443 : 488],
    max_blue_to_green_ratio: ratio,
    log10_ratio: x,
    chlorophyll_a_mg_m3: chlorophyll,
    output_clamped: chlorophyll !== raw,
    product_scope: "Band-ratio component only. The operational chlor_a product includes an additional color-index algorithm."
  }};
}
