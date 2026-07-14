import { NextResponse } from "next/server";
import { clearSessionUser } from "@/lib/auth";

export async function POST() {
  await clearSessionUser();
  return NextResponse.json({ success: true });
}
