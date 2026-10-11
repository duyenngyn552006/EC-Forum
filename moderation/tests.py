from django.test import TestCase
from django.urls import reverse

from accounts.models import User
from config.mixins import ContentStatus
from forum.models import Category, ForumPost
from notifications.models import Notification

from .models import ModerationLog, SensitiveKeyword


class SensitiveKeywordCrudViewTests(TestCase):
    """Trang quan ly tu khoa nhay cam trong giao dien EC Forum (thay the Django Admin)
    - chi Giao vu Khoa duoc truy cap."""

    def setUp(self):
        self.staff = User.objects.create_user(
            email="kw_staff@due.udn.vn", password="Pass1234!", role=User.Role.STAFF,
        )
        self.student = User.objects.create_user(
            email="kw_student@due.udn.vn", password="Pass1234!",
        )

    def test_student_cannot_access_keyword_list(self):
        self.client.force_login(self.student)
        response = self.client.get(reverse("moderation:keyword_list"))
        self.assertRedirects(response, reverse("home"))

    def test_anonymous_cannot_access_keyword_list(self):
        response = self.client.get(reverse("moderation:keyword_list"))
        self.assertRedirects(response, reverse("home"))

    def test_staff_can_view_keyword_list(self):
        SensitiveKeyword.objects.create(keyword="camtu")
        self.client.force_login(self.staff)
        response = self.client.get(reverse("moderation:keyword_list"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "camtu")

    def test_staff_can_create_keyword(self):
        self.client.force_login(self.staff)
        response = self.client.post(
            reverse("moderation:keyword_create"),
            {"keyword": "spam", "is_active": "on", "note": "tu khoa test"},
        )
        self.assertRedirects(response, reverse("moderation:keyword_list"))
        self.assertTrue(SensitiveKeyword.objects.filter(keyword="spam", is_active=True).exists())

    def test_staff_can_edit_keyword(self):
        kw = SensitiveKeyword.objects.create(keyword="old", is_active=True)
        self.client.force_login(self.staff)
        response = self.client.post(
            reverse("moderation:keyword_edit", args=[kw.pk]),
            {"keyword": "new", "note": ""},
        )
        self.assertRedirects(response, reverse("moderation:keyword_list"))
        kw.refresh_from_db()
        self.assertEqual(kw.keyword, "new")
        self.assertFalse(kw.is_active)  # checkbox khong gui = False

    def test_staff_can_delete_keyword(self):
        kw = SensitiveKeyword.objects.create(keyword="xoa_di")
        self.client.force_login(self.staff)
        response = self.client.post(reverse("moderation:keyword_delete", args=[kw.pk]))
        self.assertRedirects(response, reverse("moderation:keyword_list"))
        self.assertFalse(SensitiveKeyword.objects.filter(pk=kw.pk).exists())

    def test_student_cannot_delete_keyword(self):
        kw = SensitiveKeyword.objects.create(keyword="giu_lai")
        self.client.force_login(self.student)
        self.client.post(reverse("moderation:keyword_delete", args=[kw.pk]))
        self.assertTrue(SensitiveKeyword.objects.filter(pk=kw.pk).exists())


class PendingContentReviewTests(TestCase):
    """Duyet/tu choi noi dung cho kiem duyet phai bao ket qua cho nguoi tao (CLAUDE.md muc 5)."""

    def setUp(self):
        self.staff = User.objects.create_user(
            email="review_staff@due.udn.vn", password="Pass1234!", role=User.Role.STAFF,
        )
        self.author = User.objects.create_user(email="review_author@due.udn.vn", password="Pass1234!")
        self.category = Category.objects.create(name="Chung")
        self.post = ForumPost.objects.create(
            author=self.author, category=self.category, title="Bai cho duyet",
            body="noi dung co camtu", status=ContentStatus.PENDING_REVIEW,
        )
        self.client.force_login(self.staff)

    def test_approve_publishes_content_and_notifies_author(self):
        response = self.client.post(reverse("moderation:approve_content", args=["forumpost", self.post.pk]))
        self.assertRedirects(response, reverse("moderation:pending_content_list"))

        self.post.refresh_from_db()
        self.assertEqual(self.post.status, ContentStatus.PUBLISHED)

        notif = Notification.objects.get(recipient=self.author, verb=Notification.Verb.MODERATION)
        self.assertIn("đã được duyệt", notif.message)

        log = ModerationLog.objects.get(action=ModerationLog.Action.APPROVE_CONTENT)
        self.assertEqual(log.actor, self.staff)

    def test_reject_form_shows_full_content_for_review(self):
        response = self.client.get(reverse("moderation:reject_content", args=["forumpost", self.post.pk]))
        self.assertContains(response, "noi dung co camtu")

    def test_reject_without_reason_does_not_change_status(self):
        self.client.post(reverse("moderation:reject_content", args=["forumpost", self.post.pk]), {"reason": ""})
        self.post.refresh_from_db()
        self.assertEqual(self.post.status, ContentStatus.PENDING_REVIEW)

    def test_reject_sets_removed_and_notifies_author_with_reason(self):
        response = self.client.post(
            reverse("moderation:reject_content", args=["forumpost", self.post.pk]),
            {"reason": "Nội dung không phù hợp"},
        )
        self.assertRedirects(response, reverse("moderation:pending_content_list"))

        self.post.refresh_from_db()
        self.assertEqual(self.post.status, "removed")

        notif = Notification.objects.get(recipient=self.author, verb=Notification.Verb.MODERATION)
        self.assertIn("Nội dung không phù hợp", notif.message)

        log = ModerationLog.objects.get(action=ModerationLog.Action.REJECT_CONTENT)
        self.assertEqual(log.reason, "Nội dung không phù hợp")


class ModerationLogListViewTests(TestCase):
    """Trang xem toan bo nhat ky kiem duyet trong giao dien EC Forum (thay the Django Admin)
    - chi Giao vu Khoa duoc truy cap."""

    def setUp(self):
        self.staff = User.objects.create_user(
            email="log_staff@due.udn.vn", password="Pass1234!", role=User.Role.STAFF,
        )
        self.student = User.objects.create_user(email="log_student@due.udn.vn", password="Pass1234!")
        self.target = User.objects.create_user(email="log_target@due.udn.vn", password="Pass1234!")
        ModerationLog.objects.create(
            actor=self.staff, action=ModerationLog.Action.LOCK_ACCOUNT,
            reason="Vi pham noi quy", target_user=self.target,
        )
        ModerationLog.objects.create(
            actor=self.staff, action=ModerationLog.Action.APPEAL_ACCEPTED,
            reason="Chap nhan khang nghi", target_user=self.target,
        )

    def test_student_cannot_access_log_list(self):
        self.client.force_login(self.student)
        response = self.client.get(reverse("moderation:log_list"))
        self.assertRedirects(response, reverse("home"))

    def test_anonymous_cannot_access_log_list(self):
        response = self.client.get(reverse("moderation:log_list"))
        self.assertRedirects(response, reverse("home"))

    def test_staff_can_view_all_logs(self):
        self.client.force_login(self.staff)
        response = self.client.get(reverse("moderation:log_list"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Vi pham noi quy")
        self.assertContains(response, "Chap nhan khang nghi")

    def test_action_filter_narrows_results(self):
        self.client.force_login(self.staff)
        response = self.client.get(reverse("moderation:log_list"), {"action": ModerationLog.Action.LOCK_ACCOUNT})
        self.assertContains(response, "Vi pham noi quy")
        self.assertNotContains(response, "Chap nhan khang nghi")
