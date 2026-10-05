from django.test import TestCase
from django.urls import reverse

from .forms import CAPTCHA_AFTER_FAILED_ATTEMPTS, LOGIN_FAILED_COUNT_SESSION_KEY
from .models import User


class SignupFormTests(TestCase):
    def _signup_payload(self, email):
        return {
            "email": email,
            "last_name": "Nguyen",
            "first_name": "Van A",
            "class_name": "18K1",
            "password1": "Str0ngPass!2345",
            "password2": "Str0ngPass!2345",
        }

    def test_signup_rejects_email_outside_allowed_domain(self):
        response = self.client.post(reverse("account_signup"), self._signup_payload("someone@gmail.com"))
        self.assertEqual(response.status_code, 200)
        self.assertFalse(User.objects.filter(email="someone@gmail.com").exists())

    def test_signup_with_numeric_local_part_autofills_student_id(self):
        email = "241124022206@due.udn.vn"
        response = self.client.post(reverse("account_signup"), self._signup_payload(email))
        self.assertEqual(response.status_code, 302)
        user = User.objects.get(email=email)
        self.assertEqual(user.student_id, "241124022206")
        self.assertEqual(user.role, User.Role.STUDENT)

    def test_signup_with_non_numeric_local_part_leaves_student_id_blank(self):
        email = "nguyenvana@due.udn.vn"
        response = self.client.post(reverse("account_signup"), self._signup_payload(email))
        self.assertEqual(response.status_code, 302)
        user = User.objects.get(email=email)
        self.assertEqual(user.student_id, "")

    def test_signup_saves_last_name_and_first_name_separately(self):
        email = "hoten@due.udn.vn"
        response = self.client.post(reverse("account_signup"), self._signup_payload(email))
        self.assertEqual(response.status_code, 302)
        user = User.objects.get(email=email)
        self.assertEqual(user.last_name, "Nguyen")
        self.assertEqual(user.first_name, "Van A")

    def test_signup_saves_class_name(self):
        email = "lop@due.udn.vn"
        response = self.client.post(reverse("account_signup"), self._signup_payload(email))
        self.assertEqual(response.status_code, 302)
        user = User.objects.get(email=email)
        self.assertEqual(user.class_name, "18K1")


class FullNameDisplayTests(TestCase):
    def test_get_full_name_uses_vietnamese_order_ho_truoc_ten_sau(self):
        user = User(last_name="Nguyen", first_name="Van A")
        self.assertEqual(user.get_full_name(), "Nguyen Van A")


class ClassNameFieldVisibilityTests(TestCase):
    """'Lop' chi danh cho Sinh vien/BCH Khoa - khong danh cho Giang vien/Giao vu Khoa."""

    def test_student_and_bch_have_class_name_field(self):
        student = User.objects.create_user(email="sv-lop@due.udn.vn", password="Pass1234!", role=User.Role.STUDENT)
        bch = User.objects.create_user(email="bch-lop@due.udn.vn", password="Pass1234!", role=User.Role.BCH)
        self.assertTrue(student.has_class_name_field)
        self.assertTrue(bch.has_class_name_field)

    def test_lecturer_and_staff_have_no_class_name_field(self):
        lecturer = User.objects.create_user(email="gv-lop@due.udn.vn", password="Pass1234!", role=User.Role.LECTURER)
        staff = User.objects.create_user(email="gvk-lop@due.udn.vn", password="Pass1234!", role=User.Role.STAFF)
        self.assertFalse(lecturer.has_class_name_field)
        self.assertFalse(staff.has_class_name_field)

    def test_profile_edit_form_hides_class_name_for_lecturer(self):
        lecturer = User.objects.create_user(email="gv-form@due.udn.vn", password="Pass1234!", role=User.Role.LECTURER)
        self.client.force_login(lecturer)
        response = self.client.get(reverse("accounts:profile_edit"))
        self.assertNotIn(b'name="class_name"', response.content)

    def test_profile_edit_form_shows_class_name_for_student(self):
        student = User.objects.create_user(email="sv-form@due.udn.vn", password="Pass1234!", role=User.Role.STUDENT)
        self.client.force_login(student)
        response = self.client.get(reverse("accounts:profile_edit"))
        self.assertIn(b'name="class_name"', response.content)

    def test_assign_role_clears_class_name_when_changing_to_lecturer(self):
        staff = User.objects.create_user(email="gvk-assign@due.udn.vn", password="Pass1234!", role=User.Role.STAFF)
        student = User.objects.create_user(
            email="sv-assign@due.udn.vn", password="Pass1234!", role=User.Role.STUDENT, class_name="20K1"
        )
        self.client.force_login(staff)
        self.client.post(reverse("accounts:assign_role", args=[student.pk]), {"role": User.Role.LECTURER})
        student.refresh_from_db()
        self.assertEqual(student.role, User.Role.LECTURER)
        self.assertEqual(student.class_name, "")


class LoginCaptchaTests(TestCase):
    """Dang nhap sai nhieu lan lien tiep phai bat buoc giai CAPTCHA (CLAUDE.md:
    "yeu cau xac thuc CAPTCHA ... khi phat hien hoat dong bat thuong")."""

    def setUp(self):
        self.user = User.objects.create_user(email="login_test@due.udn.vn", password="Correct!2345")

    def _fail_login(self, password="Sai_mat_khau!"):
        return self.client.post(reverse("account_login"), {"login": self.user.email, "password": password})

    def test_login_form_has_no_captcha_initially(self):
        response = self.client.get(reverse("account_login"))
        self.assertNotIn(b"id_captcha", response.content)

    def test_captcha_required_after_threshold_failed_attempts(self):
        for _ in range(CAPTCHA_AFTER_FAILED_ATTEMPTS):
            self._fail_login()
        response = self.client.get(reverse("account_login"))
        self.assertIn(b"id_captcha", response.content)

    def test_successful_login_resets_failed_attempt_count(self):
        self._fail_login()
        response = self.client.post(
            reverse("account_login"), {"login": self.user.email, "password": "Correct!2345"},
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.client.session.get(LOGIN_FAILED_COUNT_SESSION_KEY, 0), 0)
