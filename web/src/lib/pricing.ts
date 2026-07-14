import { prisma } from "@/lib/db";
import { computeDiamondListPrice } from "@/lib/diamond-options";
import { getCachedMetalPrices } from "@/lib/metal-feed";
import type { ProductVariant } from "@prisma/client";

export const DIAMOND_PRICE: Record<string, number> = {
  "0.1": 24000,
  "0.2": 48000,
  "0.3": 79000,
  "0.5": 98000,
  "0.6": 113000,
  "0.7": 133000,
  "0.8": 159000,
  "0.9": 200000,
  "1.0": 250000,
  "1": 250000,
  "1.5": 380000,
  "2.0": 700000,
  "2": 700000,
  "3.0": 990000,
  "3": 990000,
};

export const PURITY_MULTIPLIER: Record<string, number> = {
  "9k": 0.5,
  "14k": 0.75,
  "18k": 0.85,
  pt950: 1.1,
  s925: 0.925,
};

export const METAL_SYMBOL: Record<string, string> = {
  "9k": "XAU",
  "14k": "XAU",
  "18k": "XAU",
  pt950: "XPT",
  s925: "XAG",
};

export const LABOR_FEE: Record<string, number> = {
  pendant: 5000,
  ring: 5000,
  bracelet: 5000,
  earring: 5000,
  chain: 5000,
};

export const TAX_RATE = 0.05;
export const CHIN_TO_GRAMS = 3.75;
export const CHAIN_REFERENCE_LENGTH_CM = 45;
export const BRACELET_REFERENCE_LENGTH_CM = 18;

export function getMetalPrices() {
  return getCachedMetalPrices();
}

export async function getProductVariant(
  category: string,
  styleType: string,
  gold: string,
  carat: string,
  requirePublished = true,
): Promise<ProductVariant & { product: { id: number; category: string; isPublished: boolean } }> {
  const productId = Number.parseInt(styleType, 10);
  if (!Number.isFinite(productId)) throw new Error("invalid product id");

  const variant = await prisma.productVariant.findFirst({
    where: {
      gold,
      carat,
      product: {
        id: productId,
        category,
        ...(requirePublished ? { isPublished: true } : {}),
      },
    },
    include: { product: { select: { id: true, category: true, isPublished: true } } },
  });

  if (!variant) throw new Error("no matching product variant");
  return variant;
}

export async function lookupWeight(
  category: string,
  styleType: string,
  gold: string,
  carat: string,
  lengthCm?: number | null,
  requirePublished = true,
) {
  const variant = await getProductVariant(category, styleType, gold, carat, requirePublished);
  let weight = variant.weightChin;
  if (category === "chain" && lengthCm != null) {
    weight *= lengthCm / CHAIN_REFERENCE_LENGTH_CM;
  } else if (category === "bracelet" && lengthCm != null) {
    weight *= lengthCm / BRACELET_REFERENCE_LENGTH_CM;
  }
  return weight;
}

export async function computeChainAddon(
  chainProductId: string,
  chainGold: string,
  chainLengthCm: number,
  requirePublished = true,
) {
  const chainVariant = await getProductVariant("chain", chainProductId, chainGold, "3fen", requirePublished);
  const chainChin = await lookupWeight("chain", chainProductId, chainGold, "3fen", chainLengthCm, requirePublished);
  const [chainPreTax] = await computeTotal("3fen", chainGold, chainChin * CHIN_TO_GRAMS, "chain", {
    manualPriceTwd: chainVariant.manualPriceTwd,
  });
  return { chainPreTax, chainChin, chainVariant };
}

export async function computeTotal(
  carat: string,
  gold: string,
  weightGrams: number,
  category = "ring",
  opts: {
    manualPriceTwd?: number | null;
    diamondKind?: string;
    fancyColor?: string | null;
    stoneCount?: number | null;
    diamondShape?: string;
  } = {},
): Promise<[number, number, string]> {
  const [raw, source] = getMetalPrices();
  const symbol = METAL_SYMBOL[gold];
  const perGram = raw[symbol] * PURITY_MULTIPLIER[gold];

  if (opts.manualPriceTwd != null) {
    return [opts.manualPriceTwd, perGram, "manual_override"];
  }

  const metalCost = perGram * weightGrams;
  const labor = LABOR_FEE[category] ?? 5000;

  if (category === "chain") {
    return [metalCost * 2 + labor, perGram, source];
  }

  const diamondCost =
    computeDiamondListPrice(carat, {
      diamondKind: opts.diamondKind,
      fancyColor: opts.fancyColor,
      stoneCount: opts.stoneCount,
      diamondShape: opts.diamondShape,
      category,
    }) ?? 0;

  return [diamondCost + metalCost + labor, perGram, source];
}
