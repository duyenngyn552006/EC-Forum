from django.test import TestCase
from django.urls import reverse

from accounts.models import User

from . import services
from .models import Announcement


class AnnouncementViewCountTests(TestCase):
    def setUp(self):
        self.staff = User.objects.create_user(email="vc_staff@due.udn.vn", password="Pass1234!", role=User.Role.STAFF)
        self.announcement, _ = services.create_announcement(
            self.staff, Announcement.Kind.OFFICIAL, "Thong bao test luot xem", "noi dung",
        )

    def test_detail_view_increments_view_count(self):
        self.assertEqual(self.announcement.view_count, 0)
        self.client.get(reverse("announcements:detail", args=[self.announcement.pk]))
        self.announcement.refresh_from_db()
        self.assertEqual(self.announcement.view_count, 1)


class EventDatetimeTests(TestCase):
    def setUp(self):
        self.bch = User.objects.create_user(email="bchtest2@due.udn.vn", password="Pass1234!", role=User.Role.BCH)

    def test_event_announcement_requires_event_datetime(self):
        response = self.client.post(
            reverse("announcements:create"),
            self._login_and_build_payload(kind=Announcement.Kind.EVENT, with_datetime=False),
        )
        self.assertEqual(response.status_code, 200)
        self.assertFormError(response.context["form"], "event_datetime", [
            "Bắt buộc nhập thời gian diễn ra sự kiện đối với thông báo loại sự kiện."
        ])

    def test_event_announcement_with_datetime_is_created(self):
        response = self.client.post(
            reverse("announcements:create"),
            self._login_and_build_payload(kind=Announcement.Kind.EVENT, with_datetime=True),
        )
        self.assertEqual(response.status_code, 302)
        announcement = Announcement.objects.get(title="Ngay hoi viec lam")
        self.assertIsNotNone(announcement.event_datetime)

    def _login_and_build_payload(self, kind, with_datetime):
        self.client.force_login(self.bch)
        payload = {
            "kind": kind,
            "title": "Ngay hoi viec lam",
            "body": "noi dung su kien",
            "attachments-TOTAL_FORMS": "0",
            "attachments-INITIAL_FORMS": "0",
            "attachments-MIN_NUM_FORMS": "0",
            "attachments-MAX_NUM_FORMS": "1000",
        }
        if with_datetime:
            payload["event_datetime_0"] = "2026-10-20"
            payload["event_datetime_1"] = "08:00"
        return payload

    def test_pin_scope_is_per_kind(self):
        staff = User.objects.create_user(email="staff3@due.udn.vn", password="Pass1234!", role=User.Role.STAFF)
        a1, _ = services.create_announcement(self.bch, Announcement.Kind.EVENT, "SK1", "noi dung")
        a2, _ = services.create_announcement(self.bch, Announcement.Kind.EVENT, "SK2", "noi dung")

        from django.test import override_settings

        with override_settings(MAX_PINNED_PER_CATEGORY=1):
            services.pin_announcement(a1, staff)
            from config.mixins import PinLimitExceeded

            with self.assertRaises(PinLimitExceeded):
                services.pin_announcement(a2, staff)


class AnnouncementPostPermissionTests(TestCase):
    """Giao vu Khoa, BCH Khoa, Giang vien/BCN Khoa dang thong bao duoc, dang ngay khong
    qua duyet noi bo nao (CLAUDE.md); Sinh vien khong dang duoc."""

    def setUp(self):
        self.lecturer = User.objects.create_user(email="post_lecturer@due.udn.vn", password="Pass1234!", role=User.Role.LECTURER)
        self.student = User.objects.create_user(email="post_student@due.udn.vn", password="Pass1234!", role=User.Role.STUDENT)

    def _payload(self):
        return {
            "kind": Announcement.Kind.OFFICIAL,
            "title": "Thong bao tu giang vien",
            "body": "noi dung thong bao",
            "attachments-TOTAL_FORMS": "0",
            "attachments-INITIAL_FORMS": "0",
            "attachments-MIN_NUM_FORMS": "0",
            "attachments-MAX_NUM_FORMS": "10",
        }

    def test_lecturer_can_post_announcement_immediately(self):
        self.client.force_login(self.lecturer)
        response = self.client.post(reverse("announcements:create"), self._payload())
        self.assertEqual(response.status_code, 302)
        announcement = Announcement.objects.get(title="Thong bao tu giang vien")
        self.assertEqual(announcement.status, "published")

    def test_lecturer_sees_create_button_on_list_page(self):
        self.client.force_login(self.lecturer)
        response = self.client.get(reverse("announcements:list"))
        self.assertContains(response, reverse("announcements:create"))

    def test_student_cannot_post_announcement(self):
        self.client.force_login(self.student)
        response = self.client.post(reverse("announcements:create"), self._payload(), follow=True)
        self.assertFalse(Announcement.objects.filter(title="Thong bao tu giang vien").exists())
        messages = list(response.context["messages"])
        self.assertTrue(any("Chỉ Giáo vụ Khoa" in str(m) for m in messages))
