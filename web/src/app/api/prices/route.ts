import { NextResponse } from "next/server";
import { diamondOptionsPayload } from "@/lib/diamond-options";
import { getBotGoldDisplay, getCachedMetalPrices } from "@/lib/metal-feed";
import { METAL_SYMBOL, PURITY_MULTIPLIER } from "@/lib/pricing";

export async function GET() {
  const quote = getBotGoldDisplay();
  const [raw] = getCachedMetalPrices();
  const alloyRates = Object.fromEntries(
    (["9k", "14k", "18k"] as const).map((gold) => [
      gold,
      raw[METAL_SYMBOL[gold]] * PURITY_MULTIPLIER[gold],
    ]),
  );

  return NextResponse.json({
    botGold: quote,
    alloyRates,
    diamondOptions: diamondOptionsPayload(),
  });
}
