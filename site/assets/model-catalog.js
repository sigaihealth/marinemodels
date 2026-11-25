"use strict";

const list = document.querySelector("#lanes");
const select = document.querySelector("#lane-select");
const content = document.querySelector("#lane-content");
const compare = new Intl.Collator("en", { numeric: true, sensitivity: "base" });

function node(tag, text, className) {
  const item = document.createElement(tag);
  if (text) item.textContent = text;
  if (className) item.className = className;
  return item;
}

function link(title, url) {
  const anchor = node("a", title);
  anchor.href = url;
  return anchor;
}

function modelCard(model) {
  const card = node("details", "", "model-card");
  const summary = node("summary");
  const caption = node("span");
  caption.append(node("strong", model.name), node("small", model.task));
  summary.append(caption);
  const fields = node("dl");
  for (const [key, title] of [
    ["input", "Input"], ["output", "Output"], ["accessGroup", "Access type"], ["access", "Availability"],
    ["license", "License scope"], ["compute", "Compute"], ["benchmark", "Evaluation"], ["notes", "Notes"]
  ]) {
    if (model[key]) fields.append(node("dt", title), node("dd", model[key]));
  }
  const sources = node("p", "", "catalog-links");
  if (model.actionUrl) sources.append(link(model.action, model.actionUrl));
  sources.append(link("Primary source", model.source));
  if (model.artifact && model.artifact !== model.source) sources.append(link("Repository or release", model.artifact));
  card.append(summary, fields, sources);
  return card;
}

function start(data) {
  for (const lane of data.lanes) {
    const option = node("option", lane.name);
    option.value = lane.slug;
    select.append(option);
    list.append(link(lane.name, "#" + lane.slug));
  }
  select.addEventListener("change", () => { location.hash = select.value; });
  function render() {
    const lane = data.lanes.find(item => "#" + item.slug === location.hash) || data.lanes[0];
    select.value = lane.slug;
    for (const item of list.children) item.setAttribute("aria-current", String(item.hash === "#" + lane.slug));
    const models = data.models.filter(model => model.lane === lane.id);
    const trials = node("div", "", "lane-actions");
    for (const model of models.filter(item => item.actionUrl)) {
      const action = link(model.action, model.actionUrl);
      action.className = "primary";
      trials.append(action);
    }
    const title = node("h2", lane.name);
    title.id = "lane-title";
    const protocol = node("div", "", "comparison");
    protocol.append(node("h3", "How to compare"), node("p", lane.protocol));
    if (lane.reference) protocol.append(link(lane.reference_name, lane.reference));
    const tools = node("div", "", "list-tools");
    tools.append(node("span", models.length + (models.length === 1 ? " record" : " records")));
    const label = node("label", "Sort by");
    const order = node("select");
    for (const [value, text] of [["default", "Catalog order"], ["name", "Model name"], ["accessGroup", "Access type"]]) {
      const choice = node("option", text);
      choice.value = value;
      order.append(choice);
    }
    label.append(order);
    tools.append(label);
    const cards = node("div");
    const entries = models.map(model => ({ model, card: modelCard(model) }));
    function sort() {
      const sorted = entries.slice();
      if (order.value !== "default") sorted.sort((a, b) =>
        compare.compare(a.model[order.value], b.model[order.value]) || compare.compare(a.model.name, b.model.name));
      cards.replaceChildren(...sorted.map(entry => entry.card));
    }
    sort();
    order.addEventListener("change", sort);
    content.replaceChildren(title, node("p", lane.workflow, "lane-description"), trials, protocol, tools, cards);
  }
  render();
  window.addEventListener("hashchange", render);
}

fetch("assets/model-catalog.json")
  .then(response => {
    if (!response.ok) throw new Error("Catalog download failed");
    return response.json();
  })
  .then(start)
  .catch(() => {
    document.querySelector("#loading").textContent = "The online records could not load. Download the workbook above to browse the catalog.";
  });
