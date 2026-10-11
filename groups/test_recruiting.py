"""Test tuyen thanh vien: bat/tat dang tuyen, han nhan dang ky, bo loc danh sach, xin vao kem loi nhan."""
from datetime import timedelta

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import User

from .models import Group, GroupJoinRequest, GroupMembership


class RecruitingTests(TestCase):
    def setUp(self):
        self.leader = User.objects.create_user(email="rc-leader@due.udn.vn", password="Pass1234!", role=User.Role.LECTURER)
        self.member = User.objects.create_user(email="rc-member@due.udn.vn", password="Pass1234!")
        self.applicant = User.objects.create_user(email="rc-applicant@due.udn.vn", password="Pass1234!")
        self.group = Group.objects.create(name="Nhom tuyen", created_by=self.leader, status=Group.Status.ACTIVE)
        GroupMembership.objects.create(group=self.group, user=self.leader, role=GroupMembership.Role.LEADER)
        GroupMembership.objects.create(group=self.group, user=self.member, role=GroupMembership.Role.MEMBER)
        self.edit_url = reverse("groups:edit", args=[self.group.slug])
        self.base_payload = {"name": "Nhom tuyen", "description": "Mo ta"}

    def _edit(self, user, **extra):
        self.client.force_login(user)
        return self.client.post(self.edit_url, {**self.base_payload, **extra})

    # --- bat/tat tuyen ---
    def test_leader_can_open_recruitment(self):
        deadline = timezone.localdate() + timedelta(days=7)
        self._edit(self.leader, is_recruiting="on", recruit_positions="Thiet ke, viet bai", recruit_deadline=deadline.isoformat())
        self.group.refresh_from_db()
        self.assertTrue(self.group.is_recruiting)
        self.assertEqual(self.group.recruit_positions, "Thiet ke, viet bai")
        self.assertEqual(self.group.recruit_deadline, deadline)

    def test_recruiting_requires_positions(self):
        response = self._edit(self.leader, is_recruiting="on", recruit_positions="  ")
        self.assertEqual(response.status_code, 200)
        self.group.refresh_from_db()
        self.assertFalse(self.group.is_recruiting)

    def test_deadline_in_the_past_is_rejected(self):
        past = timezone.localdate() - timedelta(days=1)
        response = self._edit(self.leader, is_recruiting="on", recruit_positions="Thiet ke", recruit_deadline=past.isoformat())
        self.assertEqual(response.status_code, 200)
        self.group.refresh_from_db()
        self.assertFalse(self.group.is_recruiting)

    def test_ordinary_member_cannot_change_recruitment(self):
        self._edit(self.member, is_recruiting="on", recruit_positions="Thiet ke")
        self.group.refresh_from_db()
        self.assertFalse(self.group.is_recruiting)

    def test_turning_off_recruitment(self):
        self.group.is_recruiting = True
        self.group.recruit_positions = "Thiet ke"
        self.group.save()
        self._edit(self.leader, recruit_positions="Thiet ke")
        self.group.refresh_from_db()
        self.assertFalse(self.group.is_recruiting)

    # --- han nhan dang ky ---
    def test_recruitment_open_without_deadline_or_before_deadline(self):
        self.group.is_recruiting = True
        self.assertTrue(self.group.is_recruiting_open)
        self.group.recruit_deadline = timezone.localdate()
        self.assertTrue(self.group.is_recruiting_open)

    def test_recruitment_closed_after_deadline_or_when_off(self):
        self.group.is_recruiting = True
        self.group.recruit_deadline = timezone.localdate() - timedelta(days=1)
        self.assertFalse(self.group.is_recruiting_open)
        self.group.is_recruiting = False
        self.group.recruit_deadline = None
        self.assertFalse(self.group.is_recruiting_open)

    # --- danh sach ---
    def test_list_filter_shows_only_open_recruiting_groups(self):
        Group.objects.create(
            name="Het han", created_by=self.leader, status=Group.Status.ACTIVE,
            is_recruiting=True, recruit_positions="x", recruit_deadline=timezone.localdate() - timedelta(days=1),
        )
        Group.objects.create(name="Khong tuyen", created_by=self.leader, status=Group.Status.ACTIVE)
        Group.objects.create(
            name="Dang tuyen", created_by=self.leader, status=Group.Status.ACTIVE, is_recruiting=True, recruit_positions="Lap trinh",
        )
        Group.objects.create(
            name="Tuyen nhung bi vo hieu", created_by=self.leader, status=Group.Status.DISABLED, is_recruiting=True, recruit_positions="x",
        )
        response = self.client.get(reverse("groups:list"), {"recruiting": "1"})
        self.assertEqual({g.name for g in response.context["groups"]}, {"Dang tuyen"})
        self.assertContains(response, "Lap trinh")

        all_names = {g.name for g in self.client.get(reverse("groups:list")).context["groups"]}
        self.assertIn("Khong tuyen", all_names)

    # --- trang nhom + xin vao ---
    def test_detail_shows_recruit_box_and_message_field_to_outsider(self):
        self.group.is_recruiting = True
        self.group.recruit_positions = "Can ban thiet ke"
        self.group.save()
        self.client.force_login(self.applicant)
        response = self.client.get(self.group.get_absolute_url())
        self.assertContains(response, "Nhóm đang tuyển thành viên")
        self.assertContains(response, "Can ban thiet ke")
        self.assertContains(response, 'name="message"')

    def test_detail_hides_recruit_box_when_not_recruiting(self):
        self.client.force_login(self.applicant)
        response = self.client.get(self.group.get_absolute_url())
        self.assertNotContains(response, "Nhóm đang tuyển thành viên")
        self.assertNotContains(response, 'name="message"')

    def test_join_request_keeps_introduction_message(self):
        self.client.force_login(self.applicant)
        self.client.post(reverse("groups:join_request_create", args=[self.group.slug]), {"message": "Em biet Photoshop"})
        self.assertEqual(GroupJoinRequest.objects.get(user=self.applicant).message, "Em biet Photoshop")
