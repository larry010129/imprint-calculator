function tr(k) { return window.t ? window.t(k) : k; }

// ── Static product data ────────────────────────────────────────────────────

const CATEGORY_STYLES = {
  pendant:  ['A', 'B', 'C'],
  ring:     ['A', 'B', 'C'],
  earring:  ['A'],
  bracelet: ['A', 'B', 'C'],
  chain:    ['A'],
};

const STYLE_NAMES = {
  pendant:  { A: 'cat_pendant_A', B: 'cat_pendant_B', C: 'cat_pendant_C' },
  ring:     { A: 'cat_ring_A',    B: 'cat_ring_B',    C: 'cat_ring_C'    },
  earring:  { A: 'cat_earring_A'                                          },
  bracelet: { A: 'cat_bracelet_A',B: 'cat_bracelet_B', C: 'cat_bracelet_C'},
  chain:    { A: 'cat_chain_A'                                            },
};

// Metals available per category
const CATEGORY_METALS = {
  pendant:  ['9k', '14k', '18k', 'pt950', 's925'],
  ring:     ['9k', '14k', '18k', 'pt950', 's925'],
  earring:  ['9k', '14k', '18k'],
  bracelet: ['9k', '14k', '18k', 'pt950', 's925'],
  chain:    ['9k', '14k', '18k', 'pt950', 's925'],
};

// Colors per metal ('none' = no color choice)
const METAL_COLORS = {
  '9k':    ['white'],
  '14k':   ['white', 'yellow', 'rose'],
  '18k':   ['white', 'yellow', 'rose'],
  'pt950': [],
  's925':  [],
};

// Valid carats per category (bracelet and chain handled specially)
const CATEGORY_CARATS = {
  pendant:  ['0.1', '0.3', '0.5', '1.0'],
  ring:     ['0.1', '0.3', '0.5', '1.0'],
  earring:  ['0.1', '0.3', '0.5', '1.0'],
  bracelet: ['0.1'],  // only 0.1ct available
  chain:    ['3fen', '4fen'],
};

