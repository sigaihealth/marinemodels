import {decodeMorphologyPng} from "./morphology-inference.js";
import {grayscalePanel, normalizedPixels, sha256, modelMetadata, runMobileNet} from "./mobilenet-inference.js";

const byId=id=>document.getElementById(id);
const modelFile=byId("model-file"), expected=byId("expected"), imageFile=byId("image-file"), button=byId("run");
const names={early:"D20260201T002546_IFCB200_00139.png",late:"D20260201T152545_IFCB200_04627.png"};
const sampleHashes={
  early:"7dd6c14fba2e62c3eaeafb0863ca52c385937aff45dc3dc31ada87508f13872b",
  late:"891ed7ceb9b97620367225ff9bd1cb8622b7c78a09d802cb26b0a2bf0c5afe55",
};
let session, modelInfo, signature, downloadUrl, busy=false;

function selected(){
  if(imageFile.files.length) return {name:imageFile.files[0].name,file:imageFile.files[0]};
  const choice=document.querySelector('input[name="specimen"]:checked');
  return choice ? {name:names[choice.value],sha256:sampleHashes[choice.value]} : null;
}
function resetOutput(){
  byId("results").hidden=true;
  if(downloadUrl) URL.revokeObjectURL(downloadUrl);
  downloadUrl=undefined;
  byId("download").removeAttribute("href");
}
function refresh(){
  resetOutput();
  const choice=selected(), checksum=expected.value.trim().toLowerCase();
  byId("selected").textContent=choice ? choice.name : "Choose a microscope crop.";
  const ready=modelFile.files.length===1 && /^[a-f\d]{64}$/.test(checksum);
  button.disabled=busy || !choice || !ready;
  byId("status").textContent=ready ? "Ready to run." : "Waiting for a model and export fingerprint.";
}
modelFile.addEventListener("change",()=>{signature=undefined;byId("model-status").textContent="The checksum and model metadata will be verified before inference.";refresh();});
expected.addEventListener("input",()=>{signature=undefined;byId("model-status").textContent="The checksum will be verified before inference.";refresh();});
imageFile.addEventListener("change",()=>{if(imageFile.files.length) document.querySelectorAll('input[name="specimen"]').forEach(el=>{el.checked=false;});refresh();});
document.querySelectorAll('input[name="specimen"]').forEach(el=>el.addEventListener("change",()=>{imageFile.value="";refresh();}));
const preset=new URLSearchParams(location.hash.slice(1)).get("sha256");
if(preset && /^[a-f\d]{64}$/i.test(preset)) expected.value=preset.toLowerCase();

async function loadModel(){
  const wanted=expected.value.trim().toLowerCase(), file=modelFile.files[0];
  if(signature===wanted && session) return;
  if(!file.size || file.size>8*1024*1024) throw new Error("Choose a project MobileNet ONNX export under 8 MiB.");
  const bytes=new Uint8Array(await file.arrayBuffer());
  const actual=await sha256(bytes);
  if(actual!==wanted) throw new Error("The file SHA-256 differs from the exporter’s fingerprint.");
  const metadata=modelMetadata(bytes);
  globalThis.ort.env.wasm.numThreads=1;
  globalThis.ort.env.wasm.wasmPaths=new URL("./ifcb-runtime/",import.meta.url).href;
  const previous=session;
  const loaded=await globalThis.ort.InferenceSession.create(bytes,{executionProviders:["wasm"]});
  if(loaded.inputNames.join(",")!=="pixels" || loaded.outputNames.join(",")!=="logits"){
    await loaded.release();throw new Error("The ONNX input or output differs from the trained pilot.");
  }
  session=loaded;signature=actual;modelInfo=metadata;
  if (previous) await previous.release();
  byId("model-status").textContent="Verified ONNX, training manifest and ten labels. Source checkpoint SHA-256 " + metadata.checkpoint_sha256 + ".";
}

button.addEventListener("click",async()=>{
  const choice=selected();
  if(busy || !choice) return;
  resetOutput();busy=true;button.disabled=true;byId("inputs").disabled=true;
  try{
    byId("status").textContent="Verifying the model and preparing the runtime…";
    await loadModel();
    byId("status").textContent="Classifying the specimen…";
    let bytes;
    if(choice.file){
      if(choice.file.size>16*1024*1024) throw new Error("Choose a PNG smaller than 16 MiB.");
      bytes=await choice.file.arrayBuffer();
    }else{
      const response=await fetch("assets/"+choice.name);
      if(!response.ok) throw new Error("The sample image could not be loaded.");
      bytes=await response.arrayBuffer();
    }
    const imageHash=await sha256(bytes);
    if(choice.sha256 && imageHash!==choice.sha256) throw new Error("The sample image checksum differs.");
    const image=await decodeMorphologyPng(bytes);
    const ranked=await runMobileNet(session,normalizedPixels(grayscalePanel(image)));
    byId("scores").replaceChildren(...ranked.slice(0,3).map((candidate,i)=>{
      const li=document.createElement("li"), label=document.createElement("span"), value=document.createElement("span");
      label.textContent=(i+1)+". "+candidate.label.replaceAll("_"," ");value.textContent=candidate.softmax.toFixed(4);
      li.append(label,value);return li;
    }));
    const record={model:"MobileNetV3-Small IFCB pilot",onnx_sha256:signature,checkpoint_sha256:modelInfo.checkpoint_sha256,
      training_manifest_sha256:modelInfo.manifest_sha256,image:choice.name,image_sha256:imageHash,size_px:[image.width,image.height],
      score_type:"uncalibrated_softmax",candidates:ranked};
    downloadUrl=URL.createObjectURL(new Blob([JSON.stringify(record,null,2)+"\n"],{type:"application/json"}));
    byId("download").href=downloadUrl;byId("results").hidden=false;byId("status").textContent="Ranked all ten model classes.";
  }catch(error){byId("status").textContent=error.message || "The trial could not run.";}
  finally{busy=false;byId("inputs").disabled=false;button.disabled=false;}
});
refresh();
