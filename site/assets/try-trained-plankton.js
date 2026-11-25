import {decodeMorphologyPng, morphologyFeatures, rankMorphology} from "./morphology-inference.js";

const element = id => document.getElementById(id);
const samples = {early: "D20260201T002546_IFCB200_00139", late: "D20260201T152545_IFCB200_04627"};
const files = element("image-file"), run = element("run"), fieldset = element("inputs");
let model, modelHash, exportUrl;

async function sha256(bytes) {
  const hash = await crypto.subtle.digest("SHA-256", bytes);
  return Array.from(new Uint8Array(hash), value => value.toString(16).padStart(2,"0")).join("");
}

function selected() {
  const sample = document.querySelector('input[name="specimen"]:checked');
  if (files.files.length) return {name: files.files[0].name, file: files.files[0]};
  if (sample) return {name: samples[sample.value] + ".png", url: "assets/" + samples[sample.value] + ".png"};
  return null;
}

function clearOutput() {
  element("results").hidden = true;
  if (exportUrl) URL.revokeObjectURL(exportUrl);
  exportUrl = undefined;
  element("download").removeAttribute("href");
}

function select() {
  clearOutput();
  const image = selected();
  element("selected").textContent = image ? image.name : "Choose an image.";
  element("status").textContent = model ? "Ready to measure the crop." : "Loading fitted parameters…";
  run.disabled = !model || !image;
}

document.querySelectorAll('input[name="specimen"]').forEach(input => input.addEventListener("change", () => {
  files.value = "";
  select();
}));
files.addEventListener("change", () => {
  if (files.files.length) document.querySelectorAll('input[name="specimen"]').forEach(input => {input.checked = false;});
  select();
});

run.addEventListener("click", async () => {
  const choice = selected();
  if (!model || !choice) return;
  clearOutput();
  fieldset.disabled = true; run.disabled = true;
  element("status").textContent = "Measuring the crop…";
  try {
    let bytes;
    if (choice.file) {
      if (choice.file.size > 16 * 1024 * 1024) throw new Error("Choose a PNG smaller than 16 MiB.");
      bytes = await choice.file.arrayBuffer();
    } else {
      const response = await fetch(choice.url);
      if (!response.ok) throw new Error("The sample image could not be loaded.");
      bytes = await response.arrayBuffer();
    }
    const {gray, width, height} = await decodeMorphologyPng(bytes);
    const vector = morphologyFeatures(gray, width, height);
    const candidates = rankMorphology(model, vector);
    const rows = candidates.slice(0, 3).map((candidate, i) => {
      const item = document.createElement("li"), name = document.createElement("span"), value = document.createElement("span");
      name.textContent = (i + 1) + ". " + candidate.label.replaceAll("_", " ");
      value.textContent = candidate.distance.toFixed(3);
      item.append(name, value);
      return item;
    });
    element("scores").replaceChildren(...rows);
    const coverage = vector[model.features.indexOf("contrast24_fraction")];
    element("measurements").textContent = width + " × " + height + " pixels. " + (100 * coverage).toFixed(1) + "% of pixels differ from the border median by at least 24 grayscale levels.";
    const record = {
      model: model.schema, model_sha256: modelHash, training_manifest_sha256: model.source.manifest_sha256,
      input: choice.name, input_sha256: await sha256(bytes), size_px: [width, height],
      feature_values: Object.fromEntries(model.features.map((name, i) => [name, vector[i]])),
      score: "euclidean_distance", candidates,
    };
    exportUrl = URL.createObjectURL(new Blob([JSON.stringify(record, null, 2) + "\n"], {type: "application/json"}));
    element("download").href = exportUrl;
    element("results").hidden = false;
    element("status").textContent = "Ranked all ten training classes.";
  } catch (error) {
    element("status").textContent = error.message || "The image could not be classified.";
  } finally {
    run.disabled = !selected(); fieldset.disabled = false;
  }
});

async function start() {
  select();
  try {
    const response = await fetch("assets/ifcb-morphology.json");
    if (!response.ok) throw new Error("The model could not be loaded. Reload to try again.");
    const bytes = await response.arrayBuffer();
    modelHash = await sha256(bytes);
    const loaded = JSON.parse(new TextDecoder().decode(bytes));
    if (loaded.schema !== "ifcb-morphology-centroids-v1" || loaded.labels.length !== 10) throw new Error("Unexpected model version.");
    model = loaded;
    const v = model.validation, t = model.training;
    element("metrics").textContent = "Training used " + t.images.toLocaleString("en-US") + " images from " + t.bins + " bins. On " + v.images + " held-out images from " + v.bins + " other bins, " + v.correct + " first choices matched the source label (" + (100 * v.accuracy).toFixed(1) + "%). Macro-F1 was " + v.macro_f1.toFixed(3) + ".";
    element("class-names").textContent = model.labels.map(label => label.replaceAll("_", " ")).join(" · ");
    select();
  } catch (error) { element("status").textContent = error.message; }
}
start();
