"use strict";

const element = id => document.getElementById(id);
const menu = Object.fromEntries(["run", "site", "variable", "depth"].map(id => [id, element(id)]));
const canvas = element("chart");
let archive;

function fillOptions(select, entries) {
  entries.forEach(([value, label]) => select.add(new Option(label, value)));
}

function locationLabel(site) {
  return Math.abs(site.longitude).toFixed(2) + "°W";
}

function valueLabel(value, digits = 2) {
  return Number.isFinite(value) ? value.toFixed(digits) : "Unavailable";
}

function rangeLabel(values, suffix) {
  const low = valueLabel(Math.min(...values));
  const high = valueLabel(Math.max(...values));
  return (low === high ? low : low + "–" + high) + suffix;
}

function alternatingLeadNote(values, suffix) {
  if (values.length < 4 || !values.every(Number.isFinite)) return "";
  let prior = Math.sign(values[1] - values[0]);
  if (!prior) return "";
  for (let i = 2; i < values.length; i++) {
    const change = Math.sign(values[i] - values[i - 1]);
    if (change !== -prior) return "";
    prior = change;
  }
  const odd = values.filter((_, index) => index % 2 === 0);
  const even = values.filter((_, index) => index % 2 === 1);
  return "The archived GLONET values alternate up and down. Odd lead days give " +
    rangeLabel(odd, suffix) + " and even lead days give " + rangeLabel(even, suffix) + ".";
}

function current() {
  const run = archive.forecasts[Number(menu.run.value)];
  const site = archive.sites.find(item => item.id === menu.site.value);
  const variable = archive.variables[menu.variable.value];
  const profile = run.profiles[site.id][menu.depth.value][menu.variable.value];
  return { run, site, variable, profile };
}

function drawChart() {
  if (!archive || element("workspace").hidden) return;
  const { profile, variable } = current();
  const context = canvas.getContext("2d");
  if (!context) return;
  const width = canvas.clientWidth;
  const height = canvas.clientHeight;
  if (width < 1 || height < 1) return;
  const ratio = window.devicePixelRatio || 1;
  canvas.width = Math.round(width * ratio);
  canvas.height = Math.round(height * ratio);
  context.setTransform(ratio, 0, 0, ratio, 0, 0);
  const left = 49, right = width - 13, top = 28, bottom = height - 43;
  const values = [...profile.forecast, profile.persistence].filter(Number.isFinite);
  if (!values.length) return;
  const min = Math.min(...values), max = Math.max(...values);
  const pad = Math.max((max - min) * 0.12, 0.01);
  const low = min - pad, high = max + pad;
  const x = index => left + (right - left) * index / 9;
  const y = value => bottom - (value - low) / (high - low) * (bottom - top);
  context.font = "12px 'DM Sans', sans-serif";
  context.fillStyle = "#415d5c";
  context.fillText(variable.units, 4, 13);
  context.textBaseline = "middle";
  context.textAlign = "right";
  for (let tick = 0; tick <= 4; tick++) {
    const value = low + tick * (high - low) / 4;
    context.strokeStyle = "#c4d2ca";
    context.lineWidth = 1;
    context.beginPath();
    context.moveTo(left, y(value));
    context.lineTo(right, y(value));
    context.stroke();
    context.fillText(value.toFixed(2), left - 7, y(value));
  }
  context.textAlign = "center";
  for (let i = 0; i < 10; i++) context.fillText(String(i + 1), x(i), bottom + 14);
  context.fillText("Lead day", (left + right) / 2, bottom + 33);
  if (Number.isFinite(profile.persistence)) {
    context.strokeStyle = "#80561a";
    context.lineWidth = 2;
    context.setLineDash([6, 4]);
    context.beginPath();
    context.moveTo(x(0), y(profile.persistence));
    context.lineTo(x(9), y(profile.persistence));
    context.stroke();
    context.setLineDash([]);
  }
  context.strokeStyle = "#086d68";
  context.fillStyle = "#086d68";
  context.lineWidth = 2.7;
  context.beginPath();
  profile.forecast.forEach((value, i) => {
    if (!Number.isFinite(value)) return;
    if (i === 0 || !Number.isFinite(profile.forecast[i - 1])) context.moveTo(x(i), y(value));
    else context.lineTo(x(i), y(value));
  });
  context.stroke();
  profile.forecast.forEach((value, i) => {
    if (!Number.isFinite(value)) return;
    context.beginPath();
    context.arc(x(i), y(value), 3, 0, 2 * Math.PI);
    context.fill();
  });
}

