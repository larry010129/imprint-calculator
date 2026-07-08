// --- Data ---
function tr(k) { return window.t ? window.t(k) : k; }

let diamondPrice = { "0.1": null, "0.3": null, "0.5": null, "1": null };

const types = [
  { id: "A", name: "款式 A" },
  { id: "B", name: "款式 B" },
  { id: "C", name: "款式 C" }
];

const purityMultiplier = { "18k": 0.75, "999": 0.999, "pt": 1, "silver925": 0.925 };
const goldLabel = { "18k": "18K金", "999": "純金999", "pt": "鉑金 Pt", "silver925": "925銀" };

// gold/platinum/silver price per gram in TWD (after purity multiplier), filled after fetch
let pricePerGram = { "18k": null, "999": null, "pt": null, "silver925": null };

// density g/cm3, used for ring-size -> weight rough estimate
const metalDensity = { "18k": 15.5, "999": 19.3, "pt": 21.4, "silver925": 10.36 };

// assumed band cross-section for weight estimate (rough estimate, adjust if needed)
const ringBandWidthMm = 2;
const ringBandThicknessMm = 1.3;

// bigger stone needs a bigger prong/basket, so scale the band cross-section by carat
// (rough heuristic, not a real setting-weight model): 0.1ct ~1.05x, 1ct ~1.5x
const caratSettingFactor = carat => 1 + carat * 0.5;

const ringSizeRange = { min: 5, max: 25 };

// used to show a rough weight before the user picks a metal (density unknown until then)
const DEFAULT_ESTIMATE_GOLD = "18k";

// --- Weight units ---
// state.weight is always stored in grams internally; unit only affects display/input.
const unitToGrams = { g: 1, chin: 3.75, taijin: 600 };
const unitDecimals = { g: 2, chin: 2, taijin: 4 };

function gramsToDisplay(grams, unit) {
  return grams / unitToGrams[unit];
}

function displayToGrams(value, unit) {
  return value * unitToGrams[unit];
}

// --- State ---

let state = { category: null, carat: null, type: null, gold: null, ringSize: null, weight: 0, weightSource: null, weightUnit: "g" };

// --- Ring size -> weight estimate ---
// diameter(mm) formula is an approximation of the Taiwan ring size chart
// (~0.4mm diameter increase per size), not an exact conversion table.

function estimateRingWeight(size, goldId, carat) {
  if (!size || !goldId || !carat) return null;
  const diameterMm = 12.8 + size * 0.4;
  const circumferenceMm = diameterMm * Math.PI;
  const volumeMm3 = circumferenceMm * ringBandWidthMm * ringBandThicknessMm * caratSettingFactor(parseFloat(carat));
  const volumeCm3 = volumeMm3 / 1000;
  return volumeCm3 * metalDensity[goldId];
}

function populateRingSizeOptions() {
  const select = document.getElementById("ring-size-select");
  for (let size = ringSizeRange.min; size <= ringSizeRange.max; size++) {
    const opt = document.createElement("option");
    opt.value = size;
    opt.textContent = tr('ring_size_option') + size;
    opt.dataset.size = size;
    select.appendChild(opt);
  }
}

// --- Fetch live metal price ---

async function loadMetalPrices() {
  try {
    const res = await fetch("/api/prices");
    if (!res.ok) throw new Error(`API returned ${res.status}`);
    const data = await res.json();
    Object.keys(data.perGram).forEach(goldId => { pricePerGram[goldId] = data.perGram[goldId]; });
    Object.keys(data.diamond).forEach(carat => { diamondPrice[carat] = data.diamond[carat]; });
    updateGoldPriceDisplay();
    updateTotal();
  } catch (err) {
    document.getElementById("sum-goldprice").textContent = tr('goldprice_failed');
    console.error("metal price fetch failed:", err);
  }
}