// Weight table in 錢 (chin); weight_grams = chin * 3.75
const WEIGHT_TABLE = {
  pendant: {
    A: { '9k':{'0.1':0.09,'0.3':0.12,'0.5':0.15,'1.0':0.20}, '14k':{'0.1':0.10,'0.3':0.14,'0.5':0.17,'1.0':0.23}, '18k':{'0.1':0.12,'0.3':0.16,'0.5':0.20,'1.0':0.27}, 'pt950':{'0.1':0.15,'0.3':0.20,'0.5':0.25,'1.0':0.35}, 's925':{'0.1':0.08,'0.3':0.11,'0.5':0.13,'1.0':0.18} },
    B: { '9k':{'0.1':0.10,'0.3':0.15,'0.5':0.19,'1.0':0.28}, '14k':{'0.1':0.11,'0.3':0.17,'0.5':0.22,'1.0':0.33}, '18k':{'0.1':0.13,'0.3':0.20,'0.5':0.26,'1.0':0.39}, 'pt950':{'0.1':0.16,'0.3':0.25,'0.5':0.34,'1.0':0.52}, 's925':{'0.1':0.09,'0.3':0.13,'0.5':0.17,'1.0':0.25} },
    C: { '9k':{'0.1':0.14,'0.3':0.21,'0.5':0.28,'1.0':0.46}, '14k':{'0.1':0.16,'0.3':0.24,'0.5':0.32,'1.0':0.52}, '18k':{'0.1':0.19,'0.3':0.28,'0.5':0.37,'1.0':0.60}, 'pt950':{'0.1':0.25,'0.3':0.37,'0.5':0.49,'1.0':0.80}, 's925':{'0.1':0.13,'0.3':0.19,'0.5':0.25,'1.0':0.40} },
  },
  ring: {
    A: { '9k':{'0.1':0.39,'0.3':0.48,'0.5':0.57,'1.0':0.74}, '14k':{'0.1':0.46,'0.3':0.57,'0.5':0.67,'1.0':0.87}, '18k':{'0.1':0.53,'0.3':0.65,'0.5':0.77,'1.0':1.01}, 'pt950':{'0.1':0.70,'0.3':0.86,'0.5':1.02,'1.0':1.33}, 's925':{'0.1':0.35,'0.3':0.44,'0.5':0.52,'1.0':0.68} },
    B: { '9k':{'0.1':0.40,'0.3':0.62,'0.5':0.84,'1.0':1.39}, '14k':{'0.1':0.47,'0.3':0.75,'0.5':1.03,'1.0':1.73}, '18k':{'0.1':0.54,'0.3':0.86,'0.5':1.18,'1.0':1.98}, 'pt950':{'0.1':0.71,'0.3':1.13,'0.5':1.55,'1.0':2.60}, 's925':{'0.1':0.36,'0.3':0.58,'0.5':0.80,'1.0':1.35} },
    C: { '9k':{'0.1':0.40,'0.3':0.69,'0.5':0.97,'1.0':1.54}, '14k':{'0.1':0.48,'0.3':0.82,'0.5':1.15,'1.0':1.82}, '18k':{'0.1':0.55,'0.3':0.92,'0.5':1.33,'1.0':2.11}, 'pt950':{'0.1':0.72,'0.3':1.24,'0.5':1.75,'1.0':2.78}, 's925':{'0.1':0.36,'0.3':0.62,'0.5':0.88,'1.0':1.40} },
  },
  earring: {
    A: { '9k':{'0.1':0.09,'0.3':0.14,'0.5':0.18,'1.0':0.27}, '14k':{'0.1':0.10,'0.3':0.15,'0.5':0.20,'1.0':0.30}, '18k':{'0.1':0.12,'0.3':0.18,'0.5':0.24,'1.0':0.36} },
  },
  bracelet: {
    A: { '9k':{'0.1':0.66},'14k':{'0.1':0.78},'18k':{'0.1':0.91},'pt950':{'0.1':1.19},'s925':{'0.1':0.60} },
    B: { '9k':{'0.1':0.46},'14k':{'0.1':0.55},'18k':{'0.1':0.64},'pt950':{'0.1':0.84},'s925':{'0.1':0.77} },
    C: { '9k':{'0.1':0.30},'14k':{'0.1':0.36},'18k':{'0.1':0.42},'pt950':{'0.1':0.55},'s925':{'0.1':0.28} },
  },
  chain: {
    A: { '9k':{'3fen':0.3,'4fen':0.4},'14k':{'3fen':0.3,'4fen':0.4},'18k':{'3fen':0.3,'4fen':0.4},'pt950':{'3fen':0.3,'4fen':0.4},'s925':{'3fen':0.3,'4fen':0.4} },
  },
};

const LABOR_FEE = { pendant:5000, ring:5000, bracelet:5000, earring:3000, chain:0 };
const CHIN_TO_GRAMS = 3.75;
const RING_SIZE_MIN = 7, RING_SIZE_MAX = 11;

// ── Live price data (from /api/prices) ────────────────────────────────────

let diamondPrice = { "0.1": null, "0.3": null, "0.5": null, "1.0": null };
let pricePerGram = {};  // filled by loadMetalPrices()

// ── State ──────────────────────────────────────────────────────────────────

let state = {
  category: null,   // pendant / ring / earring / bracelet / chain
  type: null,       // A / B / C
  gold: null,       // 9k / 14k / 18k / pt950 / s925
  color: null,      // white / yellow / rose / null
  carat: null,      // 0.1 / 0.3 / 0.5 / 1.0 / 3fen / 4fen
  ringSize: null,   // float 7–11
};

// ── Helpers ───────────────────────────────────────────────────────────────

