from django.contrib.contenttypes.models import ContentType
from django.test import TestCase
from django.urls import reverse

from accounts.models import User
from forum.models import Category, ForumPost
from notifications.models import Notification

from .models import Comment
from .utils import get_top_level_comments


class ReplyToCommentTests(TestCase):
    """Tra loi binh luan (threaded, 1 cap) - giong Facebook: nut Tra loi, hien thi long ben duoi."""

    def setUp(self):
        self.author = User.objects.create_user(email="post-author@due.udn.vn", password="Pass1234!")
        self.commenter = User.objects.create_user(email="commenter@due.udn.vn", password="Pass1234!")
        self.replier = User.objects.create_user(email="replier@due.udn.vn", password="Pass1234!")
        category = Category.objects.create(name="ReplyCat")
        self.post = ForumPost.objects.create(author=self.author, category=category, title="Bai test reply", body="noi dung", status="published")
        self.content_type = ContentType.objects.get_for_model(ForumPost)
        self.top_comment = Comment.objects.create(
            author=self.commenter, content_type=self.content_type, object_id=self.post.pk, body="Binh luan goc",
        )

    def test_reply_saved_with_correct_parent(self):
        self.client.force_login(self.replier)
        response = self.client.post(
            reverse("interactions:add_comment", args=["forumpost", self.post.pk]),
            {"body": "Day la reply", "parent_id": self.top_comment.pk},
        )
        self.assertEqual(response.status_code, 302)
        reply = Comment.objects.get(body="Day la reply")
        self.assertEqual(reply.parent_id, self.top_comment.pk)

    def test_reply_notifies_parent_comment_author(self):
        self.client.force_login(self.replier)
        self.client.post(
            reverse("interactions:add_comment", args=["forumpost", self.post.pk]),
            {"body": "Day la reply", "parent_id": self.top_comment.pk},
        )
        self.assertTrue(
            Notification.objects.filter(recipient=self.commenter, verb=Notification.Verb.COMMENT).exists()
        )

    def test_top_level_comments_prefetch_includes_published_replies(self):
        Comment.objects.create(
            author=self.replier, content_type=self.content_type, object_id=self.post.pk,
            parent=self.top_comment, body="Reply da duyet", status="published",
        )
        comments = list(get_top_level_comments(self.content_type, self.post.pk))
        self.assertEqual(len(comments), 1)
        replies = list(comments[0].replies.all())
        self.assertEqual(len(replies), 1)
        self.assertEqual(replies[0].body, "Reply da duyet")

    def test_reply_form_and_button_render_on_detail_page(self):
        self.client.force_login(self.replier)
        response = self.client.get(self.post.get_absolute_url())
        self.assertContains(response, "Trả lời")
        self.assertContains(response, f'id="reply-form-{self.top_comment.pk}"')


class EditDeleteCommentTests(TestCase):
    """Tac gia binh luan (hoac Giao vu Khoa) sua/xoa duoc binh luan cua minh, nguoi khac thi khong."""

    def setUp(self):
        self.author = User.objects.create_user(email="edc-author@due.udn.vn", password="Pass1234!")
        self.commenter = User.objects.create_user(email="edc-commenter@due.udn.vn", password="Pass1234!")
        self.other_user = User.objects.create_user(email="edc-other@due.udn.vn", password="Pass1234!")
        self.staff = User.objects.create_user(email="edc-staff@due.udn.vn", password="Pass1234!", role=User.Role.STAFF)
        category = Category.objects.create(name="EditDeleteCat")
        self.post = ForumPost.objects.create(author=self.author, category=category, title="Bai test edit", body="noi dung", status="published")
        content_type = ContentType.objects.get_for_model(ForumPost)
        self.comment = Comment.objects.create(
            author=self.commenter, content_type=content_type, object_id=self.post.pk, body="Noi dung goc",
        )

    def test_author_can_edit_own_comment(self):
        self.client.force_login(self.commenter)
        response = self.client.post(
            reverse("interactions:edit_comment", args=[self.comment.pk]), {"body": "Noi dung moi"}
        )
        self.assertEqual(response.status_code, 302)
        self.comment.refresh_from_db()
        self.assertEqual(self.comment.body, "Noi dung moi")
        self.assertTrue(self.comment.is_edited)

    def test_other_user_cannot_edit_comment(self):
        self.client.force_login(self.other_user)
        response = self.client.post(
            reverse("interactions:edit_comment", args=[self.comment.pk]), {"body": "Bi doi trai phep"}
        )
        self.assertEqual(response.status_code, 302)
        self.comment.refresh_from_db()
        self.assertEqual(self.comment.body, "Noi dung goc")

    def test_staff_can_edit_any_comment(self):
        self.client.force_login(self.staff)
        response = self.client.post(
            reverse("interactions:edit_comment", args=[self.comment.pk]), {"body": "Giao vu sua"}
        )
        self.assertEqual(response.status_code, 302)
        self.comment.refresh_from_db()
        self.assertEqual(self.comment.body, "Giao vu sua")

    def test_author_can_delete_own_comment(self):
        self.client.force_login(self.commenter)
        response = self.client.post(reverse("interactions:delete_comment", args=[self.comment.pk]))
        self.assertEqual(response.status_code, 302)
        self.assertFalse(Comment.objects.filter(pk=self.comment.pk).exists())

    def test_other_user_cannot_delete_comment(self):
        self.client.force_login(self.other_user)
        response = self.client.post(reverse("interactions:delete_comment", args=[self.comment.pk]))
        self.assertEqual(response.status_code, 302)
        self.assertTrue(Comment.objects.filter(pk=self.comment.pk).exists())

    def test_edit_and_delete_buttons_render_for_author_only(self):
        self.client.force_login(self.commenter)
        response = self.client.get(self.post.get_absolute_url())
        self.assertContains(response, f"toggleEditForm({self.comment.pk})")

        self.client.force_login(self.other_user)
        response = self.client.get(self.post.get_absolute_url())
        self.assertNotContains(response, f"toggleEditForm({self.comment.pk})")
