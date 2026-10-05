from django.test import TestCase
from django.urls import reverse

from accounts.models import User
from notifications.models import Notification

from . import services
from .models import Group, GroupMembership, GroupPost


class GroupApprovalFlowTests(TestCase):
    def setUp(self):
        self.staff = User.objects.create_user(email="staff2@due.udn.vn", password="Pass1234!", role=User.Role.STAFF)
        self.student = User.objects.create_user(email="sv3@due.udn.vn", password="Pass1234!", role=User.Role.STUDENT)
        self.lecturer = User.objects.create_user(email="gv1@due.udn.vn", password="Pass1234!", role=User.Role.LECTURER)
        self.bch = User.objects.create_user(email="bchtest1@due.udn.vn", password="Pass1234!", role=User.Role.BCH)

    def test_student_created_group_is_pending_with_no_membership_yet(self):
        group = services.request_create_group(self.student, "Nhom SV", "mo ta")
        self.assertEqual(group.status, Group.Status.PENDING)
        self.assertFalse(GroupMembership.objects.filter(group=group, user=self.student).exists())

    def test_staff_approve_activates_group_and_assigns_leader(self):
        group = services.request_create_group(self.student, "Nhom SV", "mo ta")
        services.approve_group(group, self.staff)

        group.refresh_from_db()
        self.assertEqual(group.status, Group.Status.ACTIVE)
        membership = GroupMembership.objects.get(group=group, user=self.student)
        self.assertEqual(membership.role, GroupMembership.Role.LEADER)

    def test_staff_reject_requires_reason_and_records_it(self):
        group = services.request_create_group(self.student, "Nhom SV", "mo ta")
        with self.assertRaises(ValueError):
            services.reject_group(group, self.staff, "")

        services.reject_group(group, self.staff, "Nội dung không phù hợp")
        group.refresh_from_db()
        self.assertEqual(group.status, Group.Status.REJECTED)
        self.assertEqual(group.reject_reason, "Nội dung không phù hợp")
        self.assertFalse(GroupMembership.objects.filter(group=group, user=self.student).exists())

    def test_lecturer_and_bch_groups_are_active_immediately_with_leader(self):
        for creator in (self.lecturer, self.bch):
            group = services.request_create_group(creator, f"Nhom {creator.email}", "mo ta")
            self.assertEqual(group.status, Group.Status.ACTIVE)
            membership = GroupMembership.objects.get(group=group, user=creator)
            self.assertEqual(membership.role, GroupMembership.Role.LEADER)


class GroupPostEditDeleteTests(TestCase):
    """Tac gia bai dang trong nhom (hoac Giao vu Khoa) phai sua/xoa duoc bai cua minh."""

    def setUp(self):
        self.author = User.objects.create_user(email="tacgia@due.udn.vn", password="Pass1234!", role=User.Role.STUDENT)
        self.other_member = User.objects.create_user(email="thanhvienkhac@due.udn.vn", password="Pass1234!", role=User.Role.STUDENT)
        self.group = services.request_create_group(self.author, "Nhom test edit", "mo ta")
        # Sinh vien tao nhom -> pending, tu approve de active va gan leader
        staff = User.objects.create_user(email="giaovutest@due.udn.vn", password="Pass1234!", role=User.Role.STAFF)
        services.approve_group(self.group, staff)
        GroupMembership.objects.get_or_create(group=self.group, user=self.other_member, defaults={"role": GroupMembership.Role.MEMBER})
        self.post, _ = services.create_group_post(self.group, self.author, "Tieu de goc", "noi dung goc")

    def test_author_can_edit_own_post(self):
        self.client.force_login(self.author)
        response = self.client.post(
            reverse("groups:post_edit", args=[self.group.slug, self.post.pk]),
            {"title": "Tieu de moi", "body": "noi dung moi"},
        )
        self.assertEqual(response.status_code, 302)
        self.post.refresh_from_db()
        self.assertEqual(self.post.title, "Tieu de moi")
        self.assertEqual(self.post.edit_count, 1)

    def test_other_member_cannot_edit_post(self):
        self.client.force_login(self.other_member)
        response = self.client.post(
            reverse("groups:post_edit", args=[self.group.slug, self.post.pk]),
            {"title": "Bi doi trai phep", "body": "x"},
        )
        self.assertEqual(response.status_code, 302)
        self.post.refresh_from_db()
        self.assertEqual(self.post.title, "Tieu de goc")

    def test_author_can_delete_own_post(self):
        self.client.force_login(self.author)
        response = self.client.post(reverse("groups:post_delete", args=[self.group.slug, self.post.pk]))
        self.assertEqual(response.status_code, 302)
        self.assertFalse(GroupPost.objects.filter(pk=self.post.pk).exists())


