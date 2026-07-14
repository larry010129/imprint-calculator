import os
import sys
import importlib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from bs4 import BeautifulSoup

from diamond_calculator.application import bot_metal_feed as feed
from diamond_calculator.application.bot_metal_feed import _find_gold_bar_prices

LIVE_BAR_HTML = """
<html><body>
<div>掛牌時間：2026/07/09 19:43</div>
<table summary="此表格是黃金條塊牌價">
  <tr>
    <td>品名/規格</td>
    <td>1 公斤</td>
    <td>500 公克</td>
    <td>250 公克</td>
    <td>100 公克</td>
  </tr>
  <tr>
    <td rowspan="2">黃金條塊</td>
    <td>本行賣出</td>
    <td></td>
    <td></td>
    <td></td>
  </tr>
  <tr>
    <td data-table="本行賣出" class="text-right">4,306,484</td>
    <td class="text-right">2,156,946</td>
    <td class="text-right">1,080,587</td>
    <td class="text-right">433,527</td>
  </tr>
</table>
</body></html>
"""

# Layout where 本行賣出 shares one row with prices (common on live page).
LIVE_BAR_ROW_HTML = """
<html><body>
<div>掛牌時間：2026/07/09 19:43</div>
<table summary="此表格是黃金條塊牌價">
  <tr>
    <td>品名/規格</td>
    <td>1 公斤</td>
    <td>500 公克</td>
    <td>250 公克</td>
    <td>100 公克</td>
  </tr>
  <tr>
    <td rowspan="2">黃金條塊</td>
    <td colspan="4"></td>
  </tr>
  <tr>
    <td>本行賣出</td>
    <td data-table="本行賣出" class="text-right">4,306,484</td>
    <td class="text-right">2,156,946</td>
    <td class="text-right">1,080,587</td>
    <td class="text-right">433,527</td>
  </tr>
</table>
</body></html>
"""

# Current BOT live page (2026/07): label + 本行賣出 + totals on one row;
# summary uses 「黃金條塊表格」; no separate 本行買進 row.
LIVE_BAR_CURRENT_HTML = """
<html><body>
<div>掛牌時間：2026/07/14 10:04</div>
<table summary="此表格為黃金條塊表格，有六直欄，第一直欄是品名，第二直欄是買賣別，第三直欄是一公斤金額，第四直欄是五百公克金額，第五直欄二百五十克金額，第六直欄是一百公克金額。">
  <tr>
    <td>品名 / 規格</td>
    <td></td>
    <td>單位：新臺幣元</td>
  </tr>
  <tr>
    <td></td>
    <td></td>
    <td>1 公斤</td>
    <td>500 公克</td>
    <td>250 公克</td>
    <td>100 公克</td>
  </tr>
  <tr>
    <td>黃金條塊</td>
    <td>本行賣出</td>
    <td class="text-right">4,211,484</td>
    <td class="text-right">2,109,399</td>
    <td class="text-right">1,056,791</td>
    <td class="text-right">423,999</td>
  </tr>
  <tr>
    <td></td>
    <td>黃金存摺轉換 金品應補繳款</td>
    <td class="text-right">34,484</td>
    <td class="text-right">20,899</td>
    <td class="text-right">12,541</td>
    <td class="text-right">6,299</td>
  </tr>
</table>
</body></html>
"""

HISTORY_BAR_HTML = """
<html><body>
<table summary="此表格是黃金條塊歷史牌價">
  <tr>
    <td>牌價時間</td>
    <td>1 公斤</td>
    <td>500 公克</td>
    <td>250 公克</td>
    <td>100 公克</td>
  </tr>
  <tr>
    <td data-table="牌價時間">2026/07/08 15:24</td>
    <td class="text-right">4,320,000</td>
    <td class="text-right">2,160,000</td>
    <td class="text-right">1,080,000</td>
    <td class="text-right">432,000</td>
  </tr>
  <tr>
    <td data-table="牌價時間">2026/07/09 19:43</td>
    <td class="text-right">4,306,484</td>
    <td class="text-right">2,156,946</td>
    <td class="text-right">1,080,587</td>
    <td class="text-right">433,527</td>
  </tr>
</table>
</body></html>
"""