function lookupWeight(category, type, gold, carat) {
  try { return WEIGHT_TABLE[category][type][gold][carat]; }
  catch(e) { return null; }
}

function ringHalfAbove7(size) {
  return Math.max(0, Math.round((size - 7) / 0.5));
}

function imageUrl(category, type, color) {
  if (category === 'chain') {
    const c = color || 'white';
    return `/static/images/chain-${c}.jpg`;
  }
  return `/static/images/${category}-${type}.jpg`;
}

// ── Metal price fetch ─────────────────────────────────────────────────────

async function loadMetalPrices() {
  try {
    const res = await fetch("/api/prices");
    if (!res.ok) throw new Error(`API ${res.status}`);
    const data = await res.json();
    Object.assign(pricePerGram, data.perGram);
    Object.assign(diamondPrice, data.diamond);
    updateSummary();
  } catch (err) {
    document.getElementById("sum-goldprice").textContent = tr('goldprice_failed');
  }
}

// ── Render helpers ────────────────────────────────────────────────────────

function renderTypeCards() {
  const grid = document.getElementById("type-grid");
  grid.innerHTML = "";
  const styles = CATEGORY_STYLES[state.category] || [];
  styles.forEach(styleId => {
    const i18nKey = STYLE_NAMES[state.category]?.[styleId] || styleId;
    const card = document.createElement("div");
    card.className = "type-card";
    card.dataset.type = styleId;

    const imgBox = document.createElement("div");
    imgBox.className = "img-placeholder";
    const img = document.createElement("img");
    const url = imageUrl(state.category, styleId, state.color);
    img.src = url;
    img.alt = tr(i18nKey);
    img.onerror = () => {
      imgBox.classList.add("img-missing");
      imgBox.innerHTML = `<span class="img-fallback-label">IMG<br>${state.category}-${styleId}</span>`;
    };
    imgBox.appendChild(img);

    const name = document.createElement("p");
    name.className = "type-name";
    name.textContent = tr(i18nKey);

    card.appendChild(imgBox);
    card.appendChild(name);
    card.addEventListener("click", () => selectType(styleId));
    grid.appendChild(card);
  });
}

function updateMetalButtons() {
  const allowed = CATEGORY_METALS[state.category] || [];
  document.querySelectorAll(".metal-btn").forEach(btn => {
    const visible = allowed.includes(btn.dataset.gold);
    btn.style.display = visible ? '' : 'none';
    if (!visible && btn.dataset.gold === state.gold) {
      state.gold = null;
      state.color = null;
    }
  });
}

function updateColorStep() {
  const colors = state.gold ? (METAL_COLORS[state.gold] || []) : [];
  const colorStep = document.getElementById("color-step");
  const colorBtns = document.querySelectorAll(".color-btn");

  if (colors.length > 1) {
    colorStep.classList.remove("hidden");
    colorBtns.forEach(btn => {
      btn.style.display = colors.includes(btn.dataset.color) ? '' : 'none';
      btn.classList.remove("active");
    });
  } else {
    colorStep.classList.add("hidden");
    // auto-set color for 9k (always white) or pt950/s925 (no color)
    if (colors.length === 1) {
      state.color = colors[0];
    } else {
      state.color = null;
    }
  }
}

function updateCaratButtons() {
  const validCarats = CATEGORY_CARATS[state.category] || [];
  document.querySelectorAll(".carat-btn").forEach(btn => {
    const v = btn.dataset.carat;
    btn.style.display = validCarats.includes(v) ? '' : 'none';
    btn.classList.remove("active");
  });
}

function updateRingSizeStep() {
  const step = document.getElementById("ringsize-step");
  if (state.category === 'ring') {
    step.classList.remove("hidden");
  } else {
    step.classList.add("hidden");
    state.ringSize = null;
  }
}

function updateLargeImage() {
  if (!state.category || !state.type) return;
  const container = document.getElementById("large-image-container");
  const img = document.getElementById("large-image");
  img.src = imageUrl(state.category, state.type, state.color);
  container.classList.remove("hidden");
}

