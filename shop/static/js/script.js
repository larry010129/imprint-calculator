function tr(k) { return window.t ? window.t(k) : k; }
function shopLang() { return localStorage.getItem('appLang') || 'zh'; }

const shopMode = (window.shopConfig && window.shopConfig.mode) || 'order';
const isGuestShop = shopMode === 'guest';

function guestLoginUrl() {
  return (window.shopConfig && window.shopConfig.loginUrl) || '/login';
}

function redirectGuestToLogin() {
  window.location.href = guestLoginUrl();
}

function getCsrfToken() {
  return document.querySelector('meta[name="csrf-token"]')?.content || '';
}

function shopApiHeaders() {
  return {
    'Content-Type': 'application/json',
    'X-CSRFToken': getCsrfToken(),
  };
}

async function readShopApiJson(res) {
  const text = await res.text();
  if (!text) return {};
  try {
    return JSON.parse(text);
  } catch (_) {
    return { success: false, message: text.slice(0, 200) };
  }
}

function shopApiErrorMessage(data, res) {
  if (data?.message) return data.message;
  if (res?.status === 429) return tr('rate_limit_error');
  return tr('generic_error');
}

// ── Fixed business rules (physical/tax facts, NOT catalog content) ────────
// Which metals require a color choice, and which colors they offer.
const METAL_COLORS = {
  '9k':    ['white'],
  '14k':   ['white', 'yellow', 'rose'],
  '18k':   ['white', 'yellow', 'rose'],
  'pt950': [],
  's925':  [],
};
const METAL_MATERIAL_LABELS = {
  '9k:white': 'material_9k_white',
  '14k:white': 'material_14k_white',
  '14k:yellow': 'material_14k_yellow',
  '14k:rose': 'material_14k_rose',
  '18k:white': 'material_18k_white',
  '18k:yellow': 'material_18k_yellow',
  '18k:rose': 'material_18k_rose',
  'pt950:white': 'material_pt950',
  's925:white': 'material_s925',
};
const GOLD_COLOR_METALS = ['9k', '14k', '18k'];
const METAL_DISPLAY_ORDER = ['9k', '14k', '18k', 'pt950', 's925'];

function sortGolds(golds) {
  const order = Object.fromEntries(METAL_DISPLAY_ORDER.map((g, i) => [g, i]));
  return [...golds].sort((a, b) => (order[a] ?? 99) - (order[b] ?? 99));
}

// Which carat-unit system each category uses (ct vs chain's 分). Kept as a
// display/UI hint; the actual selectable set per listing comes from the
// catalog (a listing only offers the carats it has variants for).
const CATEGORY_CARAT_UNIT = {
  pendant: 'ct', ring: 'ct', earring: 'ct', bracelet: 'ct', chain: 'fen',
};
const CATEGORY_DISPLAY_ORDER = ['pendant', 'ring', 'earring', 'bracelet', 'chain'];

// ── Live catalog data (from /api/catalog) — replaces the old hardcoded
//    CATEGORY_STYLES / STYLE_NAMES / CATEGORY_METALS / WEIGHT_TABLE. ───────
let catalog = {};          // { category: [ {id, nameZh, nameEn, defaultColor, golds, carats, colors, images, weights, manualPrices}, ... ] }
let catalogLoaded = false;

function productsFor(category) {
  return catalog[category] || [];
}

function catalogCategories() {
  const present = Object.keys(catalog).filter(cat => productsFor(cat).length > 0);
  const preferred = (window._catalogCategoryOrder && window._catalogCategoryOrder.length)
    ? window._catalogCategoryOrder
    : CATEGORY_DISPLAY_ORDER;
  const ordered = preferred.filter(cat => present.includes(cat));
  return ordered.concat(present.filter(cat => !ordered.includes(cat)));
}

function getProduct(category, typeId) {
  if (!category || typeId == null) return null;
  return productsFor(category).find(p => String(p.id) === String(typeId)) || null;
}

function getSelectedProduct() {
  return getProduct(state.category, state.type);
}

function productName(product) {
  if (!product) return '';
  return shopLang() === 'en' ? (product.nameEn || product.nameZh) : product.nameZh;
}

function materialColor(gold) {
  return (METAL_COLORS[gold] || []).length === 1 ? METAL_COLORS[gold][0] : 'white';
}

function materialLabel(gold, color) {
  return tr(METAL_MATERIAL_LABELS[`${gold}:${color || materialColor(gold)}`] || `metal_${gold}`);
}

function availableColorsForGold(gold, product) {
  const metalColors = METAL_COLORS[gold];
  if (metalColors?.length) return [...metalColors];
  return ['white'];
}

function needsColorSelection(gold, product) {
  return !!(gold && GOLD_COLOR_METALS.includes(gold));
}

function updateColorStepLabel(labelId, gold) {
  const label = document.getElementById(labelId);
  if (!label) return;
  if (gold && GOLD_COLOR_METALS.includes(gold)) {
    const key = 'step_color_' + gold;
    label.setAttribute('data-i18n', key);
    label.textContent = tr(key);
  } else {
    label.setAttribute('data-i18n', 'step_color');
    label.textContent = tr('step_color');
  }
}

function renderMetalButtons(rowId, golds, selectedGold, onSelect) {
  const row = document.getElementById(rowId);
  if (!row) return;
  row.innerHTML = '';
  sortGolds(golds).forEach(gold => {
    const btn = document.createElement('button');
    btn.type = 'button';
    btn.className = 'metal-btn variant-chip';
    btn.dataset.gold = gold;
    btn.textContent = tr('metal_' + gold);
    btn.classList.toggle('active', selectedGold === gold);
    btn.addEventListener('click', () => onSelect(gold));
    row.appendChild(btn);
  });
}

function renderColorButtons(rowId, gold, product, selectedColor, onSelect) {
  const row = document.getElementById(rowId);
  if (!row) return;
  row.innerHTML = '';
  row.classList.add('variant-chips--colors');
  availableColorsForGold(gold, product).forEach(color => {
    const labelText = materialLabel(gold, color);
    const btn = document.createElement('button');
    btn.type = 'button';
    btn.className = 'color-btn variant-chip color-swatch-labeled';
    btn.dataset.color = color;
    btn.setAttribute('aria-label', labelText);

    const swatch = document.createElement('span');
    swatch.className = 'color-swatch-dot';
    swatch.dataset.color = color;
    swatch.setAttribute('aria-hidden', 'true');

    const label = document.createElement('span');
    label.className = 'color-swatch-label';
    label.textContent = labelText;

    btn.classList.toggle('active', selectedColor === color);
    btn.appendChild(swatch);
    btn.appendChild(label);
    btn.addEventListener('click', () => onSelect(color));
    row.appendChild(btn);
  });
}

/** Image URLs for a product color, falling back through default/white/any. */
function productImagesForColor(product, color) {
  if (!product?.images) return [];
  const pick = (key) => {
    const val = product.images[key];
    if (Array.isArray(val)) return val.filter(Boolean);
    if (typeof val === 'string' && val) return [val];
    return [];
  };
  for (const key of [color, product.defaultColor, 'white']) {
    const list = pick(key);
    if (list.length) return list;
  }
  for (const list of Object.values(product.images)) {
    const normalized = Array.isArray(list) ? list.filter(Boolean) : (list ? [list] : []);
    if (normalized.length) return normalized;
  }
  return [];
}

/** Best available image URL for a product (first of the color set). */
function productImageUrl(product, color) {
  return productImagesForColor(product, color)[0] || '';
}

async function loadCatalog() {
  const grid = document.querySelector('.catalog-grid');
  let errEl = document.getElementById('catalog-error');
  try {
    const catalogUrl = window.shopConfig?.preview ? '/api/catalog?preview=1' : '/api/catalog';
    const res = await fetch(catalogUrl);
    if (!res.ok) throw new Error(`API ${res.status}`);
    const data = await res.json();
    catalog = data.categories || {};
    window._catalogCategoryOrder = data.categoryOrder || null;
    catalogLoaded = true;
    grid?.classList.remove('is-loading');
    grid?.setAttribute('aria-busy', 'false');
    if (errEl) errEl.remove();
    renderCatalogTiles();
  } catch (err) {
    catalogLoaded = false;
    catalog = {};
    window._catalogCategoryOrder = null;
    grid?.classList.remove('is-loading');
    grid?.setAttribute('aria-busy', 'false');
    console.error('failed to load catalog', err);
    renderCatalogTiles();
    if (grid && !errEl) {
      errEl = document.createElement('div');
      errEl.id = 'catalog-error';
      errEl.className = 'catalog-error';
      errEl.innerHTML = `<p>${tr('catalog_load_failed')}</p><button type="button" class="btn-secondary" id="catalog-retry">${tr('catalog_retry')}</button>`;
      grid.parentElement?.insertBefore(errEl, grid);
      errEl.querySelector('#catalog-retry')?.addEventListener('click', () => {
        errEl.remove();
        loadCatalog().then(() => { if (state.category) renderTypeCards(); });
      });
    }
  }
}

