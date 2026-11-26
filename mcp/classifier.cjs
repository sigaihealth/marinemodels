const {createHash} = require("node:crypto");
const {z} = require("zod");
const {samples, sampleHashes} = require("../site/assets/plankton-examples.mjs");

const origin = "https://ocean.sig.ai";
const maxBytes = 2 * 1024 * 1024;
const pngHeader = Buffer.from([137, 80, 78, 71, 13, 10, 26, 10]);
const inputSchema = {
  sample: z.enum(Object.keys(samples)).optional().describe("Built-in crop: early and late are Pioneer IFCB, whoi is WHOI IFCB, pelgas is a ZooScan."),
  png_base64: z.string().min(1).max(4 * Math.ceil(maxBytes / 3)).optional()
    .describe("Alternative to sample: one opaque grayscale or RGB PNG, at most 2 MiB, as plain padded base64.")
};
const prediction = z.object({
  model: z.literal("SIG.AI Plankton Classifier"),
  version: z.string().min(1),
  score_type: z.literal("softmax"),
  candidates: z.array(z.object({label: z.string().min(1), score: z.number().min(0).max(1)})).length(3),
  image_sha256: z.string()
});

async function classify({sample, png_base64}, fetcher) {
  if (!!sample === !!png_base64) throw new Error("Choose exactly one input: sample or png_base64.");
  const example = sample ? samples[sample] : null;
  let bytes;
  if (example) {
    const response = await fetcher(origin + "/assets/" + example.id + ".png",
      {redirect: "error", signal: AbortSignal.timeout(8000)});
    if (!response.ok) throw new Error("The published example is temporarily unavailable.");
    bytes = Buffer.from(await response.arrayBuffer());
  } else {
    bytes = Buffer.from(png_base64, "base64");
    if (bytes.length > maxBytes || bytes.toString("base64") !== png_base64 || !bytes.subarray(0, 8).equals(pngHeader)) {
      throw new Error("Supply a PNG of at most 2 MiB, encoded as plain padded base64.");
    }
  }
  const digest = createHash("sha256").update(bytes).digest("hex");
  if (example && digest !== sampleHashes[sample]) throw new Error("The published example failed its checksum.");
  const response = await fetcher(origin + "/api/plankton/predict", {
    method: "POST", headers: {"Content-Type": "image/png", Accept: "application/json"},
    body: bytes, redirect: "error", signal: AbortSignal.timeout(48000), cache: "no-store"
  });
  if (response.status === 429) throw new Error("The classifier is busy or rate-limited. Retry after a minute.");
  if ([400, 413, 415, 422].includes(response.status)) throw new Error("The classifier could not use this crop. Supply an opaque grayscale or RGB PNG with visible detail.");
  if (!response.ok) throw new Error("The hosted classifier is temporarily unavailable.");
  const checked = prediction.safeParse(await response.json());
  if (!checked.success || checked.data.image_sha256 !== digest) throw new Error("The classifier returned an unverified prediction.");
  return {
    ...checked.data, status: "unreviewed_model_prediction", mode: "shared_101_class",
    input: example ? {sample, roi: example.roi || example.id, instrument: sample === "pelgas" ? "ZooScan" : "IFCB",
      source: example.source || "https://ifcb-data.oceanobservatories.org/data/" + example.id + ".png"} : {kind: "caller-supplied PNG"},
    interpretation: "Ranked suggestions. Instrument and collection affect transfer. Expert review is needed for a biological identification.",
    source: origin + "/sigai-plankton.html", privacy: origin + "/data-and-privacy.html#uploads"
  };
}

module.exports = {classify, inputSchema};
