"""Mixin dung chung cho cac model noi dung co the kiem duyet/ghim (ForumPost,
Announcement, GroupPost). Khong phai mot Django app - chi la module tien ich
de tranh lap field giua 3 app theo dung cau truc trong CLAUDE.md.
"""
from django.conf import settings
from django.db import models


class ContentStatus(models.TextChoices):
    DRAFT = "draft", "Bản nháp"
    PENDING_REVIEW = "pending_review", "Chờ kiểm duyệt"
    PUBLISHED = "published", "Đã đăng"
    HIDDEN = "hidden", "Đã ẩn"
    REMOVED = "removed", "Đã xóa"


class ModeratedContentMixin(models.Model):
    """Trang thai kiem duyet + dem so lan sua (version history luu rieng, xem *EditHistory)."""

    status = models.CharField(max_length=20, choices=ContentStatus.choices, default=ContentStatus.PUBLISHED)
    edit_count = models.PositiveIntegerField(default=0)
    view_count = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True

    @property
    def is_edited(self):
        return self.edit_count > 0


class PinnableMixin(models.Model):
    """Ghim bai co gioi han so luong dong thoi moi chuyen muc (xu ly o tang service/view)."""

    is_pinned = models.BooleanField(default=False)
    pinned_at = models.DateTimeField(null=True, blank=True)
    pinned_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )

    class Meta:
        abstract = True


class StaffRequiredMixin:
    """Chi Giao vu Khoa (role=staff) duoc vao trang - dung chung cho moi CBV quan tri
    thay vi moi app tu dinh nghia rieng (truoc day lap lai y het o accounts/forum/
    moderation). Redirect ve home + bao loi thay vi 403 tran trui."""

    def dispatch(self, request, *args, **kwargs):
        from django.contrib import messages
        from django.shortcuts import redirect

        if not (request.user.is_authenticated and request.user.role == "staff"):
            messages.error(request, "Chỉ Giáo vụ Khoa mới có quyền truy cập trang này.")
            return redirect("home")
        return super().dispatch(request, *args, **kwargs)


class PinLimitExceeded(Exception):
    """Chuyen muc/pham vi da dat so luong ghim toi da - khong tu dong bo ghim bai cu."""

    def __init__(self, max_pinned):
        self.max_pinned = max_pinned
        super().__init__(
            f"Đã đạt giới hạn {max_pinned} bài ghim đồng thời. "
            "Vui lòng bỏ ghim một bài cũ trước khi ghim bài mới."
        )