function renderCatalogTiles() {
  const grid = document.querySelector('.catalog-grid');
  const empty = document.getElementById('catalog-empty');
  if (!grid) return;
  grid.innerHTML = '';
  const cats = catalogLoaded ? catalogCategories() : [];
  empty?.classList.toggle('hidden', cats.length > 0);
  cats.forEach(cat => {
    const products = productsFor(cat);
    const btn = document.createElement('button');
    btn.type = 'button';
    btn.className = 'catalog-tile cat-btn';
    btn.dataset.cat = cat;
    if (state.category === cat) btn.classList.add('active');

    const img = document.createElement('img');
    img.loading = 'lazy';
    img.alt = '';
    const thumb = products[0];
    img.src = thumb ? productImageUrl(thumb, thumb.defaultColor) : '';

    const label = document.createElement('span');
    label.textContent = tr('cat_' + cat);

    btn.appendChild(img);
    btn.appendChild(label);
    btn.addEventListener('click', () => selectCategory(cat));
    grid.appendChild(btn);
  });
}

// Weight/pricing constants loaded from /api/prices (server is source of truth)
let laborFee = {};
let chinToGrams = 3.75;
let taxRate = 0.05;
let ringSizeMin = 5;
let ringSizeMax = 18;
let ringSizeReference = {};

// ── Live price data (from /api/prices) ────────────────────────────────────

let diamondPrice = { "0.1": null, "0.3": null, "0.5": null, "1.0": null };
let diamondOptions = {
  diamondColors: [],
  kinds: [],
  fancyColors: [],
  shapes: [],
  stoneCounts: [2, 3, 4],
  stoneCountCategories: ['earring'],
  fancyMinCarat: 0.3,
  nonRoundShapeMinCarat: 0.3,
  nonRoundShapeSurcharge: 0.10,
  defaultStoneCountByCategory: { earring: 2, ring: 2, pendant: 2 },
};
let pricePerGram = {};  // filled by loadMetalPrices()
let pricesLoaded = false;
let quoteTimer = null;
let quoteRequestId = 0;
let productImageIndex = 0;

// ── State ──────────────────────────────────────────────────────────────────

let state = {
  category: null,   // pendant / ring / earring / bracelet / chain
  type: null,       // Product id (string)
  gold: null,       // 9k / 14k / 18k / pt950 / s925
  color: null,      // white / yellow / rose / null
  carat: null,      // 0.1 / 0.3 / 0.5 / 1.0 / 3fen / 4fen
  ringSize: null,   // integer 5–18
  engravingBand: '',
  engravingGirdle: '',
  lengthCm: null,
  includeChain: false,
  chainProductId: null,
  chainGold: null,
  chainColor: null,
  chainLength: null,
  diamondKind: 'white',
  fancyColor: null,
  stoneCount: null,
  diamondShape: 'round',
};

let shopView = 'catalog';
const CHAIN_LENGTH_OPTIONS_CM = [35, 40, 45, 50, 55, 60];
const BRACELET_LENGTH_OPTIONS_CM = [15, 16, 17, 18, 19, 20, 21];
const BRACELET_REFERENCE_LENGTH_CM = 18;

// ── Shop view ─────────────────────────────────────────────────────────────

function setShopView(view) {
  shopView = view;
  const catalogSection = document.getElementById('shop-catalog');
  const styles = document.getElementById('shop-styles');
  const product = document.getElementById('shop-product');
  if (catalogSection) catalogSection.classList.toggle('hidden', view !== 'catalog');
  if (styles) styles.classList.toggle('hidden', view !== 'styles');
  if (product) product.classList.toggle('hidden', view !== 'product');
  document.querySelector('.shop-page')?.classList.toggle('shop-view--product', view === 'product');
  updateBreadcrumb();
  updateCtaState(null);
  updateShopProgress();
}

const SHOP_STEPS = {
  catalog: { step: 1, progress: 8 },
  styles: { step: 2, progress: 50 },
  product: { step: 3, progress: 100 },
};

function updateShopProgress() {
  const meta = SHOP_STEPS[shopView] || SHOP_STEPS.catalog;
  const fill = document.getElementById('shop-progress-fill');
  if (fill) fill.style.width = `${meta.progress}%`;
  document.querySelectorAll('.shop-progress-dot').forEach((dot, i) => {
    dot.classList.toggle('is-active', i === meta.step - 1);
    dot.classList.toggle('is-done', i < meta.step - 1);
  });
}

function updateBreadcrumb() {
  const el = document.getElementById('shop-breadcrumb');
  if (!el) return;
  const ol = document.createElement('ol');
  ol.className = 'shop-breadcrumb-list';

  const addLink = (label, onClick) => {
    const li = document.createElement('li');
    const btn = document.createElement('button');
    btn.type = 'button';
    btn.className = 'shop-breadcrumb-link';
    btn.textContent = label;
    btn.addEventListener('click', onClick);
    li.appendChild(btn);
    ol.appendChild(li);
  };

  const addCurrent = (label) => {
    const li = document.createElement('li');
    li.className = 'is-current';
    li.textContent = label;
    ol.appendChild(li);
  };

  if (shopView === 'catalog') {
    addCurrent(tr('shop_breadcrumb_shop'));
  } else {
    addLink(tr('shop_breadcrumb_shop'), () => {
      document.getElementById('back-to-catalog')?.click();
    });
    if (shopView === 'styles' && state.category) {
      addCurrent(tr('cat_' + state.category));
    } else if (shopView === 'product') {
      if (state.category) {
        addLink(tr('cat_' + state.category), () => {
          document.getElementById('back-to-styles')?.click();
        });
      }
      const product = getSelectedProduct();
      addCurrent(product ? productName(product) : tr('shop_breadcrumb_shop'));
    }
  }

  el.innerHTML = '';
  el.appendChild(ol);
}

function updateProductHeader() {
  const title = document.getElementById('product-title');
  const subtitle = document.getElementById('product-subtitle');
  const description = document.getElementById('product-description');
  if (!title) return;
  const product = getSelectedProduct();
  if (product) {
    title.textContent = productName(product);
    if (subtitle) {
      let sub = tr('cat_' + state.category);
      const badge = stoneCountBadgeText();
      if (badge) sub = `${sub} · ${badge}`;
      subtitle.textContent = sub;
    }
    if (description) {
      const desc = shopLang() === 'en'
        ? (product.descriptionEn || product.descriptionZh || '')
        : (product.descriptionZh || product.descriptionEn || '');
      description.textContent = desc || tr('shop_no_description');
      description.hidden = false;
    }
  } else {
    title.textContent = '—';
    if (subtitle) subtitle.textContent = '';
    if (description) {
      description.textContent = tr('shop_no_description');
      description.hidden = false;
    }
  }
}

function initProductTabs() {
  const nav = document.querySelector('.product-tab-nav');
  if (!nav) return;
  nav.querySelectorAll('.product-tab-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      const tab = btn.dataset.tab;
      nav.querySelectorAll('.product-tab-btn').forEach(b => {
        const active = b.dataset.tab === tab;
        b.classList.toggle('active', active);
        b.setAttribute('aria-selected', active ? 'true' : 'false');
      });
      document.querySelectorAll('.product-tab-panel').forEach(panel => {
        const show = panel.id === `product-panel-${tab}`;
        panel.classList.toggle('active', show);
        panel.hidden = !show;
      });
    });
  });
}

function updateConfigChips() {
  const container = document.getElementById('config-chips');
  if (!container) return;
  container.innerHTML = '';
  const chips = [];
  if (state.carat) {
    chips.push(
      state.carat === '3fen' ? tr('chain_3fen')
        : state.carat === '4fen' ? tr('chain_4fen')
          : state.carat + ' ct'
    );
  }
  if (state.gold) chips.push(materialLabel(state.gold, state.color));
  if (state.category !== 'chain') {
    const colorId = selectedDiamondColorId();
    const colorMeta = diamondColorOptions().find(c => c.id === colorId);
    if (colorMeta) chips.push(diamondMetaLabel(colorMeta));
    const stoneBadge = stoneCountBadgeText();
    if (stoneBadge) chips.push(stoneBadge);
  }
  if (state.category !== 'chain' && state.diamondShape && state.diamondShape !== 'round') {
    const shape = diamondOptions.shapes.find(s => s.id === state.diamondShape);
    if (shape) chips.push(shopLang() === 'en' ? shape.labelEn : shape.labelZh);
  }
  if (state.ringSize) chips.push('#' + state.ringSize);
  if (state.engravingBand) chips.push(`${tr('step_engraving_band')}: ${state.engravingBand}`);
  if (state.engravingGirdle) chips.push(`${tr('step_engraving_girdle')}: ${state.engravingGirdle}`);
  chips.forEach(text => {
    const span = document.createElement('span');
    span.className = 'config-chip';
    span.textContent = text;
    container.appendChild(span);
  });
}

function effectiveColor() {
  if (state.color) return state.color;
  const product = getSelectedProduct();
  if (state.category === 'chain' && state.gold) {
    return product?.defaultColor || materialColor(state.gold);
  }
  if (product) return product.defaultColor || 'white';
  return null;
}

function isReadyToSubmit() {
  if (!state.category || !state.type || !state.gold || !state.carat) return false;
  const product = getSelectedProduct();
  if (state.gold && needsColorSelection(state.gold, product) && !state.color) return false;
  if (state.category === 'ring' && !state.ringSize) return false;
  if (state.category === 'chain' && !state.lengthCm) return false;
  if (state.category === 'bracelet' && !state.lengthCm) return false;
  if (state.category !== 'chain' && state.diamondKind === 'fancy' && !state.fancyColor) return false;
  if (state.category === 'pendant' && state.includeChain
    && (!state.chainProductId || !state.chainGold || !state.chainColor || !state.chainLength)) return false;
  if (state.category === 'chain' && state.gold === '9k') {
    const product = getSelectedProduct();
    if (product && product.defaultColor !== 'white') return false;
  }
  return true;
}

