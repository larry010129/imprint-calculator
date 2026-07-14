"""Admin dashboard aggregates and CSV export helpers."""

import csv
import io
import re
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta, timezone

from diamond_calculator.application.order_search import STATUS_LABELS_ZH
from diamond_calculator.filters import submission_summary
from diamond_calculator.repository.models import Submission

COMPLETE_STATUSES = {'completed', 'shipped'}
GRANULARITIES = ('day', 'week', 'month')
MAX_DAY_SPAN = 90
DAY_TREND_DEFAULT = 30
WEEK_TREND_COUNT = 12
MONTH_TREND_COUNT = 12

STATUS_PIE_COLORS = (
    '#1aa8ad',
    '#26c4c9',
    '#4db8bc',
    '#8eedf0',
    '#6d6a64',
    '#c45c5c',
)

PIE_CIRCUMFERENCE = 2 * 3.14159265 * 40
_WEEK_RE = re.compile(r'^(\d{4})-W(\d{2})$')


def _now_local():
    return datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(hours=8)


def _taipei(dt):
    return dt + timedelta(hours=8) if dt else None


def _month_key(dt):
    local = _taipei(dt)
    return local.strftime('%Y-%m') if local else ''


def _day_key(dt):
    local = _taipei(dt)
    return local.strftime('%Y-%m-%d') if local else ''


def _week_key(dt):
    local = _taipei(dt)
    if not local:
        return ''
    iso = local.isocalendar()
    return f'{iso.year}-W{iso.week:02d}'


def _bucket_key(dt, granularity):
    if granularity == 'day':
        return _day_key(dt)
    if granularity == 'week':
        return _week_key(dt)
    return _month_key(dt)


def _parse_date(value):
    try:
        return datetime.strptime(value, '%Y-%m-%d').date()
    except (TypeError, ValueError):
        return None


def _parse_month(value):
    try:
        datetime.strptime(value, '%Y-%m')
        return value
    except (TypeError, ValueError):
        return None


def _parse_week(value):
    match = _WEEK_RE.match(value or '')
    if not match:
        return None
    year, week = int(match.group(1)), int(match.group(2))
    try:
        date.fromisocalendar(year, week, 1)
        return f'{year}-W{week:02d}'
    except ValueError:
        return None


def _week_start(week_str):
    year, week = map(int, week_str.split('-W'))
    return date.fromisocalendar(year, week, 1)


def _week_label(week_str):
    start = _week_start(week_str)
    end = start + timedelta(days=6)
    return f'{start.month}/{start.day}–{end.month}/{end.day}'


def _month_bucket_keys(now_local, count=MONTH_TREND_COUNT):
    keys = []
    year, month_num = now_local.year, now_local.month
    for offset in range(count - 1, -1, -1):
        index = year * 12 + (month_num - 1) - offset
        y, m = divmod(index, 12)
        keys.append(f'{y:04d}-{m + 1:02d}')
    return keys


def _week_bucket_keys(now_local, count=WEEK_TREND_COUNT):
    today = now_local.date()
    iso = today.isocalendar()
    current = date.fromisocalendar(iso.year, iso.week, 1)
    keys = []
    for offset in range(count - 1, -1, -1):
        week_start = current - timedelta(weeks=offset)
        iso_week = week_start.isocalendar()
        keys.append(f'{iso_week.year}-W{iso_week.week:02d}')
    return keys


def _day_bucket_keys(start_date, end_date):
    keys = []
    cursor = start_date
    while cursor <= end_date:
        keys.append(cursor.strftime('%Y-%m-%d'))
        cursor += timedelta(days=1)
    return keys


def _prev_month(month_str):
    year, month = map(int, month_str.split('-'))
    if month == 1:
        return f'{year - 1}-12'
    return f'{year:04d}-{month - 1:02d}'


def _prev_week(week_str):
    start = _week_start(week_str) - timedelta(weeks=1)
    iso = start.isocalendar()
    return f'{iso.year}-W{iso.week:02d}'


