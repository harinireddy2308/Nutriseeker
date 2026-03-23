const $ = (s, r = document) => r.querySelector(s);

function showTab(name) {
  document.querySelectorAll(".tab").forEach((t) => {
    t.classList.toggle("active", t.dataset.tab === name);
  });
  document.querySelectorAll(".panel").forEach((p) => {
    p.classList.toggle("active", p.id === `panel-${name}`);
  });
}

document.querySelectorAll(".tab").forEach((btn) => {
  btn.addEventListener("click", () => showTab(btn.dataset.tab));
});

const drop = $("#dropzone");
const fileInput = $("#file");
const preview = $("#preview");
const placeholder = $("#preview-placeholder");

drop.addEventListener("click", () => fileInput.click());
drop.addEventListener("dragover", (e) => {
  e.preventDefault();
  drop.style.borderColor = "rgba(94,228,168,0.6)";
});
drop.addEventListener("dragleave", () => {
  drop.style.borderColor = "";
});
drop.addEventListener("drop", (e) => {
  e.preventDefault();
  drop.style.borderColor = "";
  const f = e.dataTransfer.files[0];
  if (f && f.type.startsWith("image/")) setFile(f);
});

fileInput.addEventListener("change", () => {
  const f = fileInput.files[0];
  if (f) setFile(f);
});

function setFile(f) {
  const url = URL.createObjectURL(f);
  preview.src = url;
  preview.classList.remove("hidden");
  placeholder.classList.add("hidden");
}

function setRingPct(el, pct) {
  const p = Math.min(100, Math.max(0, pct));
  el.setAttribute("stroke-dasharray", `${p}, 100`);
}

function renderAnalyze(data) {
  $("#empty-state").classList.add("hidden");
  $("#result-body").classList.remove("hidden");
  $("#vision-backend").textContent = data.vision_backend || "—";
  const cap = data.caption || "(no image caption — text-only path)";
  $("#caption-block").textContent = cap;

  const t = data.totals || {};
  $("#tot-cal").textContent = t.calories?.toFixed(0) ?? "0";
  $("#tot-p").textContent = t.protein?.toFixed(1) ?? "0";
  $("#tot-c").textContent = t.carbs?.toFixed(1) ?? "0";
  $("#tot-f").textContent = t.fat?.toFixed(1) ?? "0";
  $("#tot-fi").textContent = t.fiber?.toFixed(1) ?? "0";

  const maxC = 800;
  setRingPct($("#arc-cal"), ((t.calories || 0) / maxC) * 100);

  const host = $("#items-table");
  host.innerHTML = "";
  (data.items || []).forEach((it) => {
    const row = document.createElement("div");
    row.className = "item-row" + (it.matched ? "" : " unmatched");
    const left = document.createElement("div");
    const title = document.createElement("div");
    title.className = "item-title";
    title.textContent = it.query;
    const meta = document.createElement("div");
    meta.className = "item-meta";
    if (it.matched) {
      meta.textContent = `${it.matched.food} · ${it.grams}g (${it.portion_basis}) · ${it.matched.source}`;
    } else {
      meta.textContent = `No DB match — try synonyms. Top alt: ${
        it.alternatives?.[0]
          ? `${it.alternatives[0].food} (${it.alternatives[0].score})`
          : "—"
      }`;
    }
    left.appendChild(title);
    left.appendChild(meta);
    const kcal = document.createElement("div");
    kcal.className = "item-kcal";
    kcal.textContent = it.scaled ? `${it.scaled.calories} kcal` : "—";
    row.appendChild(left);
    row.appendChild(kcal);
    host.appendChild(row);
  });
}

$("#btn-run").addEventListener("click", async () => {
  const text = $("#meal-text").value;
  const f = fileInput.files[0];
  if (!f && !text.trim()) {
    alert("Add a photo and/or a meal description.");
    return;
  }
  $("#loading").classList.remove("hidden");
  $("#result-body").classList.add("hidden");
  $("#empty-state").classList.add("hidden");

  const fd = new FormData();
  if (f) fd.append("image", f);
  fd.append("text", text);
  fd.append("overrides_json", "");

  try {
    const r = await fetch("/api/analyze", { method: "POST", body: fd });
    if (!r.ok) throw new Error(await r.text());
    const data = await r.json();
    renderAnalyze(data);
  } catch (e) {
    alert("Error: " + e.message);
    $("#empty-state").classList.remove("hidden");
  } finally {
    $("#loading").classList.add("hidden");
  }
});

function renderTextPanel(data) {
  $("#text-empty").classList.add("hidden");
  const body = $("#text-result-body");
  body.classList.remove("hidden");
  body.innerHTML = "";
  const wrap = document.createElement("div");
  wrap.innerHTML = `<p class="caption">Foods: ${(data.foods_detected || []).join(", ") || "—"}</p>`;
  const totals = document.createElement("div");
  totals.className = "macro-row";
  const t = data.totals || {};
  totals.innerHTML = `
    <ul class="macro-list">
      <li><span class="dot p"></span> Protein <strong>${t.protein?.toFixed(1) ?? 0}</strong> g</li>
      <li><span class="dot c"></span> Carbs <strong>${t.carbs?.toFixed(1) ?? 0}</strong> g</li>
      <li><span class="dot f"></span> Fat <strong>${t.fat?.toFixed(1) ?? 0}</strong> g</li>
      <li><span class="dot i"></span> Fiber <strong>${t.fiber?.toFixed(1) ?? 0}</strong> g</li>
    </ul>
    <div style="font-size:1.5rem;font-weight:700;color:var(--accent)">${t.calories?.toFixed(0) ?? 0} <small style="font-size:0.6em;color:var(--muted)">kcal</small></div>`;
  wrap.appendChild(totals);
  const items = document.createElement("div");
  items.className = "items";
  (data.items || []).forEach((it) => {
    const row = document.createElement("div");
    row.className = "item-row" + (it.matched ? "" : " unmatched");
    row.innerHTML = `<div><div class="item-title">${it.query}</div>
      <div class="item-meta">${it.matched ? it.matched.food : "unmatched"}</div></div>
      <div class="item-kcal">${it.scaled ? it.scaled.calories + " kcal" : "—"}</div>`;
    items.appendChild(row);
  });
  wrap.appendChild(items);
  body.appendChild(wrap);
}

$("#btn-text-run").addEventListener("click", async () => {
  const text = $("#text-only-input").value.trim();
  if (!text) {
    alert("Enter a meal description.");
    return;
  }
  $("#text-loading").classList.remove("hidden");
  $("#text-result-body").classList.add("hidden");
  const fd = new FormData();
  fd.append("text", text);
  try {
    const r = await fetch("/api/analyze-text", { method: "POST", body: fd });
    if (!r.ok) throw new Error(await r.text());
    const data = await r.json();
    renderTextPanel(data);
  } catch (e) {
    alert("Error: " + e.message);
  } finally {
    $("#text-loading").classList.add("hidden");
  }
});
