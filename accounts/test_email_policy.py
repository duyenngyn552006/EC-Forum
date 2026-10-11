"""Test email ngoai le (ALLOWED_SIGNUP_EXTRA_EMAILS): duoc dang ky / moi vao nhom du khong dung domain truong."""
from django.core import mail
from django.core.cache import cache
from django.test import TestCase, override_settings
from django.urls import reverse

from groups import services as group_services
from groups.models import Group, GroupMembership

from .email_policy import is_allowed_email
from .models import User

EXTRA = "tester.ngoaile@gmail.com"


def _payload(email):
    return {
        "email": email, "last_name": "Nguyen", "first_name": "Test", "class_name": "18K1",
        "password1": "Str0ngPass!2345", "password2": "Str0ngPass!2345",
    }


@override_settings(ALLOWED_SIGNUP_EMAIL_DOMAINS=["due.udn.vn"], ALLOWED_SIGNUP_EXTRA_EMAILS=[EXTRA])
class ExtraEmailTests(TestCase):
    def setUp(self):
        cache.clear()
        self.addCleanup(cache.clear)

    def test_policy(self):
        self.assertTrue(is_allowed_email("sv@due.udn.vn"))
        self.assertTrue(is_allowed_email(EXTRA))
        self.assertTrue(is_allowed_email("  Tester.NgoaiLe@Gmail.com "))  # khong phan biet hoa/thuong, khoang trang
        self.assertFalse(is_allowed_email("nguoi.khac@gmail.com"))
        self.assertFalse(is_allowed_email("not-an-email"))

    def test_extra_email_can_sign_up_and_receives_verification_mail(self):
        response = self.client.post(reverse("account_signup"), _payload(EXTRA))
        self.assertEqual(response.status_code, 302)
        self.assertTrue(User.objects.filter(email=EXTRA).exists())
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, [EXTRA])

    def test_other_outside_email_still_rejected(self):
        self.client.post(reverse("account_signup"), _payload("nguoi.khac@gmail.com"))
        self.assertFalse(User.objects.filter(email="nguoi.khac@gmail.com").exists())

    @override_settings(ALLOWED_SIGNUP_EXTRA_EMAILS=[])
    def test_no_exception_configured_rejects_gmail(self):
        self.client.post(reverse("account_signup"), _payload(EXTRA))
        self.assertFalse(User.objects.filter(email=EXTRA).exists())

    def test_extra_email_can_be_invited_to_group(self):
        leader = User.objects.create_user(email="leader-ex@due.udn.vn", password="Pass1234!", role=User.Role.LECTURER)
        tester = User.objects.create_user(email=EXTRA, password="Pass1234!")
        group = Group.objects.create(name="Nhom ngoai le", created_by=leader, status=Group.Status.ACTIVE)
        GroupMembership.objects.create(group=group, user=leader, role=GroupMembership.Role.LEADER)
        group_services.invite_member(group, EXTRA, leader)  # khong bao loi domain
        self.assertTrue(
            group.memberships.filter(user=tester).exists() or group.invitations.filter(invited_user=tester).exists()
        )
