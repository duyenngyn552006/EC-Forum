from allauth.account.forms import LoginForm as AllauthLoginForm
from allauth.account.forms import SignupForm
from captcha.fields import CaptchaField
from django import forms
from django.conf import settings

from .models import User

# Sau bao nhieu lan dang nhap sai lien tiep (tinh theo session trinh duyet) thi bat buoc
# giai CAPTCHA o lan thu tiep theo - "phat hien hoat dong bat thuong" (CLAUDE.md).
# Rate-limit tam khoa dang nhap theo IP/email khi vuot nguong da co san o allauth
# (xem settings.ACCOUNT_RATE_LIMITS["login_failed"]), day la lop phong thu bo sung.
CAPTCHA_AFTER_FAILED_ATTEMPTS = 2
LOGIN_FAILED_COUNT_SESSION_KEY = "login_failed_count"


class CaptchaLoginForm(AllauthLoginForm):
    """Dang nhap kem CAPTCHA sau vai lan sai lien tiep - bo sung cho rate-limit cua allauth."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        failed_count = self.request.session.get(LOGIN_FAILED_COUNT_SESSION_KEY, 0) if self.request else 0
        if failed_count >= CAPTCHA_AFTER_FAILED_ATTEMPTS:
            self.fields["captcha"] = CaptchaField(label="Xác thực CAPTCHA")

    def clean(self):
        try:
            cleaned_data = super().clean()
        except forms.ValidationError:
            self._register_failed_attempt()
            raise
        if self.errors:
            self._register_failed_attempt()
        else:
            self._reset_failed_attempts()
        return cleaned_data

    def _register_failed_attempt(self):
        if self.request is None:
            return
        count = self.request.session.get(LOGIN_FAILED_COUNT_SESSION_KEY, 0) + 1
        self.request.session[LOGIN_FAILED_COUNT_SESSION_KEY] = count

    def _reset_failed_attempts(self):
        if self.request is not None:
            self.request.session.pop(LOGIN_FAILED_COUNT_SESSION_KEY, None)


class DomainRestrictedSignupForm(SignupForm):
    """Chi cho phep dang ky bang email dung domain truong/khoa (CLAUDE.md).

    Validate ngay tai buoc signup, tu choi TRUOC khi tai khoan duoc tao.
    Vai tro mac dinh khi tu dang ky luon la sinh vien; cac vai tro khac
    (giang vien, BCH, giao vu) do Giao vu Khoa gan sau qua trang quan ly.
    """

    # Tach rieng Ho/Ten thay vi 1 o "Ho va ten" - ghep chung de may tu tach de sai
    # voi ten tieng Viet (ho dung sau ten dem, khac thu tu ho/ten cua phuong Tay)
    last_name = forms.CharField(max_length=150, label="Họ")
    first_name = forms.CharField(max_length=150, label="Tên")
    class_name = forms.CharField(max_length=50, label="Lớp")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.order_fields(["last_name", "first_name", "class_name", "email", "password1", "password2"])

    def clean_email(self):
        email = super().clean_email()
        allowed_domains = [d.lower() for d in getattr(settings, "ALLOWED_SIGNUP_EMAIL_DOMAINS", [])]
        domain = email.rsplit("@", 1)[-1].lower()
        if allowed_domains and domain not in allowed_domains:
            raise forms.ValidationError(
                "Chỉ chấp nhận email thuộc domain trường/khoa: %(domains)s",
                params={"domains": ", ".join(f"@{d}" for d in allowed_domains)},
            )
        return email

    def save(self, request):
        user = super().save(request)
        user.first_name = self.cleaned_data.get("first_name", "").strip()
        user.last_name = self.cleaned_data.get("last_name", "").strip()
        user.class_name = self.cleaned_data.get("class_name", "").strip()
        user.role = User.Role.STUDENT

        # Email truong dung dang <MSSV>@due.udn.vn (vd 241124022206@due.udn.vn) -> tu dien MSSV,
        # khoi phai nhap tay lai o ho so ca nhan
        local_part = user.email.split("@", 1)[0]
        if local_part.isdigit():
            user.student_id = local_part

        user.save()
        return user
