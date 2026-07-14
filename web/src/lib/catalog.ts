import { prisma } from "@/lib/db";
import { CATEGORY_DISPLAY_ORDER, sortGolds } from "@/lib/validation";

export async function buildCatalogResponse(preview = false) {
  const products = await prisma.product.findMany({
    where: preview ? {} : { isPublished: true },
    include: { variants: true, images: { orderBy: [{ sortOrder: "asc" }, { id: "asc" }] } },
    orderBy: [{ category: "asc" }, { sortOrder: "asc" }, { id: "asc" }],
  });

  const categories: Record<string, unknown[]> = {};

  for (const p of products) {
    const golds = sortGolds(new Set(p.variants.map((v) => v.gold)));
    const carats = [...new Set(p.variants.map((v) => v.carat))].sort();
    const weights: Record<string, Record<string, number>> = {};
    const manualPrices: Record<string, Record<string, number>> = {};
    for (const v of p.variants) {
      weights[v.gold] ??= {};
      weights[v.gold][v.carat] = v.weightChin;
      if (v.manualPriceTwd != null) {
        manualPrices[v.gold] ??= {};
        manualPrices[v.gold][v.carat] = v.manualPriceTwd;
      }
    }

    const imagesByColor: Record<string, string[]> = {};
    for (const img of p.images) {
      imagesByColor[img.color] ??= [];
      imagesByColor[img.color].push(`/static/${img.filePath.replace(/^\/+/, "")}`);
    }

    categories[p.category] ??= [];
    categories[p.category].push({
      id: p.id,
      nameZh: p.nameZh,
      nameEn: p.nameEn,
      descriptionZh: p.descriptionZh,
      descriptionEn: p.descriptionEn,
      defaultColor: p.defaultColor,
      golds,
      carats,
      colors: Object.keys(imagesByColor).sort(),
      images: imagesByColor,
      weights,
      manualPrices,
      draft: !p.isPublished,
    });
  }

  const categoryOrder = [
    ...CATEGORY_DISPLAY_ORDER.filter((c) => c in categories),
    ...Object.keys(categories).filter((c) => !CATEGORY_DISPLAY_ORDER.includes(c as (typeof CATEGORY_DISPLAY_ORDER)[number])),
  ];

  return { categories, categoryOrder };
}