function updateGoldPriceDisplay() {
  if (!state.gold || pricePerGram[state.gold] === null) {
    document.getElementById("sum-goldprice").textContent = "-";
    return;
  }
  document.getElementById("sum-goldprice").textContent =
    "NT$ " + Math.round(pricePerGram[state.gold]).toLocaleString();
}

// --- Render type cards ---

function renderTypeCards() {
  const grid = document.getElementById("type-grid");
  grid.innerHTML = "";
  types.forEach(t => {
    const card = document.createElement("div");
    card.className = "type-card";
    card.dataset.type = t.id;

    const imgBox = document.createElement("div");
    imgBox.className = "img-placeholder";

    const slotLabel = `${state.carat}ct-${t.id}`;
    const img = document.createElement("img");
    img.src = `/static/images/${state.carat}-${t.id}.jpg`;
    img.alt = `${slotLabel} ${t.name}`;
    img.onerror = () => {
      imgBox.classList.add("img-missing");
      imgBox.innerHTML = `<span class="img-fallback-label">IMG<br>${slotLabel}</span>`;
    };
    imgBox.appendChild(img);

    const name = document.createElement("p");
    name.className = "type-name";
    name.textContent = t.name;

    card.appendChild(imgBox);
    card.appendChild(name);
    card.addEventListener("click", () => selectType(t.id, t.name));
    grid.appendChild(card);
  });
}

// --- Selection handlers ---

function selectCategory(cat, label) {
  state.category = cat;
  state.carat = null;
  state.type = null;
  state.ringSize = null;
  state.weight = 0;
  state.weightSource = null;

  document.querySelectorAll(".cat-btn").forEach(b => b.classList.toggle("active", b.dataset.cat === cat));
  document.getElementById("carat-step").classList.remove("hidden");
  document.getElementById("type-step").classList.add("hidden");
  document.querySelectorAll(".carat-btn").forEach(b => b.classList.remove("active"));

  document.getElementById("ring-weight-block").classList.toggle("hidden", cat !== "ring");
  document.getElementById("necklace-weight-block").classList.toggle("hidden", cat !== "necklace");
  document.getElementById("ring-size-select").value = "";
  document.getElementById("weight-input").value = "";
  updateWeightSummaryDisplay();

  document.getElementById("sum-cat").textContent = label;
  document.getElementById("sum-carat").textContent = "-";
  document.getElementById("sum-type").textContent = "-";
  
  document.getElementById("large-image-container").classList.add("hidden");

  updateTotal();
}

function selectCarat(carat) {
  state.carat = carat;
  state.type = null;

  document.querySelectorAll(".carat-btn").forEach(b => b.classList.toggle("active", b.dataset.carat === carat));
  renderTypeCards();
  document.getElementById("type-step").classList.remove("hidden");

  document.getElementById("sum-carat").textContent = carat + "ct";
  document.getElementById("sum-type").textContent = "-";

  if (state.category === "ring" && state.ringSize && state.weightSource !== "manual") {
    applyRingWeightEstimate();
  }
  updateTotal();
}

function selectType(typeId, typeName) {
  state.type = typeId;
  document.querySelectorAll(".type-card").forEach(c => c.classList.toggle("active", c.dataset.type === typeId));
  document.getElementById("sum-type").textContent = typeName;
  document.getElementById("gold-step").classList.remove("hidden");
  
  const largeImageContainer = document.getElementById("large-image-container");
  const largeImage = document.getElementById("large-image");
  if (state.carat) {
    largeImage.src = `/static/images/${state.carat}-${typeId}.jpg`;
    largeImageContainer.classList.remove("hidden");
  }

  updateTotal();
}

function selectGold(goldId) {
  state.gold = goldId;
  document.querySelectorAll(".gold-btn").forEach(b => b.classList.toggle("active", b.dataset.gold === goldId));
  document.getElementById("sum-gold").textContent = goldLabel[goldId];
  updateGoldPriceDisplay();

  if (state.category === "ring" && state.ringSize && state.weightSource !== "manual") {
    applyRingWeightEstimate();
  }
  updateTotal();
}

