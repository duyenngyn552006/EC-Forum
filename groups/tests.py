from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse

from accounts.models import User
from config.mixins import ContentStatus
from moderation.models import ModerationLog, SensitiveKeyword
from notifications.models import Notification

from . import services
from .models import Group, GroupInvitation, GroupJoinRequest, GroupMembership, GroupPost


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

    def test_leader_can_invite_member_by_email(self):
        new_user = User.objects.create_user(email="mnew1@due.udn.vn", password="Pass1234!")
        self.client.force_login(self.leader)
        self.client.post(reverse("groups:member_add", args=[self.group.slug]), {"email": new_user.email})
        self.assertTrue(GroupMembership.objects.filter(group=self.group, user=new_user).exists())
        self.assertTrue(
            GroupInvitation.objects.filter(
                group=self.group, invited_user=new_user, status=GroupInvitation.Status.ACCEPTED,
            ).exists()
        )

    def test_cannot_invite_nonexistent_email(self):
        self.client.force_login(self.leader)
        response = self.client.post(
            reverse("groups:member_add", args=[self.group.slug]), {"email": "khongtontai@due.udn.vn"}, follow=True,
        )
        messages = list(response.context["messages"])
        self.assertTrue(any("Không tìm thấy" in str(m) for m in messages))

    def test_cannot_invite_email_outside_school_domain(self):
        self.client.force_login(self.leader)
        response = self.client.post(
            reverse("groups:member_add", args=[self.group.slug]), {"email": "someone@gmail.com"}, follow=True,
        )
        messages = list(response.context["messages"])
        self.assertTrue(any("không đúng domain" in str(m) for m in messages))

    def test_cannot_invite_existing_member(self):
        self.client.force_login(self.leader)
        response = self.client.post(
            reverse("groups:member_add", args=[self.group.slug]), {"email": self.member_user.email}, follow=True,
        )
        messages = list(response.context["messages"])
        self.assertTrue(any("đã là thành viên" in str(m) for m in messages))

    def test_outsider_cannot_invite_member(self):
        new_user = User.objects.create_user(email="mnew2@due.udn.vn", password="Pass1234!")
        self.client.force_login(self.outsider)
        self.client.post(reverse("groups:member_add", args=[self.group.slug]), {"email": new_user.email})
        self.assertFalse(GroupMembership.objects.filter(group=self.group, user=new_user).exists())
        self.assertFalse(GroupInvitation.objects.filter(group=self.group, invited_user=new_user).exists())


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

    def test_leader_leaving_auto_promotes_moderator_to_leader(self):
        self.client.force_login(self.leader)
        self.client.post(reverse("groups:leave", args=[self.group.slug]))
        self.assertFalse(GroupMembership.objects.filter(group=self.group, user=self.leader).exists())
        moderator_membership = GroupMembership.objects.get(group=self.group, user=self.moderator_user)
        self.assertEqual(moderator_membership.role, GroupMembership.Role.LEADER)

    def test_leader_cannot_leave_without_successor(self):
        GroupMembership.objects.filter(group=self.group, user=self.moderator_user).delete()
        self.client.force_login(self.leader)
        response = self.client.post(reverse("groups:leave", args=[self.group.slug]), follow=True)
        self.assertTrue(GroupMembership.objects.filter(group=self.group, user=self.leader).exists())
        messages = list(response.context["messages"])
        self.assertTrue(any("trưởng nhóm duy nhất" in str(m) for m in messages))

    def test_leader_can_transfer_leadership_then_leave(self):
        GroupMembership.objects.filter(group=self.group, user=self.moderator_user).delete()
        self.client.force_login(self.leader)
        self.client.post(
            reverse("groups:transfer_leadership", args=[self.group.slug]), {"new_leader_id": self.member_user.pk},
        )
        new_leader_membership = GroupMembership.objects.get(group=self.group, user=self.member_user)
        self.assertEqual(new_leader_membership.role, GroupMembership.Role.LEADER)
        old_leader_membership = GroupMembership.objects.get(group=self.group, user=self.leader)
        self.assertEqual(old_leader_membership.role, GroupMembership.Role.MODERATOR)

        self.client.post(reverse("groups:leave", args=[self.group.slug]))
        self.assertFalse(GroupMembership.objects.filter(group=self.group, user=self.leader).exists())

    def test_non_leader_cannot_transfer_leadership(self):
        self.client.force_login(self.moderator_user)
        self.client.post(
            reverse("groups:transfer_leadership", args=[self.group.slug]), {"new_leader_id": self.member_user.pk},
        )
        self.assertEqual(
            GroupMembership.objects.get(group=self.group, user=self.leader).role, GroupMembership.Role.LEADER,
        )
        self.assertEqual(
            GroupMembership.objects.get(group=self.group, user=self.member_user).role, GroupMembership.Role.MEMBER,
        )