function updateCtaState(total) {
  const ready = isReadyToSubmit() && total != null;

  const confirmBtns = [document.getElementById('confirm-btn'), document.getElementById('confirm-btn-mobile')];
  const cartBtns = [document.getElementById('cart-btn'), document.getElementById('cart-btn-mobile')];
  ['share-config-btn', 'quote-sheet-btn', 'favorite-btn'].forEach(id => {
    const button = document.getElementById(id);
    if (button) button.disabled = !ready;
  });

  if (isGuestShop) {
    confirmBtns.forEach(btn => {
      if (!btn) return;
      btn.hidden = false;
      btn.disabled = !ready;
      btn.textContent = tr('shop_guest_login');
    });
    cartBtns.forEach(btn => { if (btn) btn.hidden = false; });
  } else if (window.cartEditData) {
    cartBtns.forEach(btn => {
      if (!btn) return;
      btn.hidden = true;
      btn.disabled = true;
    });
    confirmBtns.forEach(btn => {
      if (!btn) return;
      btn.hidden = false;
      btn.disabled = !ready;
      btn.textContent = btn.id === 'confirm-btn-mobile' ? tr('cart_update_short') : tr('cart_update');
    });
  } else {
    confirmBtns.forEach(btn => {
      if (!btn) return;
      btn.hidden = false;
      btn.disabled = !ready;
      if (window.editData) {
        btn.textContent = tr('btn_update');
      } else {
        btn.textContent = tr('btn_add_order');
      }
    });
    cartBtns.forEach(btn => {
      if (!btn) return;
      btn.hidden = false;
      btn.disabled = !ready || !!window.editData;
      btn.textContent = btn.id === 'cart-btn-mobile' ? tr('btn_add_cart_short') : tr('btn_add_cart');
    });
  }

  const hint = document.getElementById('price-hint');
  if (hint) {
    hint.hidden = ready && total != null;
    if (!ready || total == null) hint.textContent = tr('shop_complete_options');
  }
  const bar = document.getElementById('mobile-buy-bar');
  const showMobileBar = !!state.category;
  if (bar) bar.classList.toggle('hidden', !showMobileBar);
  document.body.classList.toggle('shop-mobile-bar', showMobileBar);
}

// ── Helpers ───────────────────────────────────────────────────────────────

/** Weight in chin (錢) for a product's metal+carat variant, or null. */
function lookupWeight(category, type, gold, carat) {
  const product = getProduct(category, type);
  const w = product?.weights?.[gold]?.[carat];
  return w == null ? null : w;
}

/** Seller-set fixed price override (TWD) for a variant, or null if the
 * price should be computed from the live formula instead. */
function lookupManualPrice(category, type, gold, carat) {
  const product = getProduct(category, type);
  const p = product?.manualPrices?.[gold]?.[carat];
  return p == null ? null : p;
}

function previewColor() {
  if (state.color) return state.color;
  const product = getSelectedProduct();
  if (product) return product.defaultColor || 'white';
  return 'white';
}

function imageUrl(category, type, color) {
  return productImageUrl(getProduct(category, type), color ?? previewColor());
}

// ── Metal price fetch ─────────────────────────────────────────────────────

async function loadMetalPrices() {
  const pricePanel = document.getElementById("shop-price-panel");
  pricePanel?.classList.add("is-loading-prices");
  try {
    const res = await fetch("/api/prices");
    if (!res.ok) throw new Error(`API ${res.status}`);
    const data = await res.json();
    Object.assign(pricePerGram, data.perGram);
    Object.assign(diamondPrice, data.diamond);
    Object.assign(laborFee, data.laborFee || {});
    if (data.chinToGrams != null) chinToGrams = data.chinToGrams;
    if (data.taxRate != null) taxRate = data.taxRate;
    if (data.ringSizeMin != null) ringSizeMin = data.ringSizeMin;
    if (data.ringSizeMax != null) ringSizeMax = data.ringSizeMax;
    ringSizeReference = data.ringSizeReference || {};
    if (data.diamondOptions) {
      diamondOptions = { ...diamondOptions, ...data.diamondOptions };
    }
    pricesLoaded = true;
    populateRingSizeSelect();
    renderRingSizeGuide();
    updateSummary();
    const initialData = window.cartEditData || window.editData || window.prefillData;
    if (initialData?.ringSize) {
      setRingSizeActive(initialData.ringSize);
    }
  } catch (err) {
    pricesLoaded = false;
    updateSummary();
  } finally {
    pricePanel?.classList.remove("is-loading-prices");
  }
}

// ── Render helpers ────────────────────────────────────────────────────────

function applyTypeGridLayout(grid, count) {
  if (!grid) return;
  ['xl', 'lg', 'md', 'sm', 'xs'].forEach(size =>
    grid.classList.remove(`type-grid--size-${size}`));
  grid.dataset.count = String(count);

  let size;
  let cols;
  if (count <= 1) {
    size = 'xl';
    cols = 1;
  } else if (count <= 3) {
    size = 'lg';
    cols = count;
  } else if (count <= 4) {
    size = 'md';
    cols = 2;
  } else if (count <= 6) {
    size = 'md';
    cols = 3;
  } else if (count <= 9) {
    size = 'sm';
    cols = 3;
  } else if (count <= 12) {
    size = 'sm';
    cols = 4;
  } else {
    size = 'xs';
    cols = null;
  }

  grid.classList.add(`type-grid--size-${size}`);
  if (cols != null) {
    grid.style.setProperty('--type-cols', String(cols));
  } else {
    grid.style.removeProperty('--type-cols');
  }
}

function estimatedProductPrice(product) {
  const manual = Object.values(product.manualPrices || {})
    .flatMap(group => Object.values(group || {}))
    .filter(value => Number.isFinite(Number(value)))
    .map(Number);
  if (manual.length) return Math.min(...manual);

  const estimates = [];
  Object.entries(product.weights || {}).forEach(([gold, byCarat]) => {
    const rate = pricePerGram[gold];
    if (!rate) return;
    Object.entries(byCarat || {}).forEach(([carat, weightChin]) => {
      const diamond = Number(diamondPrice[carat] || 0);
      const metal = Number(weightChin) * chinToGrams * rate;
      estimates.push((diamond + metal + Number(laborFee[state.category] || 0)) * (1 + taxRate));
    });
  });
  return estimates.length ? Math.min(...estimates) : null;
}

function filteredProductsForCurrentCategory() {
  const query = (document.getElementById('catalog-search-input')?.value || '').trim().toLowerCase();
  const metal = document.getElementById('catalog-metal-filter')?.value || '';
  const priceBand = document.getElementById('catalog-price-filter')?.value || '';
  return productsFor(state.category).filter(product => {
    const names = `${product.nameZh || ''} ${product.nameEn || ''}`.toLowerCase();
    if (query && !names.includes(query)) return false;
    if (metal && !(product.golds || []).includes(metal)) return false;
    if (priceBand) {
      const price = estimatedProductPrice(product);
      if (price == null) return false;
      if (priceBand === 'under30000' && price >= 30000) return false;
      if (priceBand === '30000to80000' && (price < 30000 || price > 80000)) return false;
      if (priceBand === 'over80000' && price <= 80000) return false;
    }
    return true;
  });
}

function renderTypeCards() {
  const grid = document.getElementById("type-grid");
  if (!grid) return;
  grid.innerHTML = "";
  const products = filteredProductsForCurrentCategory();
  products.forEach(product => {
    const styleId = String(product.id);
    const card = document.createElement("button");
    card.type = "button";
    card.className = "type-card";
    card.dataset.type = styleId;
    if (state.type === styleId) card.classList.add("active");

    const img = document.createElement("img");
    img.src = productImageUrl(product, product.defaultColor);
    img.alt = productName(product);
    img.loading = "lazy";

    const name = document.createElement("span");
    name.className = "type-name";
    name.textContent = productName(product);

    card.appendChild(img);
    card.appendChild(name);
    if (product.draft) {
      const badge = document.createElement("span");
      badge.className = "type-draft-badge";
      badge.textContent = "草稿預覽";
      card.appendChild(badge);
    }
    card.addEventListener("click", () => selectType(styleId));
    grid.appendChild(card);
  });
  applyTypeGridLayout(grid, products.length);
  document.getElementById('catalog-filter-empty')?.classList.toggle('hidden', products.length > 0);
}

function syncVariantChipActiveStates() {
  document.querySelectorAll('.carat-btn').forEach(b =>
    b.classList.toggle('active', b.dataset.carat === state.carat));
  document.querySelectorAll('#metal-btn-row .metal-btn').forEach(b =>
    b.classList.toggle('active', b.dataset.gold === state.gold));
  document.querySelectorAll('#color-btn-row .color-btn').forEach(b =>
    b.classList.toggle('active', b.dataset.color === state.color));
  const sel = document.getElementById('ring-size-select');
  if (sel) sel.value = state.ringSize != null ? String(state.ringSize) : '';
}

function updateMetalButtons() {
  const product = getSelectedProduct();
  renderMetalButtons('metal-btn-row', product?.golds || [], state.gold, selectMetal);
  if (state.gold && product && !product.golds.includes(state.gold)) {
    state.gold = null;
    state.color = null;
  }
  updateColorStep();
}