// ── Summary update ────────────────────────────────────────────────────────

function updateSummary() {
  // Category
  document.getElementById("sum-cat").textContent =
    state.category ? tr('cat_' + state.category) : '-';

  // Style
  const styleKey = state.category && state.type
    ? (STYLE_NAMES[state.category]?.[state.type] || state.type) : null;
  document.getElementById("sum-type").textContent =
    styleKey ? tr(styleKey) : '-';

  // Metal
  document.getElementById("sum-gold").textContent =
    state.gold ? tr('metal_' + state.gold) : '-';

  // Color
  const colorRow = document.getElementById("sum-color-row");
  if (state.color && state.gold && METAL_COLORS[state.gold]?.length > 1) {
    colorRow.style.display = '';
    document.getElementById("sum-color").textContent = tr('color_' + state.color);
  } else {
    colorRow.style.display = 'none';
  }

  // Carat / chain weight
  const caratDisplay = state.carat
    ? (state.carat === '3fen' ? tr('chain_3fen')
      : state.carat === '4fen' ? tr('chain_4fen')
      : state.carat + 'ct')
    : '-';
  document.getElementById("sum-carat").textContent = caratDisplay;

  // Weight lookup
  const chin = (state.category && state.type && state.gold && state.carat)
    ? lookupWeight(state.category, state.type, state.gold, state.carat)
    : null;
  const weightGrams = chin !== null ? (chin * CHIN_TO_GRAMS) : null;

  if (chin !== null) {
    document.getElementById("sum-weight").textContent =
      chin.toFixed(2) + ' 錢 (' + weightGrams.toFixed(3) + 'g)';
  } else {
    document.getElementById("sum-weight").textContent = '-';
  }

  // Gold price per gram
  const ppm = state.gold ? pricePerGram[state.gold] : null;
  document.getElementById("sum-goldprice").textContent =
    ppm != null ? Math.round(ppm).toLocaleString() : tr('goldprice_loading');

  // Diamond price (non-chain)
  const diamondRow = document.getElementById("sum-diamond-row");
  if (state.category === 'chain') {
    diamondRow.style.display = 'none';
  } else {
    diamondRow.style.display = '';
    const dp = state.carat ? diamondPrice[state.carat] : null;
    document.getElementById("sum-diamond-price").textContent =
      dp != null ? dp.toLocaleString() : (state.carat ? tr('goldprice_loading') : '0');
  }

  // Metal cost
  const metalCost = (ppm != null && weightGrams != null) ? ppm * weightGrams : null;
  document.getElementById("sum-gold-cost").textContent =
    metalCost != null ? Math.round(metalCost).toLocaleString() : '-';

  // Labor fee
  const labor = state.category ? LABOR_FEE[state.category] : 0;
  document.getElementById("sum-labor").textContent =
    state.category === 'chain' ? '0' : labor.toLocaleString();

  // Ring surcharge
  const surchargeRow = document.getElementById("sum-surcharge-row");
  let surcharge = 0;
  if (state.category === 'ring' && state.ringSize) {
    surcharge = ringHalfAbove7(state.ringSize) * 500;
    surchargeRow.style.display = '';
    document.getElementById("sum-surcharge").textContent = surcharge.toLocaleString();
    document.getElementById("sum-ring-size-val").textContent = '#' + state.ringSize;
  } else {
    surchargeRow.style.display = 'none';
  }

  // Total
  const dp2 = (state.category !== 'chain' && state.carat) ? (diamondPrice[state.carat] || 0) : 0;
  let total = null;
  if (metalCost != null) {
    if (state.category === 'chain') {
      total = metalCost * 2;
    } else if (diamondPrice[state.carat] != null || state.category === 'chain') {
      total = dp2 + metalCost + labor + surcharge;
    } else if (state.carat) {
      total = null; // diamond price still loading
    } else {
      total = dp2 + metalCost + labor + surcharge;
    }
  }

  document.getElementById("sum-total").textContent =
    total != null ? Math.round(total).toLocaleString() : '-';
}

