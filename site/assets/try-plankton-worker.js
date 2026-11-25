"use strict";

const revision = "71bc362e8c75014c27692a8f10637d36f411962e";
const modelBase = "https://huggingface.co/sosiklab/NES-plankton-IFCB-classifier-2022";
const weightsUrl = modelBase + "/resolve/" + revision + "/20220209_Jan2022_NES_2.4.onnx";
const weightsSha = "d95db6614d7ccb94738404cf3250506b15b55e853fad09c8a87debdf0e2a0901";
const labelsSha = "e20ed2a59c672b2af10b1cda6743694f52ce728412d9c344ef90c5cb2cc02d03";
const weightsLength = 88391200;
const target = 299;
const runtimeDir = new URL("ifcb-runtime/", self.location.href).href;
let loadedModel;
function status(text, progress) { self.postMessage({type: "status", text, progress}); }

async function sha256(bytes) {
  const digest = new Uint8Array(await crypto.subtle.digest("SHA-256", bytes));
  return Array.from(digest, byte => byte.toString(16).padStart(2, "0")).join("");
}

// Keep native PNG decoding but discard profiles, gamma and orientation metadata.
// The Python reference reads the stored sample values without applying these transforms.
function imagePng(bytes) {
  const raw = new Uint8Array(bytes);
  const header = [137, 80, 78, 71, 13, 10, 26, 10];
  if (raw.length < 33 || !header.every((value, i) => raw[i] === value)) {
    throw new Error("Choose a valid 8-bit PNG microscope crop.");
  }
  const view = new DataView(bytes);
  const parts = [raw.subarray(0, 8)];
  let first = true;
  for (let start = 8; start + 12 <= raw.length;) {
    const length = view.getUint32(start);
    const end = start + 12 + length;
    if (end > raw.length) break;
    const type = String.fromCharCode(...raw.subarray(start + 4, start + 8));
    if (first) {
      if (type !== "IHDR" || length !== 13) break;
      const width = view.getUint32(start + 8);
      const height = view.getUint32(start + 12);
      if (!width || !height || width > 8192 || height > 8192 || width * height > 4000000) {
        throw new Error("Choose a crop up to 4 megapixels, with each edge at most 8,192 pixels.");
      }
      if (raw[start + 16] !== 8) throw new Error("Convert this image to an opaque 8-bit PNG crop first.");
      first = false;
    }
    if (type === "acTL") throw new Error("Use a single still PNG crop.");
    if (["IHDR", "PLTE", "IDAT", "IEND", "tRNS"].includes(type)) parts.push(raw.subarray(start, end));
    if (type === "IEND") return new Blob(parts, {type: "image/png"});
    start = end;
  }
  throw new Error("The PNG file is incomplete. Choose the original image and try again.");
}

async function grayscale(bytes) {
  const image = imagePng(bytes);
  let bitmap;
  try {
    bitmap = await createImageBitmap(image, {colorSpaceConversion: "none", premultiplyAlpha: "none"});
  } catch {
    throw new Error("This PNG could not be decoded. Try saving the microscope crop as a new PNG.");
  }
  try {
    const {width, height} = bitmap;
    const canvas = new OffscreenCanvas(width, height);
    const context = canvas.getContext("2d", {willReadFrequently: true});
    if (!context) throw new Error("A 2D canvas is required to read this image.");
    context.drawImage(bitmap, 0, 0);
    const rgba = context.getImageData(0, 0, width, height).data;
    const pixels = new Uint8Array(width * height);
    for (let i = 0; i < pixels.length; i++) {
      const j = i * 4;
      if (rgba[j + 3] !== 255) throw new Error("This crop contains transparent pixels. Flatten it to an opaque image before running.");
      pixels[i] = (19595 * rgba[j] + 38470 * rgba[j + 1] + 7471 * rgba[j + 2] + 32768) >> 16;
    }
    return {pixels, width, height};
  } finally {
    bitmap.close();
  }
}

function cubic(distance) {
  const x = Math.abs(distance);
  if (x < 1) return ((1.5 * x - 2.5) * x * x + 1);
  if (x < 2) return -0.5 * (((x - 5) * x + 8) * x - 4);
  return 0;
}

// Separable 8-bit bicubic interpolation matching Pillow's sampling centers,
// scale-aware support and 22-bit fixed-point rounding after each axis.
const precision = 1 << 22;
function taps(inputSize) {
  const scale = inputSize / target;
  const filterScale = Math.max(1, scale);
  return Array.from({length: target}, (_, i) => {
    const center = (i + 0.5) * scale;
    const first = Math.max(0, Math.trunc(center - 2 * filterScale + 0.5));
    const end = Math.min(inputSize, Math.trunc(center + 2 * filterScale + 0.5));
    const weights = Array.from({length: end - first}, (_, j) => cubic((j + first - center + 0.5) / filterScale));
    const sum = weights.reduce((a, b) => a + b, 0);
    return {first, coeffs: weights.map(w => {
      const scaled = precision * (w / sum);
      return Math.trunc(scaled + (scaled < 0 ? -0.5 : 0.5));
    })};
  });
}

function sample(pixels, origin, stride, tap) {
  let sum = precision / 2;
  for (let j = 0; j < tap.coeffs.length; j++) sum += pixels[origin + (tap.first + j) * stride] * tap.coeffs[j];
  return Math.max(0, Math.min(255, Math.floor(sum / precision)));
}

