from django.contrib.auth.base_user import BaseUserManager
from django.contrib.auth.models import AbstractUser
from django.db import models


class UserManager(BaseUserManager):
    """Dang nhap bang email nen can manager rieng (manager mac dinh cua AbstractUser
    doi hoi username la tham so dau tien, khong phu hop khi USERNAME_FIELD = email)."""

    use_in_migrations = True

    def _create_user(self, email, password, **extra_fields):
        if not email:
            raise ValueError("Email là bắt buộc")
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_user(self, email=None, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", False)
        extra_fields.setdefault("is_superuser", False)
        return self._create_user(email, password, **extra_fields)

    def create_superuser(self, email=None, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        if extra_fields.get("is_staff") is not True:
            raise ValueError("Superuser must have is_staff=True.")
        if extra_fields.get("is_superuser") is not True:
            raise ValueError("Superuser must have is_superuser=True.")
        return self._create_user(email, password, **extra_fields)


class User(AbstractUser):
    """Tai khoan nguoi dung. 4 actor phan biet qua field `role`."""

    class Role(models.TextChoices):
        STUDENT = "student", "Sinh viên"
        LECTURER = "lecturer", "Giảng viên / BCN Khoa"
        BCH = "bch", "BCH Khoa"
        STAFF = "staff", "Giáo vụ Khoa (Quản trị viên)"

    # BCH Khoa ban chat la sinh vien kiem nhiem nen van co "Lop"; Giang vien/BCN Khoa
    # va Giao vu Khoa la giang vien/can bo nen khong co "Lop".
    ROLES_WITH_CLASS_NAME = (Role.STUDENT, Role.BCH)

    email = models.EmailField(unique=True)
    role = models.CharField(max_length=20, choices=Role.choices, default=Role.STUDENT)

    student_id = models.CharField("Mã số sinh viên/CB", max_length=20, blank=True)
    class_name = models.CharField("Lớp", max_length=50, blank=True)
    phone = models.CharField(max_length=20, blank=True)
    avatar = models.ImageField(upload_to="avatars/", blank=True, null=True)
    cover_image = models.ImageField("Ảnh bìa", upload_to="covers/", blank=True, null=True)
    bio = models.TextField(blank=True)

    # Khoa tai khoan do vi pham - phan biet voi is_active mac dinh cua Django
    # (is_active con duoc dung de tat dang nhap khi khoa, locked_reason/locked_at
    # luu lai boi canh de hien thi cho user va cho Giao vu Khoa doi chieu)
    locked_reason = models.TextField(blank=True)
    locked_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []

    objects = UserManager()

    def __str__(self):
        return self.get_full_name() or self.email

    def get_full_name(self):
        # Ten tieng Viet viet theo thu tu Ho + Ten (nguoc voi mac dinh cua Django la
        # "first_name last_name" kieu phuong Tay) - last_name luu Ho, first_name luu Ten
        full_name = f"{self.last_name} {self.first_name}".strip()
        return full_name

    def save(self, *args, **kwargs):
        # Dang nhap bang email (allauth), username chi con ton tai vi AbstractUser
        # yeu cau - tu sinh de khong bat nguoi dung phai nhap.
        if not self.username:
            self.username = self.email
        super().save(*args, **kwargs)

    @property
    def is_locked(self):
        return not self.is_active

    @property
    def has_class_name_field(self):
        return self.role in self.ROLES_WITH_CLASS_NAME
