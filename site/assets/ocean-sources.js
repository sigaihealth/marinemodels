// Source atlas: renders assets/ocean-sources.json as a filterable list grouped by lane.
(() => {
  const STATUS = {
    ok: ["Link answered", "ok"], "needs login": ["Account or access needed", "login"], api: ["API endpoint", "api"],
    broken: ["Not found", "bad"], error: ["Server error", "warn"], unreachable: ["No answer", "warn"], "no link": ["Not a web link", "warn"],
  };
  const LICENCES = ["Open", "Share-alike", "Non-commercial or restricted", "Unclear"];
  const licenceGroup = text => {
    const t = String(text || "").toLowerCase();
    if (/-nc|non-?commercial|nc-|academic|all rights|proprietary|permission/.test(t)) return "Non-commercial or restricted";
    if ((/-sa|share-?alike|gpl/.test(t)) && !/lgpl/.test(t)) return "Share-alike";
    if (/cc0|public domain|cc-by|cc by|mit|apache|bsd|eupl|copernicus|us government|open government|unrestricted|no restrictions/.test(t)) return "Open";
    return "Unclear";
  };
  const signup = text => {
    const t = String(text || "").toLowerCase();
    return t.startsWith("none") ? "none" : /application|restricted/.test(t) ? "restricted" : "account";
  };
  const esc = s => String(s ?? "").replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c]);
  const web = u => (/^https?:\/\//.test(String(u || "")) ? String(u) : "");
  const $ = id => document.getElementById(id);
  let rows = [], lane = "";

  function stats() {
    const kinds = {};
    rows.forEach(r => (kinds[r.kind] = (kinds[r.kind] || 0) + 1));
    const cells = [[rows.length, "Sources"], ...Object.entries(kinds).sort((a, b) => b[1] - a[1]).map(([k, n]) => [n, k + "s"]),
      [rows.filter(r => r.status === "ok").length, "Links answered"],
      [rows.filter(r => r.licence === "Open").length, "Open licence"],
      [rows.filter(r => r.signup === "none").length, "No sign-up"]];
    $("stats").innerHTML = cells.map(([n, label]) => `<div><b>${n.toLocaleString("en")}</b><span>${esc(label)}</span></div>`).join("");
  }

  function entry(r) {
    const [label, cls] = STATUS[r.status] || [r.status || "Not checked", "warn"];
    const url = web(r.access_url), src = web(r.source_url);
    const detail = (name, value) => (value ? `<dt>${name}</dt><dd>${value}</dd>` : "");
    return `<article class="source"><div>
      <h3>${url ? `<a href="${esc(url)}" rel="noopener">${esc(r.name)}</a>` : esc(r.name)}</h3>
      <p class="meta">${esc([r.operator, r.country_or_region].filter(Boolean).join(" · "))}</p>
      <p class="desc">${esc(r.description)}</p></div>
      <div class="tags"><span class="tag">${esc(r.kind)}</span><span class="tag">${esc(r.licence)}</span><span class="tag ${cls}">${esc(label)}</span></div>
      <details><summary>How to get it</summary><dl>
        ${detail("Licence", esc(r.license || "Unclear"))}
        ${detail("Sign-up", esc(r.registration || "Unknown"))}
        ${detail("Access", esc(r.access_method))}
        ${detail("Try it", r.example_access ? `<code>${esc(r.example_access)}</code>` : "")}
        ${detail("Coverage", esc(r.coverage))}
        ${detail("Size", esc(r.size))}
        ${detail("Link check", `${esc(label)}${r.code ? ` (HTTP ${r.code})` : ""}, ${esc(r.checked)}`)}
        ${detail("Source", src ? `<a href="${esc(src)}" rel="noopener">${esc(src)}</a>` : "")}
      </dl></details></article>`;
  }

  function render() {
    const q = $("q").value.trim().toLowerCase();
    const kind = $("kind").value, licence = $("licence").value, sign = $("signup").value, status = $("status").value;
    const shown = rows.filter(r => (!lane || r.lane === lane) && (!kind || r.kind === kind) && (!licence || r.licence === licence)
      && (!sign || r.signup === sign) && (!status || r.status === status) && (!q || r.text.includes(q)));
    $("count").textContent = `${shown.length.toLocaleString("en")} of ${rows.length.toLocaleString("en")} sources shown`;
    const groups = {};
    shown.forEach(r => (groups[r.lane] ||= []).push(r));
    $("list").innerHTML = Object.keys(groups).sort().map(name =>
      `<section class="sources-lane"><h2>${esc(name)} <span>${groups[name].length}</span></h2>${groups[name].map(entry).join("")}</section>`).join("")
      || `<p class="sources-empty">No sources match these filters. Clear the search or choose another lane.</p>`;
  }

  function options(id, values, label = v => v) {
    values.forEach(v => { const o = document.createElement("option"); o.value = v; o.textContent = label(v); $(id).appendChild(o); });
  }

  fetch("assets/ocean-sources.json").then(response => response.json()).then(data => {
    rows = data.map(r => ({
      ...r, lane: String(r.lane || "Other").replace(/^New lane:\s*/i, ""), status: r.check?.status, code: r.check?.code,
      checked: r.check?.date, licence: licenceGroup(r.license), signup: signup(r.registration),
      text: [r.name, r.operator, r.country_or_region, r.description, r.lane, r.access_method, r.license].join(" ").toLowerCase(),
    }));
    stats();
    options("kind", [...new Set(rows.map(r => r.kind))].sort());
    options("licence", LICENCES);
    options("status", Object.keys(STATUS).filter(s => rows.some(r => r.status === s)), s => STATUS[s][0]);
    const counts = {};
    rows.forEach(r => (counts[r.lane] = (counts[r.lane] || 0) + 1));
    [["", "All lanes", rows.length], ...Object.entries(counts).sort((a, b) => b[1] - a[1]).map(([k, n]) => [k, k, n])].forEach(([value, text, n]) => {
      const button = document.createElement("button");
      button.type = "button";
      button.setAttribute("aria-pressed", String(value === lane));
      button.innerHTML = `${esc(text)} <small>${n}</small>`;
      button.addEventListener("click", () => {
        lane = value;
        $("lanes").querySelectorAll("button").forEach(b => b.setAttribute("aria-pressed", String(b === button)));
        render();
      });
      $("lanes").appendChild(button);
    });
    ["q", "kind", "licence", "signup", "status"].forEach(id => $(id).addEventListener("input", render));
    const date = rows.find(r => r.checked)?.checked;
    if (date) $("note").insertAdjacentText("afterbegin", `Links were checked on ${date}. `);
    render();
  }).catch(() => {
    $("list").innerHTML = `<p class="sources-empty">The source list didn’t load. Reload the page, or <a href="assets/ocean-sources.json">download it as JSON</a>.</p>`;
  });
})();
