const samples = {
  early: {id: "D20260201T002546_IFCB200_00139", title: "Pioneer region 139"},
  late: {id: "D20260201T152545_IFCB200_04627", title: "Pioneer region 4627"},
  whoi: {id: "whoi-coscinodiscus-reference", title: "WHOI reference · Coscinodiscus",
         roi: "IFCB5_2017_103_164054_01283", source: "https://doi.org/10.57967/hf/10839"}
};
const sampleHashes = {
  early: "7dd6c14fba2e62c3eaeafb0863ca52c385937aff45dc3dc31ada87508f13872b",
  late: "891ed7ceb9b97620367225ff9bd1cb8622b7c78a09d802cb26b0a2bf0c5afe55",
  whoi: "ee17e94ed8473fb1debf7273340974bd70fc5efb86d9866484a79628cdb12ad7"
};
const maxBytes = 2 * 1024 * 1024;
const get = id => document.getElementById(id);
const upload = get("crop");
const submit = get("run");
const sourceOptIn = get("source-opt-in");
const sourcePicker = get("source-id");
const sourceNames = new Map(Array.from(sourcePicker.options).filter(o => o.value).map(o => [o.value, o.text]));
const status = get("status");
let downloadUrl;
let currentRequest;

function selection() {
  const file = upload.files[0];
  if (file) return {title: file.name, file};
  const sample = document.querySelector('input[name="sample"]:checked');
  return sample ? samples[sample.value] : null;
}

function message(text, error = false) {
  status.textContent = text;
  status.classList.toggle("error", error);
}

function clearResult() {
  get("results").hidden = true;
  if (downloadUrl) URL.revokeObjectURL(downloadUrl);
  downloadUrl = undefined;
  get("download").removeAttribute("href");
}

function selectedSource(image) {
  if (!sourceOptIn.checked || sourceOptIn.disabled) return null;
  if (image === samples.whoi) return "whoi_nes";
  if (image?.file && sourceNames.has(sourcePicker.value)) return sourcePicker.value;
  return null;
}

function resetSource() {
  sourceOptIn.checked = false;
  sourcePicker.value = "";
}

function changed() {
  const image = selection();
  clearResult();
  get("selected").textContent = image ? "Selected image · " + image.title : "Choose an image.";
  message(image ? "Ready to classify." : "Select a Pioneer sample or a PNG.");
  const eligible = Boolean(image?.file || image === samples.whoi);
  if (!eligible) resetSource();
  sourceOptIn.disabled = !eligible;
  get("source-help").textContent = image === samples.whoi
    ? "This image is from the WHOI Northeast U.S. Shelf IFCB collection. Select the comparison to see how a model fitted to that source ranks it."
    : image?.file
      ? "Select this if the image came from a fitted collection and you know which one."
      : "The Pioneer samples have no fitted source-specific ranking.";
  get("source-picker").hidden = !(image?.file && sourceOptIn.checked);
  const needsSource = sourceOptIn.checked && !selectedSource(image);
  submit.disabled = !image || needsSource;
  if (needsSource) message("Choose the recorded source collection, or clear the source comparison.");
}

function validatePng(buffer) {
  const bytes = new Uint8Array(buffer);
  const view = new DataView(buffer);
  const signature = [137, 80, 78, 71, 13, 10, 26, 10];
  const invalid = "Choose a complete 8-bit grayscale or RGB PNG.";
  if (bytes.length < 45 || !signature.every((byte, i) => bytes[i] === byte)) throw new Error(invalid);
  if (view.getUint32(8) !== 13 || view.getUint32(12) !== 0x49484452) throw new Error(invalid);
  const width = view.getUint32(16);
  const height = view.getUint32(20);
  if (!width || !height || width * height > 4_000_000) throw new Error("Choose an image with at most four megapixels.");
  if (bytes[24] !== 8 || ![0, 2].includes(bytes[25])) throw new Error("Choose an opaque 8-bit grayscale or RGB PNG.");
  let pixels = false;
  for (let i = 33; i + 12 <= bytes.length;) {
    const length = view.getUint32(i);
    const type = view.getUint32(i + 4);
    if (length > bytes.length - i - 12) throw new Error(invalid);
    if (type === 0x74524e53 || type === 0x6163544c) throw new Error("Choose a single opaque PNG without transparency or animation.");
    if (type === 0x49444154) pixels = true;
    if (type === 0x49454e44 && pixels && length === 0 && i + 12 === bytes.length) return {width, height};
    i += 12 + length;
  }
  throw new Error(invalid);
}

