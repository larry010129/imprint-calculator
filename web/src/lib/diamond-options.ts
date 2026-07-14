import { DIAMOND_PRICE } from "@/lib/pricing";

export const VALID_DIAMOND_KINDS = new Set(["white", "fancy"]);
export const VALID_FANCY_COLORS = new Set(["yellow", "pink", "blue"]);
export const VALID_DIAMOND_SHAPES = new Set(["round"]);
export const VALID_STONE_COUNTS = new Set([2, 3, 4]);
export const FANCY_MIN_CARAT = "0.3";
export const NON_ROUND_SHAPE_MIN_CARAT = "0.3";
export const NON_ROUND_SHAPE_SURCHARGE = 0.1;

export const COLORED_SINGLE_DIAMOND_PRICE: Record<string, number> = {
  "0.3": 102000,
  "0.5": 127000,
  "0.6": 147000,
  "0.7": 172000,
  "0.8": 206000,
  "0.9": 260000,
  "1.0": 325000,
  "1": 325000,
  "1.5": 494000,
  "2.0": 910000,
  "2": 910000,
  "3.0": 1287000,
  "3": 1287000,
};

export const WHITE_MULTI_DIAMOND_PRICE: Record<string, Record<number, number>> = {
  "0.1": { 2: 45600, 3: 61200, 4: 81000 },
  "0.2": { 2: 86400, 3: 122400, 4: 162000 },
  "0.3": { 2: 142200, 3: 189600, 4: 250000 },
};

export const COLORED_MULTI_DIAMOND_PRICE: Record<string, Record<number, number>> = {
  "0.3": { 2: 173400, 3: 244800, 4: 322300 },
};

export const MULTI_STONE_ABOVE_03_MULTIPLIER: Record<number, number> = {
  2: 0.85,
  3: 0.8,
  4: 0.75,
};

export const DEFAULT_STONE_COUNT_BY_CATEGORY: Record<string, number> = {
  earring: 2,
  ring: 2,
  pendant: 2,
};

export const STONE_COUNT_CATEGORIES = new Set(["earring"]);

export const DIAMOND_COLOR_META = [
  { id: "white", kind: "white", labelZh: "白鑽", labelEn: "White", swatch: "#e8e8e8", image: "diamonds/shapes/round.svg" },
  { id: "yellow", kind: "fancy", labelZh: "黃鑽", labelEn: "Yellow", swatch: "#e6c200", image: "diamonds/fancy/yellow.svg" },
  { id: "pink", kind: "fancy", labelZh: "粉鑽", labelEn: "Pink", swatch: "#f4a6c8", image: "diamonds/fancy/pink.svg" },
  { id: "blue", kind: "fancy", labelZh: "藍鑽", labelEn: "Blue", swatch: "#7ec8e3", image: "diamonds/fancy/blue.svg" },
];

function caratFloat(carat: string | undefined | null): number | null {
  if (!carat) return null;
  const v = Number.parseFloat(String(carat).replace("fen", ""));
  return Number.isFinite(v) ? v : null;
}

export function isFancyCaratAllowed(carat: string) {
  const value = caratFloat(carat);
  return value != null && value >= Number(FANCY_MIN_CARAT);
}

export function isShapeCaratAllowed(carat: string, diamondShape = "round") {
  if ((diamondShape || "round") === "round") return true;
  return isFancyCaratAllowed(carat);
}

function multiStoneTier(carat: string, table: Record<string, Record<number, number>>) {
  if (carat in table) return carat;
  const value = caratFloat(carat);
  if (value != null && value > Number(FANCY_MIN_CARAT)) return "0.3_plus";
  return null;
}

function resolveMultiPrice(
  table: Record<string, Record<number, number>>,
  tier: string,
  stoneCount: number,
) {
  if (tier === "0.3_plus") {
    const row = table["0.3"] ?? {};
    const multiplier = MULTI_STONE_ABOVE_03_MULTIPLIER[stoneCount];
    const base = row[stoneCount];
    return base != null && multiplier != null ? Math.round(base * multiplier) : null;
  }
  return table[tier]?.[stoneCount] ?? null;
}

