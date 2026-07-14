import { NextResponse } from "next/server";
import { prisma } from "@/lib/db";
import { getSessionUser } from "@/lib/auth";
import { validateSubmissionFields } from "@/lib/validation";
import {
  applyPricingToSubmissionFields,
  computeOrderPricing,
} from "@/lib/order-pricing";

export async function POST(request: Request) {
  const user = await getSessionUser();
  if (!user) return NextResponse.json({ status: "error", message: "login required" }, { status: 401 });

  const data = await request.json().catch(() => null);
  if (!data) return NextResponse.json({ status: "error", message: "invalid JSON" }, { status: 400 });

  const { cleaned, error } = validateSubmissionFields(data);
  if (error) return NextResponse.json({ status: "error", message: error }, { status: 400 });

  const pricing = await computeOrderPricing(cleaned, { partial: false });
  if (!pricing.ready) {
    return NextResponse.json(
      { status: "error", message: pricing.error ?? "pricing error" },
      { status: 400 },
    );
  }

  const fields = applyPricingToSubmissionFields(cleaned, pricing);

  try {
    const submission = await prisma.submission.create({
      data: {
        userId: user.id,
        productId: fields.productId,
        category: cleaned.category!,
        carat: cleaned.carat!,
        styleType: cleaned.type!,
        goldPurity: cleaned.gold!,
        color: cleaned.color ?? null,
        diamondKind: cleaned.diamondKind ?? "white",
        fancyColor: cleaned.fancyColor ?? null,
        stoneCount: cleaned.stoneCount ?? null,
        diamondShape: cleaned.diamondShape ?? "round",
        weight: fields.weight ?? null,
        ringSize: cleaned.ringSize ?? null,
        engravingBand: cleaned.engravingBand ?? null,
        engravingGirdle: cleaned.engravingGirdle ?? null,
        includeChain: cleaned.includeChain ?? false,
        chainProductId: fields.chainProductId,
        chainGold: cleaned.chainGold ?? null,
        chainColor: cleaned.chainColor ?? null,
        chainLengthCm:
          cleaned.category === "chain" || cleaned.category === "bracelet"
            ? cleaned.lengthCm ?? null
            : cleaned.includeChain
              ? cleaned.chainLength ?? null
              : null,
        chainWeightChin: fields.chainWeightChin ?? null,
        chainTotalTwd: fields.chainTotalTwd ?? null,
        diamondPriceTwd: fields.diamondPriceTwd ?? null,
        taijinPriceTwd: fields.taijinPriceTwd ?? null,
        laborPriceTwd: fields.laborPriceTwd ?? null,
        taxAmountTwd: fields.taxAmountTwd ?? null,
        totalPrice: fields.totalPrice ?? null,
        goldRatePerGram: fields.goldRatePerGram ?? null,
        priceSource: fields.priceSource ?? null,
        status: "pending",
      },
    });

    return NextResponse.json({
      status: "success",
      message: "Selection confirmed and saved.",
      total_price: submission.totalPrice,
    });
  } catch {
    return NextResponse.json({ status: "error", message: "save failed" }, { status: 400 });
  }
}
