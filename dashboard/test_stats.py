"""Test thong ke dashboard theo ky lich (tuan T2-CN / thang / nam) va chuyen ky."""
from datetime import date, datetime, time, timedelta

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import User
from forum.models import Category, ForumPost

from . import stats

TODAY = date(2026, 10, 11)  # chu nhat


def _at(day, hour=10):
    return timezone.make_aware(datetime.combine(day, time(hour, 0)))


class ResolvePeriodTests(TestCase):
    def test_week_is_monday_to_sunday_containing_date(self):
        info = stats.resolve_period("week", {"date": "2026-10-08"}, TODAY)  # thu 5
        self.assertEqual((info["start"], info["end"]), (date(2026, 10, 5), date(2026, 10, 12)))
        self.assertEqual(info["buckets"][0].weekday(), 0)
        self.assertEqual(len(info["buckets"]), 7)
        self.assertEqual(info["prev_start"], date(2026, 9, 28))
        self.assertEqual(info["label"], "Tuần 41 · 05/10 – 11/10/2026")

    def test_default_week_is_current_week_and_next_is_disabled(self):
        info = stats.resolve_period(None, {}, TODAY)
        self.assertEqual((info["period"], info["start"], info["is_current"]), ("week", date(2026, 10, 5), True))
        self.assertIsNone(info["next_params"])
        self.assertEqual(info["prev_params"], {"period": "week", "date": "2026-09-28"})

    def test_month_has_one_bucket_per_day(self):
        for (year, month), days in {(2026, 2): 28, (2024, 2): 29, (2026, 10): 31, (2026, 9): 30}.items():
            info = stats.resolve_period("month", {"year": str(year), "month": str(month)}, TODAY)
            self.assertEqual(len(info["buckets"]), days, (year, month))
            self.assertEqual(info["buckets"][0], date(year, month, 1))

    def test_month_navigation_wraps_year(self):
        info = stats.resolve_period("month", {"year": "2026", "month": "1"}, TODAY)
        self.assertEqual(info["prev_params"], {"period": "month", "year": 2025, "month": 12})
        self.assertEqual(info["next_params"], {"period": "month", "year": 2026, "month": 2})
        self.assertEqual(info["prev_start"], date(2025, 12, 1))

    def test_year_has_twelve_month_buckets(self):
        info = stats.resolve_period("year", {"year": "2025"}, TODAY)
        self.assertEqual((info["unit"], len(info["buckets"]), info["buckets"][-1]), ("month", 12, date(2025, 12, 1)))
        self.assertEqual(info["next_params"], {"period": "year", "year": 2026})
        self.assertFalse(info["is_current"])

    def test_invalid_params_fall_back_to_current(self):
        info = stats.resolve_period("month", {"year": "abc", "month": "13"}, TODAY)
        self.assertEqual(info["start"], date(2026, 10, 1))
        info = stats.resolve_period("week", {"date": "not-a-date"}, TODAY)
        self.assertEqual(info["start"], date(2026, 10, 5))
        self.assertEqual(stats.resolve_period("decade", {}, TODAY)["period"], "week")

    def test_labels(self):
        self.assertEqual(stats.bucket_label(date(2026, 10, 5), "day", "week"), "T2 05/10")
        self.assertEqual(stats.bucket_label(date(2026, 10, 11), "day", "week"), "CN 11/10")
        self.assertEqual(stats.bucket_label(date(2026, 10, 5), "day", "month"), "05/10")
        self.assertEqual(stats.bucket_label(date(2026, 3, 1), "month", "year"), "T3")

    def test_delta_percent(self):
        self.assertEqual(stats.delta_percent(15, 10), 50)
        self.assertEqual(stats.delta_percent(5, 10), -50)
        self.assertIsNone(stats.delta_percent(3, 0))