def _pct_change(current, previous):
    if not previous:
        return None
    return ((current - previous) / previous) * 100


def _normalize_range(granularity=None, period=None, start=None, end=None, legacy_month=None):
    now_local = _now_local()
    today = now_local.date()
    granularity = (granularity or 'month').strip().lower()
    if granularity not in GRANULARITIES:
        granularity = 'month'

    if legacy_month and not period:
        period = legacy_month

    month_keys = _month_bucket_keys(now_local)
    week_keys = _week_bucket_keys(now_local)
    month_options = [{'value': key, 'label': key} for key in reversed(month_keys)]
    week_options = [
        {'value': key, 'label': _week_label(key)}
        for key in reversed(week_keys)
    ]

    if granularity == 'month':
        selected = _parse_month(period) or now_local.strftime('%Y-%m')
        bucket_keys = month_keys
        period_label = selected
        range_start = range_end = None
        compare_key = _prev_month(selected)
        compare_label_key = 'admin_dashboard_vs_last_month'
    elif granularity == 'week':
        selected = _parse_week(period) or _week_key(now_local)
        bucket_keys = week_keys
        period_label = _week_label(selected)
        range_start = range_end = None
        compare_key = _prev_week(selected)
        compare_label_key = 'admin_dashboard_vs_last_week'
    else:
        end_date = _parse_date(end) or today
        start_date = _parse_date(start) or (end_date - timedelta(days=DAY_TREND_DEFAULT - 1))
        if start_date > end_date:
            start_date, end_date = end_date, start_date
        if (end_date - start_date).days > MAX_DAY_SPAN - 1:
            start_date = end_date - timedelta(days=MAX_DAY_SPAN - 1)
        bucket_keys = _day_bucket_keys(start_date, end_date)
        selected = None
        period_label = f'{start_date.strftime("%Y-%m-%d")} – {end_date.strftime("%Y-%m-%d")}'
        range_start = start_date.strftime('%Y-%m-%d')
        range_end = end_date.strftime('%Y-%m-%d')
        span_days = (end_date - start_date).days + 1
        prev_end = start_date - timedelta(days=1)
        prev_start = prev_end - timedelta(days=span_days - 1)
        compare_key = (prev_start, prev_end)
        compare_label_key = 'admin_dashboard_vs_prev_range'

    return {
        'granularity': granularity,
        'period': selected or '',
        'start': range_start or (today - timedelta(days=DAY_TREND_DEFAULT - 1)).strftime('%Y-%m-%d'),
        'end': range_end or today.strftime('%Y-%m-%d'),
        'period_label': period_label,
        'month_options': month_options,
        'week_options': week_options,
        'bucket_keys': bucket_keys,
        'compare_key': compare_key,
        'compare_label_key': compare_label_key,
        'now_local': now_local,
    }


def _submission_in_period(sub, granularity, period, start, end):
    key = _bucket_key(sub.created_at, granularity)
    if not key:
        return False
    if granularity == 'day':
        return start <= key <= end
    return key == period


def _trend_label(key, granularity):
    if granularity == 'month':
        return key[5:]
    if granularity == 'week':
        return _week_label(key)
    return key[5:]


