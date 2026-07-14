import fs from "node:fs";
import path from "node:path";
import * as cheerio from "cheerio";

export const FALLBACK_TWD_PER_GRAM: Record<string, number> = {
  XAU: 4300,
  XPT: 1050,
  XAG: 30,
};

const CACHE_PATH =
  process.env.GOLD_CACHE_PATH ??
  path.join(process.cwd(), "data", "gold_price_cache.json");

type CachePayload = {
  prices: Record<string, number>;
  source: string;
  updatedAt: string;
};

let memoryCache: CachePayload | null = null;

function readDiskCache(): CachePayload | null {
  try {
    const raw = fs.readFileSync(CACHE_PATH, "utf8");
    return JSON.parse(raw) as CachePayload;
  } catch {
    return null;
  }
}

function writeDiskCache(payload: CachePayload) {
  try {
    fs.mkdirSync(path.dirname(CACHE_PATH), { recursive: true });
    fs.writeFileSync(CACHE_PATH, JSON.stringify(payload, null, 2));
  } catch {
    // ignore on read-only serverless FS
  }
}

function envOverride(): Record<string, number> | null {
  const xau = process.env.GOLD_XAU_PER_GRAM;
  if (!xau) return null;
  const xpt = process.env.GOLD_XPT_PER_GRAM ?? String(FALLBACK_TWD_PER_GRAM.XPT);
  const xag = process.env.GOLD_XAG_PER_GRAM ?? String(FALLBACK_TWD_PER_GRAM.XAG);
  return {
    XAU: Number(xau),
    XPT: Number(xpt),
    XAG: Number(xag),
  };
}

function parseBotRecentHtml(html: string): number | null {
  const $ = cheerio.load(html);
  const anchor = $("td, th").filter((_, el) => $(el).text().includes("黃金條塊")).first();
  if (!anchor.length) return null;
  const row = anchor.closest("tr");
  const cells = row.find("td").map((_, el) => $(el).text().replace(/,/g, "").trim()).get();
  for (const text of cells) {
    const n = Number.parseFloat(text);
    if (Number.isFinite(n) && n > 3500 && n < 5500) return n;
  }
  return null;
}

export async function fetchTaiwanBankPrices(): Promise<CachePayload> {
  const override = envOverride();
  if (override) {
    const payload = {
      prices: override,
      source: "env_override",
      updatedAt: new Date().toISOString(),
    };
    memoryCache = payload;
    writeDiskCache(payload);
    return payload;
  }

  if (process.env.DISABLE_BOT_SCRAPER === "1") {
    const cached = memoryCache ?? readDiskCache();
    if (cached) return cached;
    const payload = {
      prices: { ...FALLBACK_TWD_PER_GRAM },
      source: "fallback",
      updatedAt: new Date().toISOString(),
    };
    memoryCache = payload;
    return payload;
  }

  try {
    const res = await fetch("https://rate.bot.com.tw/gold/quote/recent", {
      headers: {
        "User-Agent":
          "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
        "Accept-Language": "zh-TW,zh;q=0.9,en;q=0.8",
      },
      next: { revalidate: 0 },
    });
    const html = await res.text();
    const xau = parseBotRecentHtml(html);
    const prices = {
      XAU: xau ?? memoryCache?.prices.XAU ?? readDiskCache()?.prices.XAU ?? FALLBACK_TWD_PER_GRAM.XAU,
      XPT: memoryCache?.prices.XPT ?? readDiskCache()?.prices.XPT ?? FALLBACK_TWD_PER_GRAM.XPT,
      XAG: memoryCache?.prices.XAG ?? readDiskCache()?.prices.XAG ?? FALLBACK_TWD_PER_GRAM.XAG,
    };
    const payload = {
      prices,
      source: xau ? "bot_scrape" : "cache_fallback",
      updatedAt: new Date().toISOString(),
    };
    memoryCache = payload;
    writeDiskCache(payload);
    return payload;
  } catch {
    const cached = memoryCache ?? readDiskCache();
    if (cached) return cached;
    return {
      prices: { ...FALLBACK_TWD_PER_GRAM },
      source: "fallback",
      updatedAt: new Date().toISOString(),
    };
  }
}

export function getCachedMetalPrices(): [Record<string, number>, string] {
  const override = envOverride();
  if (override) return [override, "env_override"];
  const cached = memoryCache ?? readDiskCache();
  if (cached) return [cached.prices, cached.source];
  return [{ ...FALLBACK_TWD_PER_GRAM }, "fallback"];
}

export function getBotGoldDisplay() {
  const [prices, source] = getCachedMetalPrices();
  const sellPerGram = prices.XAU;
  const sellPerChin = sellPerGram * 3.75;
  return {
    available: sellPerGram > 0,
    sell: sellPerChin / 3.75,
    sellPerChin,
    sellPerGram,
    source,
    updatedAt: memoryCache?.updatedAt ?? readDiskCache()?.updatedAt ?? null,
  };
}

// Warm cache on cold start in Node runtime
void fetchTaiwanBankPrices();
