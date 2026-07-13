"""Fetch and cache Taiwan Bank (BOT) precious-metal prices.

Pricing uses **黃金條塊** (gold bar) 「本行賣出」 from the BOT gold quote
page, converted to TWD per gram (preferring the 1 kg column).

For cloud deploys without a headless browser, set ``GOLD_XAU_PER_GRAM`` in
``.env`` (and optionally ``DISABLE_BOT_SCRAPER=1``). Playwright is optional.
"""

from __future__ import annotations

import json
import logging
import os
import re
import threading
import time
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

from bs4 import BeautifulSoup

log = logging.getLogger(__name__)

# Last-resort constant, only used if we have *never* successfully scraped a
# price, not even in a previous run (i.e. PERSIST_PATH doesn't exist either).
FALLBACK_TWD_PER_GRAM = {"XAU": 4300, "XPT": 1050, "XAG": 30}

PERSIST_PATH = Path(__file__).resolve().parent.parent.parent / "instance" / "gold_price_cache.json"

BOT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "zh-TW,zh;q=0.9,en;q=0.8",
}

BOT_LIVE_URL = "https://rate.bot.com.tw/gold?Lang=zh-TW"
BOT_RECENT_URL = "https://rate.bot.com.tw/gold/quote/recent"
BOT_PUBLIC_URL = BOT_RECENT_URL

GOLD_BAR_ANCHOR = "黃金條塊"

# Map BOT table column headers to weight in grams.
_WEIGHT_HEADER_PATTERNS = (
    (re.compile(r"1\s*公斤"), 1000),
    (re.compile(r"500\s*公克"), 500),
    (re.compile(r"250\s*公克"), 250),
    (re.compile(r"100\s*公克"), 100),
)

# Per-gram price derived from bar totals (typically ~4,000–5,000 TWD/g).
BAR_DERIVED_GRAM_MIN = 3500
BAR_DERIVED_GRAM_MAX = 5500

CHALLENGE_MAX_WAIT_SECONDS = 75
CHALLENGE_POLL_INTERVAL_SECONDS = 5
MIN_REFRESH_INTERVAL_SECONDS = 60


def _env_gold_price() -> float | None:
    """Optional manual gold price (TWD/gram) for servers without Playwright."""
    raw = (os.environ.get('GOLD_XAU_PER_GRAM') or '').strip()
    if not raw:
        return None
    try:
        value = float(raw)
    except ValueError:
        log.warning('GOLD_XAU_PER_GRAM is not a number: %r', raw)
        return None
    if value <= 0:
        return None
    return value


def _bot_scraper_enabled() -> bool:
    if os.environ.get('DISABLE_BOT_SCRAPER', '').strip().lower() in ('1', 'true', 'yes'):
        return False
    return True


def _is_bot_stamp(value) -> bool:
    """True when value looks like a BOT 掛牌時間, not a source label."""
    if not value:
        return False
    return bool(re.search(r'\d{4}/\d{2}/\d{2}', str(value)))


def _manual_price_cache(manual: float) -> dict:
    return {
        'prices': {
            'XAU': manual,
            'XPT': FALLBACK_TWD_PER_GRAM['XPT'],
            'XAG': FALLBACK_TWD_PER_GRAM['XAG'],
        },
        'fetched_at': time.time(),
        'source': 'manual',
        'bot_posted_at': None,
        'bank_sell': manual,
        'price_kind': 'gold_bar',
    }