export function computeDiamondListPrice(
  carat: string,
  opts: {
    diamondKind?: string;
    fancyColor?: string | null;
    stoneCount?: number | null;
    diamondShape?: string;
    category?: string | null;
  } = {},
): number | null {
  const {
    diamondKind = "white",
    fancyColor = null,
    stoneCount = null,
    diamondShape = "round",
    category = null,
  } = opts;

  if (!carat || category === "chain") return null;
  if (!isShapeCaratAllowed(carat, diamondShape)) return null;

  const multiStone = category != null && STONE_COUNT_CATEGORIES.has(category);
  let base: number | null = null;

  if (diamondKind === "white") {
    if (multiStone) {
      const count = stoneCount != null && VALID_STONE_COUNTS.has(stoneCount)
        ? stoneCount
        : DEFAULT_STONE_COUNT_BY_CATEGORY[category ?? ""] ?? 2;
      const tier = multiStoneTier(carat, WHITE_MULTI_DIAMOND_PRICE);
      if (!tier) return null;
      base = resolveMultiPrice(WHITE_MULTI_DIAMOND_PRICE, tier, count);
    } else {
      base = DIAMOND_PRICE[carat] ?? null;
    }
  } else if (diamondKind === "fancy") {
    if (!fancyColor || !VALID_FANCY_COLORS.has(fancyColor)) return null;
    if (!isFancyCaratAllowed(carat)) return null;
    if (multiStone) {
      const count = stoneCount != null && VALID_STONE_COUNTS.has(stoneCount)
        ? stoneCount
        : DEFAULT_STONE_COUNT_BY_CATEGORY[category ?? ""] ?? 2;
      const tier = multiStoneTier(carat, COLORED_MULTI_DIAMOND_PRICE);
      if (!tier) return null;
      base = resolveMultiPrice(COLORED_MULTI_DIAMOND_PRICE, tier, count);
    } else {
      base = COLORED_SINGLE_DIAMOND_PRICE[carat] ?? (carat === "1.0" ? COLORED_SINGLE_DIAMOND_PRICE["1"] : null);
    }
  }

  if (base == null) return null;
  if (diamondShape !== "round") return Math.round(base * (1 + NON_ROUND_SHAPE_SURCHARGE));
  return base;
}

export function diamondOptionsPayload() {
  return {
    kinds: [
      { id: "white", labelZh: "白鑽", labelEn: "White" },
      { id: "fancy", labelZh: "彩鑽", labelEn: "Fancy Color" },
    ],
    diamondColors: DIAMOND_COLOR_META,
    fancyColors: DIAMOND_COLOR_META.filter((c) => c.kind === "fancy"),
    shapes: [{ id: "round", labelZh: "圓鑽", labelEn: "Round", image: "diamonds/shapes/round.svg" }],
    stoneCounts: [...VALID_STONE_COUNTS].sort(),
    defaultStoneCountByCategory: DEFAULT_STONE_COUNT_BY_CATEGORY,
    stoneCountCategories: [...STONE_COUNT_CATEGORIES],
    fancyMinCarat: FANCY_MIN_CARAT,
    nonRoundShapeMinCarat: NON_ROUND_SHAPE_MIN_CARAT,
    nonRoundShapeSurcharge: NON_ROUND_SHAPE_SURCHARGE,
    coloredDiamondPrice: COLORED_MULTI_DIAMOND_PRICE,
    coloredSingleDiamondPrice: COLORED_SINGLE_DIAMOND_PRICE,
    whiteMultiDiamondPrice: WHITE_MULTI_DIAMOND_PRICE,
    coloredAbove03Multiplier: MULTI_STONE_ABOVE_03_MULTIPLIER,
    shapeSurcharge: {},
  };
}
