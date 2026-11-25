"use strict";
const form = document.querySelector("#compare-form");
const statusLine = document.querySelector("#result-status");
const result = document.querySelector("#result");
const button = form.querySelector("button");
let downloadUrl;

function parseRows(text, kind) {
  const [digest, label, score] = kind === "WHOI" ? ["roi_sha256","label_1","softmax_1"] : ["image_sha256","label","confidence"];
  const parsed = Papa.parse(text, {header:true, skipEmptyLines:"greedy", delimiter:","});
  const required = [digest, label, score];
  if (kind === "WHOI") required.push("roi_id");
  if (parsed.errors.length || Object.keys(parsed.meta.renamedHeaders || {}).length || !required.every(key => parsed.meta.fields?.includes(key))) {
    throw new Error(kind + " needs a valid CSV with " + required.join(", ") + ".");
  }
  const rows = new Map();
  const ids = new Set();
  for (const row of parsed.data) {
    const hash = row[digest].trim().toLowerCase();
    const value = Number(row[score]);
    if (!/^[a-f0-9]{64}$/.test(hash) || rows.has(hash) || !row[label].trim() || !row[score].trim() || !Number.isFinite(value) || value < 0 || value > 1) {
      throw new Error(kind + " has a duplicate, invalid checksum, label or score.");
    }
    if (kind === "WHOI" && (!row.roi_id.trim() || ids.has(row.roi_id))) throw new Error("WHOI requires distinct ROI identifiers.");
    ids.add(row.roi_id);
    rows.set(hash, {label:row[label], score:value, id:row.roi_id});
  }
  if (!rows.size) throw new Error(kind + " has no predictions.");
  return rows;
}

function element(tag, value) {
  const item = document.createElement(tag);
  item.textContent = value;
  return item;
}

async function fileText(file) {
  if (file.size > 12 * 1024 * 1024) throw new Error("For files over 12 MiB use the offline comparison tool.");
  return file.text();
}

form.addEventListener("submit", async event => {
  event.preventDefault();
  result.replaceChildren();
  if (downloadUrl) URL.revokeObjectURL(downloadUrl);
  statusLine.textContent = "Matching original image checksums…";
  button.disabled = true;
  try {
    const scopeFile = document.querySelector("#scope-file").files[0];
    const whoiFile = document.querySelector("#whoi-file").files[0];
    const scope = parseRows(await fileText(scopeFile), "PlankScope");
    let reference;
    if (whoiFile) reference = await fileText(whoiFile);
    else {
      const response = await fetch("assets/pioneer_whoi_predictions.csv");
      if (!response.ok) throw new Error("Could not fetch the Pioneer WHOI reference.");
      reference = await response.text();
    }
    const whoi = parseRows(reference, "WHOI");
    if (scope.size !== whoi.size || [...scope.keys()].some(hash => !whoi.has(hash))) throw new Error("The image sets differ. Export predictions for the same original crops.");
    const pairs = Array.from(whoi, ([hash,left]) => ({image_sha256:hash, roi_id:left.id, whoi_label:left.label, whoi_score:left.score, plankscope_label:scope.get(hash).label, plankscope_score:scope.get(hash).score}));
    const table = document.createElement("table");
    const head = table.createTHead().insertRow();
    for (const column of ["Image","WHOI suggestion","PlankScope suggestion"]) head.append(element("th",column));
    const body = table.createTBody();
    for (const pair of pairs.slice(0,100)) {
      const row = body.insertRow();
      for (const value of [pair.roi_id,pair.whoi_label,pair.plankscope_label]) row.append(element("td",value));
    }
    const scroller = document.createElement("div"); scroller.className = "result-table";scroller.append(table);
    const link = element("a","Download all paired predictions (JSON)");
    downloadUrl = URL.createObjectURL(new Blob([JSON.stringify({status:"unreviewed_model_predictions", pairs},null,2)],{type:"application/json"}));
    link.href = downloadUrl; link.download = "plankscope-whoi-pairs.json";
    result.append(scroller,link);
    statusLine.textContent = pairs.length + " matched images. Showing " + Math.min(pairs.length,100) + ". Predictions await expert review.";
  } catch (error) {
    statusLine.textContent = error.message;
  } finally {
    button.disabled = false;
  }
});
