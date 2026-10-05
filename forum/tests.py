from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse

from accounts.models import User
from config.mixins import ContentStatus, PinLimitExceeded
from moderation.models import SensitiveKeyword

from . import services
from .models import Category


class SensitiveKeywordFilterTests(TestCase):
    def setUp(self):
        self.author = User.objects.create_user(email="sv1@due.udn.vn", password="Pass1234!")
        self.category = Category.objects.create(name="Chung")
        SensitiveKeyword.objects.create(keyword="camtu")

    def test_post_with_sensitive_keyword_goes_to_pending_review(self):
        post, keyword = services.create_post(self.author, self.category, "Tieu de co camtu", "noi dung")
        self.assertEqual(post.status, ContentStatus.PENDING_REVIEW)
        self.assertIsNotNone(keyword)

    def test_post_without_sensitive_keyword_is_published(self):
        post, keyword = services.create_post(self.author, self.category, "Tieu de binh thuong", "noi dung")
        self.assertEqual(post.status, ContentStatus.PUBLISHED)
        self.assertIsNone(keyword)

    def test_update_reverts_to_pending_review_when_keyword_added(self):
        post, _ = services.create_post(self.author, self.category, "Tieu de", "noi dung")
        self.assertEqual(post.status, ContentStatus.PUBLISHED)
        post, keyword = services.update_post(post, self.author, "Tieu de", "noi dung co camtu")
        self.assertEqual(post.status, ContentStatus.PENDING_REVIEW)
        self.assertIsNotNone(keyword)


class PinLimitTests(TestCase):
    def setUp(self):
        self.staff = User.objects.create_user(email="staff1@due.udn.vn", password="Pass1234!", role=User.Role.STAFF)
        self.category = Category.objects.create(name="Chung", max_pinned=1)

    def _make_post(self, title):
        return services.create_post(
            User.objects.create_user(email=f"{title}@due.udn.vn", password="Pass1234!"),
            self.category, title, "noi dung",
        )[0]

    def test_pin_is_rejected_when_category_limit_reached(self):
        post1 = self._make_post("post1")
        post2 = self._make_post("post2")

        services.pin_post(post1, self.staff)
        self.assertTrue(post1.is_pinned)

        with self.assertRaises(PinLimitExceeded):
            services.pin_post(post2, self.staff)

        # Bai cu KHONG bi tu dong bo ghim
        post1.refresh_from_db()
        self.assertTrue(post1.is_pinned)

    def test_unpin_then_pin_new_post_succeeds(self):
        post1 = self._make_post("post1")
        post2 = self._make_post("post2")

        services.pin_post(post1, self.staff)
        services.unpin_post(post1, self.staff)
        services.pin_post(post2, self.staff)
        self.assertTrue(post2.is_pinned)


class EditHistoryTests(TestCase):
    def setUp(self):
        self.author = User.objects.create_user(email="sv2@due.udn.vn", password="Pass1234!")
        self.category = Category.objects.create(name="Chung")

    def test_edit_creates_history_snapshot_without_overwriting(self):
        post, _ = services.create_post(self.author, self.category, "Tieu de goc", "noi dung goc")
        services.update_post(post, self.author, "Tieu de moi", "noi dung moi")
        services.update_post(post, self.author, "Tieu de moi 2", "noi dung moi 2")

        self.assertEqual(post.edit_count, 2)
        self.assertEqual(post.history.count(), 2)
        # Ban ghi lich su phai luu noi dung TRUOC khi sua, theo dung thu tu
        first_snapshot = post.history.order_by("edited_at").first()
        self.assertEqual(first_snapshot.title, "Tieu de goc")


class PostCreateRateLimitTests(TestCase):
    """Gioi han 10 bai/phut cho moi user (xem @ratelimit tren PostCreateView)."""

    def setUp(self):
        cache.clear()
        self.category = Category.objects.create(name="Chung")
        self.user = User.objects.create_user(email="ratelimit1@due.udn.vn", password="Pass1234!")
        self.client.force_login(self.user)

    def test_11th_post_within_a_minute_is_blocked(self):
        for i in range(10):
            response = self.client.post(
                reverse("forum:post_create"),
                {"category": self.category.pk, "title": f"Bai {i}", "body": "noi dung", "tags": []},
            )
            self.assertEqual(response.status_code, 302, f"Bài thứ {i + 1} phải thành công")

        response = self.client.post(
            reverse("forum:post_create"),
            {"category": self.category.pk, "title": "Bai thu 11", "body": "noi dung", "tags": []},
        )
        self.assertEqual(response.status_code, 403)


class RichTextSanitizeTests(TestCase):
    """Noi dung tu CKEditor la HTML - phai loc bo the/attribute nguy hiem (XSS) truoc khi luu."""

    def setUp(self):
        self.author = User.objects.create_user(email="richtext@due.udn.vn", password="Pass1234!")
        self.category = Category.objects.create(name="Chung")

    def test_script_tag_is_stripped_on_create(self):
        malicious_body = "<p>Noi dung binh thuong</p><script>alert('xss')</script>"
        post, _ = services.create_post(self.author, self.category, "Bai test XSS", malicious_body)
        self.assertNotIn("<script>", post.body)
        self.assertIn("Noi dung binh thuong", post.body)

    def test_onerror_attribute_is_stripped_on_create(self):
        malicious_body = '<img src="x" onerror="alert(1)">'
        post, _ = services.create_post(self.author, self.category, "Bai test XSS 2", malicious_body)
        self.assertNotIn("onerror", post.body)

    def test_allowed_formatting_tags_are_kept(self):
        body = "<p><strong>Dam</strong> va <em>nghieng</em></p><ul><li>Muc 1</li></ul>"
        post, _ = services.create_post(self.author, self.category, "Bai test formatting", body)
        self.assertIn("<strong>", post.body)
        self.assertIn("<ul>", post.body)
