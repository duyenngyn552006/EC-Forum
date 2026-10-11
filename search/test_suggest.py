"""Test goi y tim kiem truc tiep (/search/suggest/)."""
from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse

from accounts.models import User
from announcements.models import Announcement
from forum.models import Category, ForumPost
from groups.models import Group

WORD = "zebraxyz"  # tu hiem de khong trung du lieu mau tu migration seed


class SuggestTests(TestCase):
    def setUp(self):
        cache.clear()
        self.addCleanup(cache.clear)
        self.student = User.objects.create_user(email="sg-sv@due.udn.vn", password="Pass1234!")
        self.staff = User.objects.create_user(email="sg-staff@due.udn.vn", password="Pass1234!", role=User.Role.STAFF)
        self.category = Category.objects.create(name="SuggestCat")
        ForumPost.objects.create(author=self.student, category=self.category, title=f"Hoi ve {WORD} python", body="x", status="published")
        ForumPost.objects.create(author=self.student, category=self.category, title=f"Bai {WORD} cho duyet", body="x", status="pending_review")
        ForumPost.objects.create(author=self.student, category=self.category, title="Khong lien quan", body=f"noi dung co {WORD}", status="published")
        Announcement.objects.create(author=self.staff, title=f"Thong bao {WORD.upper()}", body="x", status="published")
        Group.objects.create(name=f"CLB {WORD}", created_by=self.staff, status=Group.Status.ACTIVE)
        Group.objects.create(name=f"Nhom {WORD} cho duyet", created_by=self.student, status=Group.Status.PENDING)

    def _titles(self, q, user=None):
        if user:
            self.client.force_login(user)
        response = self.client.get(reverse("search:suggest"), {"q": q})
        self.assertEqual(response.status_code, 200)
        return [r["title"] for r in response.json()["results"]]

    def test_matches_titles_case_insensitive_across_types(self):
        titles = self._titles(WORD)
        self.assertIn(f"Hoi ve {WORD} python", titles)
        self.assertIn(f"Thong bao {WORD.upper()}", titles)
        self.assertIn(f"CLB {WORD}", titles)

    def test_matches_title_only_not_body(self):
        self.assertNotIn("Khong lien quan", self._titles(WORD))

    def test_pending_content_hidden_from_students_and_anonymous(self):
        for user in (None, self.student):
            titles = self._titles(WORD, user)
            self.assertNotIn(f"Bai {WORD} cho duyet", titles)
            self.assertNotIn(f"Nhom {WORD} cho duyet", titles)  # nhom chua duyet khong bao gio hien

    def test_staff_sees_pending_posts(self):
        self.assertIn(f"Bai {WORD} cho duyet", self._titles(WORD, self.staff))

    def test_short_query_returns_nothing(self):
        self.assertEqual(self._titles("z"), [])

    def test_result_shape_and_limit(self):
        for i in range(12):
            ForumPost.objects.create(author=self.student, category=self.category, title=f"{WORD} so {i}", body="x", status="published")
        response = self.client.get(reverse("search:suggest"), {"q": WORD})
        results = response.json()["results"]
        self.assertEqual(len(results), 8)
        self.assertEqual(set(results[0]), {"type", "type_label", "title", "url", "meta"})
        self.assertEqual(results[0]["type"], "group")  # nhom dua len dau

    def test_does_not_record_search_history(self):
        self._titles(WORD, self.student)
        self.assertFalse(self.student.search_history.exists())

    def test_header_has_suggest_url(self):
        response = self.client.get(reverse("home"))
        self.assertContains(response, f'data-suggest-url="{reverse("search:suggest")}"')
