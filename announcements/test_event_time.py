"""Test thoi gian dien ra su kien: 1 moc thoi gian hoac 1 khoang thoi gian (bat dau -> ket thuc)."""
from datetime import datetime

from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import User

from .forms import AnnouncementForm
from .models import Announcement

TITLE = "Hoi thao khoang thoi gian"


def _aware(year, month, day, hour, minute):
    return timezone.make_aware(datetime(year, month, day, hour, minute))


class EventTimeRangeTests(TestCase):
    def setUp(self):
        # Rate limit dang bai (10/phut) dung chung cache giua cac test -> don truoc/sau de khong anh huong test khac
        cache.clear()
        self.addCleanup(cache.clear)
        self.bch = User.objects.create_user(email="et-bch@due.udn.vn", password="Pass1234!", role=User.Role.BCH)
        self.staff = User.objects.create_user(email="et-staff@due.udn.vn", password="Pass1234!", role=User.Role.STAFF)
        self.client.force_login(self.bch)

    def _payload(self, **extra):
        payload = {
            "kind": "event", "title": TITLE, "body": "noi dung",
            "attachments-TOTAL_FORMS": "0", "attachments-INITIAL_FORMS": "0",
            "attachments-MIN_NUM_FORMS": "0", "attachments-MAX_NUM_FORMS": "1000",
            "event_datetime_0": "2026-10-20", "event_datetime_1": "08:00",
        }
        payload.update(extra)
        return payload

    def _post(self, **extra):
        return self.client.post(reverse("announcements:create"), self._payload(**extra))

    # --- che do 1 moc ---
    def test_single_mode_has_no_end(self):
        self._post(event_time_mode="single")
        a = Announcement.objects.get(title=TITLE)
        self.assertIsNone(a.event_end_datetime)
        self.assertEqual(a.event_time_display, "20/10/2026 08:00")

    def test_mode_missing_defaults_to_single(self):
        self._post()
        self.assertIsNone(Announcement.objects.get(title=TITLE).event_end_datetime)

    def test_single_mode_drops_leftover_end_values(self):
        # Nguoi dung nhap gio ket thuc roi chuyen lai "1 moc": gio ket thuc con trong form khong duoc luu
        self._post(event_time_mode="single", event_end_datetime_0="2026-10-21", event_end_datetime_1="17:00")
        self.assertIsNone(Announcement.objects.get(title=TITLE).event_end_datetime)

    # --- che do khoang ---
    def test_range_within_one_day(self):
        response = self._post(event_time_mode="range", event_end_datetime_0="2026-10-20", event_end_datetime_1="11:30")
        self.assertEqual(response.status_code, 302)
        a = Announcement.objects.get(title=TITLE)
        self.assertEqual(a.event_end_datetime, _aware(2026, 10, 20, 11, 30))
        self.assertEqual(a.event_time_display, "20/10/2026, 08:00 – 11:30")

    def test_range_across_days(self):
        self._post(event_time_mode="range", event_end_datetime_0="2026-10-22", event_end_datetime_1="17:00")
        self.assertEqual(
            Announcement.objects.get(title=TITLE).event_time_display, "20/10/2026 08:00 – 22/10/2026 17:00",
        )

    def test_range_requires_end(self):
        response = self._post(event_time_mode="range")
        self.assertEqual(response.status_code, 200)
        self.assertIn("event_end_datetime", response.context["form"].errors)
        self.assertFalse(Announcement.objects.filter(title=TITLE).exists())

    def test_end_must_be_after_start(self):
        for end_date, end_time in (("2026-10-20", "08:00"), ("2026-10-20", "07:00"), ("2026-10-19", "23:00")):
            response = self._post(event_time_mode="range", event_end_datetime_0=end_date, event_end_datetime_1=end_time)
            self.assertEqual(response.status_code, 200, (end_date, end_time))
            self.assertEqual(
                response.context["form"].errors["event_end_datetime"], ["Thời điểm kết thúc phải sau thời điểm bắt đầu."],
            )
        self.assertFalse(Announcement.objects.filter(title=TITLE).exists())

    def test_range_without_start_only_reports_missing_start(self):
        response = self._post(
            event_time_mode="range", event_datetime_0="", event_datetime_1="",
            event_end_datetime_0="2026-10-21", event_end_datetime_1="10:00",
        )
        self.assertEqual(list(response.context["form"].errors), ["event_datetime"])

    def test_official_announcement_ignores_event_time(self):
        self.client.force_login(self.staff)
        self._post(
            kind="official", event_time_mode="range", event_end_datetime_0="2026-10-22", event_end_datetime_1="17:00",
        )
        self.assertIsNone(Announcement.objects.get(title=TITLE).event_end_datetime)

    # --- sua bai ---
    def _make_range_event(self):
        return Announcement.objects.create(
            author=self.bch, kind="event", title=TITLE, body="x", status="published",
            event_datetime=_aware(2026, 10, 20, 8, 0), event_end_datetime=_aware(2026, 10, 20, 11, 0),
        )

    def test_edit_form_opens_in_range_mode_when_event_has_end(self):
        a = self._make_range_event()
        response = self.client.get(reverse("announcements:edit", args=[a.pk]))
        self.assertEqual(response.context["form"]["event_time_mode"].value(), "range")
        self.assertContains(response, 'data-mode="range"')

    def test_edit_form_opens_in_single_mode_when_event_has_no_end(self):
        a = self._make_range_event()
        a.event_end_datetime = None
        a.save()
        response = self.client.get(reverse("announcements:edit", args=[a.pk]))
        self.assertEqual(response.context["form"]["event_time_mode"].value(), "single")

    def test_switching_range_back_to_single_clears_end(self):
        a = self._make_range_event()
        self.client.post(reverse("announcements:edit", args=[a.pk]), self._payload(
            event_time_mode="single", event_end_datetime_0="2026-10-20", event_end_datetime_1="11:00",
            **{"attachments-TOTAL_FORMS": "0"},
        ))
        a.refresh_from_db()
        self.assertIsNone(a.event_end_datetime)

    # --- hien thi ---
    def test_detail_and_list_show_range(self):
        a = self._make_range_event()
        detail = self.client.get(reverse("announcements:detail", args=[a.pk]))
        self.assertContains(detail, "20/10/2026, 08:00 – 11:00")
        listing = self.client.get(reverse("announcements:list"))
        self.assertContains(listing, "20/10/2026, 08:00 – 11:00")

    def test_form_page_renders_mode_choices_and_both_time_inputs(self):
        response = self.client.get(reverse("announcements:create"))
        for text in ("Một mốc thời gian", "Khoảng thời gian", 'name="event_datetime_0"', 'name="event_end_datetime_1"'):
            self.assertContains(response, text)

    # --- quyen theo vai tro ---
    def test_kind_choices_per_role(self):
        lecturer = User.objects.create_user(email="et-lec@due.udn.vn", password="Pass1234!", role=User.Role.LECTURER)
        for user in (self.staff, lecturer, self.bch):
            choices = {value for value, _ in AnnouncementForm(user=user).fields["kind"].choices}
            self.assertEqual(choices, {"official", "event"}, user.role)

    def test_default_kind_is_event_for_bch_and_official_for_others(self):
        self.assertEqual(AnnouncementForm(user=self.bch)["kind"].value(), "event")
        self.assertEqual(AnnouncementForm(user=self.staff)["kind"].value(), "official")

    def test_staff_and_lecturer_can_post_event_with_time_range(self):
        lecturer = User.objects.create_user(email="et-lec2@due.udn.vn", password="Pass1234!", role=User.Role.LECTURER)
        for i, user in enumerate((self.staff, lecturer)):
            self.client.force_login(user)
            title = f"Su kien cua {user.role}"
            self._post(title=title, event_time_mode="range", event_end_datetime_0="2026-10-20", event_end_datetime_1="10:00")
            a = Announcement.objects.get(title=title)
            self.assertEqual((a.kind, a.event_time_display), ("event", "20/10/2026, 08:00 – 10:00"))

    def test_bch_can_post_official_announcement(self):
        response = self._post(kind="official")
        self.assertEqual(response.status_code, 302)
        a = Announcement.objects.get(title=TITLE)
        self.assertEqual((a.kind, a.event_end_datetime), ("official", None))

    def test_display_is_empty_without_start(self):
        self.assertEqual(Announcement(title="x").event_time_display, "")

    def test_form_defaults_to_single_mode(self):
        self.assertEqual(AnnouncementForm(user=self.bch)["event_time_mode"].value(), "single")