class GroupJoinRequestTests(TestCase):
    def setUp(self):
        self.leader = User.objects.create_user(email="jrleader1@due.udn.vn", password="Pass1234!", role=User.Role.LECTURER)
        self.applicant = User.objects.create_user(email="jrapplicant1@due.udn.vn", password="Pass1234!")
        self.group = services.request_create_group(self.leader, "Nhom Test Join Request", "mo ta")

    def test_user_can_request_to_join_group(self):
        self.client.force_login(self.applicant)
        self.client.post(reverse("groups:join_request_create", args=[self.group.slug]), {"message": "Cho em vao nhom voi"})
        self.assertTrue(
            GroupJoinRequest.objects.filter(
                group=self.group, user=self.applicant, status=GroupJoinRequest.Status.PENDING,
            ).exists()
        )

    def test_cannot_request_twice_while_pending(self):
        self.client.force_login(self.applicant)
        self.client.post(reverse("groups:join_request_create", args=[self.group.slug]), {"message": ""})
        self.client.post(reverse("groups:join_request_create", args=[self.group.slug]), {"message": ""})
        self.assertEqual(
            GroupJoinRequest.objects.filter(group=self.group, user=self.applicant).count(), 1,
        )

    def test_leader_can_approve_join_request(self):
        join_request = services.request_to_join_group(self.group, self.applicant)
        self.client.force_login(self.leader)
        self.client.post(reverse("groups:join_request_approve", args=[self.group.slug, join_request.pk]))
        self.assertTrue(GroupMembership.objects.filter(group=self.group, user=self.applicant).exists())
        join_request.refresh_from_db()
        self.assertEqual(join_request.status, GroupJoinRequest.Status.ACCEPTED)

    def test_leader_can_reject_join_request_with_reason(self):
        join_request = services.request_to_join_group(self.group, self.applicant)
        self.client.force_login(self.leader)
        self.client.post(
            reverse("groups:join_request_reject", args=[self.group.slug, join_request.pk]), {"reason": "Khong phu hop"},
        )
        self.assertFalse(GroupMembership.objects.filter(group=self.group, user=self.applicant).exists())
        join_request.refresh_from_db()
        self.assertEqual(join_request.status, GroupJoinRequest.Status.REJECTED)
        self.assertEqual(join_request.reject_reason, "Khong phu hop")

    def test_reject_without_reason_does_not_change_status(self):
        join_request = services.request_to_join_group(self.group, self.applicant)
        self.client.force_login(self.leader)
        self.client.post(reverse("groups:join_request_reject", args=[self.group.slug, join_request.pk]), {"reason": ""})
        join_request.refresh_from_db()
        self.assertEqual(join_request.status, GroupJoinRequest.Status.PENDING)

    def test_non_manager_cannot_approve_join_request(self):
        outsider = User.objects.create_user(email="jroutsider1@due.udn.vn", password="Pass1234!")
        join_request = services.request_to_join_group(self.group, self.applicant)
        self.client.force_login(outsider)
        self.client.post(reverse("groups:join_request_approve", args=[self.group.slug, join_request.pk]))
        self.assertFalse(GroupMembership.objects.filter(group=self.group, user=self.applicant).exists())

    def test_cannot_request_to_join_if_already_member(self):
        GroupMembership.objects.create(group=self.group, user=self.applicant, role=GroupMembership.Role.MEMBER)
        self.client.force_login(self.applicant)
        response = self.client.post(
            reverse("groups:join_request_create", args=[self.group.slug]), {"message": ""}, follow=True,
        )
        messages = list(response.context["messages"])
        self.assertTrue(any("đã là thành viên" in str(m) for m in messages))
        self.assertFalse(GroupJoinRequest.objects.filter(group=self.group, user=self.applicant).exists())