class MentionTests(TestCase):
    """@gan the thanh vien nhom - CKEditor Mention (bai dang) + hidden input (binh luan)."""

    def setUp(self):
        self.author = User.objects.create_user(email="mention-author@due.udn.vn", password="Pass1234!", role=User.Role.STUDENT)
        self.tagged = User.objects.create_user(email="mention-tagged@due.udn.vn", password="Pass1234!", role=User.Role.STUDENT)
        staff = User.objects.create_user(email="mention-staff@due.udn.vn", password="Pass1234!", role=User.Role.STAFF)
        self.group = services.request_create_group(self.author, "Nhom test mention", "mo ta")
        services.approve_group(self.group, staff)
        GroupMembership.objects.get_or_create(group=self.group, user=self.tagged, defaults={"role": GroupMembership.Role.MEMBER})

    def test_post_create_page_includes_mention_feed_for_group_member(self):
        self.client.force_login(self.author)
        response = self.client.get(reverse("groups:post_create", args=[self.group.slug]))
        self.assertContains(response, f"@user-{self.tagged.pk}")

    def test_creating_post_with_mention_span_notifies_tagged_user(self):
        self.client.force_login(self.author)
        body = f'<p>Xin chao <span class="mention" data-mention="@user-{self.tagged.pk}">@{self.tagged.get_full_name()}</span></p>'
        response = self.client.post(
            reverse("groups:post_create", args=[self.group.slug]),
            {"title": "Bai co tag", "body": body},
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(
            Notification.objects.filter(recipient=self.tagged, verb=Notification.Verb.MENTION).exists()
        )

    def test_comment_with_mentioned_user_ids_notifies_tagged_user(self):
        post, _ = services.create_group_post(self.group, self.author, "Bai test", "noi dung")
        self.client.force_login(self.author)
        response = self.client.post(
            reverse("interactions:add_comment", args=["grouppost", post.pk]),
            {"body": f"Chao @{self.tagged.get_full_name()}", "mentioned_user_ids": [str(self.tagged.pk)]},
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(
            Notification.objects.filter(recipient=self.tagged, verb=Notification.Verb.MENTION).exists()
        )

    def test_group_post_detail_renders_mention_feed_for_comments(self):
        post, _ = services.create_group_post(self.group, self.author, "Bai test 2", "noi dung")
        self.client.force_login(self.author)
        response = self.client.get(post.get_absolute_url())
        self.assertContains(response, "mentionFeedData")
        self.assertContains(response, f"@user-{self.tagged.pk}")


class GroupPostViewCountTests(TestCase):
    def setUp(self):
        self.leader = User.objects.create_user(email="vcleader1@due.udn.vn", password="Pass1234!", role=User.Role.LECTURER)
        self.group = services.request_create_group(self.leader, "Nhom Test Luot Xem", "mo ta")
        self.post, _ = services.create_group_post(self.group, self.leader, "Bai test luot xem", "noi dung")

    def test_detail_view_increments_view_count(self):
        self.assertEqual(self.post.view_count, 0)
        self.client.force_login(self.leader)
        self.client.get(reverse("groups:post_detail", args=[self.group.slug, self.post.pk]))
        self.post.refresh_from_db()
        self.assertEqual(self.post.view_count, 1)


class GroupEditDisableEnableTests(TestCase):
    def setUp(self):
        self.staff = User.objects.create_user(email="gstaff1@due.udn.vn", password="Pass1234!", role=User.Role.STAFF)
        self.leader = User.objects.create_user(email="gleader1@due.udn.vn", password="Pass1234!", role=User.Role.LECTURER)
        self.outsider = User.objects.create_user(email="goutsider1@due.udn.vn", password="Pass1234!")
        self.group = services.request_create_group(self.leader, "Nhom Test Edit", "mo ta goc")

    def test_leader_can_edit_group_info(self):
        self.client.force_login(self.leader)
        self.client.post(
            reverse("groups:edit", args=[self.group.slug]),
            {"name": "Nhom Da Doi Ten", "description": "mo ta moi"},
        )
        self.group.refresh_from_db()
        self.assertEqual(self.group.name, "Nhom Da Doi Ten")
        self.assertEqual(self.group.description, "mo ta moi")

    def test_non_leader_cannot_edit_group_info(self):
        self.client.force_login(self.outsider)
        response = self.client.post(
            reverse("groups:edit", args=[self.group.slug]),
            {"name": "Hack ten nhom", "description": ""},
        )
        self.group.refresh_from_db()
        self.assertNotEqual(self.group.name, "Hack ten nhom")

    def test_staff_can_disable_and_reenable_group(self):
        self.client.force_login(self.staff)
        self.client.post(reverse("groups:disable", args=[self.group.slug]), {"reason": "Vi pham noi quy"})
        self.group.refresh_from_db()
        self.assertEqual(self.group.status, Group.Status.DISABLED)

        response = self.client.get(reverse("groups:list"))
        self.assertNotIn(self.group, response.context["groups"])

        self.client.get(reverse("groups:enable", args=[self.group.slug]))
        self.group.refresh_from_db()
        self.assertEqual(self.group.status, Group.Status.ACTIVE)

    def test_leader_cannot_disable_group_only_staff_can(self):
        self.client.force_login(self.leader)
        response = self.client.post(reverse("groups:disable", args=[self.group.slug]), {"reason": "test"})
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.url.startswith(reverse("home")))
        self.group.refresh_from_db()
        self.assertEqual(self.group.status, Group.Status.ACTIVE)


class GroupMembershipManagementTests(TestCase):
    def setUp(self):
        self.leader = User.objects.create_user(email="mleader1@due.udn.vn", password="Pass1234!", role=User.Role.LECTURER)
        self.moderator_user = User.objects.create_user(email="mmod1@due.udn.vn", password="Pass1234!")
        self.member_user = User.objects.create_user(email="mmember1@due.udn.vn", password="Pass1234!")
        self.outsider = User.objects.create_user(email="moutsider1@due.udn.vn", password="Pass1234!")
        self.group = services.request_create_group(self.leader, "Nhom Test Member", "mo ta")
        GroupMembership.objects.create(group=self.group, user=self.moderator_user, role=GroupMembership.Role.MODERATOR)
        GroupMembership.objects.create(group=self.group, user=self.member_user, role=GroupMembership.Role.MEMBER)

    def test_leader_can_add_member_by_email(self):
        new_user = User.objects.create_user(email="mnew1@due.udn.vn", password="Pass1234!")
        self.client.force_login(self.leader)
        self.client.post(reverse("groups:member_add", args=[self.group.slug]), {"email": new_user.email})
        self.assertTrue(GroupMembership.objects.filter(group=self.group, user=new_user).exists())

    def test_cannot_add_nonexistent_email(self):
        self.client.force_login(self.leader)
        response = self.client.post(
            reverse("groups:member_add", args=[self.group.slug]), {"email": "khongtontai@due.udn.vn"}, follow=True,
        )
        messages = list(response.context["messages"])
        self.assertTrue(any("Không tìm thấy" in str(m) for m in messages))

    def test_outsider_cannot_add_member(self):
        new_user = User.objects.create_user(email="mnew2@due.udn.vn", password="Pass1234!")
        self.client.force_login(self.outsider)
        self.client.post(reverse("groups:member_add", args=[self.group.slug]), {"email": new_user.email})
        self.assertFalse(GroupMembership.objects.filter(group=self.group, user=new_user).exists())

    def test_moderator_can_remove_regular_member(self):
        self.client.force_login(self.moderator_user)
        self.client.post(reverse("groups:member_remove", args=[self.group.slug, self.member_user.pk]))
        self.assertFalse(GroupMembership.objects.filter(group=self.group, user=self.member_user).exists())

    def test_cannot_remove_leader(self):
        self.client.force_login(self.moderator_user)
        self.client.post(reverse("groups:member_remove", args=[self.group.slug, self.leader.pk]))
        self.assertTrue(GroupMembership.objects.filter(group=self.group, user=self.leader).exists())

    def test_regular_member_cannot_remove_others(self):
        self.client.force_login(self.member_user)
        self.client.post(reverse("groups:member_remove", args=[self.group.slug, self.moderator_user.pk]))
        self.assertTrue(GroupMembership.objects.filter(group=self.group, user=self.moderator_user).exists())

    def test_leader_can_promote_member_to_moderator(self):
        self.client.force_login(self.leader)
        self.client.post(
            reverse("groups:member_role", args=[self.group.slug, self.member_user.pk]), {"role": "moderator"},
        )
        membership = GroupMembership.objects.get(group=self.group, user=self.member_user)
        self.assertEqual(membership.role, GroupMembership.Role.MODERATOR)

    def test_cannot_change_leader_role(self):
        self.client.force_login(self.moderator_user)
        self.client.post(
            reverse("groups:member_role", args=[self.group.slug, self.leader.pk]), {"role": "member"},
        )
        membership = GroupMembership.objects.get(group=self.group, user=self.leader)
        self.assertEqual(membership.role, GroupMembership.Role.LEADER)

    def test_member_can_leave_group(self):
        self.client.force_login(self.member_user)
        self.client.post(reverse("groups:leave", args=[self.group.slug]))
        self.assertFalse(GroupMembership.objects.filter(group=self.group, user=self.member_user).exists())

    def test_leader_cannot_leave_group(self):
        self.client.force_login(self.leader)
        self.client.post(reverse("groups:leave", args=[self.group.slug]))
        self.assertTrue(GroupMembership.objects.filter(group=self.group, user=self.leader).exists())
