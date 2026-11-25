const TARGET = 224, PRECISION = 2**22;
const f32 = Math.fround;
const MEAN = [.485,.456,.406].map(f32), STD = [.229,.224,.225].map(f32);
export const classOrder = ["Balanion","Dictyocha","Guinardia_delicatula","Mesodinium","Pseudo-nitzschia","Thalassiosira","Tripos_lineatus","detritus","flagellate","nanoplankton_mix"];
export const manifestSHA = "529d03a9cc930528ea19b4c21893e74d0df57bdb801c7242d606858aa7af76d7";
const preprocessId = "grayscale; aspect-preserving bilinear fit and corner-median padding to 224x224; repeated RGB; ImageNet mean/std";

function roundEven(value) {
  const floor = Math.floor(value);
  return value - floor === .5 ? floor + floor % 2 : Math.round(value);
}

// Pillow's 8-bit separable BILINEAR resampler: sampling centers, scale-expanded
// support for downsampling, rounded 22-bit weights, and rounding after each axis.
function taps(input, output) {
  const scale = input / output, support = Math.max(1, scale);
  return Array.from({length:output}, (_, i) => {
    const mid = (i + .5) * scale;
    const start = Math.max(0, Math.trunc(mid - support + .5));
    const end = Math.min(input, Math.trunc(mid + support + .5));
    const weights = Array.from({length:end-start}, (_, j) => Math.max(0, 1 - Math.abs((j + start - mid + .5) / support)));
    const total = weights.reduce((s, w) => s + w, 0);
    return [start, weights.map(w => Math.trunc((w / total) * PRECISION + .5))];
  });
}
function sample(pixels, offset, stride, [start, weights]) {
  let sum = PRECISION / 2;
  for (let i = 0; i < weights.length; i++) sum += pixels[offset + (start + i) * stride] * weights[i];
  return Math.min(255, Math.max(0, Math.floor(sum / PRECISION)));
}
export function grayscalePanel({gray, width, height}) {
  const ratio = Math.min(TARGET / width, TARGET / height);
  const w = Math.max(1, roundEven(width * ratio)), h = Math.max(1, roundEven(height * ratio));
  const corners = [gray[0],gray[width-1],gray[(height-1)*width],gray[gray.length-1]].sort((a,b) => a-b);
  const panel = new Uint8Array(TARGET * TARGET).fill(Math.floor((corners[1] + corners[2]) / 2));
  const ox = Math.floor((TARGET-w)/2), oy = Math.floor((TARGET-h)/2);
  const xtaps = taps(width, w), ytaps = taps(height, h);
  const rows = new Uint8Array(height*w);
  for (let y=0; y<height; y++) for (let x=0; x<w; x++) rows[y*w+x]=sample(gray,y*width,1,xtaps[x]);
  for (let y=0; y<h; y++) for (let x=0; x<w; x++) panel[(y+oy)*TARGET+x+ox]=sample(rows,x,w,ytaps[y]);
  return panel;
}
export function normalizedPixels(panel) {
  const out = new Float32Array(panel.length * 3);
  for (let c=0; c<3; c++) for (let i=0; i<panel.length; i++) {
    out[c*panel.length+i]=f32(f32(f32(panel[i]/255)-MEAN[c])/STD[c]);
  }
  return out;
}
export async function sha256(bytes) {
  const digest = await crypto.subtle.digest("SHA-256", bytes);
  return Array.from(new Uint8Array(digest), b => b.toString(16).padStart(2,"0")).join("");
}

// Read ModelProto.metadata_props (field 14), skipping the graph and tensors.
function fields(bytes) {
  const result = [];
  let i = 0;
  function variable() {
    let n = 0;
    for (let shift=0; shift<=49 && i<bytes.length; shift+=7) {
      const b = bytes[i++]; n += (b & 127) * 2**shift;
      if (b < 128) return n;
    }
    throw new Error("Malformed ONNX header.");
  }
  while (i < bytes.length) {
    const tag = variable(), wire = tag % 8, field = Math.floor(tag/8);
    if (wire === 0) variable();
    else if (wire === 1) i += 8;
    else if (wire === 5) i += 4;
    else if (wire === 2) {
      const n = variable(), end = i+n;
      if (!Number.isSafeInteger(end) || end > bytes.length) throw new Error("Invalid ONNX field.");
      result.push([field,bytes.subarray(i,end)]);
      i=end;
    } else throw new Error("Unsupported ONNX encoding.");
    if (i>bytes.length) throw new Error("Incomplete ONNX file.");
  }
  return result;
}
export function modelMetadata(bytes) {
  const decoder=new TextDecoder();
  const items=fields(bytes).filter(([n]) => n === 14);
  for (const [, entry] of items) {
    const props=new Map(fields(entry));
    if (decoder.decode(props.get(1)) !== "sigai_plankton") continue;
    const m=JSON.parse(decoder.decode(props.get(2)));
    if (m.format !== "sigai-ifcb-mobilenet-onnx-v1" || m.manifest_sha256 !== manifestSHA ||
        m.preprocessing !== preprocessId || m.outputs !== "unnormalized_logits" ||
        !/^[a-f0-9]{64}$/.test(m.checkpoint_sha256) || JSON.stringify(m.labels) !== JSON.stringify(classOrder)) {
      throw new Error("This export has a different training manifest, class order or preprocessing.");
    }
    return m;
  }
  throw new Error("Choose an ONNX file produced by the project's MobileNet export script.");
}
export async function runMobileNet(session, pixels) {
  const input = new globalThis.ort.Tensor("float32", pixels, [1,3,TARGET,TARGET]);
  let output;
  try {
    output = (await session.run({pixels:input})).logits;
    if (!output || output.data.length !== classOrder.length || !output.data.every(Number.isFinite)) throw new Error("Invalid model output.");
    const max = Math.max(...output.data), values=Array.from(output.data, v => Math.exp(v-max));
    const total=values.reduce((a,b) => a+b,0);
    return values.map((v,i) => ({label:classOrder[i], softmax:v/total})).sort((a,b) => b.softmax-a.softmax);
  } finally { input.dispose(); if (output) output.dispose(); }
}