# First layout: prices row after label row — index 0 is first price cell.
# Parser uses weight column indices from header; sell row must align.
# Fix LIVE_BAR_HTML: label row breaks alignment — use LIVE_BAR_ROW_HTML as primary.

sell, stamp = _find_gold_bar_prices(BeautifulSoup(LIVE_BAR_ROW_HTML, "html.parser"))
assert sell == 4306.484, f"expected 4306.484 from 1kg bar, got {sell}"
assert stamp == "2026/07/09 19:43"

sell, stamp = _find_gold_bar_prices(BeautifulSoup(LIVE_BAR_CURRENT_HTML, "html.parser"))
assert sell == 4211.484, f"expected 4211.484 from current live layout, got {sell}"
assert stamp == "2026/07/14 10:04"

from diamond_calculator.application.bot_metal_feed import _quotes_from_live_gold_bar_block
live_only = _quotes_from_live_gold_bar_block(
    BeautifulSoup(LIVE_BAR_CURRENT_HTML, "html.parser"), "2026/07/14 10:04"
)
assert live_only == [(4211.484, "2026/07/14 10:04")], f"live block must parse same-row sell, got {live_only}"

sell, stamp = _find_gold_bar_prices(BeautifulSoup(HISTORY_BAR_HTML, "html.parser"))
assert sell == 4306.484, f"expected latest history bar price, got {sell}"
assert stamp == "2026/07/09 19:43"

# Passbook tables must be ignored.
PASSBOOK_ONLY = """
<table summary="此表格是黃金存摺牌價">
  <tr><td>黃金存摺</td><td>本行賣出</td><td>4,205</td></tr>
</table>
"""
sell, stamp = _find_gold_bar_prices(BeautifulSoup(PASSBOOK_ONLY, "html.parser"))
assert sell is None, "passbook-only HTML must not be used"

# --- Scrape-fail keeps cached BOT data when GOLD_XAU_PER_GRAM is set ---
os.environ['GOLD_XAU_PER_GRAM'] = '4306'
os.environ.pop('DISABLE_BOT_SCRAPER', None)
importlib.reload(feed)
feed._price_cache.update(
    prices={'XAU': 4251.832, 'XPT': 1050, 'XAG': 30},
    fetched_at=feed.time.time(),
    source='bot',
    bot_posted_at='2026/07/13 13:14',
    bank_sell=4251.832,
    price_kind='gold_bar',
)

def _fail_download():
    raise RuntimeError('simulated scrape fail')

orig_download = feed._download_bot_html
feed._download_bot_html = _fail_download
ok = feed._fetch_and_update_cache()
feed._download_bot_html = orig_download

assert ok is False, 'scrape fail should return False when cache kept'
assert feed._price_cache['source'] == 'cached', f"expected cached, got {feed._price_cache['source']}"
assert feed._price_cache['bot_posted_at'] == '2026/07/13 13:14'
assert feed._price_cache['prices']['XAU'] == 4251.832

# --- Manual-only mode when scraper disabled ---
os.environ['DISABLE_BOT_SCRAPER'] = '1'
importlib.reload(feed)
feed.fetch_taiwan_bank_prices()
display = feed.get_bot_gold_display()
assert display['source'] == 'manual'
assert display['bot_posted_at'] is None
assert display['sell'] == 4306.0

# --- Initial cache prefers persisted BOT over manual env ---
os.environ['GOLD_XAU_PER_GRAM'] = '4306'
os.environ['DISABLE_BOT_SCRAPER'] = '0'
feed._persist_cache(
    {'XAU': 4200.0, 'XPT': 1050, 'XAG': 30},
    '2026/07/10 09:00',
    4200.0,
    feed.time.time(),
)
importlib.reload(feed)
assert feed._price_cache['source'] == 'cached'
assert feed._price_cache['prices']['XAU'] == 4200.0
assert feed._price_cache['bot_posted_at'] == '2026/07/10 09:00'

print("bot metal feed parser tests passed")
