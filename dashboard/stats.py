"""Thong ke dashboard theo ky lich:

- Tuan: thu 2 -> chu nhat, bieu do theo tung ngay trong tuan.
- Thang: 1 thang duong lich (chon trong 12 thang cua nam), bieu do theo tung ngay trong thang.
- Nam: 1 nam duong lich, bieu do theo tung thang.

Moi ky so voi ky lien truoc cung loai (tuan truoc / thang truoc / nam truoc). Ngay chua toi trong ky dang dien ra
co gia tri None (bieu do dung lai o hom nay thay vi ve so 0 gay hieu nham). Mui gio: Asia/Ho_Chi_Minh.
"""
from datetime import date, datetime, time, timedelta

from django.db.models import Count
from django.db.models.functions import TruncDate, TruncMonth
from django.utils import timezone

PERIOD_LABELS = {"week": "Tuần", "month": "Tháng", "year": "Năm"}
DEFAULT_PERIOD = "week"
WEEKDAY_LABELS = ["T2", "T3", "T4", "T5", "T6", "T7", "CN"]


def shift_month(day, months):
    """Ngay 1 cua thang cach thang cua `day` `months` thang."""
    index = day.year * 12 + (day.month - 1) + months
    return date(index // 12, index % 12 + 1, 1)


def _int(value, default, low, high):
    try:
        number = int(value)
    except (TypeError, ValueError):
        return default
    return number if low <= number <= high else default


def _parse_date(value, default):
    try:
        return date.fromisoformat(value)
    except (TypeError, ValueError):
        return default


def resolve_period(period, params, today=None):
    """Xac dinh ky dang xem tu tham so GET -> dict: start/end (end khong bao gom), prev_start, unit, buckets,
    label, prev_label, prev_params / next_params (None neu ky sau con o tuong lai), cac gia tri cho o chon."""
    today = today or timezone.localdate()
    if period not in PERIOD_LABELS:
        period = DEFAULT_PERIOD

    if period == "week":
        anchor = _parse_date(params.get("date"), today)
        start = anchor - timedelta(days=anchor.weekday())
        end = start + timedelta(days=7)
        prev_start = start - timedelta(days=7)
        buckets = [start + timedelta(days=i) for i in range(7)]
        week_no = start.isocalendar()[1]
        last = end - timedelta(days=1)
        label = f"Tuần {week_no} · {start:%d/%m} – {last:%d/%m/%Y}"
        prev_label = "tuần trước"
        prev_params = {"period": "week", "date": prev_start.isoformat()}
        next_params = {"period": "week", "date": end.isoformat()}
        unit = "day"
    elif period == "month":
        year = _int(params.get("year"), today.year, 2000, 2100)
        month = _int(params.get("month"), today.month, 1, 12)
        start = date(year, month, 1)
        end = shift_month(start, 1)
        prev_start = shift_month(start, -1)
        buckets = [start + timedelta(days=i) for i in range((end - start).days)]
        label = f"Tháng {month}/{year}"
        prev_label = "tháng trước"
        prev_params = {"period": "month", "year": prev_start.year, "month": prev_start.month}
        next_params = {"period": "month", "year": end.year, "month": end.month}
        unit = "day"
    else:
        year = _int(params.get("year"), today.year, 2000, 2100)
        start = date(year, 1, 1)
        end = date(year + 1, 1, 1)
        prev_start = date(year - 1, 1, 1)
        buckets = [date(year, m, 1) for m in range(1, 13)]
        label = f"Năm {year}"
        prev_label = "năm trước"
        prev_params = {"period": "year", "year": year - 1}
        next_params = {"period": "year", "year": year + 1}
        unit = "month"

    return {
        "period": period, "start": start, "end": end, "prev_start": prev_start, "unit": unit, "buckets": buckets,
        "label": label, "prev_label": prev_label, "prev_params": prev_params,
        "next_params": next_params if end <= today else None,
        "is_current": start <= today < end, "today": today,
    }


def _aware(day):
    return timezone.make_aware(datetime.combine(day, time.min))


def count_series(queryset, field, info):
    """So ban ghi theo tung moc cua ky; moc con o tuong lai -> None."""
    trunc = TruncMonth(field) if info["unit"] == "month" else TruncDate(field)
    rows = (
        queryset.filter(**{f"{field}__gte": _aware(info["start"]), f"{field}__lt": _aware(info["end"])})
        .annotate(bucket=trunc).values("bucket").annotate(n=Count("id")).values_list("bucket", "n")
    )
    counts = {}
    for bucket, n in rows:
        # TruncMonth tren DateTimeField tra ve datetime (theo mui gio hien tai), TruncDate tra ve date
        key = timezone.localtime(bucket).date() if isinstance(bucket, datetime) else bucket
        if info["unit"] == "month":
            key = key.replace(day=1)
        counts[key] = counts.get(key, 0) + n
    return [None if b > info["today"] else counts.get(b, 0) for b in info["buckets"]]


def period_count(queryset, field, start, end):
    return queryset.filter(**{f"{field}__gte": _aware(start), f"{field}__lt": _aware(end)}).count()


def delta_percent(current, previous):
    """% thay doi so voi ky truoc; None neu ky truoc = 0 (khong chia duoc -> hien 'moi phat sinh')."""
    if previous == 0:
        return None
    return round((current - previous) * 100 / previous)


def bucket_label(day, unit, period):
    if unit == "month":
        return f"T{day.month}"
    if period == "week":
        return f"{WEEKDAY_LABELS[day.weekday()]} {day:%d/%m}"
    return f"{day:%d/%m}"