def build_dashboard_data(month=None, granularity=None, period=None, start=None, end=None):
    cfg = _normalize_range(granularity, period, start, end, legacy_month=month)
    granularity = cfg['granularity']
    selected_period = cfg['period']
    range_start = cfg['start']
    range_end = cfg['end']

    submissions = Submission.query.order_by(Submission.created_at.asc()).all()
    completed = [sub for sub in submissions if sub.status in COMPLETE_STATUSES]

    period_submissions = [
        sub for sub in submissions
        if _submission_in_period(sub, granularity, selected_period, range_start, range_end)
    ]
    period_completed = [
        sub for sub in period_submissions if sub.status in COMPLETE_STATUSES
    ]
    period_revenue = sum(sub.total_price or 0 for sub in period_completed)
    average_order = (
        sum(sub.total_price or 0 for sub in period_completed) / len(period_completed)
        if period_completed else 0
    )

    status_counts = Counter(sub.status for sub in period_submissions)
    buckets = defaultdict(lambda: {
        'orders': 0, 'order_total': 0.0, 'revenue': 0.0, 'completed_orders': 0,
    })
    product_counts = Counter()
    product_labels = {}
    stores = defaultdict(lambda: {'orders': 0, 'revenue': 0.0})

    for sub in submissions:
        key = _bucket_key(sub.created_at, granularity)
        if key in cfg['bucket_keys']:
            buckets[key]['orders'] += 1
            buckets[key]['order_total'] += sub.total_price or 0
            if sub.status in COMPLETE_STATUSES:
                buckets[key]['revenue'] += sub.total_price or 0
                buckets[key]['completed_orders'] += 1

    for sub in period_submissions:
        product_key = sub.product_id or f'legacy:{sub.category}:{sub.style_type}'
        product_labels[product_key] = (
            sub.product.name_zh if sub.product else
            submission_summary(sub.category, sub.style_type, product=sub.product)
        )
        product_counts[product_key] += 1

        store_name = sub.user.store_name or sub.user.username if sub.user else 'Unknown'
        stores[store_name]['orders'] += 1
        if sub.status in COMPLETE_STATUSES:
            stores[store_name]['revenue'] += sub.total_price or 0

    trends = [
        {
            'key': key,
            'label': _trend_label(key, granularity),
            'month': key,
            'orders': buckets[key]['orders'],
            'order_total': buckets[key]['order_total'],
            'revenue': buckets[key]['revenue'],
            'completed_orders': buckets[key]['completed_orders'],
        }
        for key in cfg['bucket_keys']
    ]
    max_orders = max((item['orders'] for item in trends), default=1) or 1
    max_revenue = max((item['revenue'] for item in trends), default=1) or 1
    total_status = sum(status_counts.values()) or 1
    for item in trends:
        item['order_percent'] = item['orders'] / max_orders * 100
        item['revenue_percent'] = item['revenue'] / max_revenue * 100

    top_products = [
        {'name': product_labels[key], 'orders': count}
        for key, count in product_counts.most_common(10)
    ]
    store_rows = [
        {'name': name, **values}
        for name, values in sorted(
            stores.items(), key=lambda row: (-row[1]['revenue'], row[0])
        )
    ]
    status_rows = [
        {
            'code': status,
            'label': label,
            'count': status_counts.get(status, 0),
            'percent': status_counts.get(status, 0) / total_status * 100,
        }
        for status, label in STATUS_LABELS_ZH.items()
    ]

    status_pie = []
    pie_offset = 0.0
    for index, row in enumerate(status_rows):
        if row['count'] == 0:
            continue
        dash = row['percent'] / 100 * PIE_CIRCUMFERENCE
        status_pie.append({
            **row,
            'dash': round(dash, 2),
            'offset': round(pie_offset, 2),
            'color': STATUS_PIE_COLORS[index % len(STATUS_PIE_COLORS)],
        })
        pie_offset += dash

    if granularity == 'day':
        prev_start, prev_end = cfg['compare_key']
        prev_start_s = prev_start.strftime('%Y-%m-%d')
        prev_end_s = prev_end.strftime('%Y-%m-%d')
        prev_submissions = [
            sub for sub in submissions
            if _submission_in_period(sub, granularity, None, prev_start_s, prev_end_s)
        ]
        prev_completed = [
            sub for sub in prev_submissions if sub.status in COMPLETE_STATUSES
        ]
        prev_orders = len(prev_submissions)
        prev_revenue = sum(sub.total_price or 0 for sub in prev_completed)
        active_trend_key = range_end
    else:
        prev_submissions = [
            sub for sub in submissions
            if _bucket_key(sub.created_at, granularity) == cfg['compare_key']
        ]
        prev_completed = [
            sub for sub in prev_submissions if sub.status in COMPLETE_STATUSES
        ]
        prev_orders = len(prev_submissions)
        prev_revenue = sum(sub.total_price or 0 for sub in prev_completed)
        active_trend_key = selected_period

    selected_trend = next(
        (item for item in trends if item['key'] == active_trend_key),
        {'orders': 0, 'revenue': 0},
    )

    sparkline = trends[-8:]
    spark_max = max((item['orders'] for item in sparkline), default=1) or 1
    spark_points = []
    for index, item in enumerate(sparkline):
        item['spark_percent'] = item['orders'] / spark_max * 100
        x = (index / (len(sparkline) - 1) * 240) if len(sparkline) > 1 else 0
        y = 72 - (item['spark_percent'] * 0.62)
        spark_points.append(f'{x:.1f},{y:.1f}')
    spark_points_str = ' '.join(spark_points)

    trends_sub_keys = {
        'day': 'admin_dashboard_trends_sub_day',
        'week': 'admin_dashboard_trends_sub_week',
        'month': 'admin_dashboard_trends_sub_month',
    }
    kpi_revenue_keys = {
        'day': 'admin_dashboard_revenue_range',
        'week': 'admin_dashboard_revenue_week',
        'month': 'admin_dashboard_revenue_month',
    }
    kpi_orders_keys = {
        'day': 'admin_dashboard_orders_range',
        'week': 'admin_dashboard_orders_week',
        'month': 'admin_dashboard_orders_month',
    }

    return {
        'status_counts': {status: status_counts.get(status, 0) for status in STATUS_LABELS_ZH},
        'status_rows': status_rows,
        'status_pie': status_pie,
        'granularity': granularity,
        'period': selected_period or '',
        'start': cfg['start'],
        'end': cfg['end'],
        'period_label': cfg['period_label'],
        'month_options': cfg['month_options'],
        'week_options': cfg['week_options'],
        'compare_label_key': cfg['compare_label_key'],
        'trends_sub_key': trends_sub_keys[granularity],
        'kpi_revenue_key': kpi_revenue_keys[granularity],
        'kpi_orders_key': kpi_orders_keys[granularity],
        'month': selected_period or cfg['period_label'],
        'month_orders': len(period_submissions),
        'month_revenue': period_revenue,
        'month_trend_orders': selected_trend['orders'],
        'month_trend_revenue': selected_trend['revenue'],
        'average_order': average_order,
        'total_orders': len(period_submissions),
        'order_change_pct': _pct_change(len(period_submissions), prev_orders),
        'revenue_change_pct': _pct_change(period_revenue, prev_revenue),
        'top_products': top_products[:5],
        'top_store': store_rows[0] if store_rows else None,
        'stores': store_rows[:8],
        'trends': trends,
        'sparkline': sparkline,
        'spark_points': spark_points_str,
        'trend_range_label': (
            f"{trends[0]['label']} – {trends[-1]['label']}"
            if trends else cfg['period_label']
        ),
        'active_trend_key': active_trend_key,
    }


def dashboard_csv(month=None, granularity=None, period=None, start=None, end=None):
    cfg = _normalize_range(granularity, period, start, end, legacy_month=month)
    granularity = cfg['granularity']
    selected_period = cfg['period']
    range_start = cfg['start']
    range_end = cfg['end']

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        '訂單編號', '日期', '店家', '商品', '狀態', '含稅總計',
    ])
    for sub in Submission.query.order_by(Submission.created_at.asc()).all():
        if not _submission_in_period(
            sub, granularity, selected_period, range_start, range_end
        ):
            continue
        writer.writerow([
            sub.id,
            _taipei(sub.created_at).strftime('%Y-%m-%d %H:%M') if sub.created_at else '',
            (sub.user.store_name or sub.user.username) if sub.user else '',
            submission_summary(sub.category, sub.style_type, product=sub.product),
            STATUS_LABELS_ZH.get(sub.status, sub.status),
            round(sub.total_price or 0),
        ])
    slug = selected_period or f'{range_start}_{range_end}' or 'all'
    return '\ufeff' + output.getvalue(), slug