function render() {
  const { run, site, variable, profile } = current();
  const unit = variable.units;
  const depth = Number(menu.depth.value).toFixed(2);
  element("plot-heading").textContent = variable.name;
  element("context").textContent = "36.00°N, " + locationLabel(site) + " · " + depth + " m · Reference " + run.referenceDate + " UTC";
  const suffix = variable.archiveUnits === "1e-3" ? " × " + unit : " " + unit;
  const available = profile.forecast.filter(Number.isFinite);
  const range = available.length ? "The GLONET range is " + rangeLabel(available, suffix) +
    " across " + available.length + (available.length === 1 ? " daily mean." : " daily means.") :
    "GLONET daily means are unavailable.";
  const persistence = Number.isFinite(profile.persistence) ?
    "GLO12 persistence stays at " + valueLabel(profile.persistence) + suffix + "." :
    "GLO12 persistence is unavailable.";
  element("forecast-range").textContent = run.dates[0] + " to " + run.dates[run.dates.length - 1] + " UTC. " + range + " " + persistence;
  const note = alternatingLeadNote(profile.forecast, suffix);
  element("lead-pattern").textContent = note;
  element("lead-pattern").hidden = !note;
  canvas.setAttribute("aria-label", variable.name + " at " + depth + " m across ten lead days, compared with GLO12 persistence. Daily values follow the chart.");
  element("table-caption").textContent = variable.name + " (" + unit + "). Difference is GLONET minus persistence.";
  const rows = run.dates.map((day, i) => {
    const row = document.createElement("tr");
    const forecast = profile.forecast[i];
    const baseline = profile.persistence;
    const difference = Number.isFinite(forecast) && Number.isFinite(baseline) ? forecast - baseline : null;
    const cells = [String(i + 1), day, valueLabel(forecast, 3), valueLabel(baseline, 3), valueLabel(difference, 3)];
    cells.forEach((value, col) => {
      const cell = document.createElement(col === 0 ? "th" : "td");
      if (col === 0) cell.scope = "row";
      cell.textContent = value;
      row.appendChild(cell);
    });
    return row;
  });
  element("values").replaceChildren(...rows);
  const links = [["forecast", "GLONET archive metadata"], ["persistence", "Persistence archive metadata"]].map(([key, name]) => {
    const link = document.createElement("a");
    link.href = run.sources[key];
    link.textContent = name + " · " + run.referenceDate;
    return link;
  });
  element("archive-links").replaceChildren(...links);
  drawChart();
}

async function start() {
  element("load-status").hidden = false;
  try {
    const response = await fetch("assets/glonet-midatlantic-2024.json");
    if (!response.ok) throw new Error("Forecast values could not be downloaded.");
    archive = await response.json();
    fillOptions(menu.run, archive.forecasts.map((r, i) => [i, r.referenceDate]));
    fillOptions(menu.site, archive.sites.map(site => [site.id, locationLabel(site)]));
    fillOptions(menu.variable, Object.entries(archive.variables).map(([key, variable]) => [key, variable.name]));
    fillOptions(menu.depth, archive.depths.map(depth => [depth, depth.toFixed(2) + " m"]));
    Object.values(menu).forEach(select => select.addEventListener("change", render));
    element("workspace").hidden = false;
    render();
    if ("ResizeObserver" in window) new ResizeObserver(drawChart).observe(canvas);
    else window.addEventListener("resize", drawChart);
    if (document.fonts) document.fonts.ready.then(drawChart);
    element("load-status").hidden = true;
  } catch {
    element("workspace").hidden = true;
    element("load-status").textContent = "The archive could not be loaded. Download the point data below or reload this page.";
  }
}

start();