function selectRingSize(size) {
  state.ringSize = size ? parseFloat(size) : null;
  if (state.ringSize) {
    applyRingWeightEstimate();
  }
  updateTotal();
}

function applyRingWeightEstimate() {
  const goldIdForEstimate = state.gold || DEFAULT_ESTIMATE_GOLD;
  const estimateGrams = estimateRingWeight(state.ringSize, goldIdForEstimate, state.carat);
  if (estimateGrams === null) return;
  setWeightGrams(estimateGrams, "estimate");
  updateRingHelperText();
}

function updateRingHelperText() {
  const helper = document.getElementById("ring-helper-text");
  if (!helper) return;
  helper.textContent = state.gold
    ? tr('helper_estimate')
    : tr('helper_no_gold');
}

// value is in whatever unit is currently selected (state.weightUnit)
function onWeightChange(value, source) {
  const raw = parseFloat(value);
  const grams = isNaN(raw) || raw < 0 ? 0 : displayToGrams(raw, state.weightUnit);
  state.weight = grams;
  state.weightSource = source || "manual";
  updateWeightSummaryDisplay();
  updateTotal();
}

// grams is always in grams; used by ring-size estimate and unit switching
function setWeightGrams(grams, source) {
  state.weight = grams < 0 ? 0 : grams;
  state.weightSource = source || "manual";
  document.getElementById("weight-input").value = gramsToDisplay(state.weight, state.weightUnit).toFixed(unitDecimals[state.weightUnit]);
  updateWeightSummaryDisplay();
  updateTotal();
}

function updateWeightSummaryDisplay() {
  const displayValue = gramsToDisplay(state.weight, state.weightUnit);
  document.getElementById("sum-weight").textContent = state.weight > 0 ? displayValue.toFixed(unitDecimals[state.weightUnit]) : "-";
  document.getElementById("sum-weight-unit").textContent = tr('unit_' + state.weightUnit);
}

function selectUnit(unit) {
  state.weightUnit = unit;
  document.getElementById("weight-input").value = state.weight > 0 ? gramsToDisplay(state.weight, unit).toFixed(unitDecimals[unit]) : "";
  updateWeightSummaryDisplay();
}

// --- Total calculation ---

function updateTotal() {
  const diamondPriceUnavailable = state.carat && diamondPrice[state.carat] === null;
  const dPrice = state.carat && diamondPrice[state.carat] ? diamondPrice[state.carat] : 0;
  const goldPriceUnavailable = state.gold && pricePerGram[state.gold] === null;
  const gRate = state.gold && pricePerGram[state.gold] ? pricePerGram[state.gold] : 0;
  const gCost = gRate * state.weight;
  const total = dPrice + gCost;

  document.getElementById("sum-diamond-price").textContent =
    diamondPriceUnavailable ? tr('goldprice_loading') : dPrice.toLocaleString();

  if (goldPriceUnavailable || diamondPriceUnavailable) {
    document.getElementById("sum-gold-cost").textContent = tr('price_unavailable');
    document.getElementById("sum-total").textContent = tr('total_unavailable');
  } else {
    document.getElementById("sum-gold-cost").textContent = Math.round(gCost).toLocaleString();
    document.getElementById("sum-total").textContent = Math.round(total).toLocaleString();
  }
}

// --- Event wiring ---

document.querySelectorAll(".cat-btn").forEach(btn => {
  btn.addEventListener("click", () => selectCategory(btn.dataset.cat, tr(btn.dataset.cat === 'ring' ? 'cat_ring' : 'cat_necklace')));
});

document.querySelectorAll(".carat-btn").forEach(btn => {
  btn.addEventListener("click", () => selectCarat(btn.dataset.carat));
});

document.querySelectorAll(".gold-btn").forEach(btn => {
  btn.addEventListener("click", () => selectGold(btn.dataset.gold));
});