function enforceMetalColor(gold, color, product) {
  if (!gold) return null;
  if (!needsColorSelection(gold, product)) return materialColor(gold);
  const colors = availableColorsForGold(gold, product);
  return colors.includes(color) ? color : (colors[0] || null);
}

function updateColorStep(goldOverride) {
  const product = getSelectedProduct();
  const step = document.getElementById('color-step');
  const row = document.getElementById('color-btn-row');
  if (!step) return;
  const gold = goldOverride ?? state.gold;
  const show = gold && needsColorSelection(gold, product);
  updateColorStepLabel('color-step-label', gold);
  step.classList.toggle('hidden', !show);
  if (!show) {
    if (gold) state.color = materialColor(gold);
    if (row) row.innerHTML = '';
    return;
  }
  const preferredColor = state.color || (state.category === 'chain' ? product?.defaultColor : null);
  state.color = enforceMetalColor(gold, preferredColor, product);
  renderColorButtons('color-btn-row', gold, product, state.color, selectColor);
}

function isCaratHiddenForShop(carat) {
  const value = parseFloat(String(carat));
  const minCarat = diamondOptions.fancyMinCarat || diamondOptions.nonRoundShapeMinCarat || 0.3;
  if (Number.isNaN(value)) return false;
  if (state.diamondKind === 'fancy' && value < minCarat) return true;
  if (state.diamondShape && state.diamondShape !== 'round' && value < minCarat) return true;
  return false;
}

function updateCaratButtons() {
  const product = getSelectedProduct();
  const validCarats = product ? product.carats : [];
  document.querySelectorAll(".carat-btn").forEach(btn => {
    const v = btn.dataset.carat;
    const visible = validCarats.includes(v) && !isCaratHiddenForShop(v);
    btn.style.display = visible ? '' : 'none';
    btn.classList.toggle('active', v === state.carat);
    btn.disabled = !visible;
  });
  updateDiamondSteps();
}

function resetDiamondOptions() {
  state.diamondKind = 'white';
  state.fancyColor = null;
  state.stoneCount = null;
  state.diamondShape = 'round';
}

function diamondMetaLabel(item) {
  if (!item) return '';
  return shopLang() === 'en' ? (item.labelEn || item.labelZh) : item.labelZh;
}

function diamondAssetUrl(relativePath) {
  if (!relativePath) return '';
  return `/static/images/${relativePath}`;
}

function usesAutoStoneCount(category = state.category) {
  const cats = diamondOptions.stoneCountCategories || ['earring'];
  return cats.includes(category);
}

function defaultStoneCountForCategory(category = state.category) {
  if (category === 'earring') return 2;
  return diamondOptions.defaultStoneCountByCategory?.[category] || 2;
}

function stoneCountBadgeText() {
  if (!usesAutoStoneCount() || !state.stoneCount) return null;
  return tr('stone_count_badge').replace('{n}', String(state.stoneCount));
}

function ensureStoneCountDefault() {
  if (!usesAutoStoneCount()) {
    state.stoneCount = null;
    return;
  }
  state.stoneCount = defaultStoneCountForCategory();
}

function diamondColorOptions() {
  if (diamondOptions.diamondColors?.length) return diamondOptions.diamondColors;
  return [
    { id: 'white', kind: 'white', labelZh: '白鑽', labelEn: 'White', swatch: '#e8e8e8', image: 'diamonds/shapes/round.svg' },
    ...(diamondOptions.fancyColors || []),
  ];
}

function selectedDiamondColorId() {
  return state.diamondKind === 'white' ? 'white' : state.fancyColor;
}

function updateCarouselNav({ carouselId, prevId, nextId }) {
  const carousel = document.getElementById(carouselId);
  const prev = document.getElementById(prevId);
  const next = document.getElementById(nextId);
  if (!carousel || !prev || !next) return;

  const scrollable = carousel.scrollWidth > carousel.clientWidth + 1;
  prev.hidden = !scrollable;
  next.hidden = !scrollable;
  carousel.closest('.diamond-carousel-wrap')?.classList.toggle('diamond-carousel-wrap--no-nav', !scrollable);
}

const DIAMOND_CAROUSELS = [
  { carouselId: 'fancy-color-carousel', prevId: 'fancy-color-prev', nextId: 'fancy-color-next' },
];

function updateAllDiamondCarouselNav() {
  DIAMOND_CAROUSELS.forEach(updateCarouselNav);
}

function scheduleDiamondCarouselNavUpdate() {
  requestAnimationFrame(() => requestAnimationFrame(updateAllDiamondCarouselNav));
}

function renderDiamondColorCarousel() {
  const carousel = document.getElementById('fancy-color-carousel');
  if (!carousel) return;
  carousel.innerHTML = '';
  const activeId = selectedDiamondColorId();
  diamondColorOptions().forEach(color => {
    const btn = document.createElement('button');
    btn.type = 'button';
    btn.className = 'diamond-carousel-item fancy-color-item';
    btn.dataset.color = color.id;
    btn.classList.toggle('active', activeId === color.id);
    const icon = document.createElement('span');
    icon.className = 'gem-icon';
    if (color.image) {
      const img = document.createElement('img');
      img.src = diamondAssetUrl(color.image);
      img.alt = diamondMetaLabel(color);
      img.loading = 'lazy';
      icon.appendChild(img);
    } else {
      icon.style.background = color.swatch || '#eee';
    }
    const label = document.createElement('span');
    label.className = 'gem-label';
    label.textContent = diamondMetaLabel(color);
    btn.appendChild(icon);
    btn.appendChild(label);
    btn.addEventListener('click', () => selectDiamondColor(color.id));
    carousel.appendChild(btn);
  });
  scheduleDiamondCarouselNavUpdate();
}


function scrollCarousel(carouselId, direction) {
  const el = document.getElementById(carouselId);
  if (!el) return;
  el.scrollBy({ left: direction * 120, behavior: 'smooth' });
}

function updateDiamondSteps() {
  const isChain = state.category === 'chain';
  const fancyStep = document.getElementById('fancy-diamond-step');
  fancyStep?.classList.toggle('hidden', isChain);
  if (isChain) {
    resetDiamondOptions();
    return;
  }
  renderDiamondColorCarousel();
  ensureStoneCountDefault();
}

function selectDiamondColor(colorId) {
  const meta = diamondColorOptions().find(c => c.id === colorId);
  if (!meta) return;
  if (meta.kind === 'white' || colorId === 'white') {
    state.diamondKind = 'white';
    state.fancyColor = null;
  } else {
    state.diamondKind = 'fancy';
    state.fancyColor = colorId;
    if (state.carat && isCaratHiddenForShop(state.carat)) {
      state.carat = null;
      document.querySelectorAll('.carat-btn').forEach(b => b.classList.remove('active'));
    }
  }
  ensureStoneCountDefault();
  updateDiamondSteps();
  updateCaratButtons();
  updateSummary();
}


function buildQuotePayload() {
  ensureStoneCountDefault();
  return {
    category: state.category,
    type: state.type,
    gold: state.gold,
    color: effectiveColor() || state.color,
    carat: state.carat,
    ringSize: state.ringSize,
    lengthCm: state.lengthCm,
    includeChain: state.includeChain,
    chainProductId: state.chainProductId,
    chainGold: state.chainGold,
    chainColor: state.chainColor,
    chainLength: state.chainLength,
    diamondKind: state.diamondKind,
    fancyColor: state.fancyColor,
    stoneCount: state.stoneCount,
    diamondShape: state.diamondShape,
  };
}

async function fetchQuote() {
  const id = ++quoteRequestId;
  try {
    const quoteUrl = window.shopConfig?.preview ? '/api/quote?preview=1' : '/api/quote';
    const res = await fetch(quoteUrl, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken': document.querySelector('meta[name="csrf-token"]')?.content || '',
      },
      body: JSON.stringify(buildQuotePayload()),
    });
    if (!res.ok) return null;
    const data = await res.json();
    return id === quoteRequestId ? data : null;
  } catch (err) {
    console.error('quote fetch failed', err);
    return null;
  }
}

function scheduleQuoteRefresh() {
  clearTimeout(quoteTimer);
  quoteTimer = setTimeout(() => { refreshQuotePrices(); }, 120);
}