function preprocess({pixels, width, height}) {
  const horizontalTaps = taps(width);
  const verticalTaps = taps(height);
  const rows = new Uint8Array(height * target);
  for (let y = 0; y < height; y++) {
    for (let x = 0; x < target; x++) rows[y * target + x] = sample(pixels, y * width, 1, horizontalTaps[x]);
  }
  const planeSize = target * target;
  const data = new Float32Array(planeSize * 3);
  for (let y = 0; y < target; y++) {
    for (let x = 0; x < target; x++) data[y * target + x] = sample(rows, x, target, verticalTaps[y]) / 255;
  }
  data.set(data.subarray(0, planeSize), planeSize);
  data.set(data.subarray(0, planeSize), 2 * planeSize);
  return data;
}

async function downloadWeights() {
  const response = await fetch(weightsUrl, {credentials: "omit", referrerPolicy: "no-referrer"});
  if (!response.ok) throw new Error("The model host returned HTTP " + response.status + ". Please retry.");
  const reader = response.body.getReader();
  const result = new Uint8Array(weightsLength);
  let received = 0;
  let lastPercent = -1;
  for (;;) {
    const {done, value} = await reader.read();
    if (done) break;
    if (received + value.length > weightsLength) {
      await reader.cancel();
      throw new Error("The model download has an unexpected size.");
    }
    result.set(value, received);
    received += value.length;
    const percent = Math.floor(100 * received / weightsLength);
    if (percent !== lastPercent) {
      status("Downloading model weights · " + percent + "%", received / weightsLength);
      lastPercent = percent;
    }
  }
  if (received !== weightsLength || await sha256(result) !== weightsSha) {
    throw new Error("The model download failed its integrity check. Please retry.");
  }
  return result;
}

async function initialize() {
  status("Loading the browser runtime…");
  importScripts(runtimeDir + "ort.wasm.min.js");
  ort.env.wasm.numThreads = 1;
  ort.env.wasm.wasmPaths = runtimeDir;
  ort.env.wasm.proxy = false;
  const response = await fetch(runtimeDir + "labels.json");
  if (!response.ok) throw new Error("The model labels could not be loaded. Please retry.");
  const bytes = await response.arrayBuffer();
  if (await sha256(bytes) !== labelsSha) throw new Error("The model label file failed its integrity check.");
  const labels = JSON.parse(new TextDecoder().decode(bytes));
  status("Connecting to the model host…");
  let weights;
  try {
    weights = await downloadWeights();
  } catch (error) {
    if (error instanceof TypeError) throw new Error("Could not download model weights. Check your connection to Hugging Face and retry.");
    throw error;
  }
  status("Preparing the model on this device…");
  const session = await ort.InferenceSession.create(weights, {executionProviders: ["wasm"]});
  return {session, labels};
}

async function predict(bytes, input) {
  if (!self.crypto?.subtle || !self.OffscreenCanvas || !self.createImageBitmap || !self.WebAssembly) {
    throw new Error("Open this page over HTTPS in a current browser with WebAssembly and worker canvas support.");
  }
  const hash = await sha256(bytes);
  if (input.expected_sha256 && hash !== input.expected_sha256) throw new Error("The sample image failed its integrity check.");
  const image = await grayscale(bytes);
  const data = preprocess(image);
  if (!loadedModel) loadedModel = initialize().catch(error => { loadedModel = null; throw error; });
  const {session, labels} = await loadedModel;
  status("Classifying this crop…");
  const tensor = new ort.Tensor("float32", data, [1, 3, target, target]);
  let output;
  try {
    ({output} = await session.run({input: tensor}));
    const logits = Array.from(output.data);
    if (logits.length !== 155 || !logits.every(Number.isFinite)) throw new Error("The model returned unexpected scores. Please retry.");
    const max = Math.max(...logits);
    const exp = logits.map(value => Math.exp(Math.fround(value - max)));
    const sum = exp.reduce((a, b) => a + b, 0);
    const predictions = exp.map((value, index) => ({index, label: labels[index], softmax: value / sum}))
      .sort((a, b) => b.softmax - a.softmax).slice(0, 3);
    const source = {name: input.name, sha256: hash, width_px: image.width, height_px: image.height};
    if (input.source_url) source.source_url = input.source_url;
    return {
      status: "provisional_model_prediction_unreviewed", input: source,
      model: {name: "WHOI Northeast U.S. Shelf IFCB v2.4", revision, sha256: weightsSha, labels_sha256: labelsSha, source: modelBase + "/tree/" + revision},
      runtime: {name: "ONNX Runtime Web", version: "1.22.0", provider: "wasm", threads: 1},
      preprocessing: "8-bit grayscale, Pillow-compatible bicubic 299 × 299, repeated RGB, NCHW float32 / 255", predictions
    };
  } finally {
    tensor.dispose();
    if (output) output.dispose();
  }
}

self.onmessage = async event => {
  try {
    const result = await predict(event.data.bytes, event.data.input);
    self.postMessage({type: "result", result});
  } catch (error) {
    self.postMessage({type: "error", text: typeof error.message === "string" ? error.message : "Inference failed on this device. Please retry."});
  }
};
