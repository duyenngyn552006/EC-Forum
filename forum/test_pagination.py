"""Test phan trang danh sach dien dan (10 bai/trang) + tag phan trang dung chung."""
from django.core.paginator import Paginator
from django.test import RequestFactory, TestCase
from django.urls import reverse

from accounts.models import User
from config.pagination_tags import page_url, page_window

from .models import Category, ForumPost, Tag


class ForumPaginationTests(TestCase):
    def setUp(self):
        self.author = User.objects.create_user(email="pg-author@due.udn.vn", password="Pass1234!")
        self.category = Category.objects.create(name="PagCat")
        self.tag = Tag.objects.create(name="pagtag")
        # Loc theo chuyen muc rieng cua test (DB test da co san bai viet mau tu migration seed)
        self.url = reverse("forum:post_list_by_category", args=[self.category.slug])
        for i in range(23):
            p = ForumPost.objects.create(author=self.author, category=self.category, title=f"Bai so {i:02d}", body="x", status="published")
            if i % 2 == 0:
                p.tags.add(self.tag)

    def test_ten_posts_per_page(self):
        response = self.client.get(self.url)
        self.assertEqual(len(response.context["posts"]), 10)
        self.assertEqual(response.context["page_obj"].paginator.num_pages, 3)

    def test_last_page_has_remaining_posts(self):
        response = self.client.get(self.url, {"page": 3})
        self.assertEqual(len(response.context["posts"]), 3)

    def test_pagination_controls_rendered(self):
        response = self.client.get(self.url)
        self.assertContains(response, 'aria-label="Phân trang"')
        self.assertContains(response, 'aria-current="page">1<')
        self.assertContains(response, 'href="?page=2"')
        self.assertContains(response, "Hiển thị 1–10 trên tổng 23 bài viết")

    def test_links_keep_filters(self):
        response = self.client.get(reverse("forum:post_list"), {"tag": "pagtag", "sort": "activity"})
        # 12 bai co the -> 2 trang, link trang 2 van giu tag + sort
        self.assertEqual(response.context["page_obj"].paginator.num_pages, 2)
        self.assertContains(response, 'href="?tag=pagtag&amp;sort=activity&amp;page=2"')

    def test_no_pagination_when_single_page(self):
        response = self.client.get(reverse("forum:post_list"), {"tag": "khong-co"})
        self.assertNotContains(response, 'aria-label="Phân trang"')


class PaginationTagTests(TestCase):
    def _page(self, number, total_pages):
        return Paginator(range(total_pages * 10), 10).page(number)

    def test_window_with_gaps(self):
        self.assertEqual(page_window(self._page(6, 12)), [1, None, 4, 5, 6, 7, 8, None, 12])

    def test_window_near_start_and_end(self):
        self.assertEqual(page_window(self._page(1, 12)), [1, 2, 3, None, 12])
        self.assertEqual(page_window(self._page(12, 12)), [1, None, 10, 11, 12])

    def test_window_small_total_has_no_gaps(self):
        self.assertEqual(page_window(self._page(2, 3)), [1, 2, 3])

    def test_page_url_replaces_existing_page_param(self):
        request = RequestFactory().get("/forum/", {"kind": "question", "page": "5"})
        self.assertEqual(page_url({"request": request}, 2), "?kind=question&page=2")
        self.assertEqual(page_url({"request": RequestFactory().get("/forum/")}, 3), "?page=3")
