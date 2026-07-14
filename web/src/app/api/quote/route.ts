import { NextResponse } from "next/server";
import { computeOrderPricing, pricingToQuoteDict } from "@/lib/order-pricing";

export async function POST(request: Request) {
  const data = await request.json().catch(() => null);
  if (!data) return NextResponse.json({ ready: false, error: "invalid JSON" }, { status: 400 });
  const pricing = await computeOrderPricing(data, { partial: true });
  return NextResponse.json(pricingToQuoteDict(pricing));
}