async function refreshQuotePrices() {
  const pricePanel = document.getElementById('shop-price-panel');
  pricePanel?.classList.add('is-loading-prices');
  const quote = await fetchQuote();
  pricePanel?.classList.remove('is-loading-prices');
  const diamondRow = document.getElementById('sum-diamond-row');
  const chainRow = document.getElementById('sum-chain-row');
  const totalEl = document.getElementById('sum-total');
  const mobileTotal = document.getElementById('sum-total-mobile');
  const hint = document.getElementById('price-hint');

  if (!quote || !quote.ready) {
    if (quote && quote.error && window.showToast) {
      window.showToast(tr('price_unavailable'), 'error');
    } else if (isReadyToSubmit() && window.showToast) {
      window.showToast(tr('price_unavailable'), 'error');
    }
    if (diamondRow && state.category !== 'chain') diamondRow.style.display = state.carat ? '' : 'none';
    chainRow?.classList.add('hidden');
    document.getElementById('sum-diamond-price').textContent = state.carat ? '-' : '0';
    document.getElementById('sum-taijin-price').textContent = '-';
    document.getElementById('sum-labor-price').textContent = '-';
    if (totalEl) totalEl.textContent = '—';
    if (mobileTotal) mobileTotal.textContent = '—';
    hint?.classList.remove('hidden');
    updateCtaState(null);
    return;
  }

  if (quote.manualOverride) {
    if (diamondRow) diamondRow.style.display = 'none';
    chainRow?.classList.add('hidden');
    document.getElementById('sum-taijin-price').textContent = '—';
    document.getElementById('sum-labor-price').textContent = '—';
  } else {
    if (diamondRow) diamondRow.style.display = state.category === 'chain' ? 'none' : '';
    if (quote.diamondPrice != null) {
      document.getElementById('sum-diamond-price').textContent = Math.round(quote.diamondPrice).toLocaleString();
    }
    if (quote.taijinPrice != null) {
      document.getElementById('sum-taijin-price').textContent = Math.round(quote.taijinPrice).toLocaleString();
    }
    if (quote.laborPrice != null) {
      document.getElementById('sum-labor-price').textContent = Math.round(quote.laborPrice).toLocaleString();
    }
    const showChain = state.category === 'pendant' && state.includeChain && quote.chainPrice != null;
    chainRow?.classList.toggle('hidden', !showChain);
    if (showChain) {
      document.getElementById('sum-chain-price').textContent = Math.round(quote.chainPrice).toLocaleString();
    }
  }

  const total = quote.total;
  if (total != null && window.animateCountUp) {
    if (totalEl) window.animateCountUp(totalEl, Math.round(total));
    if (mobileTotal) window.animateCountUp(mobileTotal, Math.round(total));
  } else {
    const totalStr = total != null ? Math.round(total).toLocaleString() : '—';
    if (totalEl) totalEl.textContent = totalStr;
    if (mobileTotal) mobileTotal.textContent = totalStr;
  }
  hint?.classList.toggle('hidden', total != null);
  updateCtaState(total);
}

function updateRingSizeStep() {
  const step = document.getElementById("ringsize-step");
  const guideStep = document.getElementById("ringsize-guide-step");
  if (state.category === 'ring') {
    step.classList.remove("hidden");
    if (guideStep) guideStep.classList.remove("hidden");
  } else {
    step.classList.add("hidden");
    if (guideStep) guideStep.classList.add("hidden");
    state.ringSize = null;
  }
}

function updateEngravingSteps() {
  const bandStep = document.getElementById('engraving-band-step');
  const girdleStep = document.getElementById('engraving-girdle-step');
  const hasBand = state.category === 'ring';
  const hasGirdle = state.category !== 'chain';
  bandStep?.classList.toggle('hidden', !hasBand);
  girdleStep?.classList.toggle('hidden', !hasGirdle);
  if (!hasBand) state.engravingBand = '';
  if (!hasGirdle) state.engravingGirdle = '';
  const bandInput = document.getElementById('engraving-band-input');
  const girdleInput = document.getElementById('engraving-girdle-input');
  if (bandInput) bandInput.value = state.engravingBand;
  if (girdleInput) girdleInput.value = state.engravingGirdle;
}

function renderLengthButtons(containerId, options, selected, onSelect) {
  const row = document.getElementById(containerId);
  if (!row) return;
  row.innerHTML = '';
  row.classList.add('variant-chips--grid');
  options.forEach(length => {
    const btn = document.createElement('button');
    btn.type = 'button';
    btn.className = 'variant-chip';
    btn.textContent = `${length} cm`;
    btn.classList.toggle('active', selected === length);
    btn.addEventListener('click', () => onSelect(length));
    row.appendChild(btn);
  });
}

function updateLengthStep() {
  const step = document.getElementById('chain-length-step');
  const row = document.getElementById('chain-length-btn-row');
  const label = step?.querySelector('.variant-label');
  const isChain = state.category === 'chain';
  const isBracelet = state.category === 'bracelet';
  const show = isChain || isBracelet;
  step?.classList.toggle('hidden', !show);
  if (label) {
    const key = isBracelet ? 'step_bracelet_length' : 'step_chain_length';
    label.setAttribute('data-i18n', key);
    label.textContent = tr(key);
  }
  const guideBtn = document.getElementById('chain-length-guide-open');
  if (guideBtn) guideBtn.style.display = show ? '' : 'none';

  if (isChain) {
    renderLengthButtons('chain-length-btn-row', CHAIN_LENGTH_OPTIONS_CM, state.lengthCm, length => {
      state.lengthCm = length;
      updateLengthStep();
      updateSummary();
    });
  } else if (isBracelet) {
    renderLengthButtons('chain-length-btn-row', BRACELET_LENGTH_OPTIONS_CM, state.lengthCm, length => {
      state.lengthCm = length;
      updateLengthStep();
      updateSummary();
    });
  } else {
    state.lengthCm = null;
    if (row) row.innerHTML = '';
  }
}

function updateChainOptions() {
  const pendantStep = document.getElementById('pendant-chain-step');
  const isPendant = state.category === 'pendant';
  updateLengthStep();
  pendantStep?.classList.toggle('hidden', !isPendant);

  if (!isPendant) {
    state.includeChain = false;
    state.chainProductId = null;
    return;
  }

  document.querySelectorAll('.pendant-chain-toggle').forEach(btn =>
    btn.classList.toggle('active', String(state.includeChain) === btn.dataset.includeChain));
  const options = document.getElementById('pendant-chain-options');
  options?.classList.toggle('hidden', !state.includeChain);
  if (!state.includeChain) return;

  const select = document.getElementById('pendant-chain-product');
  if (select) {
    select.innerHTML = '';
    productsFor('chain').forEach(product => {
      const option = document.createElement('option');
      option.value = String(product.id);
      option.textContent = productName(product);
      select.appendChild(option);
    });
    if (!state.chainProductId) state.chainProductId = select.value || null;
    select.value = String(state.chainProductId || '');
  }
  const chainProduct = getProduct('chain', state.chainProductId);
  if (!state.chainGold && chainProduct?.golds?.length) {
    state.chainGold = sortGolds(chainProduct.golds)[0];
    state.chainColor = enforceMetalColor(state.chainGold, null, chainProduct);
  }
  renderMetalButtons('pendant-chain-metal-row', chainProduct?.golds || [], state.chainGold, gold => {
    state.chainGold = gold;
    state.chainColor = enforceMetalColor(gold, state.chainColor, chainProduct);
    updateChainOptions();
    updateSummary();
  });

  const chainColorStep = document.getElementById('pendant-chain-color-step');
  const chainColorRow = document.getElementById('pendant-chain-color-row');
  const showChainColor = state.chainGold && needsColorSelection(state.chainGold, chainProduct);
  chainColorStep?.classList.toggle('hidden', !showChainColor);
  updateColorStepLabel('pendant-chain-color-label', state.chainGold);
  if (!showChainColor) {
    if (state.chainGold) state.chainColor = materialColor(state.chainGold);
    if (chainColorRow) chainColorRow.innerHTML = '';
  } else {
    state.chainColor = enforceMetalColor(state.chainGold, state.chainColor, chainProduct);
    renderColorButtons('pendant-chain-color-row', state.chainGold, chainProduct, state.chainColor, color => {
      const colors = availableColorsForGold(state.chainGold, chainProduct);
      if (!colors.includes(color)) return;
      state.chainColor = color;
      document.querySelectorAll('#pendant-chain-color-row .color-btn').forEach(b =>
        b.classList.toggle('active', b.dataset.color === color));
      updateSummary();
    });
  }
  if (!state.chainLength) {
    state.chainLength = CHAIN_LENGTH_OPTIONS_CM[0];
  }
  renderLengthButtons('pendant-chain-length-row', CHAIN_LENGTH_OPTIONS_CM, state.chainLength, length => {
    state.chainLength = length;
    updateChainOptions();
    updateSummary();
  });
}

function currentProductImages() {
  const product = getSelectedProduct();
  if (!product) return [];
  return productImagesForColor(product, previewColor());
}

function renderProductThumbnails(images) {
  const row = document.getElementById('product-image-thumbs');
  if (!row) return;
  row.innerHTML = '';
  if (images.length <= 1) {
    row.hidden = true;
    return;
  }
  row.hidden = false;
  images.forEach((url, index) => {
    const btn = document.createElement('button');
    btn.type = 'button';
    btn.className = 'product-thumb-btn' + (index === productImageIndex ? ' active' : '');
    btn.setAttribute('aria-label', `Image ${index + 1}`);
    const thumb = document.createElement('img');
    thumb.src = url;
    thumb.alt = '';
    btn.appendChild(thumb);
    btn.addEventListener('click', () => {
      productImageIndex = index;
      updateLargeImage();
    });
    row.appendChild(btn);
  });
}

function updateGalleryNav(images) {
  const scrollable = images.length > 1;
  const prevBtn = document.getElementById('product-gallery-prev');
  const nextBtn = document.getElementById('product-gallery-next');
  const counter = document.getElementById('product-gallery-counter');
  if (prevBtn) {
    prevBtn.hidden = !scrollable;
    prevBtn.disabled = !scrollable;
  }
  if (nextBtn) {
    nextBtn.hidden = !scrollable;
    nextBtn.disabled = !scrollable;
  }
  if (counter) {
    counter.hidden = !scrollable;
    counter.textContent = scrollable ? `${productImageIndex + 1} / ${images.length}` : '';
  }
}

function stepProductImage(delta) {
  const images = currentProductImages();
  if (images.length <= 1) return;
  productImageIndex = (productImageIndex + delta + images.length) % images.length;
  updateLargeImage();
}

