"""Test hoi dap: danh dau bai la cau hoi, chon/bo chon cau tra loi, thong bao, bo loc danh sach."""
from django.contrib.contenttypes.models import ContentType
from django.test import TestCase
from django.urls import reverse

from accounts.models import User
from interactions.models import Comment
from notifications.models import Notification

from . import services
from .models import Category, ForumPost


class AcceptedAnswerTests(TestCase):
    def setUp(self):
        self.asker = User.objects.create_user(email="qa-asker@due.udn.vn", password="Pass1234!")
        self.answerer = User.objects.create_user(email="qa-answerer@due.udn.vn", password="Pass1234!")
        self.bystander = User.objects.create_user(email="qa-bystander@due.udn.vn", password="Pass1234!")
        self.lecturer = User.objects.create_user(email="qa-lec@due.udn.vn", password="Pass1234!", role=User.Role.LECTURER)
        self.bch = User.objects.create_user(email="qa-bch@due.udn.vn", password="Pass1234!", role=User.Role.BCH)
        self.category = Category.objects.create(name="QACat")
        self.question = ForumPost.objects.create(
            author=self.asker, category=self.category, title="Cau hoi", body="x", status="published", is_question=True,
        )
        self.content_type = ContentType.objects.get_for_model(ForumPost)
        self.answer = self._comment(self.answerer, "Tra loi dung")
        self.other_answer = self._comment(self.bystander, "Tra loi khac")

    def _comment(self, author, body, post=None, **kwargs):
        post = post or self.question
        return Comment.objects.create(author=author, content_type=self.content_type, object_id=post.pk, body=body, **kwargs)

    def _accept(self, user, comment, post=None):
        post = post or self.question
        self.client.force_login(user)
        return self.client.post(reverse("forum:accept_answer", args=[post.pk, comment.pk]))

    def test_asker_can_accept_answer_and_author_is_notified(self):
        self._accept(self.asker, self.answer)
        self.question.refresh_from_db()
        self.assertEqual(self.question.accepted_answer_id, self.answer.pk)
        self.assertTrue(Notification.objects.filter(
            recipient=self.answerer, verb=Notification.Verb.ANSWER_ACCEPTED, actor=self.asker,
        ).exists())

    def test_lecturer_can_accept_answer_on_someone_elses_question(self):
        self._accept(self.lecturer, self.answer)
        self.question.refresh_from_db()
        self.assertEqual(self.question.accepted_answer_id, self.answer.pk)

    def test_bch_and_random_user_cannot_accept_answer(self):
        self._accept(self.bch, self.answer)
        self._accept(self.bystander, self.answer)
        self.question.refresh_from_db()
        self.assertIsNone(self.question.accepted_answer_id)

    def test_accepting_another_answer_replaces_previous(self):
        self._accept(self.asker, self.answer)
        self._accept(self.asker, self.other_answer)
        self.question.refresh_from_db()
        self.assertEqual(self.question.accepted_answer_id, self.other_answer.pk)

    def test_accepting_same_answer_again_unaccepts_without_new_notification(self):
        self._accept(self.asker, self.answer)
        self._accept(self.asker, self.answer)
        self.question.refresh_from_db()
        self.assertIsNone(self.question.accepted_answer_id)
        self.assertEqual(Notification.objects.filter(verb=Notification.Verb.ANSWER_ACCEPTED).count(), 1)

    def test_no_notification_when_accepting_own_comment(self):
        own = self._comment(self.asker, "Tu tra loi")
        self._accept(self.asker, own)
        self.assertFalse(Notification.objects.filter(verb=Notification.Verb.ANSWER_ACCEPTED).exists())

    def test_cannot_accept_on_non_question_post(self):
        plain = ForumPost.objects.create(author=self.asker, category=self.category, title="Bai thuong", body="x", status="published")
        comment = self._comment(self.answerer, "Binh luan", post=plain)
        self._accept(self.asker, comment, post=plain)
        plain.refresh_from_db()
        self.assertIsNone(plain.accepted_answer_id)

    def test_cannot_accept_comment_from_another_post(self):
        other = ForumPost.objects.create(author=self.asker, category=self.category, title="Bai khac", body="x", status="published", is_question=True)
        foreign = self._comment(self.answerer, "Binh luan bai khac", post=other)
        response = self._accept(self.asker, foreign)
        self.assertEqual(response.status_code, 404)
        self.question.refresh_from_db()
        self.assertIsNone(self.question.accepted_answer_id)

    def test_cannot_accept_comment_pending_review(self):
        pending = self._comment(self.answerer, "Cho duyet", status=Comment.Status.PENDING_REVIEW)
        response = self._accept(self.asker, pending)
        self.assertEqual(response.status_code, 404)

    def test_deleting_accepted_comment_clears_answer(self):
        self._accept(self.asker, self.answer)
        self.answer.delete()
        self.question.refresh_from_db()
        self.assertIsNone(self.question.accepted_answer_id)

    def test_detail_page_shows_accept_button_only_to_allowed_users(self):
        url = self.question.get_absolute_url()
        accept_url = reverse("forum:accept_answer", args=[self.question.pk, self.answer.pk])
        self.client.force_login(self.asker)
        self.assertContains(self.client.get(url), accept_url)
        self.client.force_login(self.bystander)
        self.assertNotContains(self.client.get(url), accept_url)

    def test_detail_page_marks_accepted_answer(self):
        self._accept(self.asker, self.answer)
        response = self.client.get(self.question.get_absolute_url())
        self.assertContains(response, "Câu trả lời được chọn")
        self.assertContains(response, "Đã giải đáp")


class QuestionFlagTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(email="qf-user@due.udn.vn", password="Pass1234!")
        self.category = Category.objects.create(name="QFCat")

    def test_create_post_as_question(self):
        post, _ = services.create_post(self.user, self.category, "Hoi", "noi dung", is_question=True)
        self.assertTrue(post.is_question)

    def test_unmarking_question_clears_accepted_answer(self):
        post, _ = services.create_post(self.user, self.category, "Hoi", "noi dung", is_question=True)
        comment = Comment.objects.create(
            author=self.user, content_type=ContentType.objects.get_for_model(ForumPost), object_id=post.pk, body="tl",
        )
        post.accepted_answer = comment
        post.save()
        services.update_post(post, self.user, "Hoi", "noi dung", is_question=False)
        post.refresh_from_db()
        self.assertFalse(post.is_question)
        self.assertIsNone(post.accepted_answer_id)

    def test_update_without_flag_keeps_question_state(self):
        post, _ = services.create_post(self.user, self.category, "Hoi", "noi dung", is_question=True)
        services.update_post(post, self.user, "Hoi sua", "noi dung")
        post.refresh_from_db()
        self.assertTrue(post.is_question)

    def test_form_checkbox_creates_question(self):
        self.client.force_login(self.user)
        self.client.post(reverse("forum:post_create"), {
            "category": self.category.pk, "title": "Co hoi", "body": "<p>noi dung</p>", "is_question": "on",
        })
        self.assertTrue(ForumPost.objects.get(title="Co hoi").is_question)

    def test_list_filter_question_and_unsolved(self):
        solved, _ = services.create_post(self.user, self.category, "Da giai dap", "x", is_question=True)
        unsolved, _ = services.create_post(self.user, self.category, "Chua giai dap", "x", is_question=True)
        services.create_post(self.user, self.category, "Bai thuong", "x")
        comment = Comment.objects.create(
            author=self.user, content_type=ContentType.objects.get_for_model(ForumPost), object_id=solved.pk, body="tl",
        )
        solved.accepted_answer = comment
        solved.save()

        def titles(kind):
            response = self.client.get(reverse("forum:post_list"), {"kind": kind})
            return {p.title for p in response.context["posts"]}

        self.assertEqual(titles("question"), {"Da giai dap", "Chua giai dap"})
        self.assertEqual(titles("unsolved"), {"Chua giai dap"})