class CountingTests(TestCase):
    def setUp(self):
        self.author = User.objects.create_user(email="st-author@due.udn.vn", password="Pass1234!")
        self.category = Category.objects.create(name="StatsCat")
        self.qs = ForumPost.objects.filter(author=self.author)

    def _post_on(self, day):
        post = ForumPost.objects.create(author=self.author, category=self.category, title="x", body="x", status="published")
        ForumPost.objects.filter(pk=post.pk).update(created_at=_at(day))

    def test_week_series_counts_and_future_days_are_none(self):
        today = timezone.localdate()
        info = stats.resolve_period("week", {}, today)
        self._post_on(info["start"])
        self._post_on(info["start"])
        self._post_on(info["start"] - timedelta(days=1))  # chu nhat tuan truoc
        series = stats.count_series(self.qs, "created_at", info)
        self.assertEqual(series[0], 2)
        future = [v for b, v in zip(info["buckets"], series) if b > today]
        self.assertTrue(all(v is None for v in future))
        self.assertEqual(stats.period_count(self.qs, "created_at", info["start"], info["end"]), 2)
        self.assertEqual(stats.period_count(self.qs, "created_at", info["prev_start"], info["start"]), 1)

    def test_past_year_by_month(self):
        info = stats.resolve_period("year", {"year": "2025"}, date(2026, 10, 11))
        self._post_on(date(2025, 3, 15))
        self._post_on(date(2025, 3, 20))
        self._post_on(date(2025, 12, 31))
        self._post_on(date(2026, 1, 1))  # khong thuoc nam 2025
        series = stats.count_series(self.qs, "created_at", info)
        self.assertEqual((series[2], series[11], sum(series)), (2, 1, 3))

    def test_past_month_by_day(self):
        info = stats.resolve_period("month", {"year": "2025", "month": "2"}, date(2026, 10, 11))
        self._post_on(date(2025, 2, 28))
        self._post_on(date(2025, 3, 1))
        series = stats.count_series(self.qs, "created_at", info)
        self.assertEqual((len(series), series[-1], sum(series)), (28, 1, 1))


class DashboardViewTests(TestCase):
    def setUp(self):
        self.staff = User.objects.create_user(email="st-staff@due.udn.vn", password="Pass1234!", role=User.Role.STAFF)
        self.client.force_login(self.staff)

    def _get(self, **params):
        response = self.client.get(reverse("dashboard:overview"), params)
        self.assertEqual(response.status_code, 200)
        return response

    def test_each_period_renders(self):
        for period, length in (("week", 7), ("year", 12)):
            response = self._get(period=period)
            self.assertEqual(len(response.context["chart"]["labels"]), length)
            self.assertContains(response, 'aria-current="page">' + stats.PERIOD_LABELS[period])
        month = self._get(period="month", year="2026", month="2")
        self.assertEqual(len(month.context["chart"]["labels"]), 28)
        self.assertContains(month, "Tháng 2/2026")

    def test_navigation_links_and_pickers(self):
        response = self._get(period="month", year="2025", month="12")
        self.assertContains(response, 'href="?period=month&amp;year=2025&amp;month=11"')
        self.assertContains(response, 'href="?period=month&amp;year=2026&amp;month=1"')
        self.assertContains(response, 'name="month"')
        self.assertContains(response, 'name="year"')
        self.assertContains(response, "Về kỳ hiện tại")
        week = self._get(period="week")
        self.assertContains(week, 'name="date"')
        self.assertContains(week, "Đang diễn ra")
        self.assertContains(week, 'aria-disabled="true"')

    def test_chart_and_table_tabs(self):
        response = self._get()
        self.assertContains(response, 'role="tablist"')
        self.assertContains(response, 'id="panelChart"')
        self.assertContains(response, 'id="panelTable"')

    def test_comparison_uses_previous_period_name(self):
        response = self._get(period="year")
        self.assertContains(response, "năm trước")

    def test_year_options_start_from_earliest_data(self):
        User.objects.filter(pk=self.staff.pk).update(date_joined=_at(date(2023, 5, 1)))
        response = self._get(period="year")
        self.assertEqual(response.context["year_options"][0], 2023)
        self.assertEqual(response.context["year_options"][-1], timezone.localdate().year)

    def test_year_options_include_viewed_year(self):
        response = self._get(period="year", year="2019")
        self.assertIn(2019, response.context["year_options"])
        self.assertContains(response, '<option value="2019" selected>')

    def test_only_staff_can_view(self):
        student = User.objects.create_user(email="st-sv@due.udn.vn", password="Pass1234!")
        self.client.force_login(student)
        self.assertEqual(self.client.get(reverse("dashboard:overview")).status_code, 302)