function updateLargeImage() {
  if (!state.category || !state.type) return;
  const images = currentProductImages();
  if (productImageIndex >= images.length) productImageIndex = 0;
  const src = images[productImageIndex] || imageUrl(state.category, state.type);
  const img = document.getElementById("large-image");
  const zoomBtn = document.getElementById("product-zoom-btn");
  if (img) img.src = src;
  if (zoomBtn) zoomBtn.hidden = !(src && !src.endsWith('/'));
  renderProductThumbnails(images);
  updateGalleryNav(images);
}

function syncLightboxImage() {
  const images = currentProductImages();
  const lbImg = document.getElementById("product-lightbox-img");
  const prevBtn = document.getElementById("product-lightbox-prev");
  const nextBtn = document.getElementById("product-lightbox-next");
  if (!lbImg) return;
  const src = images[productImageIndex] || document.getElementById("large-image")?.src || '';
  lbImg.src = src;
  lbImg.alt = document.getElementById("product-title")?.textContent || '';
  const multi = images.length > 1;
  if (prevBtn) prevBtn.hidden = !multi;
  if (nextBtn) nextBtn.hidden = !multi;
}

function openProductImageLightbox() {
  const src = document.getElementById("large-image")?.src;
  if (!src || src.endsWith('/')) return;
  const lb = document.getElementById("product-image-lightbox");
  if (!lb) return;
  syncLightboxImage();
  if (typeof lb.showModal === 'function') lb.showModal();
}

function initProductImageLightbox() {
  document.getElementById("product-zoom-btn")?.addEventListener("click", openProductImageLightbox);
  document.getElementById("large-image")?.addEventListener("click", openProductImageLightbox);
  document.getElementById("product-gallery-prev")?.addEventListener("click", (e) => {
    e.stopPropagation();
    stepProductImage(-1);
  });
  document.getElementById("product-gallery-next")?.addEventListener("click", (e) => {
    e.stopPropagation();
    stepProductImage(1);
  });
  document.getElementById("product-lightbox-close")?.addEventListener("click", () => {
    document.getElementById("product-image-lightbox")?.close();
  });
  document.getElementById("product-lightbox-prev")?.addEventListener("click", () => {
    stepProductImage(-1);
    syncLightboxImage();
  });
  document.getElementById("product-lightbox-next")?.addEventListener("click", () => {
    stepProductImage(1);
    syncLightboxImage();
  });
  document.getElementById("product-image-lightbox")?.addEventListener("click", e => {
    if (e.target.id === 'product-image-lightbox') {
      e.target.close();
    }
  });
}

// ── Summary update ────────────────────────────────────────────────────────

function updateSummary() {
  // Category
  document.getElementById("sum-cat").textContent =
    state.category ? tr('cat_' + state.category) : '-';

  // Style
  const selectedProduct = getSelectedProduct();
  document.getElementById("sum-type").textContent =
    selectedProduct ? productName(selectedProduct) : '-';

  document.getElementById("sum-material").textContent =
    state.gold ? materialLabel(state.gold, state.color) : '-';

  // Carat / chain weight
  const caratBase = state.carat
    ? (state.carat === '3fen' ? tr('chain_3fen')
      : state.carat === '4fen' ? tr('chain_4fen')
      : state.carat + 'ct')
    : '-';
  const badge = stoneCountBadgeText();
  const caratDisplay = badge && state.carat && state.carat !== '3fen' && state.carat !== '4fen'
    ? `${caratBase} ${badge}`
    : caratBase;
  document.getElementById("sum-carat").textContent = caratDisplay;

  // Weight lookup (from the selected product's own variant data)
  const baseChin = (state.category && state.type && state.gold && state.carat)
    ? lookupWeight(state.category, state.type, state.gold, state.carat)
    : null;
  const chin = baseChin !== null && state.category === 'chain' && state.lengthCm
    ? baseChin * (state.lengthCm / 45)
    : baseChin !== null && state.category === 'bracelet' && state.lengthCm
      ? baseChin * (state.lengthCm / BRACELET_REFERENCE_LENGTH_CM)
      : baseChin;

  scheduleQuoteRefresh();

  updateCtaState(null);
  updateBreadcrumb();
  updateConfigChips();
  updateProductHeader();
}

function clearRingSizeSelection() {
  state.ringSize = null;
  state.engravingBand = '';
  state.engravingGirdle = '';
  state.lengthCm = null;
  state.includeChain = false;
  state.chainProductId = null;
  state.chainGold = null;
  state.chainColor = null;
  state.chainLength = null;
  resetDiamondOptions();
  const sel = document.getElementById('ring-size-select');
  if (sel) sel.value = '';
}

function selectRingSize(size) {
  const parsed = size != null && size !== '' ? parseFloat(size) : null;
  state.ringSize = parsed;
  const sel = document.getElementById('ring-size-select');
  if (sel) sel.value = parsed != null ? String(parsed) : '';
  updateSummary();
}

function setRingSizeActive(size) {
  selectRingSize(size);
}

function populateRingSizeSelect() {
  const sel = document.getElementById('ring-size-select');
  if (!sel) return;
  const current = state.ringSize;
  const placeholder = tr('ring_size_placeholder');
  sel.innerHTML = '';
  const ph = document.createElement('option');
  ph.value = '';
  ph.textContent = placeholder;
  sel.appendChild(ph);
  for (let s = ringSizeMin; s <= ringSizeMax; s += 1) {
    const opt = document.createElement('option');
    opt.value = String(s);
    opt.textContent = tr('ring_size_option') + s;
    sel.appendChild(opt);
  }
  if (current != null) sel.value = String(current);
}

function renderRingSizeGuide() {
  const body = document.getElementById('ring-size-guide-body');
  if (!body) return;
  body.innerHTML = '';
  for (let size = ringSizeMin; size <= ringSizeMax; size += 1) {
    const ref = ringSizeReference[String(size)] || ringSizeReference[size] || {};
    const row = document.createElement('tr');
    const values = [
      `#${size}`,
      ref.diameter_cm != null ? `${Number(ref.diameter_cm).toFixed(2)} cm` : '—',
      ref.circumference_cm != null ? `${Number(ref.circumference_cm).toFixed(2)} cm` : '—',
      ref.jp != null ? `#${ref.jp}` : '—',
      ref.us != null ? `#${ref.us}` : '—',
      ref.eu != null ? `#${ref.eu}` : '—',
    ];
    values.forEach(value => {
      const cell = document.createElement('td');
      cell.textContent = value;
      row.appendChild(cell);
    });
    body.appendChild(row);
  }
}

// ── Selection handlers ────────────────────────────────────────────────────

function selectCategory(cat) {
  state.category = cat;
  state.type = null;
  state.gold = null;
  state.color = null;
  state.carat = null;
  state.ringSize = null;
  state.engravingBand = '';
  state.engravingGirdle = '';
  state.lengthCm = null;
  state.includeChain = false;
  state.chainProductId = null;
  state.chainGold = null;
  state.chainColor = null;
  state.chainLength = null;

  document.querySelectorAll(".cat-btn").forEach(b =>
    b.classList.toggle("active", b.dataset.cat === cat));

  renderTypeCards();
  const titleEl = document.getElementById("shop-category-title");
  if (titleEl) titleEl.textContent = tr('cat_' + cat);

  document.querySelectorAll(".carat-btn, #metal-btn-row .metal-btn, #color-btn-row .color-btn").forEach(b => b.classList.remove("active"));
  clearRingSizeSelection();
  updateMetalButtons();
  updateCaratButtons();
  updateChainOptions();
  setShopView('styles');
  updateSummary();
}

function selectType(typeId) {
  state.type = typeId;
  state.carat = null;
  state.gold = null;
  const product = getSelectedProduct();
  state.color = null;
  state.ringSize = null;
  state.engravingBand = '';
  state.engravingGirdle = '';
  resetDiamondOptions();

  document.querySelectorAll(".type-card").forEach(c =>
    c.classList.toggle("active", c.dataset.type === typeId));

  updateCaratButtons();
  updateMetalButtons();
  document.querySelectorAll(".carat-btn, #metal-btn-row .metal-btn, #color-btn-row .color-btn").forEach(b => b.classList.remove("active"));
  clearRingSizeSelection();

  productImageIndex = 0;
  updateLargeImage();
  updateRingSizeStep();
  updateEngravingSteps();
  updateDiamondSteps();
  updateChainOptions();
  setShopView('product');
  updateSummary();
}

function selectMetal(gold) {
  const product = getSelectedProduct();
  if (product && gold && !product.golds.includes(gold)) return;
  state.gold = gold;
  state.color = enforceMetalColor(gold, state.color, product);
  renderMetalButtons('metal-btn-row', product?.golds || [], gold, selectMetal);
  updateColorStep(gold);
  updateRingSizeStep();
  updateEngravingSteps();
  updateDiamondSteps();
  updateChainOptions();
  updateLargeImage();
  updateSummary();
}

function selectColor(color) {
  const product = getSelectedProduct();
  if (!needsColorSelection(state.gold, product)) return;
  const colors = availableColorsForGold(state.gold, product);
  if (!colors.includes(color)) return;
  state.color = color;
  document.querySelectorAll('#color-btn-row .color-btn').forEach(b =>
    b.classList.toggle('active', b.dataset.color === color));
  productImageIndex = 0;
  updateRingSizeStep();
  updateEngravingSteps();
  updateDiamondSteps();
  updateChainOptions();
  updateLargeImage();
  updateSummary();
}

