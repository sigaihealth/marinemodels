"use strict";

// The catalog is readable HTML. Enhance its lane links and existing model cards.
const catalog = document.querySelector(".catalog-main");
const laneLinks = Array.from(document.querySelectorAll("#lanes a"));
const laneSelect = document.querySelector("#lane-select");
const sortTemplate = document.querySelector("#sort-control");
const compare = new Intl.Collator("en", { numeric: true, sensitivity: "base" });
const lanes = Array.from(document.querySelectorAll(".catalog-lane"));

for (const link of laneLinks) {
  laneSelect.add(new Option(link.textContent, link.hash.slice(1)));
}

for (const lane of lanes) {
  const list = lane.querySelector(".model-list");
  const records = Array.from(list.children, card => ({
    card,
    name: card.querySelector("summary strong").textContent,
    accessGroup: card.dataset.access
  }));
  const controls = sortTemplate.content.cloneNode(true);
  const order = controls.querySelector("select");
  order.addEventListener("change", () => {
    const sorted = records.slice();
    if (order.value !== "default") {
      sorted.sort((a, b) => compare.compare(a[order.value], b[order.value]) || compare.compare(a.name, b.name));
    }
    list.replaceChildren(...sorted.map(record => record.card));
  });
  lane.querySelector(".list-tools").append(controls);
}

function showSelectedLane() {
  const selected = lanes.find(lane => "#" + lane.id === location.hash) || lanes[0];
  for (const lane of lanes) lane.hidden = lane !== selected;
  for (const link of laneLinks) {
    if (link.hash === "#" + selected.id) link.setAttribute("aria-current", "true");
    else link.removeAttribute("aria-current");
  }
  laneSelect.value = selected.id;
}

laneSelect.addEventListener("change", () => { location.hash = laneSelect.value; });
window.addEventListener("hashchange", showSelectedLane);
showSelectedLane();
laneSelect.hidden = false;
catalog.classList.add("catalog-enhanced");
