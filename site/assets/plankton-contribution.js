const element = id => document.getElementById(id);
const consent = element("contribution-consent");
const contribute = element("contribute");
const contributeStatus = element("contribution-status");
const receiptFile = element("withdraw-receipt");
const withdrawStatus = element("withdraw-status");
const records = new Map();
let candidate;
let busy = false;
let receiptNumber = 0;

function refresh() {
  const record = records.get(candidate?.sha);
  const finished = Boolean(record?.confirmed || record?.conflict);
  element("contribution-choice").hidden = !candidate;
  consent.disabled = busy || finished;
  contribute.disabled = !candidate || !consent.checked || busy || finished;
  receiptFile.disabled = busy;
  element("withdraw-button").disabled = busy || !receiptFile.files.length;
}

export function setEligibleContribution(image) {
  candidate = image;
  consent.checked = false;
  if (!busy) contributeStatus.textContent = records.get(image?.sha)?.confirmed
    ? "You have already contributed this crop in this tab." : "";
  refresh();
}

function hex(bytes) {
  return Array.from(bytes, byte => byte.toString(16).padStart(2, "0")).join("");
}

async function receiptId(token) {
  const digest = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(token));
  return hex(new Uint8Array(digest));
}

function downloadReceipt(record) {
  const data = {receipt: record.id, deletion_token: record.token};
  if (record.expiresAt) data.expires_at = record.expiresAt;
  const file = new Blob([JSON.stringify(data, null, 2) + "\n"], {type: "application/json"});
  const url = URL.createObjectURL(file);
  const link = document.createElement("a");
  link.href = url;
  link.download = "sigai-ocean-withdrawal-" + record.number + ".json";
  link.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

async function prepareReceipt(sha) {
  const token = hex(crypto.getRandomValues(new Uint8Array(32)));
  const id = await receiptId(token);
  const number = ++receiptNumber;
  const row = document.createElement("li");
  const button = document.createElement("button");
  const note = document.createElement("span");
  const record = {id, token, number, row, note, confirmed: false};
  button.type = "button";
  button.textContent = "Download receipt for contribution " + number;
  button.addEventListener("click", () => downloadReceipt(record));
  row.append(button, note);
  element("receipt-list").append(row);
  element("contribution-receipts").hidden = false;
  records.set(sha, record);
  return record;
}

function forgetReceipt(sha, record) {
  records.delete(sha);
  record.row.remove();
  element("contribution-receipts").hidden = !records.size;
}

function post(path, headers, body) {
  return fetch("/api/plankton/" + path, {
    method: "POST", body, headers: {Accept: "application/json", ...headers},
    credentials: "omit", cache: "no-store", redirect: "error", referrerPolicy: "no-referrer",
    signal: AbortSignal.timeout(60_000)
  });
}

consent.addEventListener("change", refresh);
contribute.addEventListener("click", async () => {
  if (!candidate || !consent.checked || busy || contribute.disabled) return;
  const image = candidate;
  busy = true;
  refresh();
  contributeStatus.textContent = "Sending your contribution…";
  let record = records.get(image.sha);
  const previousAttempt = Boolean(record);
  try {
    record ??= await prepareReceipt(image.sha);
    const response = await post("contribute", {
      "Content-Type": "image/png", "X-Contribution-Consent": "training-evaluation-v1",
      "X-Contribution-Key": record.token
    }, image.buffer);
    if (response.status === 429) {
      record.note.textContent = " · Last attempt rate limited";
      contributeStatus.textContent = "Too many requests. Wait a moment, then try again in this tab.";
      return;
    }
    if (response.status === 409) {
      const detail = await response.json().catch(() => null);
      consent.checked = false;
      if (detail?.error === "This contribution was withdrawn.") {
        forgetReceipt(image.sha, record);
        contributeStatus.textContent = "This contribution was previously withdrawn. To contribute the crop again, give fresh permission.";
      } else {
        record.conflict = true;
        record.note.textContent = " · Receipt conflict";
        contributeStatus.textContent = "This receipt could not be used for this crop. Keep the receipt if you want to withdraw its earlier contribution.";
      }
      return;
    }
    if ([400, 403, 413, 415, 422].includes(response.status)) {
      contributeStatus.textContent = "The service declined this contribution. Use a microscope crop you have the right to share. Built-in examples are excluded.";
      if (previousAttempt) record.note.textContent = " · Last request declined";
      else forgetReceipt(image.sha, record);
      return;
    }
    if (![200, 201].includes(response.status)) throw new Error();
    const data = await response.json();
    if (data.receipt !== record.id || data.deletion_token !== record.token ||
        typeof data.expires_at !== "string" || !Number.isFinite(Date.parse(data.expires_at))) throw new Error();
    record.expiresAt = new Date(data.expires_at).toISOString();
    record.confirmed = true;
    record.note.textContent = " · Expires " + record.expiresAt.slice(0, 10) + " (UTC)";
    consent.checked = false;
    contributeStatus.textContent = "Contribution " + record.number + " received. Download its private withdrawal receipt.";
  } catch {
    if (record) record.note.textContent = " · Receipt available, storage unconfirmed";
    contributeStatus.textContent = record
      ? "We could not confirm storage. Save the receipt to withdraw, or try again with this crop in this tab. Retrying here uses the same receipt."
      : "Your browser could not create a private withdrawal key. Please try again in a current browser.";
  } finally {
    busy = false;
    refresh();
  }
});

async function readReceipt(file) {
  if (file.size > 4096) throw new Error();
  const {receipt, deletion_token} = JSON.parse(await file.text());
  if (typeof receipt !== "string" || typeof deletion_token !== "string" ||
      !/^[0-9a-f]{64}$/.test(deletion_token) || receipt !== await receiptId(deletion_token)) throw new Error();
  return {receipt, deletion_token};
}

receiptFile.addEventListener("change", () => {
  withdrawStatus.textContent = "";
  refresh();
});

element("withdraw-form").addEventListener("submit", async event => {
  event.preventDefault();
  const file = receiptFile.files[0];
  if (busy || !file) return;
  busy = true;
  refresh();
  withdrawStatus.textContent = "Checking the receipt…";
  let credentials;
  try {
    credentials = await readReceipt(file);
    withdrawStatus.textContent = "Withdrawing your contribution…";
    const response = await post("withdraw", {"Content-Type": "application/json"}, JSON.stringify(credentials));
    if (response.status === 403) {
      withdrawStatus.textContent = "The service did not accept this receipt. Choose the original withdrawal receipt and try again.";
      return;
    }
    if (response.status !== 200 || (await response.json()).status !== "removed") throw new Error();
    for (const [sha, record] of records) {
      if (record.id === credentials.receipt) {
        forgetReceipt(sha, record);
        break;
      }
    }
    contributeStatus.textContent = "";
    consent.checked = false;
    receiptFile.value = "";
    withdrawStatus.textContent = "Withdrawal confirmed. The service has no stored contribution for this receipt.";
  } catch {
    withdrawStatus.textContent = credentials
      ? "We could not confirm withdrawal. Keep the receipt and try again."
      : "Choose the original JSON withdrawal receipt downloaded from this page.";
  } finally {
    busy = false;
    refresh();
  }
});