class GroupBulkInviteTests(TestCase):
    def setUp(self):
        self.leader = User.objects.create_user(email="bileader1@due.udn.vn", password="Pass1234!", role=User.Role.LECTURER)
        self.outsider = User.objects.create_user(email="bioutsider1@due.udn.vn", password="Pass1234!")
        self.group = services.request_create_group(self.leader, "Nhom Test Bulk Invite", "mo ta")

    def _csv(self, content):
        return SimpleUploadedFile("members.csv", content.encode("utf-8"), content_type="text/csv")

    def test_leader_can_bulk_invite_valid_emails(self):
        u1 = User.objects.create_user(email="bi1@due.udn.vn", password="Pass1234!")
        u2 = User.objects.create_user(email="bi2@due.udn.vn", password="Pass1234!")
        csv_content = "email\nbi1@due.udn.vn\nbi2@due.udn.vn\n"
        self.client.force_login(self.leader)
        self.client.post(
            reverse("groups:member_bulk_invite", args=[self.group.slug]), {"csv_file": self._csv(csv_content)},
        )
        self.assertTrue(GroupMembership.objects.filter(group=self.group, user=u1).exists())
        self.assertTrue(GroupMembership.objects.filter(group=self.group, user=u2).exists())

    def test_bulk_invite_reports_invalid_rows_without_failing_others(self):
        u1 = User.objects.create_user(email="bi3@due.udn.vn", password="Pass1234!")
        csv_content = "bi3@due.udn.vn\nkhongtontai@due.udn.vn\n"
        self.client.force_login(self.leader)
        response = self.client.post(
            reverse("groups:member_bulk_invite", args=[self.group.slug]), {"csv_file": self._csv(csv_content)},
            follow=True,
        )
        self.assertTrue(GroupMembership.objects.filter(group=self.group, user=u1).exists())
        messages = list(response.context["messages"])
        self.assertTrue(any("khongtontai@due.udn.vn" in str(m) for m in messages))

    def test_outsider_cannot_bulk_invite(self):
        u1 = User.objects.create_user(email="bi4@due.udn.vn", password="Pass1234!")
        csv_content = "bi4@due.udn.vn\n"
        self.client.force_login(self.outsider)
        self.client.post(
            reverse("groups:member_bulk_invite", args=[self.group.slug]), {"csv_file": self._csv(csv_content)},
        )
        self.assertFalse(GroupMembership.objects.filter(group=self.group, user=u1).exists())

    def test_bulk_invite_reports_emails_outside_school_domain(self):
        csv_content = "email\nsomeone@gmail.com\n"
        self.client.force_login(self.leader)
        response = self.client.post(
            reverse("groups:member_bulk_invite", args=[self.group.slug]), {"csv_file": self._csv(csv_content)},
            follow=True,
        )
        messages = list(response.context["messages"])
        self.assertTrue(any("không đúng domain" in str(m) for m in messages))

    def test_non_csv_file_rejected(self):
        self.client.force_login(self.leader)
        bad_file = SimpleUploadedFile("members.txt", b"bi5@due.udn.vn", content_type="text/plain")
        response = self.client.post(
            reverse("groups:member_bulk_invite", args=[self.group.slug]), {"csv_file": bad_file}, follow=True,
        )
        messages = list(response.context["messages"])
        self.assertTrue(any("Chỉ chấp nhận tệp .csv" in str(m) for m in messages))


