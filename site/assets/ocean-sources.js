// Source atlas: filters the list that scripts/sync_ocean_sources.py renders into the page.
(() => {
  const $ = id => document.getElementById(id);
  const sections = [...document.querySelectorAll(".sources-lane")];
  const entries = [...document.querySelectorAll("article.source")].map(el => ({
    el, section: el.closest(".sources-lane"), text: el.textContent.toLowerCase(), ...el.dataset,
  }));
  if (!entries.length) return;
  let lane = "";

  function render() {
    const q = $("q").value.trim().toLowerCase().split(/\s+/).filter(Boolean);
    const kind = $("kind").value, licence = $("licence").value, signup = $("signup").value, status = $("status").value;
    let shown = 0;
    entries.forEach(e => {
      const visible = (!lane || e.section.id === lane) && (!kind || e.kind === kind) && (!licence || e.licence === licence)
        && (!signup || e.signup === signup) && (!status || e.status === status) && q.every(word => e.text.includes(word));
      e.el.hidden = !visible;
      shown += visible;
    });
    sections.forEach(s => (s.hidden = !s.querySelector("article.source:not([hidden])")));
    $("count").textContent = `${shown.toLocaleString("en")} of ${entries.length.toLocaleString("en")} sources shown`;
    $("empty").hidden = shown > 0;
  }

  function options(id, pairs) {
    pairs.forEach(([value, label]) => {
      const o = document.createElement("option");
      o.value = value;
      o.textContent = label;
      $(id).appendChild(o);
    });
  }
  const unique = key => [...new Map(entries.map(e => [e[key], e])).values()];
  options("kind", unique("kind").map(e => [e.kind, e.kind]).sort());
  options("licence", ["Open", "Share-alike", "Non-commercial or restricted", "Unclear"]
    .filter(v => entries.some(e => e.licence === v)).map(v => [v, v]));
  options("status", unique("status").map(e => [e.status, e.statusLabel]));

  const chips = [["", "All lanes", entries.length],
    ...sections.map(s => [s.id, s.querySelector("h2").firstChild.textContent.trim(), s.querySelectorAll("article.source").length])
      .sort((a, b) => b[2] - a[2])];
  chips.forEach(([id, name, n]) => {
    const button = document.createElement("button");
    button.type = "button";
    button.setAttribute("aria-pressed", String(id === lane));
    button.append(name + " ");
    const small = document.createElement("small");
    small.textContent = n;
    button.append(small);
    button.addEventListener("click", () => {
      lane = id;
      $("lanes").querySelectorAll("button").forEach(b => b.setAttribute("aria-pressed", String(b === button)));
      render();
    });
    $("lanes").appendChild(button);
  });
  ["q", "kind", "licence", "signup", "status"].forEach(id => $(id).addEventListener("input", render));
  document.querySelector(".sources-filters").hidden = false;
  render();
})();