async function readImage(image, signal) {
  let blob = image.file;
  if (!blob) {
    const source = await fetch("assets/" + image.id + ".png", {signal});
    if (!source.ok) throw new Error("The sample image could not be loaded. Try again or choose a file.");
    blob = await source.blob();
  }
  if (!blob.size || blob.size > maxBytes) throw new Error("Choose a PNG file up to 2 MiB.");
  const buffer = await blob.arrayBuffer();
  const size = validatePng(buffer);
  const digest = await crypto.subtle.digest("SHA-256", buffer);
  const sha = Array.from(new Uint8Array(digest), b => b.toString(16).padStart(2, "0")).join("");
  return {buffer, size, sha};
}

function responseError(statusCode) {
  if (statusCode === 429) return "The service has received too many requests. Please try again shortly.";
  if (statusCode === 413) return "The image exceeds the upload limit. Choose a PNG up to 2 MiB.";
  if ([400, 415, 422].includes(statusCode)) return "The classifier could not read this crop. Choose an opaque grayscale or RGB PNG.";
  return "The classification service is unavailable. Please try again later.";
}

function referenceResult(data) {
  if (!data || !["reference_suggestion", "expert_review"].includes(data.status) ||
      typeof data.scope !== "string" || !data.scope || typeof data.reason !== "string" || !data.reason ||
      !Number.isFinite(data.reference_score) || data.reference_score < 0 || data.reference_score > 1 ||
      (data.status === "reference_suggestion" && (typeof data.suggestion !== "string" || !data.suggestion.trim())) ||
      (data.status === "expert_review" && data.suggestion !== null)) return null;
  return {scope: data.scope, status: data.status, suggestion: data.suggestion,
          reference_score: data.reference_score, reason: data.reason};
}

function sourceComparison(data, expectedSource, original) {
  if (!data || data.mode !== "source-opt-in" || data.source !== expectedSource ||
      !["unchanged", "reordered"].includes(data.status) || !Array.isArray(data.ranked_labels) ||
      data.ranked_labels.length !== 3 || data.ranked_labels.some(s => typeof s !== "string" || !s.trim()) ||
      new Set(data.ranked_labels).size !== 3) return null;
  const [pick, ...rest] = data.ranked_labels;
  const native = original.map(row => row.label);
  const changed = pick !== native[0];
  if (changed !== (data.status === "reordered")) return null;
  const remainder = native.filter(label => label !== pick).slice(0, 2);
  if (!rest.every((label, i) => label === remainder[i])) return null;
  return {mode: data.mode, source: expectedSource, status: data.status, ranked_labels: [pick, ...rest]};
}

function publicResult(data, image, sha, size, useReference, source) {
  const badResponse = "The service returned an incomplete prediction. Please try again.";
  if (data?.model !== "SIG.AI Plankton Classifier" ||
      typeof data.version !== "string" || !data.version.trim() ||
      !Array.isArray(data.candidates) || data.candidates.length !== 3) throw new Error(badResponse);
  const candidates = data.candidates.map(({label, score}) => {
    if (typeof label !== "string" || !label.trim() || !Number.isFinite(score) || score < 0 || score > 1) {
      throw new Error(badResponse);
    }
    return {label, score};
  });
  if (new Set(candidates.map(row => row.label)).size !== 3 ||
      candidates.some((row, i) => i && row.score > candidates[i - 1].score)) throw new Error(badResponse);
  return {
    model: data.model, version: data.version, status: "provisional_model_suggestions",
    image: image.file ? image.title : image.id, input_sha256: sha, size_px: [size.width, size.height],
    ...(image.file ? {} : {roi_id: image.roi || image.id,
                           source: image.source || "https://ifcb-data.oceanobservatories.org/data/" + image.id + ".png"}),
    candidates, ...(useReference ? {reference: referenceResult(data.reference)} : {}),
    ...(source ? {
      source_candidate_request: {source, source_basis: image.file ? "user_selected_collection" : "verified_example_collection"},
      source_candidate: sourceComparison(data.source_candidate, source, candidates)
    } : {})
  };
}