document.getElementById("weight-input").addEventListener("input", e => onWeightChange(e.target.value));

document.getElementById("ring-size-select").addEventListener("change", e => selectRingSize(e.target.value));

document.getElementById("unit-select").addEventListener("change", e => selectUnit(e.target.value));

populateRingSizeOptions();
loadMetalPrices();

if (window.editData) {
  const btn = document.getElementById("confirm-btn");
  btn.textContent = tr('btn_update');
  
  const catBtn = document.querySelector(`.cat-btn[data-cat="${window.editData.category}"]`);
  if (catBtn) catBtn.click();
  
  const caratBtn = document.querySelector(`.carat-btn[data-carat="${window.editData.carat}"]`);
  if (caratBtn) caratBtn.click();
  
  const typeName = types.find(t => t.id === window.editData.type)?.name || window.editData.type;
  selectType(window.editData.type, typeName);
  
  const goldBtn = document.querySelector(`.gold-btn[data-gold="${window.editData.gold}"]`);
  if (goldBtn) goldBtn.click();
  
  if (window.editData.ringSize !== null) {
    document.getElementById("ring-size-select").value = window.editData.ringSize;
    selectRingSize(window.editData.ringSize);
  }
  
  if (window.editData.weight !== null) {
    setWeightGrams(window.editData.weight, "manual");
  }
}

document.getElementById("confirm-btn").addEventListener("click", async () => {
  if (!state.category) {
    alert(tr('alert_pick_category'));
    return;
  }
  if (!state.carat) {
    alert(tr('alert_pick_carat'));
    return;
  }
  if (!state.type) {
    alert(tr('alert_pick_type'));
    return;
  }
  if (!state.gold) {
    alert(tr('alert_pick_gold'));
    return;
  }
  if (state.category === "ring" && !state.ringSize) {
    alert(tr('alert_pick_ring_size'));
    return;
  }
  if (!state.weight || state.weight <= 0) {
    alert(tr('alert_enter_weight'));
    return;
  }
  
  const btn = document.getElementById("confirm-btn");
  btn.disabled = true;
  btn.textContent = tr('btn_submitting');

  const dPrice = state.carat && diamondPrice[state.carat] ? diamondPrice[state.carat] : 0;
  const gRate = state.gold && pricePerGram[state.gold] ? pricePerGram[state.gold] : 0;
  const gCost = gRate * state.weight;
  const total = dPrice + gCost;

  const payload = {
    ...state,
    totalPrice: total
  };

  try {
    const url = window.editData ? `/edit/${window.editData.id}` : "/submit";
    const res = await fetch(url, {
      method: "POST",
      headers: { 
        "Content-Type": "application/json",
        "X-CSRFToken": document.querySelector('meta[name="csrf-token"]').content
      },
      body: JSON.stringify(payload)
    });
    if (res.status === 401) { window.location.href = "/login"; return; }
    const result = await res.json();
    if (result.status === "success" || result.success) {
      window.location.href = "/success";
    } else {
      alert(tr('save_failed') + (result.message || ""));
    }
  } catch (err) {
    console.error(err);
    alert(tr('generic_error'));
  } finally {
    btn.disabled = false;
    btn.textContent = window.editData ? tr('btn_update') : tr('btn_confirm');
  }
});

document.addEventListener('langchange', () => {
  document.querySelectorAll('#ring-size-select option[data-size]').forEach(o => {
    o.textContent = tr('ring_size_option') + o.dataset.size;
  });
  if (state.category) {
    document.getElementById("sum-cat").textContent = tr(state.category === 'ring' ? 'cat_ring' : 'cat_necklace');
  }
  document.getElementById('confirm-btn').textContent = window.editData ? tr('btn_update') : tr('btn_confirm');
  updateWeightSummaryDisplay();
  updateGoldPriceDisplay();
  updateRingHelperText();
  updateTotal();
});
