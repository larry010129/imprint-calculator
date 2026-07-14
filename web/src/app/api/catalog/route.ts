import { NextResponse } from "next/server";
import { buildCatalogResponse } from "@/lib/catalog";
import { getSessionUser } from "@/lib/auth";

export async function GET(request: Request) {
  const url = new URL(request.url);
  const preview = url.searchParams.get("preview") === "1";
  if (preview) {
    const user = await getSessionUser();
    if (!user || user.role !== "admin") {
      return NextResponse.json({ message: "Unauthorized" }, { status: 403 });
    }
  }
  const payload = await buildCatalogResponse(preview);
  return NextResponse.json(payload);
}
