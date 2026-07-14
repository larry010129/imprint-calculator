import { computeDiamondListPrice } from "@/lib/diamond-options";
import {
  CHIN_TO_GRAMS,
  computeChainAddon,
  getMetalPrices,
  lookupWeight,
  METAL_SYMBOL,
  PURITY_MULTIPLIER,
  TAX_RATE,
  LABOR_FEE,
  getProductVariant,
} from "@/lib/pricing";
import { validateSubmissionFields, type CleanedSubmission } from "@/lib/validation";
import type { ProductVariant } from "@prisma/client";

export type OrderPricingResult = {
  ready: boolean;
  error?: string | null;
  diamondPrice?: number | null;
  taijinPreTax?: number | null;
  taijinDisplay?: number | null;
  laborPreTax?: number | null;
  laborDisplay?: number | null;
  chainDisplay?: number | null;
  chainPreTax?: number | null;
  taxAmount?: number | null;
  total?: number | null;
  manualOverride?: boolean;
  goldRatePerGram?: number | null;
  priceSource?: string | null;
  variant?: ProductVariant | null;
  chainVariant?: ProductVariant | null;
  chainWeightChin?: number | null;
  weightChin?: number | null;
  weightGrams?: number | null;
};

function metalPreTax(gold: string, weightGrams: number, category: string) {
  const [raw, source] = getMetalPrices();
  const perGram = raw[METAL_SYMBOL[gold]] * PURITY_MULTIPLIER[gold];
  const multiplier = category === "chain" ? 2 : 1;
  return { taijinPreTax: perGram * weightGrams * multiplier, perGram, source };
}

export function pricingToQuoteDict(pricing: OrderPricingResult) {
  if (!pricing.ready) {
    return pricing.error ? { ready: false, error: pricing.error } : { ready: false };
  }
  if (pricing.manualOverride) {
    return {
      ready: true,
      diamondPrice: null,
      taijinPrice: null,
      laborPrice: null,
      total: pricing.total,
      manualOverride: true,
    };
  }
  return {
    ready: true,
    diamondPrice: pricing.diamondPrice,
    taijinPrice: pricing.taijinDisplay,
    laborPrice: pricing.laborDisplay,
    chainPrice: pricing.chainDisplay,
    total: pricing.total,
    manualOverride: false,
  };
}

export async function computeOrderPricing(
  data: Record<string, unknown>,
  opts: { partial?: boolean; requirePublished?: boolean } = {},
): Promise<OrderPricingResult> {
  const { partial = false, requirePublished = true } = opts;
  const { cleaned, error } = validateSubmissionFields(data, partial);
  if (error) return { ready: false, error };

  const category = cleaned.category;
  const carat = cleaned.carat;
  const gold = cleaned.gold;
  const typeId = cleaned.type;
  if (!category || !carat || !gold || !typeId) return { ready: false };

  if ((category === "chain" || category === "bracelet") && cleaned.lengthCm == null) {
    return { ready: false };
  }

  let variant: ProductVariant;
  let weightChin: number;
  try {
    variant = await getProductVariant(category, typeId, gold, carat, requirePublished);
    weightChin = await lookupWeight(category, typeId, gold, carat, cleaned.lengthCm, requirePublished);
  } catch {
    return { ready: false, error: "product not available" };
  }

  const weightGrams = weightChin * CHIN_TO_GRAMS;
  const laborPreTax = LABOR_FEE[category] ?? 5000;

  if (variant.manualPriceTwd != null) {
    const [raw] = getMetalPrices();
    const rateUsed = raw[METAL_SYMBOL[gold]] * PURITY_MULTIPLIER[gold];
    return {
      ready: true,
      total: variant.manualPriceTwd,
      manualOverride: true,
      goldRatePerGram: rateUsed,
      priceSource: "manual_override",
      variant,
      weightChin,
      weightGrams,
    };
  }

  let taijinPreTax: number;
  let rateUsed: number;
  let source: string;
  try {
    ({ taijinPreTax, perGram: rateUsed, source } = metalPreTax(gold, weightGrams, category));
  } catch {
    return { ready: false };
  }

  const taijinDisplay = Math.round(taijinPreTax * (1 + TAX_RATE));
  const laborDisplay = Math.round(laborPreTax * (1 + TAX_RATE));
  let taxAmount = taijinDisplay - taijinPreTax + (laborDisplay - laborPreTax);

  let diamondPrice: number | null = null;
  if (category !== "chain") {
    diamondPrice = computeDiamondListPrice(carat, {
      diamondKind: cleaned.diamondKind,
      fancyColor: cleaned.fancyColor,
      stoneCount: cleaned.stoneCount,
      diamondShape: cleaned.diamondShape,
      category,
    });
    if (diamondPrice == null) return { ready: false };
  }

  let total = (diamondPrice ?? 0) + taijinDisplay + laborDisplay;
  let chainDisplay: number | null = null;
  let chainPreTax: number | null = null;
  let chainVariant: ProductVariant | null = null;
  let chainWeightChin: number | null = null;

  if (category === "pendant" && cleaned.includeChain) {
    const chainId = cleaned.chainProductId;
    const chainGold = cleaned.chainGold;
    const chainLength = cleaned.chainLength;
    if (chainId && chainGold && chainLength != null) {
      try {
        const addon = await computeChainAddon(chainId, chainGold, chainLength, requirePublished);
        chainPreTax = addon.chainPreTax;
        chainWeightChin = addon.chainChin;
        chainVariant = addon.chainVariant;
        chainDisplay = Math.round(chainPreTax * (1 + TAX_RATE));
        taxAmount += chainDisplay - chainPreTax;
        total += chainDisplay;
      } catch {
        return { ready: false, error: "invalid chain option" };
      }
    }
  }

  return {
    ready: true,
    diamondPrice,
    taijinPreTax,
    taijinDisplay,
    laborPreTax,
    laborDisplay,
    chainDisplay,
    chainPreTax,
    taxAmount: Math.round(taxAmount),
    total: Math.round(total),
    goldRatePerGram: rateUsed,
    priceSource: source,
    variant,
    chainVariant,
    chainWeightChin,
    weightChin,
    weightGrams,
  };
}

export function applyPricingToSubmissionFields(
  cleaned: CleanedSubmission,
  pricing: OrderPricingResult,
) {
  return {
    totalPrice: pricing.total,
    diamondPriceTwd: pricing.diamondPrice,
    taijinPriceTwd: pricing.taijinDisplay,
    laborPriceTwd: pricing.laborDisplay,
    taxAmountTwd: pricing.taxAmount,
    goldRatePerGram: pricing.goldRatePerGram,
    priceSource: pricing.priceSource,
    chainTotalTwd: pricing.chainDisplay ?? (cleaned.includeChain ? undefined : null),
    chainProductId: pricing.chainVariant?.productId ?? null,
    chainWeightChin:
      pricing.chainWeightChin ??
      (cleaned.category === "chain" ? pricing.weightChin : null),
    weight: pricing.weightGrams,
    productId: pricing.variant?.productId ?? null,
  };
}
