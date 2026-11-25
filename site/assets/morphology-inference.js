/* Pixel definitions mirror train_morphology_baseline.py. */
export function morphologyFeatures(gray, width, height) {
  if (!width || !height || gray.length !== width * height) throw new Error("Invalid image dimensions.");
  const count = gray.length, hist = new Uint32Array(256), border = new Uint32Array(256);
  let borderCount = 0, sum = 0, sum2 = 0;
  for (let y = 0; y < height; y++) {
    for (let x = 0; x < width; x++) {
      const value = gray[y * width + x];
      hist[value]++;
      sum += value;
      sum2 += value * value;
      if (x === 0 || y === 0 || x === width - 1 || y === height - 1) {
        border[value]++;
        borderCount++;
      }
    }
  }
  const middle = Math.floor((borderCount - 1) / 2);
  let background = 0, cumulative = border[0];
  while (cumulative <= middle) cumulative += border[++background];
  const coarseHist = [];
  for (let left = 0; left < 256; left += 32) {
    let n = 0;
    for (let value = left; value < left + 32; value++) n += hist[value];
    coarseHist.push(n / count);
  }
  let n12 = 0, n24 = 0, n48 = 0, adjacent = 0;
  let x1 = width, y1 = height, x2 = -1, y2 = -1, sx = 0, sy = 0, sxx = 0, syy = 0, sxy = 0;
  for (let y = 0; y < height; y++) {
    for (let x = 0; x < width; x++) {
      const i = y * width + x;
      const contrast = Math.abs(gray[i] - background);
      if (contrast >= 12) n12++;
      if (contrast >= 48) n48++;
      if (contrast < 24) continue;
      n24++;
      if (x && Math.abs(gray[i - 1] - background) >= 24) adjacent++;
      if (y && Math.abs(gray[i - width] - background) >= 24) adjacent++;
      x1 = Math.min(x1, x); x2 = Math.max(x2, x);
      y1 = Math.min(y1, y); y2 = Math.max(y2, y);
      sx += x; sy += y; sxx += x * x; syy += y * y; sxy += x * y;
    }
  }
  let fill = 0, elongation = 0, perimeter = 0, anisotropy = 0;
  if (n24) {
    const bw = x2 - x1 + 1, bh = y2 - y1 + 1;
    fill = n24 / (bw * bh);
    elongation = 1 - Math.min(bw, bh) / Math.max(bw, bh);
    perimeter = (4 * n24 - 2 * adjacent) / n24;
    const vx = sxx / n24 - (sx / n24) ** 2;
    const vy = syy / n24 - (sy / n24) ** 2;
    const cov = sxy / n24 - (sx / n24) * (sy / n24);
    if (vx + vy > 0) anisotropy = Math.hypot(vx - vy, 2 * cov) / (vx + vy);
  }
  const mean = sum / count, sd = Math.sqrt(Math.max(0, sum2 / count - mean * mean));
  return [Math.log1p(Math.min(width, height)), Math.log1p(Math.max(width, height)),
    background / 255, mean / 255, sd / 255, ...coarseHist, n12 / count, n24 / count, n48 / count,
    fill, elongation, perimeter, anisotropy];
}

export function rankMorphology(model, features) {
  if (model.schema !== "ifcb-morphology-centroids-v1" || features.length !== model.features.length) {
    throw new Error("The feature format differs from the model. Reload this page.");
  }
  const scaled = features.map((v, i) => (v - model.mean[i]) / model.scale[i]);
  return model.centroids.map((center, i) => {
    const squared = center.reduce((sum, v, k) => sum + (v - scaled[k]) ** 2, 0);
    return {label: model.labels[i], distance: Math.sqrt(squared)};
  }).sort((a, b) => a.distance - b.distance);
}

export async function decodeMorphologyPng(buffer) {
  const bytes = new Uint8Array(buffer), header = [137,80,78,71,13,10,26,10];
  const bad = "Choose an opaque 8-bit grayscale PNG microscope crop.";
  if (bytes.length < 33 || !header.every((v, i) => bytes[i] === v)) throw new Error(bad);
  const view = new DataView(buffer);
  const width = view.getUint32(16), height = view.getUint32(20);
  if (width === 0 || height === 0 || width * height > 4_000_000 || Math.max(width, height) > 8192) {
    throw new Error("Use a crop up to 4 megapixels with each side at most 8192 pixels.");
  }
  if (bytes[24] !== 8 || bytes[25] !== 0) throw new Error(bad);
  // Browser color management can act on embedded profiles. Rebuild from the
  // required chunks so raw gray bytes follow Pillow's stored grayscale samples.
  const parts = [bytes.subarray(0, 8)];
  let complete = false;
  for (let at = 8; at + 12 <= bytes.length;) {
    const n = view.getUint32(at), end = at + 12 + n;
    if (end > bytes.length) throw new Error(bad);
    const tag = String.fromCharCode(...bytes.subarray(at + 4, at + 8));
    if (at === 8 && (tag !== "IHDR" || n !== 13)) throw new Error(bad);
    if (tag === "tRNS" || tag === "acTL") throw new Error(bad);
    if (["IHDR","IDAT","IEND"].includes(tag)) parts.push(bytes.subarray(at, end));
    if (tag === "IEND") { complete = true; break; }
    at = end;
  }
  if (!complete) throw new Error(bad);
  const bitmap = await createImageBitmap(new Blob(parts, {type:"image/png"}), {colorSpaceConversion:"none", imageOrientation:"none"});
  try {
    const canvas = document.createElement("canvas");
    canvas.width = width; canvas.height = height;
    const ctx = canvas.getContext("2d", {willReadFrequently:true});
    ctx.drawImage(bitmap, 0, 0);
    const rgba = ctx.getImageData(0, 0, width, height).data;
    const gray = new Uint8Array(width * height);
    for (let i = 0; i < gray.length; i++) gray[i] = rgba[4 * i];
    return {gray, width, height};
  } finally { bitmap.close(); }
}
