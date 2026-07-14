/**
 * One-time migration: SQLite (Flask) → Postgres (Next.js).
 *
 * Usage:
 *   DATABASE_URL=postgresql://... SQLITE_PATH=../instance/database.db npm run migrate:sqlite
 */
import Database from "better-sqlite3";
import path from "node:path";
import { PrismaClient } from "@prisma/client";

const sqlitePath =
  process.env.SQLITE_PATH ??
  path.join(process.cwd(), "..", "instance", "database.db");

const prisma = new PrismaClient();

function q<T>(db: Database.Database, sql: string): T[] {
  return db.prepare(sql).all() as T[];
}

async function main() {
  const db = new Database(sqlitePath, { readonly: true });
  console.log("Reading", sqlitePath);

  const users = q<{
    id: number;
    username: string;
    password_hash: string;
    role: string;
    store_name: string | null;
    is_active: number;
    last_login_at: string | null;
  }>(db, "SELECT * FROM user ORDER BY id");

  for (const u of users) {
    await prisma.user.upsert({
      where: { username: u.username },
      create: {
        id: u.id,
        username: u.username,
        passwordHash: u.password_hash,
        role: u.role,
        storeName: u.store_name,
        isActive: Boolean(u.is_active),
        lastLoginAt: u.last_login_at ? new Date(u.last_login_at) : null,
      },
      update: {
        passwordHash: u.password_hash,
        role: u.role,
        storeName: u.store_name,
        isActive: Boolean(u.is_active),
        lastLoginAt: u.last_login_at ? new Date(u.last_login_at) : null,
      },
    });
  }

  const products = q<Record<string, unknown>>(db, "SELECT * FROM product ORDER BY id");
  for (const p of products) {
    await prisma.product.upsert({
      where: { id: Number(p.id) },
      create: {
        id: Number(p.id),
        category: String(p.category),
        nameZh: String(p.name_zh),
        nameEn: (p.name_en as string) ?? null,
        descriptionZh: (p.description_zh as string) ?? null,
        descriptionEn: (p.description_en as string) ?? null,
        defaultColor: String(p.default_color ?? "white"),
        isPublished: Boolean(p.is_published),
        firstPublishedAt: p.first_published_at ? new Date(String(p.first_published_at)) : null,
        sortOrder: Number(p.sort_order ?? 0),
        createdById: p.created_by_id ? Number(p.created_by_id) : null,
        createdAt: p.created_at ? new Date(String(p.created_at)) : undefined,
        updatedAt: p.updated_at ? new Date(String(p.updated_at)) : undefined,
      },
      update: {
        category: String(p.category),
        nameZh: String(p.name_zh),
        nameEn: (p.name_en as string) ?? null,
        descriptionZh: (p.description_zh as string) ?? null,
        descriptionEn: (p.description_en as string) ?? null,
        defaultColor: String(p.default_color ?? "white"),
        isPublished: Boolean(p.is_published),
        sortOrder: Number(p.sort_order ?? 0),
      },
    });
  }

  const variants = q<Record<string, unknown>>(db, "SELECT * FROM product_variant ORDER BY id");
  for (const v of variants) {
    await prisma.productVariant.upsert({
      where: { id: Number(v.id) },
      create: {
        id: Number(v.id),
        productId: Number(v.product_id),
        gold: String(v.gold),
        carat: String(v.carat),
        weightChin: Number(v.weight_chin),
        manualPriceTwd: v.manual_price_twd != null ? Number(v.manual_price_twd) : null,
      },
      update: {
        gold: String(v.gold),
        carat: String(v.carat),
        weightChin: Number(v.weight_chin),
        manualPriceTwd: v.manual_price_twd != null ? Number(v.manual_price_twd) : null,
      },
    });
  }

  const images = q<Record<string, unknown>>(db, "SELECT * FROM product_image ORDER BY id");
  for (const img of images) {
    await prisma.productImage.upsert({
      where: { id: Number(img.id) },
      create: {
        id: Number(img.id),
        productId: Number(img.product_id),
        color: String(img.color),
        filePath: String(img.file_path),
        sortOrder: Number(img.sort_order ?? 0),
      },
      update: {
        color: String(img.color),
        filePath: String(img.file_path),
        sortOrder: Number(img.sort_order ?? 0),
      },
    });
  }

  const submissions = q<Record<string, unknown>>(db, "SELECT * FROM submission ORDER BY id");
  for (const s of submissions) {
    await prisma.submission.upsert({
      where: { id: Number(s.id) },
      create: {
        id: Number(s.id),
        userId: Number(s.user_id),
        productId: s.product_id != null ? Number(s.product_id) : null,
        category: (s.category as string) ?? null,
        carat: (s.carat as string) ?? null,
        styleType: (s.style_type as string) ?? null,
        goldPurity: (s.gold_purity as string) ?? null,
        color: (s.color as string) ?? null,
        diamondKind: String(s.diamond_kind ?? "white"),
        fancyColor: (s.fancy_color as string) ?? null,
        stoneCount: s.stone_count != null ? Number(s.stone_count) : null,
        diamondShape: String(s.diamond_shape ?? "round"),
        weight: s.weight != null ? Number(s.weight) : null,
        ringSize: s.ring_size != null ? Number(s.ring_size) : null,
        engravingBand: (s.engraving_band as string) ?? null,
        engravingGirdle: (s.engraving_girdle as string) ?? null,
        includeChain: Boolean(s.include_chain),
        chainProductId: s.chain_product_id != null ? Number(s.chain_product_id) : null,
        chainGold: (s.chain_gold as string) ?? null,
        chainColor: (s.chain_color as string) ?? null,
        chainLengthCm: s.chain_length_cm != null ? Number(s.chain_length_cm) : null,
        chainWeightChin: s.chain_weight_chin != null ? Number(s.chain_weight_chin) : null,
        chainTotalTwd: s.chain_total_twd != null ? Number(s.chain_total_twd) : null,
        cancelReason: (s.cancel_reason as string) ?? null,
        diamondPriceTwd: s.diamond_price_twd != null ? Number(s.diamond_price_twd) : null,
        taijinPriceTwd: s.taijin_price_twd != null ? Number(s.taijin_price_twd) : null,
        laborPriceTwd: s.labor_price_twd != null ? Number(s.labor_price_twd) : null,
        taxAmountTwd: s.tax_amount_twd != null ? Number(s.tax_amount_twd) : null,
        totalPrice: s.total_price != null ? Number(s.total_price) : null,
        goldRatePerGram: s.gold_rate_per_gram != null ? Number(s.gold_rate_per_gram) : null,
        priceSource: (s.price_source as string) ?? null,
        status: String(s.status ?? "pending"),
        createdAt: s.created_at ? new Date(String(s.created_at)) : undefined,
        updatedAt: s.updated_at ? new Date(String(s.updated_at)) : null,
      },
      update: { status: String(s.status ?? "pending") },
    });
  }

  console.log("Migrated:", {
    users: users.length,
    products: products.length,
    variants: variants.length,
    images: images.length,
    submissions: submissions.length,
  });
}

main()
  .catch((err) => {
    console.error(err);
    process.exit(1);
  })
  .finally(async () => {
    await prisma.$disconnect();
  });