// ── Selection handlers ────────────────────────────────────────────────────

function selectCategory(cat) {
  state.category = cat;
  state.type = null;
  state.gold = null;
  state.color = null;
  state.carat = null;
  state.ringSize = null;

  document.querySelectorAll(".cat-btn").forEach(b =>
    b.classList.toggle("active", b.dataset.cat === cat));

  renderTypeCards();
  document.getElementById("type-step").classList.remove("hidden");
  document.getElementById("carat-step").classList.add("hidden");
  document.getElementById("metal-step").classList.add("hidden");
  document.getElementById("color-step").classList.add("hidden");
  document.getElementById("ringsize-step").classList.add("hidden");
  document.getElementById("large-image-container").classList.add("hidden");

  document.querySelectorAll(".metal-btn, .color-btn, .carat-btn").forEach(b => b.classList.remove("active"));
  document.getElementById("ring-size-select").value = "";
  updateMetalButtons();
  updateSummary();
}

function selectType(typeId) {
  state.type = typeId;
  state.carat = null;
  state.gold = null;
  state.color = null;
  state.ringSize = null;

  document.querySelectorAll(".type-card").forEach(c =>
    c.classList.toggle("active", c.dataset.type === typeId));

  updateCaratButtons();
  document.getElementById("carat-step").classList.remove("hidden");
  document.getElementById("metal-step").classList.add("hidden");
  document.getElementById("color-step").classList.add("hidden");
  document.getElementById("ringsize-step").classList.add("hidden");
  document.querySelectorAll(".carat-btn, .metal-btn, .color-btn").forEach(b => b.classList.remove("active"));
  document.getElementById("ring-size-select").value = "";

  updateLargeImage();
  updateSummary();
}

function selectMetal(goldId) {
  state.gold = goldId;
  state.color = null;
  state.ringSize = null;

  document.querySelectorAll(".metal-btn").forEach(b =>
    b.classList.toggle("active", b.dataset.gold === goldId));
  document.querySelectorAll(".color-btn").forEach(b => b.classList.remove("active"));
  document.getElementById("ring-size-select").value = "";

  updateColorStep();

  const colors = METAL_COLORS[goldId] || [];
  if (colors.length > 1) {
    // color step shown by updateColorStep(); hide ringsize until color chosen
    document.getElementById("ringsize-step").classList.add("hidden");
  } else {
    // skip color step — show ringsize if ring, else summary ready
    updateRingSizeStep();
  }

  updateSummary();
}

function selectColor(color) {
  state.color = color;
  state.ringSize = null;

  document.querySelectorAll(".color-btn").forEach(b =>
    b.classList.toggle("active", b.dataset.color === color));
  document.getElementById("ring-size-select").value = "";

  updateRingSizeStep();
  updateLargeImage();
  updateSummary();
}

function selectCarat(carat) {
  state.carat = carat;
  state.gold = null;
  state.color = null;
  state.ringSize = null;

  document.querySelectorAll(".carat-btn").forEach(b =>
    b.classList.toggle("active", b.dataset.carat === carat));
  document.querySelectorAll(".metal-btn, .color-btn").forEach(b => b.classList.remove("active"));
  document.getElementById("ring-size-select").value = "";

  document.getElementById("metal-step").classList.remove("hidden");
  document.getElementById("color-step").classList.add("hidden");
  document.getElementById("ringsize-step").classList.add("hidden");
  updateSummary();
}

function selectRingSize(size) {
  state.ringSize = size ? parseFloat(size) : null;
  updateSummary();
}

// ── Event wiring ──────────────────────────────────────────────────────────

