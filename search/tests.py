from django.contrib.auth.models import AnonymousUser
from django.test import TestCase
from django.urls import reverse

from accounts.models import User
from announcements.models import Announcement
from config.mixins import ContentStatus
from forum.models import Category, ForumPost

from .models import SearchHistory
from .services import MAX_HISTORY_PER_USER, record_search


class SearchHistoryServiceTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(email="sv1@due.udn.vn", password="Pass1234!")

    def test_record_search_saves_query_for_logged_in_user(self):
        record_search(self.user, "chuyen de tot nghiep")
        self.assertEqual(SearchHistory.objects.filter(user=self.user).count(), 1)
        self.assertEqual(SearchHistory.objects.first().query, "chuyen de tot nghiep")

    def test_repeated_query_is_deduplicated_not_duplicated(self):
        record_search(self.user, "hoc bong")
        record_search(self.user, "Hoc Bong")  # khac hoa/thuong - van tinh la 1 query
        self.assertEqual(SearchHistory.objects.filter(user=self.user).count(), 1)

    def test_blank_query_is_not_saved(self):
        record_search(self.user, "   ")
        self.assertEqual(SearchHistory.objects.count(), 0)

    def test_history_is_capped_at_max_per_user(self):
        for i in range(MAX_HISTORY_PER_USER + 5):
            record_search(self.user, f"tu khoa {i}")
        self.assertEqual(SearchHistory.objects.filter(user=self.user).count(), MAX_HISTORY_PER_USER)

    def test_anonymous_user_search_is_not_saved(self):
        record_search(AnonymousUser(), "khach vang lai")
        self.assertEqual(SearchHistory.objects.count(), 0)


class SearchViewTests(TestCase):
    def setUp(self):
        self.student = User.objects.create_user(
            email="sv2@due.udn.vn", password="Pass1234!", first_name="An", last_name="Nguyen Van",
            class_name="23K5",
        )
        self.staff = User.objects.create_user(email="staff_search@due.udn.vn", password="Pass1234!", role=User.Role.STAFF)
        self.category = Category.objects.create(name="Hoc tap")

        self.published_post = ForumPost.objects.create(
            author=self.student, category=self.category, title="Hoi ve do an tot nghiep",
            body="noi dung thao luan", status=ContentStatus.PUBLISHED,
        )
        self.pending_post = ForumPost.objects.create(
            author=self.student, category=self.category, title="Bai cho duyet do an",
            body="noi dung nhay cam", status=ContentStatus.PENDING_REVIEW,
        )
        self.announcement = Announcement.objects.create(
            author=self.staff, title="Thong bao do an tot nghiep", body="noi dung thong bao",
            status=ContentStatus.PUBLISHED,
        )

    def test_search_by_keyword_matches_title_across_content_types(self):
        response = self.client.get(reverse("search:results"), {"q": "do an"})
        titles = [r["object"].title for r in response.context["page_obj"]]
        self.assertIn(self.published_post.title, titles)
        self.assertIn(self.announcement.title, titles)

    def test_pending_review_content_hidden_from_regular_user(self):
        self.client.force_login(self.student)
        response = self.client.get(reverse("search:results"), {"q": "do an"})
        titles = [r["object"].title for r in response.context["page_obj"]]
        self.assertNotIn(self.pending_post.title, titles)

    def test_staff_can_see_pending_review_content_in_search(self):
        self.client.force_login(self.staff)
        response = self.client.get(reverse("search:results"), {"q": "do an"})
        titles = [r["object"].title for r in response.context["page_obj"]]
        self.assertIn(self.pending_post.title, titles)

    def test_filter_by_class_name(self):
        other_student = User.objects.create_user(
            email="sv3@due.udn.vn", password="Pass1234!", class_name="23K6",
        )
        ForumPost.objects.create(
            author=other_student, category=self.category, title="Bai cua lop khac",
            body="noi dung", status=ContentStatus.PUBLISHED,
        )
        response = self.client.get(reverse("search:results"), {"class_name": "23K5"})
        titles = [r["object"].title for r in response.context["page_obj"]]
        self.assertIn(self.published_post.title, titles)
        self.assertNotIn("Bai cua lop khac", titles)

    def test_content_type_filter_restricts_to_one_model(self):
        response = self.client.get(reverse("search:results"), {"q": "do an", "type": "announcement"})
        type_keys = {r["type_key"] for r in response.context["page_obj"]}
        self.assertEqual(type_keys, {"announcement"})

    def test_search_with_query_saves_history_for_logged_in_user(self):
        self.client.force_login(self.student)
        self.client.get(reverse("search:results"), {"q": "do an tot nghiep"})
        self.assertTrue(SearchHistory.objects.filter(user=self.student, query="do an tot nghiep").exists())

    def test_search_without_login_does_not_save_history(self):
        self.client.get(reverse("search:results"), {"q": "do an tot nghiep"})
        self.assertEqual(SearchHistory.objects.count(), 0)

    def test_clear_history_removes_all_rows_for_current_user(self):
        self.client.force_login(self.student)
        record_search(self.student, "abc")
        response = self.client.post(reverse("search:clear_history"))
        self.assertRedirects(response, reverse("search:results"))
        self.assertEqual(SearchHistory.objects.filter(user=self.student).count(), 0)