function show(result) {
  const nodes = result.candidates.map((item, i) => {
    const row = document.createElement("li");
    const label = document.createElement("span");
    const score = document.createElement("span");
    label.textContent = (i + 1) + ". " + item.label;
    score.textContent = item.score.toFixed(4);
    row.append(label, score);
    return row;
  });
  get("scores").replaceChildren(...nodes);
  const includeReference = Object.hasOwn(result, "reference");
  get("reference").hidden = !includeReference;
  if (includeReference) {
    const ref = result.reference;
    get("reference-choice").textContent = !ref ? "Reference comparison unavailable for this run." :
      ref.status === "reference_suggestion" ? "Reference suggestion · " + ref.suggestion : "Expert review recommended.";
    get("reference-explanation").textContent = ref?.reason || "";
    get("reference-score").textContent = ref ?
      "Reference score · " + ref.reference_score.toFixed(4) + ". This score comes from a separate model." : "";
  }
  const requestedScope = result.source_candidate_request;
  get("original-title").hidden = !requestedScope;
  get("source-result").hidden = !requestedScope;
  if (requestedScope) {
    const comparison = result.source_candidate;
    const scope = sourceNames.get(requestedScope.source);
    get("source-result-note").textContent = !comparison
      ? scope + " · Comparison unavailable for this run. The original suggestions are shown above."
      : scope + (comparison.status === "reordered" ? " · The first suggestion changed." : " · The first suggestion stayed the same.");
    const entries = (comparison?.ranked_labels || []).map(label => {
      const li = document.createElement("li");
      li.textContent = label;
      return li;
    });
    get("source-ranks").replaceChildren(...entries);
    get("source-result-score").textContent = comparison
      ? "The comparison returns an ordering. The scores above belong to the original 101-category model." : "";
  }
  get("version").textContent = "Model version · " + result.version;
  downloadUrl = URL.createObjectURL(new Blob([JSON.stringify(result, null, 2) + "\n"], {type: "application/json"}));
  get("download").href = downloadUrl;
  get("results").hidden = false;
  message("Three provisional suggestions.");
}

document.querySelectorAll('input[name="sample"]').forEach(input => input.addEventListener("change", () => {
  upload.value = "";
  resetSource();
  changed();
}));
upload.addEventListener("change", () => {
  resetSource();
  if (upload.files[0]) {
    document.querySelectorAll('input[name="sample"]').forEach(input => { input.checked = false; });
  }
  changed();
});
get("ifcb-context").addEventListener("change", changed);
sourceOptIn.addEventListener("change", () => {
  if (!sourceOptIn.checked) sourcePicker.value = "";
  changed();
});
sourcePicker.addEventListener("change", changed);
get("cancel").addEventListener("click", () => currentRequest?.abort());
get("classify").addEventListener("submit", async event => {
  event.preventDefault();
  const image = selection();
  if (currentRequest || !image) return;
  const source = selectedSource(image);
  if (sourceOptIn.checked && !source) {
    changed();
    return;
  }
  const controller = new AbortController();
  currentRequest = controller;
  let timedOut = false;
  const timeout = setTimeout(() => { timedOut = true; controller.abort(); }, 60_000);
  clearResult();
  get("inputs").disabled = submit.disabled = true;
  get("cancel").hidden = false;
  message("Checking the selected image…");
  try {
    const {buffer, size, sha} = await readImage(image, controller.signal);
    message("Waiting for the classifier…");
    const useReference = get("ifcb-context").checked;
    if (source && [sampleHashes.early, sampleHashes.late].includes(sha)) {
      throw new Error("This image matches a Pioneer sample. Clear the source comparison to classify it.");
    }
    if (source && sha === sampleHashes.whoi && source !== "whoi_nes") {
      throw new Error("This image matches the WHOI reference crop. Choose the WHOI collection or clear the comparison.");
    }
    const params = new URLSearchParams();
    if (useReference) params.set("context", "ifcb");
    if (source) params.set("source_candidate", source);
    const url = "/api/plankton/predict" + (params.size ? "?" + params.toString() : "");
    const response = await fetch(url, {
      method: "POST", headers: {"Content-Type": "image/png", "Accept": "application/json"},
      body: buffer, signal: controller.signal, cache: "no-store", credentials: "omit", redirect: "error"
    });
    if (!response.ok) {
      if (response.status === 422 && response.headers.get("Content-Type")?.includes("application/json")) {
        const detail = await response.json().catch(() => null);
        if (detail?.error === "empty_crop") throw new Error("This crop contains a single color. Choose an image with visible specimen detail.");
      }
      throw new Error(responseError(response.status));
    }
    if (!response.headers.get("Content-Type")?.includes("application/json")) throw new Error(responseError(503));
    const data = await response.json();
    show(publicResult(data, image, sha, size, useReference, source));
  } catch (error) {
    if (controller.signal.aborted) {
      message(timedOut ? "The classifier timed out. Please try again." : "Run canceled.", timedOut);
    } else {
      message(error instanceof TypeError || error instanceof SyntaxError ? responseError(503) : error.message, true);
    }
  } finally {
    clearTimeout(timeout);
    currentRequest = undefined;
    get("inputs").disabled = false;
    submit.disabled = !selection() || (sourceOptIn.checked && !selectedSource(selection()));
    get("cancel").hidden = true;
  }
});
changed();