document.querySelectorAll(".cat-btn").forEach(btn =>
  btn.addEventListener("click", () => selectCategory(btn.dataset.cat)));

document.querySelectorAll(".type-card").forEach(card =>
  card.addEventListener("click", () => selectType(card.dataset.type)));

document.querySelectorAll(".metal-btn").forEach(btn =>
  btn.addEventListener("click", () => selectMetal(btn.dataset.gold)));

document.querySelectorAll(".color-btn").forEach(btn =>
  btn.addEventListener("click", () => selectColor(btn.dataset.color)));

document.querySelectorAll(".carat-btn").forEach(btn =>
  btn.addEventListener("click", () => selectCarat(btn.dataset.carat)));

document.getElementById("ring-size-select").addEventListener("change", e =>
  selectRingSize(e.target.value));

// Populate ring size dropdown 7–11 in 0.5 steps
function populateRingSizeOptions() {
  const select = document.getElementById("ring-size-select");
  for (let s = RING_SIZE_MIN; s <= RING_SIZE_MAX; s += 0.5) {
    const opt = document.createElement("option");
    opt.value = s;
    opt.textContent = tr('ring_size_option') + s;
    opt.dataset.size = s;
    select.appendChild(opt);
  }
}

populateRingSizeOptions();
loadMetalPrices();

// ── Edit mode restore ─────────────────────────────────────────────────────

if (window.editData) {
  document.getElementById("confirm-btn").textContent = tr('btn_update');

  const catBtn = document.querySelector(`.cat-btn[data-cat="${window.editData.category}"]`);
  if (catBtn) { catBtn.click(); }

  // Delay subsequent steps so DOM updates cascade
  // Order: category → type → carat → metal → color → ringSize
  setTimeout(() => {
    const card = document.querySelector(`.type-card[data-type="${window.editData.type}"]`);
    if (card) { card.click(); }

    setTimeout(() => {
      const caratBtn = document.querySelector(`.carat-btn[data-carat="${window.editData.carat}"]`);
      if (caratBtn) { caratBtn.click(); }

      setTimeout(() => {
        const metalBtn = document.querySelector(`.metal-btn[data-gold="${window.editData.gold}"]`);
        if (metalBtn) { metalBtn.click(); }

        setTimeout(() => {
          if (window.editData.color) {
            const colorBtn = document.querySelector(`.color-btn[data-color="${window.editData.color}"]`);
            if (colorBtn) colorBtn.click();
          }

          if (window.editData.ringSize) {
            setTimeout(() => {
              document.getElementById("ring-size-select").value = window.editData.ringSize;
              selectRingSize(window.editData.ringSize);
            }, 50);
          }
        }, 50);
      }, 50);
    }, 50);
  }, 50);
}

// ── Submit / Update ───────────────────────────────────────────────────────

document.getElementById("confirm-btn").addEventListener("click", async () => {
  if (!state.category) { alert(tr('alert_pick_category')); return; }
  if (!state.type)     { alert(tr('alert_pick_type'));     return; }
  if (!state.gold)     { alert(tr('alert_pick_gold'));     return; }

  const needsColor = state.gold && METAL_COLORS[state.gold]?.length > 1;
  if (needsColor && !state.color) { alert(tr('alert_pick_color')); return; }

  if (!state.carat) { alert(tr('alert_pick_carat')); return; }

  if (state.category === 'ring' && !state.ringSize) {
    alert(tr('alert_pick_ring_size')); return;
  }

  const btn = document.getElementById("confirm-btn");
  btn.disabled = true;
  btn.textContent = tr('btn_submitting');

  const payload = {
    category: state.category,
    type:     state.type,
    gold:     state.gold,
    color:    state.color,
    carat:    state.carat,
    ringSize: state.ringSize,
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
  document.getElementById('confirm-btn').textContent =
    window.editData ? tr('btn_update') : tr('btn_confirm');
  updateSummary();
  if (state.category) renderTypeCards();
});