function selectCarat(carat) {
  state.carat = carat;

  document.querySelectorAll(".carat-btn").forEach(b =>
    b.classList.toggle("active", b.dataset.carat === carat));

  updateMetalButtons();
  updateRingSizeStep();
  updateEngravingSteps();
  updateDiamondSteps();
  updateChainOptions();
  syncVariantChipActiveStates();
  updateLargeImage();
  updateSummary();
}

// ── Event wiring ──────────────────────────────────────────────────────────

document.querySelectorAll(".carat-btn").forEach(btn =>
  btn.addEventListener("click", () => selectCarat(btn.dataset.carat)));

document.getElementById('ring-size-select')?.addEventListener('change', (e) =>
  selectRingSize(e.target.value));

document.getElementById('engraving-band-input')?.addEventListener('input', (e) => {
  state.engravingBand = e.target.value;
  updateSummary();
});
document.getElementById('engraving-girdle-input')?.addEventListener('input', (e) => {
  const cleaned = e.target.value.replace(/[^A-Za-z0-9]/g, '').slice(0, 10);
  if (e.target.value !== cleaned) e.target.value = cleaned;
  state.engravingGirdle = cleaned;
  updateSummary();
});
document.querySelectorAll('.pendant-chain-toggle').forEach(btn =>
  btn.addEventListener('click', () => {
    state.includeChain = btn.dataset.includeChain === 'true';
    if (state.includeChain && !state.chainLength) {
      state.chainLength = CHAIN_LENGTH_OPTIONS_CM[0];
    }
    updateChainOptions();
    updateSummary();
  }));

document.getElementById('fancy-color-prev')?.addEventListener('click', () => scrollCarousel('fancy-color-carousel', -1));
document.getElementById('fancy-color-next')?.addEventListener('click', () => scrollCarousel('fancy-color-carousel', 1));
window.addEventListener('resize', scheduleDiamondCarouselNavUpdate, { passive: true });
document.getElementById('pendant-chain-product')?.addEventListener('change', (e) => {
  state.chainProductId = e.target.value;
  state.chainGold = null;
  state.chainColor = null;
  state.chainLength = null;
  updateChainOptions();
  updateSummary();
});

const ringSizeGuideDialog = document.getElementById('ring-size-guide-dialog');
document.getElementById('ring-size-guide-open')?.addEventListener('click', () =>
  ringSizeGuideDialog?.showModal());
document.getElementById('ring-size-guide-close')?.addEventListener('click', () =>
  ringSizeGuideDialog?.close());

const chainLengthGuideDialog = document.getElementById('chain-length-guide-dialog');
function openChainLengthGuide(mode) {
  const isBracelet = mode === 'bracelet' || (mode !== 'necklace' && state.category === 'bracelet');
  document.getElementById('chain-length-guide-necklace')?.classList.toggle('hidden', isBracelet);
  document.getElementById('chain-length-guide-bracelet')?.classList.toggle('hidden', !isBracelet);
  const title = chainLengthGuideDialog?.querySelector('h2');
  if (title) {
    const key = isBracelet ? 'bracelet_length_guide_title' : 'chain_length_guide_title';
    title.setAttribute('data-i18n', key);
    title.textContent = tr(key);
  }
  const intro = chainLengthGuideDialog?.querySelector('.ring-size-guide-header p');
  if (intro) {
    const key = isBracelet ? 'bracelet_length_guide_intro' : 'chain_length_guide_intro';
    intro.setAttribute('data-i18n', key);
    intro.textContent = tr(key);
  }
  chainLengthGuideDialog?.showModal();
}
document.getElementById('chain-length-guide-open')?.addEventListener('click', () => openChainLengthGuide());
document.getElementById('pendant-chain-length-guide-open')?.addEventListener('click', () => openChainLengthGuide('necklace'));
document.getElementById('chain-length-guide-close')?.addEventListener('click', () =>
  chainLengthGuideDialog?.close());

document.getElementById('back-to-catalog')?.addEventListener('click', () => {
  state.category = null;
  state.type = null;
  state.gold = null;
  state.color = null;
  state.carat = null;
  state.ringSize = null;
  state.engravingBand = '';
  state.engravingGirdle = '';
  state.lengthCm = null;
  state.includeChain = false;
  state.chainProductId = null;
  state.chainGold = null;
  state.chainColor = null;
  state.chainLength = null;
  document.querySelectorAll('.cat-btn, .carat-btn, #metal-btn-row .metal-btn, #color-btn-row .color-btn').forEach(b => b.classList.remove('active'));
  clearRingSizeSelection();
  updateChainOptions();
  setShopView('catalog');
  updateSummary();
});

document.getElementById('back-to-styles')?.addEventListener('click', () => {
  if (!state.category) return;
  setShopView('styles');
  renderTypeCards();
  updateSummary();
});

// ── Submit / Update ───────────────────────────────────────────────────────

function buildSubmitPayload() {
  ensureStoneCountDefault();
  const submitColor = effectiveColor();
  return {
    category: state.category,
    type:     state.type,
    gold:     state.gold,
    color:    submitColor || state.color,
    carat:    state.carat,
    ringSize: state.ringSize,
    engravingBand: state.engravingBand,
    engravingGirdle: state.engravingGirdle,
    lengthCm: state.lengthCm,
    includeChain: state.includeChain,
    chainProductId: state.chainProductId,
    chainGold: state.chainGold,
    chainColor: state.chainColor,
    chainLength: state.chainLength,
    diamondKind: state.diamondKind,
    fancyColor: state.fancyColor,
    stoneCount: state.stoneCount,
    diamondShape: state.diamondShape,
  };
}

function encodeConfigToken(payload) {
  const bytes = new TextEncoder().encode(JSON.stringify(payload));
  let binary = '';
  bytes.forEach(byte => { binary += String.fromCharCode(byte); });
  return btoa(binary).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
}

function openQuoteSheet() {
  const token = encodeConfigToken(buildSubmitPayload());
  const base = window.shopConfig?.quoteSheetUrl || '/quote-sheet';
  window.open(`${base}?config=${encodeURIComponent(token)}`, '_blank', 'noopener');
}

function openShareSummary() {
  const token = encodeConfigToken(buildSubmitPayload());
  const template = window.shopConfig?.shareBaseUrl || '/s/TOKEN';
  window.open(template.replace('TOKEN', encodeURIComponent(token)), '_blank', 'noopener');
}

async function addCurrentFavorite() {
  const button = document.getElementById('favorite-btn');
  if (!button) return;
  button.disabled = true;
  try {
    const response = await fetch('/api/favorites/add', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken': document.querySelector('meta[name="csrf-token"]').content,
      },
      body: JSON.stringify(buildSubmitPayload()),
    });
    if (response.status === 401) {
      redirectGuestToLogin();
      return;
    }
    const data = await response.json();
    if (!response.ok || !data.success) throw new Error(data.message || 'favorite failed');
    button.textContent = '♥';
    button.classList.add('is-saved');
    const toast = window.showToast || alert;
    toast(tr('favorite_added'), 'success');
  } catch (error) {
    console.error(error);
    (window.showToast || alert)(tr('generic_error'), 'error');
  } finally {
    button.disabled = false;
  }
}

function validateBeforeSubmit(toast) {
  if (!state.category) { toast(tr('alert_pick_category')); return false; }
  if (!state.type)     { toast(tr('alert_pick_type'));     return false; }
  if (!state.gold)     { toast(tr('alert_pick_gold'));     return false; }

  const submitColor = effectiveColor();
  if (!submitColor) {
    const product = getSelectedProduct();
    toast(needsColorSelection(state.gold, product) ? tr('alert_pick_color') : tr('alert_pick_material'));
    return false;
  }

  if (!state.carat) { toast(tr('alert_pick_carat')); return false; }

  if (state.category === 'ring' && !state.ringSize) {
    toast(tr('alert_pick_ring_size')); return false;
  }

  if (state.category === 'chain' && !state.lengthCm) {
    toast(tr('alert_pick_chain_length')); return false;
  }

  if (state.category === 'bracelet' && !state.lengthCm) {
    toast(tr('alert_pick_bracelet_length')); return false;
  }

  if (state.category !== 'chain' && state.diamondKind === 'fancy' && !state.fancyColor) {
    toast(tr('step_diamond_color')); return false;
  }

  if (state.category === 'pendant' && state.includeChain
    && (!state.chainProductId || !state.chainGold || !state.chainColor || !state.chainLength)) {
    toast(tr('alert_pick_chain_length')); return false;
  }

  if (state.category === 'chain' && state.gold === '9k') {
    const product = getSelectedProduct();
    if (product && product.defaultColor !== 'white') {
      toast(tr('alert_chain_9k_white_only')); return false;
    }
  }
  return true;
}