class GroupPostModerationByLeaderTests(TestCase):
    """Bai viet trong nhom dinh tu khoa nhay cam -> pending_review -> do TRUONG/PHO NHOM
    tu duyet, khong qua Giao vu Khoa (khac ForumPost/Announcement)."""

    def setUp(self):
        SensitiveKeyword.objects.create(keyword="camtu")
        self.leader = User.objects.create_user(email="gpmleader1@due.udn.vn", password="Pass1234!", role=User.Role.LECTURER)
        self.moderator_user = User.objects.create_user(email="gpmmod1@due.udn.vn", password="Pass1234!")
        self.author = User.objects.create_user(email="gpmauthor1@due.udn.vn", password="Pass1234!")
        self.outsider = User.objects.create_user(email="gpmoutsider1@due.udn.vn", password="Pass1234!")
        self.staff = User.objects.create_user(email="gpmstaff1@due.udn.vn", password="Pass1234!", role=User.Role.STAFF)
        self.group = services.request_create_group(self.leader, "Nhom Test Moderation", "mo ta")
        GroupMembership.objects.create(group=self.group, user=self.moderator_user, role=GroupMembership.Role.MODERATOR)
        GroupMembership.objects.create(group=self.group, user=self.author, role=GroupMembership.Role.MEMBER)
        self.post, keyword = services.create_group_post(self.group, self.author, "Tieu de", "noi dung co camtu")
        assert keyword is not None

    def test_post_with_keyword_is_pending_review(self):
        self.assertEqual(self.post.status, ContentStatus.PENDING_REVIEW)

    def test_pending_post_not_in_staff_moderation_queue(self):
        self.client.force_login(self.staff)
        response = self.client.get(reverse("moderation:pending_content_list"))
        self.assertNotContains(response, self.post.title)

    def test_staff_cannot_approve_group_post_via_generic_endpoint(self):
        self.client.force_login(self.staff)
        self.client.post(reverse("moderation:approve_content", args=["grouppost", self.post.pk]))
        self.post.refresh_from_db()
        self.assertEqual(self.post.status, ContentStatus.PENDING_REVIEW)

    def test_leader_can_approve_pending_post(self):
        self.client.force_login(self.leader)
        self.client.post(reverse("groups:post_approve", args=[self.group.slug, self.post.pk]))
        self.post.refresh_from_db()
        self.assertEqual(self.post.status, ContentStatus.PUBLISHED)
        self.assertTrue(ModerationLog.objects.filter(action=ModerationLog.Action.APPROVE_CONTENT, actor=self.leader).exists())

    def test_moderator_can_reject_pending_post_with_reason(self):
        self.client.force_login(self.moderator_user)
        self.client.post(
            reverse("groups:post_reject", args=[self.group.slug, self.post.pk]), {"reason": "Vi pham noi quy"},
        )
        self.post.refresh_from_db()
        self.assertEqual(self.post.status, ContentStatus.REMOVED)
        log = ModerationLog.objects.get(action=ModerationLog.Action.REJECT_CONTENT)
        self.assertEqual(log.reason, "Vi pham noi quy")

    def test_reject_without_reason_does_not_change_status(self):
        self.client.force_login(self.leader)
        self.client.post(reverse("groups:post_reject", args=[self.group.slug, self.post.pk]), {"reason": ""})
        self.post.refresh_from_db()
        self.assertEqual(self.post.status, ContentStatus.PENDING_REVIEW)

    def test_outsider_cannot_approve_pending_post(self):
        self.client.force_login(self.outsider)
        self.client.post(reverse("groups:post_approve", args=[self.group.slug, self.post.pk]))
        self.post.refresh_from_db()
        self.assertEqual(self.post.status, ContentStatus.PENDING_REVIEW)

    def test_pending_post_shows_keyword_note_to_manager(self):
        self.client.force_login(self.leader)
        response = self.client.get(self.group.get_absolute_url())
        self.assertContains(response, "camtu")

    def test_post_without_keyword_is_also_pending_review(self):
        post, keyword = services.create_group_post(self.group, self.author, "Bai binh thuong", "noi dung hop le")
        self.assertIsNone(keyword)
        self.assertEqual(post.status, ContentStatus.PENDING_REVIEW)

    def test_pending_post_without_keyword_shows_awaiting_review_badge(self):
        services.approve_group_post(self.post, self.leader)  # loai bai co tu khoa ra khoi hang doi truoc
        services.create_group_post(self.group, self.author, "Bai binh thuong 2", "noi dung hop le khac")
        self.client.force_login(self.leader)
        response = self.client.get(self.group.get_absolute_url())
        self.assertContains(response, "Đang chờ xét duyệt")
        self.assertNotContains(response, "Có chứa từ khóa nhạy cảm")

    def test_pending_post_not_shown_in_public_discussion_list(self):
        self.client.force_login(self.leader)
        response = self.client.get(self.group.get_absolute_url())
        self.assertNotIn(self.post, response.context["posts"])

    def test_editing_published_post_sends_it_back_to_pending_review(self):
        services.approve_group_post(self.post, self.leader)
        self.post.refresh_from_db()
        self.assertEqual(self.post.status, ContentStatus.PUBLISHED)

        self.client.force_login(self.author)
        self.client.post(
            reverse("groups:post_edit", args=[self.group.slug, self.post.pk]),
            {"title": "Tieu de da sua", "body": "noi dung da sua"},
        )
        self.post.refresh_from_db()
        self.assertEqual(self.post.status, ContentStatus.PENDING_REVIEW)
