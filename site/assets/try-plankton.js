"use strict";

const samples = {
  early: {
    id: "D20260201T002546_IFCB200_00139", name: "OOI region 139",
    sha256: "7dd6c14fba2e62c3eaeafb0863ca52c385937aff45dc3dc31ada87508f13872b"
  },
  late: {
    id: "D20260201T152545_IFCB200_04627", name: "OOI region 4627",
    sha256: "891ed7ceb9b97620367225ff9bd1cb8622b7c78a09d802cb26b0a2bf0c5afe55"
  }
};
const element = id => document.getElementById(id);
const button = element("run");
const fileInput = element("image-file");
const resultLink = element("download");
const csvLink = element("csv-download");
const statusText = element("status");
const progress = element("progress");
let engine;
let running = false;
let runNumber = 0;
let downloadUrl;
let csvUrl;

function selection() {
  if (fileInput.files.length) return {name: fileInput.files[0].name, file: fileInput.files[0]};
  const selected = document.querySelector('input[name="source"]:checked');
  return selected ? samples[selected.value] : null;
}

function announce(message, error = false) {
  statusText.textContent = message;
  statusText.classList.toggle("error", error);
}

function clearOutput() {
  element("results").hidden = true;
  progress.hidden = true;
  if (downloadUrl) URL.revokeObjectURL(downloadUrl);
  if (csvUrl) URL.revokeObjectURL(csvUrl);
  downloadUrl = null;
  csvUrl = null;
  resultLink.removeAttribute("href");
  csvLink.removeAttribute("href");
}

function busy(value) {
  running = value;
  element("inputs").disabled = value;
  button.disabled = value || !selection();
  button.textContent = value ? "Running…" : "Run classifier";
  element("cancel").hidden = !value;
}

function updateSelection() {
  clearOutput();
  const choice = selection();
  element("selected").textContent = choice ? "Selected image · " + choice.name : "Choose an image to begin.";
  announce(choice ? "Ready to run." : "Select a sample or a PNG file.");
  busy(false);
}

document.querySelectorAll('input[name="source"]').forEach(radio => {
  radio.addEventListener("change", () => {
    fileInput.value = "";
    updateSelection();
  });
});
fileInput.addEventListener("change", () => {
  if (fileInput.files.length) {
    document.querySelectorAll('input[name="source"]').forEach(radio => { radio.checked = false; });
  }
  updateSelection();
});

const percent = new Intl.NumberFormat("en", {maximumSignificantDigits: 4, style: "percent"});
function showResult(result) {
  const items = result.predictions.map(prediction => {
    const item = document.createElement("li");
    const name = document.createElement("span");
    const score = document.createElement("span");
    name.textContent = prediction.label.replaceAll("_", " ");
    score.textContent = percent.format(prediction.softmax);
    item.append(name, score);
    return item;
  });
  element("scores").replaceChildren(...items);
  downloadUrl = URL.createObjectURL(new Blob([JSON.stringify(result, null, 2) + "\n"], {type: "application/json"}));
  resultLink.href = downloadUrl;
  resultLink.download = "ifcb-" + result.input.sha256.slice(0, 12) + ".json";
  const roiId = result.input.source_url ? result.input.name.replace(/\.png$/, "") : result.input.sha256;
  const row = {roi_id: roiId, roi_sha256: result.input.sha256, status: result.status, model_revision: result.model.revision};
  result.predictions.forEach(({label, index, softmax}, i) => {
    row["label_" + (i + 1)] = label;
    row["index_" + (i + 1)] = index;
    row["softmax_" + (i + 1)] = softmax;
  });
  const escapeField = value => '"' + String(value).replaceAll('"', '""') + '"';
  const csv = [Object.keys(row), Object.values(row)].map(fields => fields.map(escapeField).join(",")).join("\r\n") + "\r\n";
  csvUrl = URL.createObjectURL(new Blob([csv], {type: "text/csv;charset=utf-8"}));
  csvLink.href = csvUrl;
  csvLink.download = "ifcb-" + result.input.sha256.slice(0, 12) + ".csv";
  element("results").hidden = false;
}

function fail(message) {
  clearOutput();
  announce(message, true);
  busy(false);
}

function getWorker() {
  if (engine) return engine;
  engine = new Worker("assets/try-plankton-worker.js");
  engine.onmessage = event => {
    const message = event.data;
    if (message.type === "status") {
      announce(message.text);
      progress.hidden = message.progress === undefined;
      if (!progress.hidden) {
        progress.max = 1;
        progress.value = message.progress;
      }
      return;
    }
    if (message.type === "error") {
      fail(message.text);
      return;
    }
    if (message.type === "result") {
      progress.hidden = true;
      announce("Three provisional suggestions · unreviewed");
      showResult(message.result);
      busy(false);
    }
  };
  engine.onerror = () => {
    engine.terminate();
    engine = null;
    fail("The classifier worker stopped. Try again in a current browser with WebAssembly enabled.");
  };
  return engine;
}

button.addEventListener("click", async () => {
  const choice = selection();
  if (!choice || running) return;
  const currentRun = ++runNumber;
  clearOutput();
  busy(true);
  announce("Reading the selected image…");
  try {
    let file = choice.file;
    if (!file) {
      const response = await fetch("assets/" + choice.id + ".png");
      if (!response.ok) throw new Error("The sample image could not be loaded. Try again.");
      file = await response.blob();
    }
    if (file.size > 16 * 1024 * 1024) throw new Error("Choose a PNG file of 16 MiB or smaller.");
    const bytes = await file.arrayBuffer();
    if (currentRun !== runNumber) return;
    const input = {name: choice.file ? choice.name : choice.id + ".png"};
    if (choice.id) {
      input.source_url = "https://ifcb-data.oceanobservatories.org/data/" + choice.id + ".png";
      input.expected_sha256 = choice.sha256;
    }
    getWorker().postMessage({bytes, input}, [bytes]);
  } catch (error) {
    if (currentRun === runNumber) fail(error.message || "This image could not be read. Choose another PNG and try again.");
  }
});

element("cancel").addEventListener("click", () => {
  runNumber++;
  if (engine) {
    engine.onmessage = null;
    engine.onerror = null;
    engine.terminate();
    engine = null;
  }
  clearOutput();
  busy(false);
  announce("Run canceled. You can choose another image or try again.");
  button.focus();
});
