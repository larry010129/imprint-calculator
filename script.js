// --- Data ---

const diamondPrice = {
  "0.1": 24000,
  "0.3": 79000,
  "0.5": 98000,
  "1": 250000
};

const types = [
  { id: "A", name: "款式 A" },
  { id: "B", name: "款式 B" },
  { id: "C", name: "款式 C" }
];

const purityMultiplier = { "18k": 0.75, "999": 0.999, "pt": 1, "silver925": 0.925 };
const goldLabel = { "18k": "18K金", "999": "純金999", "pt": "鉑金 Pt", "silver925": "925銀" };

// which goldapi.io metal symbol each option prices off of
const metalSymbol = { "18k": "XAU", "999": "XAU", "pt": "XPT", "silver925": "XAG" };

// goldapi.io free-tier key - client-side exposed, fine for local/internal use only.
// If this page ever goes public, move this fetch behind a backend proxy instead.
const GOLDAPI_KEY = "goldapi-eb915d55941859c5bec9d3d1cbaff238-io";

// metal price per gram in TWD (before purity multiplier), filled after fetch
let pricePerGramRaw = { XAU: null, XPT: null, XAG: null };

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
const unitDecimals = { g: 1, chin: 2, taijin: 4 };
const unitLabel = { g: "克", chin: "錢", taijin: "台斤" };

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
    opt.textContent = "台灣戒圍 #" + size;
    select.appendChild(opt);
  }
}

// --- Fetch live metal price ---

async function fetchMetalPriceTwd(symbol) {
  const res = await fetch("https://www.goldapi.io/api/" + symbol + "/TWD", {
    headers: {
      "x-access-token": GOLDAPI_KEY,
      "Content-Type": "application/json"
    }
  });
  const data = await res.json();
  return data.price / 31.1034768; // troy oz -> gram, already in TWD
}

async function loadMetalPrices() {
  try {
    const [xauPerGram, xptPerGram, xagPerGram] = await Promise.all([
      fetchMetalPriceTwd("XAU"),
      fetchMetalPriceTwd("XPT"),
      fetchMetalPriceTwd("XAG")
    ]);

    pricePerGramRaw.XAU = xauPerGram;
    pricePerGramRaw.XPT = xptPerGram;
    pricePerGramRaw.XAG = xagPerGram;

    Object.keys(metalSymbol).forEach(goldId => {
      pricePerGram[goldId] = pricePerGramRaw[metalSymbol[goldId]] * purityMultiplier[goldId];
    });

    updateGoldPriceDisplay();
  } catch (err) {
    document.getElementById("sum-goldprice").textContent = "無法取得即時金價";
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
    img.src = `images/${state.carat}-${t.id}.jpg`;
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
  if (state.ringSize && state.weightSource !== "manual") {
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
    ? "依戒圍粗估金重，可於下方微調"
    : "尚未選擇金屬成色，暫以18K密度估算，選擇金屬後將自動更新";
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
  document.getElementById("sum-weight-unit").textContent = unitLabel[state.weightUnit];
}

function selectUnit(unit) {
  state.weightUnit = unit;
  document.getElementById("weight-input").value = state.weight > 0 ? gramsToDisplay(state.weight, unit).toFixed(unitDecimals[unit]) : "";
  updateWeightSummaryDisplay();
}

// --- Total calculation ---

function updateTotal() {
  const dPrice = state.carat ? diamondPrice[state.carat] : 0;
  const goldPriceUnavailable = state.gold && pricePerGram[state.gold] === null;
  const gRate = state.gold && pricePerGram[state.gold] ? pricePerGram[state.gold] : 0;
  const gCost = gRate * state.weight;
  const total = dPrice + gCost;

  document.getElementById("sum-diamond-price").textContent = dPrice.toLocaleString();

  if (goldPriceUnavailable) {
    document.getElementById("sum-gold-cost").textContent = "無法取得金價";
    document.getElementById("sum-total").textContent = "無法計算";
  } else {
    document.getElementById("sum-gold-cost").textContent = Math.round(gCost).toLocaleString();
    document.getElementById("sum-total").textContent = Math.round(total).toLocaleString();
  }
}

// --- Event wiring ---

document.querySelectorAll(".cat-btn").forEach(btn => {
  btn.addEventListener("click", () => selectCategory(btn.dataset.cat, btn.textContent));
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