def _load_persisted_cache():
    try:
        with open(PERSIST_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        prices = data.get("prices")
        if not prices or not prices.get("XAU"):
            return None
        return data
    except (OSError, ValueError, TypeError):
        return None


def _persist_cache(prices, bot_posted_at, bank_sell, fetched_at):
    try:
        PERSIST_PATH.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = PERSIST_PATH.with_suffix(".tmp")
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump({
                "prices": prices,
                "bot_posted_at": bot_posted_at,
                "last_updated": bot_posted_at,
                "bank_sell": bank_sell,
                "price_kind": "gold_bar",
                "fetched_at": fetched_at,
            }, f)
        tmp_path.replace(PERSIST_PATH)
    except OSError as exc:
        log.warning("Could not persist gold price cache to %s: %s", PERSIST_PATH, exc)


def _cache_from_persisted(persisted: dict) -> dict:
    bot_posted_at = persisted.get("bot_posted_at") or persisted.get("last_updated")
    return {
        "prices": persisted["prices"],
        "fetched_at": persisted.get("fetched_at", 0),
        "source": "cached",
        "bot_posted_at": bot_posted_at if _is_bot_stamp(bot_posted_at) else None,
        "bank_sell": persisted.get("bank_sell"),
        "price_kind": persisted.get("price_kind", "gold_bar"),
    }


def _has_bot_price_data(cache: dict | None = None) -> bool:
    data = cache or _price_cache
    if not data.get("prices"):
        return False
    if data.get("source") in ("bot", "cached"):
        return True
    return _is_bot_stamp(data.get("bot_posted_at"))


def _initial_price_cache():
    persisted = _load_persisted_cache()
    if persisted:
        bot_posted_at = persisted.get("bot_posted_at") or persisted.get("last_updated")
        if _is_bot_stamp(bot_posted_at):
            return _cache_from_persisted(persisted)

    manual = _env_gold_price()
    if manual is not None and (not _bot_scraper_enabled() or not persisted):
        return _manual_price_cache(manual)

    if persisted:
        return _cache_from_persisted(persisted)

    return {
        "prices": None,
        "fetched_at": 0,
        "source": "fallback",
        "bot_posted_at": None,
        "bank_sell": None,
        "price_kind": "gold_bar",
    }


_price_cache = _initial_price_cache()
_fetch_lock = threading.Lock()


def _parse_twd_amount(text):
    cleaned = re.sub(r"[^\d,.]", "", (text or "").strip())
    if not cleaned:
        return None
    try:
        return float(cleaned.replace(",", ""))
    except ValueError:
        return None


def _cell_amount(td):
    if td is None:
        return None
    for node in td.strings:
        amount = _parse_twd_amount(node)
        if amount is not None:
            return amount
    return _parse_twd_amount(td.get_text(" ", strip=True))


def _grams_from_header_text(text):
    normalized = re.sub(r"\s+", "", text or "")
    for pattern, grams in _WEIGHT_HEADER_PATTERNS:
        if pattern.search(text or "") or pattern.search(normalized):
            return grams
    return None


def _is_bar_derived_gram_price(amount):
    return amount is not None and BAR_DERIVED_GRAM_MIN <= amount <= BAR_DERIVED_GRAM_MAX


def _parse_bot_datetime(stamp):
    if not stamp:
        return None
    m = re.search(r"(\d{4})/(\d{2})/(\d{2})\s+(\d{2}):(\d{2})", stamp)
    if not m:
        return None
    return tuple(int(part) for part in m.groups())


def _extract_page_stamp(soup):
    text = soup.get_text(" ", strip=True)
    for pattern in (
        r"掛牌時間[：:]\s*(\d{4}/\d{2}/\d{2}\s+\d{2}:\d{2})",
        r"牌價時間[：:]\s*(\d{4}/\d{2}/\d{2}\s+\d{2}:\d{2})",
    ):
        match = re.search(pattern, text)
        if match:
            return match.group(1).strip()

    time_span = soup.find("span", class_="time")
    if time_span:
        match = re.search(
            r"(\d{4}/\d{2}/\d{2}\s+\d{2}:\d{2})",
            time_span.get_text(" ", strip=True),
        )
        if match:
            return match.group(1)

    time_cell = soup.find("td", {"data-table": "牌價時間"})
    if time_cell:
        match = re.search(
            r"(\d{4}/\d{2}/\d{2}\s+\d{2}:\d{2})",
            time_cell.get_text(" ", strip=True),
        )
        if match:
            return match.group(1)
    return None


def _extract_stamp_from_row(row):
    time_cell = row.find("td", {"data-table": re.compile("牌價時間")})
    if time_cell:
        match = re.search(
            r"(\d{4}/\d{2}/\d{2}\s+\d{2}:\d{2})",
            time_cell.get_text(" ", strip=True),
        )
        if match:
            return match.group(1)
    match = re.search(r"(\d{4}/\d{2}/\d{2}\s+\d{2}:\d{2})", row.get_text(" ", strip=True))
    return match.group(1) if match else None


def _weight_columns_from_table(table):
    """Return {cell_index: grams} from the first row that lists bar weights."""
    for row in table.find_all("tr"):
        cols = {}
        for idx, cell in enumerate(row.find_all(["td", "th"])):
            grams = _grams_from_header_text(cell.get_text(" ", strip=True))
            if grams:
                cols[idx] = grams
        if cols:
            return cols
    return {}


def _per_gram_from_bar_sell_row(row, weight_cols):
    """Convert bar total prices in a 本行賣出 row to TWD/gram."""
    cells = row.find_all(["td", "th"])
    candidates = []
    for idx, grams in weight_cols.items():
        if idx >= len(cells):
            continue
        amount = _cell_amount(cells[idx])
        if amount is None or amount < 10_000:
            continue
        per_gram = amount / grams
        if _is_bar_derived_gram_price(per_gram):
            candidates.append((per_gram, grams))
    if not candidates:
        return None
    candidates.sort(key=lambda item: item[1], reverse=True)
    return candidates[0][0]


def _is_gold_bar_table(table):
    summary = table.get("summary") or table.get("title") or ""
    if "黃金條塊" in summary:
        return True
    for td in table.find_all("td"):
        if td.get_text(strip=True) == GOLD_BAR_ANCHOR:
            return True
    return False


def _find_gold_bar_anchor(soup):
    for td in soup.find_all("td"):
        if td.get_text(strip=True) == GOLD_BAR_ANCHOR:
            return td
    return None


def _quotes_from_live_gold_bar_block(soup, page_stamp):
    anchor = _find_gold_bar_anchor(soup)
    if anchor is None:
        return []

    table = anchor.find_parent("table")
    if table is None:
        return []

    weight_cols = _weight_columns_from_table(table)
    if not weight_cols:
        return []

    anchor_row = anchor.find_parent("tr")
    quotes = []
    started = anchor_row is None
    for row in table.find_all("tr"):
        if row is anchor_row:
            started = True
            continue
        if not started:
            continue

        row_text = row.get_text(" ", strip=True)
        if "轉換" in row_text:
            continue
        if "本行賣出" not in row_text and row.find("td", {"data-table": "本行賣出"}) is None:
            continue

        per_gram = _per_gram_from_bar_sell_row(row, weight_cols)
        if per_gram is not None:
            quotes.append((per_gram, page_stamp or _extract_page_stamp(soup)))
            break

    return quotes


def _quotes_from_history_tables(soup):
    quotes = []
    for table in soup.find_all("table"):
        summary = table.get("summary") or table.get("title") or ""
        if not _is_gold_bar_table(table):
            continue
        if "黃金存摺" in summary and "黃金條塊" not in summary:
            continue

        weight_cols = _weight_columns_from_table(table)
        if not weight_cols:
            continue

        for row in table.find_all("tr"):
            row_text = row.get_text(" ", strip=True)
            if "轉換" in row_text:
                continue

            stamp = _extract_stamp_from_row(row)
            per_gram = _per_gram_from_bar_sell_row(row, weight_cols)
            if per_gram is None:
                continue

            if "本行賣出" in row_text or stamp:
                quotes.append((per_gram, stamp))

    return quotes


def _pick_latest_quote(quotes):
    best = None
    best_key = None
    for sell, stamp in quotes:
        if sell is None:
            continue
        key = _parse_bot_datetime(stamp) or (0, 0, 0, 0, 0)
        if best is None or key >= best_key:
            best = (sell, stamp)
            best_key = key
    return best


def _find_gold_bar_prices(soup):
    page_stamp = _extract_page_stamp(soup)
    quotes = []
    quotes.extend(_quotes_from_live_gold_bar_block(soup, page_stamp))
    quotes.extend(_quotes_from_history_tables(soup))

    if not quotes:
        return None, None

    sell, stamp = _pick_latest_quote(quotes)
    if sell is None:
        return None, None

    if not stamp:
        stamp = page_stamp
    return sell, stamp


# Backward-compatible alias for tests / older imports.
_find_passbook_prices = _find_gold_bar_prices


def _is_bot_challenge(html):
    if len(html) < 10000:
        return True
    lowered = html.lower()
    return "challenge validation" in lowered or "<title>challenge" in lowered


def _wait_out_challenge(page, max_wait=CHALLENGE_MAX_WAIT_SECONDS,
                         poll=CHALLENGE_POLL_INTERVAL_SECONDS):
    waited = 0
    html = page.content()
    while _is_bot_challenge(html) and waited < max_wait:
        time.sleep(poll)
        waited += poll
        html = page.content()
    return html


def _fetch_via_http(url: str) -> str | None:
    """Lightweight fetch — works when BOT does not serve a bot challenge."""
    req = urllib.request.Request(url, headers=BOT_HEADERS)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.read().decode('utf-8', errors='replace')
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        log.debug('HTTP fetch failed for %s: %s', url, exc)
        return None


def _fetch_live_page_via_playwright(url: str) -> str | None:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        log.debug('playwright not installed — skipping browser fetch')
        return None

    launch_attempts = (
        {'channel': 'chrome'},
        {},
    )
    last_error = None
    for launch_kwargs in launch_attempts:
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(
                    headless=True,
                    args=['--disable-blink-features=AutomationControlled'],
                    **launch_kwargs,
                )
                try:
                    context = browser.new_context(
                        user_agent=BOT_HEADERS['User-Agent'],
                        locale='zh-TW',
                        viewport={'width': 1280, 'height': 900},
                    )
                    page = context.new_page()
                    page.add_init_script(
                        "Object.defineProperty(navigator, 'webdriver', {get: () => undefined});"
                    )
                    page.goto(url, wait_until='load', timeout=30000)
                    return _wait_out_challenge(page)
                finally:
                    browser.close()
        except Exception as exc:
            last_error = exc
            label = launch_kwargs.get('channel', 'bundled')
            log.debug('Playwright (%s) failed for %s: %s', label, url, exc)
    if last_error:
        log.warning('Playwright unavailable (%s); use GOLD_XAU_PER_GRAM or install playwright', last_error)
    return None


def _fetch_page_html(url: str) -> str | None:
    html = _fetch_via_http(url)
    if html and not _is_bot_challenge(html):
        return html
    if not _bot_scraper_enabled():
        return None
    return _fetch_live_page_via_playwright(url)


def _download_bot_html():
    last_error = None
    for url in (BOT_LIVE_URL, BOT_RECENT_URL):
        try:
            html = _fetch_page_html(url)
            if not html:
                raise RuntimeError(f'{url}: fetch unavailable (no HTTP data / scraper disabled)')
        except Exception as exc:
            last_error = RuntimeError(f'{url}: {exc}')
            continue

        if _is_bot_challenge(html):
            last_error = RuntimeError(
                f'{url}: bot challenge did not clear within {CHALLENGE_MAX_WAIT_SECONDS}s'
            )
            continue

        sell, stamp = _find_gold_bar_prices(BeautifulSoup(html, 'html.parser'))
        if sell is None:
            last_error = RuntimeError(f'{url}: 黃金條塊 sell price not found on page')
            continue

        return html, url, sell, stamp

    raise last_error or RuntimeError('黃金條塊 sell price not found on BOT pages')


def fetch_taiwan_bank_prices():
    """Refresh BOT 黃金條塊 sell (TWD/gram). Keeps prior cache on failure."""
    global _price_cache
    with _fetch_lock:
        manual = _env_gold_price()
        if manual is not None and not _bot_scraper_enabled():
            _apply_manual_price(manual)
            return True

        age = time.time() - _price_cache.get('fetched_at', 0)
        if _price_cache.get('source') == 'bot' and age < MIN_REFRESH_INTERVAL_SECONDS:
            return True
        return _fetch_and_update_cache()


def _apply_manual_price(manual: float) -> None:
    global _price_cache
    fetched_at = time.time()
    prices = {
        'XAU': manual,
        'XPT': FALLBACK_TWD_PER_GRAM['XPT'],
        'XAG': FALLBACK_TWD_PER_GRAM['XAG'],
    }
    _price_cache.update(
        prices=prices,
        fetched_at=fetched_at,
        source='manual',
        bot_posted_at=None,
        bank_sell=manual,
        price_kind='gold_bar',
    )
    _persist_cache(prices, None, manual, fetched_at)


def _fetch_and_update_cache():
    global _price_cache
    manual = _env_gold_price()
    try:
        html, source_url, sell, stamp = _download_bot_html()

        prev = _price_cache.get("prices") or dict(FALLBACK_TWD_PER_GRAM)
        prices = {
            "XAU": sell,
            "XPT": prev.get("XPT", FALLBACK_TWD_PER_GRAM["XPT"]),
            "XAG": prev.get("XAG", FALLBACK_TWD_PER_GRAM["XAG"]),
        }
        updated = stamp or time.strftime("%Y-%m-%d %H:%M:%S")

        fetched_at = time.time()
        _price_cache.update(
            prices=prices,
            fetched_at=fetched_at,
            source="bot",
            bot_posted_at=updated,
            bank_sell=sell,
            price_kind="gold_bar",
        )
        _persist_cache(prices, updated, sell, fetched_at)
        log.info(
            "BOT gold bar price sync OK from %s: sell_per_gram=%s stamp=%s",
            source_url,
            round(sell, 2),
            updated,
        )
        return True
    except Exception as exc:
        log.warning('BOT price sync failed: %s', exc)
        if _has_bot_price_data():
            _price_cache['source'] = 'cached'
            return False
        persisted = _load_persisted_cache()
        if persisted and _is_bot_stamp(
            persisted.get('bot_posted_at') or persisted.get('last_updated')
        ):
            _price_cache.update(_cache_from_persisted(persisted))
            return False
        if manual is not None and not _bot_scraper_enabled():
            _apply_manual_price(manual)
            return True
        if manual is not None and not _price_cache.get('prices'):
            _apply_manual_price(manual)
            return True
        _price_cache.update(
            prices=dict(FALLBACK_TWD_PER_GRAM),
            fetched_at=time.time(),
            source="fallback",
            bot_posted_at=None,
            bank_sell=None,
            price_kind="gold_bar",
        )
        return False


def get_cached_metal_prices():
    """TWD per gram for XAU/XPT/XAG from in-memory cache. Never raises."""
    cached = _price_cache
    if cached["prices"]:
        return cached["prices"], cached["source"]
    prices = dict(FALLBACK_TWD_PER_GRAM)
    return prices, "fallback"


def get_price_metadata():
    bot_posted_at = _price_cache.get("bot_posted_at")
    if not bot_posted_at:
        legacy = _price_cache.get("last_updated")
        if _is_bot_stamp(legacy):
            bot_posted_at = legacy
    return {
        "bot_posted_at": bot_posted_at,
        "bank_sell": _price_cache.get("bank_sell"),
        "fetched_at": _price_cache.get("fetched_at"),
        "price_kind": _price_cache.get("price_kind", "gold_bar"),
    }


def get_bot_gold_display():
    """Summary for templates: BOT 黃金條塊 sell (TWD/gram) and cache status."""
    prices, source = get_cached_metal_prices()
    meta = get_price_metadata()
    fetched_at = meta.get("fetched_at")
    age_seconds = max(0, time.time() - fetched_at) if fetched_at else None
    fetched_at_display = None
    if fetched_at:
        fetched_at_display = (
            datetime.fromtimestamp(fetched_at, timezone.utc) + timedelta(hours=8)
        ).strftime('%Y-%m-%d %H:%M')
    sell = meta.get("bank_sell")
    if sell is None:
        sell = prices.get("XAU")
    bot_posted_at = meta.get("bot_posted_at")
    return {
        "sell": sell,
        "bot_posted_at": bot_posted_at,
        "last_updated": bot_posted_at,
        "fetched_at": fetched_at,
        "fetched_at_display": fetched_at_display,
        "age_seconds": age_seconds,
        "is_stale": (
            source == 'fallback'
            or (source == 'cached' and (
                age_seconds is None or age_seconds > 24 * 60 * 60
            ))
        ),
        "source": source,
        "source_url": BOT_PUBLIC_URL,
        "price_kind": meta.get("price_kind", "gold_bar"),
        "available": sell is not None,
    }