async function handleAddToCart() {
  if (window.cartEditData) {
    return handleCartUpdate();
  }

  const toast = (msg, type) => window.showToast ? window.showToast(msg, type || 'error') : alert(msg);
  if (window.shopConfig?.preview) {
    toast(tr('cart_preview_blocked'));
    return;
  }
  if (!validateBeforeSubmit(toast)) return;
  if (isGuestShop) {
    redirectGuestToLogin();
    return;
  }
  if (!getCsrfToken()) {
    toast(tr('csrf_reload'));
    return;
  }

  const btns = [document.getElementById('cart-btn'), document.getElementById('cart-btn-mobile')];
  const originalLabels = btns.map(b => b?.textContent);
  btns.forEach(b => { if (b) { b.disabled = true; b.classList.add('is-loading'); } });

  try {
    const res = await fetch('/api/cart/add', {
      method: 'POST',
      headers: shopApiHeaders(),
      body: JSON.stringify(buildSubmitPayload()),
    });
    if (res.status === 401) { window.location.href = guestLoginUrl(); return; }
    const data = await readShopApiJson(res);
    if (res.ok && data.success) {
      toast(tr('cart_added'), 'success');
      if (typeof window.updateCartBadge === 'function') window.updateCartBadge(data.count);
    } else {
      const msg = shopApiErrorMessage(data, res);
      if (msg.includes('session expired') || msg.includes('CSRF')) {
        toast(tr('csrf_reload'));
      } else {
        toast(tr('save_failed') + msg);
      }
    }
  } catch (err) {
    console.error(err);
    toast(tr('generic_error'));
  } finally {
    btns.forEach((b, i) => {
      if (b) {
        b.disabled = false;
        b.textContent = originalLabels[i];
        b.classList.remove('is-loading');
      }
    });
    updateSummary();
  }
}

async function handleCartUpdate() {
  const toast = (msg, type) => window.showToast ? window.showToast(msg, type || 'error') : alert(msg);
  if (!validateBeforeSubmit(toast)) return;

  const btns = [document.getElementById('confirm-btn'), document.getElementById('confirm-btn-mobile')];
  const originalLabels = btns.map(b => b?.textContent);
  btns.forEach(b => { if (b) { b.disabled = true; b.classList.add('is-loading'); } });

  try {
    const res = await fetch('/api/cart/' + window.cartEditData.id, {
      method: 'PUT',
      headers: shopApiHeaders(),
      body: JSON.stringify(buildSubmitPayload()),
    });
    if (res.status === 401) { window.location.href = guestLoginUrl(); return; }
    const data = await readShopApiJson(res);
    if (res.ok && data.success) {
      toast(tr('cart_updated'), 'success');
      if (typeof window.updateCartBadge === 'function') window.updateCartBadge(data.count);
      window.location.href = window.shopConfig?.cartUrl || '/cart';
    } else {
      toast(tr('save_failed') + shopApiErrorMessage(data, res));
    }
  } catch (err) {
    console.error(err);
    toast(tr('generic_error'));
  } finally {
    btns.forEach((b, i) => {
      if (b) {
        b.disabled = false;
        b.textContent = originalLabels[i];
        b.classList.remove('is-loading');
      }
    });
    updateSummary();
  }
}

async function handleSubmit() {
  if (window.cartEditData) {
    return handleCartUpdate();
  }

  const toast = (msg) => window.showToast ? window.showToast(msg, 'error') : alert(msg);
  if (!validateBeforeSubmit(toast)) return;
  if (isGuestShop) {
    redirectGuestToLogin();
    return;
  }

  const btns = [document.getElementById("confirm-btn"), document.getElementById("confirm-btn-mobile")];
  const originalLabels = btns.map(b => b?.textContent);
  btns.forEach(b => { if (b) { b.disabled = true; b.textContent = tr('btn_submitting'); b.classList.add('is-loading'); } });
  const resetButtons = () => btns.forEach((b, i) => {
    if (b) { b.disabled = false; b.textContent = originalLabels[i]; b.classList.remove('is-loading'); }
  });

  const payload = buildSubmitPayload();

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
      resetButtons();
      toast(tr('save_failed') + (result.message || ""));
    }
  } catch (err) {
    console.error(err);
    resetButtons();
    toast(tr('generic_error'));
  } finally {
    updateSummary();
  }
}

document.getElementById("confirm-btn")?.addEventListener("click", handleSubmit);
document.getElementById("confirm-btn-mobile")?.addEventListener("click", handleSubmit);
document.getElementById("cart-btn")?.addEventListener("click", handleAddToCart);
document.getElementById("cart-btn-mobile")?.addEventListener("click", handleAddToCart);
document.getElementById("quote-sheet-btn")?.addEventListener("click", openQuoteSheet);
document.getElementById("share-config-btn")?.addEventListener("click", openShareSummary);
document.getElementById("favorite-btn")?.addEventListener("click", addCurrentFavorite);

(function setupMobilePricePanel() {
  const details = document.getElementById('price-breakdown-details');
  const toggle = document.getElementById('mobile-price-toggle');
  const panel = document.getElementById('shop-price-panel');

  function isMobileShop() {
    return window.matchMedia('(max-width: 900px)').matches;
  }

  function syncDetailsOpen() {
    if (!details) return;
    if (!isMobileShop()) {
      details.open = true;
      panel?.classList.remove('is-mobile-open');
      return;
    }
    if (!details.dataset.userOpened) details.open = false;
  }

  syncDetailsOpen();
  window.addEventListener('resize', syncDetailsOpen);

  toggle?.addEventListener('click', () => {
    if (!panel || !details) return;
    const willOpen = !panel.classList.contains('is-mobile-open');
    panel.classList.toggle('is-mobile-open', willOpen);
    details.dataset.userOpened = '1';
    details.open = willOpen;
    toggle.setAttribute('aria-expanded', willOpen ? 'true' : 'false');
    if (willOpen) {
      panel.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    }
  });
})();

['catalog-search-input', 'catalog-metal-filter', 'catalog-price-filter'].forEach(id => {
  const element = document.getElementById(id);
  element?.addEventListener(element.tagName === 'INPUT' ? 'input' : 'change', renderTypeCards);
});
function clearCatalogFilters() {
  const search = document.getElementById('catalog-search-input');
  const metal = document.getElementById('catalog-metal-filter');
  const price = document.getElementById('catalog-price-filter');
  if (search) search.value = '';
  if (metal) metal.value = '';
  if (price) price.value = '';
  renderTypeCards();
}
document.getElementById('catalog-filter-clear')?.addEventListener('click', clearCatalogFilters);
document.getElementById('catalog-filter-empty-clear')?.addEventListener('click', clearCatalogFilters);

document.addEventListener('langchange', () => {
  populateRingSizeSelect();
  updateMetalButtons();
  updateColorStep();
  updateChainOptions();
  renderCatalogTiles();
  const titleEl = document.getElementById("shop-category-title");
  if (titleEl && state.category) titleEl.textContent = tr('cat_' + state.category);
  updateSummary();
  if (state.category) renderTypeCards();
  if (shopView === 'product') updateLargeImage();
  updateShopProgress();
});

// ── Bootstrap: load the catalog first (type cards/images depend on it),
//    then wire up the initial view + optional deep-link/edit-mode restore. ─

async function init() {
  await loadCatalog();
  initProductImageLightbox();
  initProductTabs();

  setShopView('catalog');
  populateRingSizeSelect();
  loadMetalPrices();

  const urlCategory = new URLSearchParams(window.location.search).get('category');
  if (urlCategory && productsFor(urlCategory).length && !window.editData && !window.cartEditData && !window.prefillData) {
    requestAnimationFrame(() => {
      document.querySelector(`.cat-btn[data-cat="${urlCategory}"]`)?.click();
    });
  }

  const previewProduct = new URLSearchParams(window.location.search).get('product');
  if (window.shopConfig?.preview && previewProduct && urlCategory) {
    setTimeout(() => {
      document.querySelector(`.type-card[data-type="${previewProduct}"]`)?.click();
    }, 50);
  }

  const prefillData = window.cartEditData || window.editData || window.prefillData;
  if (prefillData) {
    const catBtn = document.querySelector(`.cat-btn[data-cat="${prefillData.category}"]`);
    if (catBtn) { catBtn.click(); }

    // Delay subsequent steps so DOM updates cascade
    // Order: category → type → carat → metal → color → ringSize
    setTimeout(() => {
      const card = document.querySelector(`.type-card[data-type="${prefillData.type}"]`);
      if (card) { card.click(); }

      setTimeout(() => {
        const caratBtn = document.querySelector(`.carat-btn[data-carat="${prefillData.carat}"]`);
        if (caratBtn) { caratBtn.click(); }

        setTimeout(() => {
          selectMetal(prefillData.gold);
          if (prefillData.color && needsColorSelection(prefillData.gold, getSelectedProduct())) {
            selectColor(prefillData.color);
          }

          setTimeout(() => {
            if (prefillData.ringSize) {
              setTimeout(() => setRingSizeActive(prefillData.ringSize), 50);
            }
            state.engravingBand = prefillData.engravingBand || '';
            state.engravingGirdle = prefillData.engravingGirdle || '';
            state.lengthCm = prefillData.lengthCm || null;
            state.includeChain = !!prefillData.includeChain;
            state.chainProductId = prefillData.chainProductId || null;
            state.chainGold = prefillData.chainGold || null;
            state.chainColor = prefillData.chainColor || null;
            state.chainLength = prefillData.chainLength || null;
            state.diamondKind = prefillData.diamondKind || 'white';
            state.fancyColor = prefillData.fancyColor || null;
            state.stoneCount = prefillData.stoneCount || null;
            ensureStoneCountDefault();
            state.diamondShape = prefillData.diamondShape || 'round';
            updateDiamondSteps();
            updateEngravingSteps();
            updateChainOptions();
            updateSummary();
          }, 50);
        }, 50);
      }, 50);
    }, 50);
  }
}

init();
