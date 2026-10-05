from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models


class SensitiveKeyword(models.Model):
    """Danh sach tu khoa cam cho bo loc tien kiem duyet tu dong. Giao vu Khoa quan ly qua admin."""

    keyword = models.CharField(max_length=100, unique=True)
    is_active = models.BooleanField(default=True)
    note = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["keyword"]

    def __str__(self):
        return self.keyword


class Report(models.Model):
    """Bao cao vi pham tu nguoi dung ve mot noi dung bat ky (Announcement/ForumPost/GroupPost/Comment)."""

    class Status(models.TextChoices):
        PENDING = "pending", "Chờ xử lý"
        REVIEWING = "reviewing", "Đang xem xét"
        RESOLVED = "resolved", "Đã xử lý"
        DISMISSED = "dismissed", "Đã bỏ qua"

    reporter = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="reports_made")

    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveIntegerField()
    content_object = GenericForeignKey("content_type", "object_id")

    reason = models.TextField()
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)

    handled_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="reports_handled"
    )
    resolution_note = models.TextField(blank=True)
    handled_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["content_type", "object_id"])]

    def __str__(self):
        return f"Report#{self.pk} by {self.reporter}"


class ModerationLog(models.Model):
    """Nhat ky moi hanh dong kiem duyet: ai, khi nao, hanh dong gi, ly do (CLAUDE.md muc 5)."""

    class Action(models.TextChoices):
        WARN = "warn", "Cảnh báo"
        HIDE = "hide", "Ẩn nội dung"
        DELETE = "delete", "Xóa nội dung"
        RESTORE = "restore", "Khôi phục nội dung"
        APPROVE_CONTENT = "approve_content", "Duyệt nội dung chờ kiểm duyệt"
        REJECT_CONTENT = "reject_content", "Từ chối nội dung chờ kiểm duyệt"
        LOCK_ACCOUNT = "lock_account", "Khóa tài khoản"
        UNLOCK_ACCOUNT = "unlock_account", "Mở khóa tài khoản"
        ROLE_CHANGE = "role_change", "Thay đổi vai trò"
        APPROVE_GROUP = "approve_group", "Duyệt yêu cầu tạo nhóm"
        REJECT_GROUP = "reject_group", "Từ chối yêu cầu tạo nhóm"
        DISABLE_GROUP = "disable_group", "Vô hiệu hóa nhóm"
        ENABLE_GROUP = "enable_group", "Kích hoạt lại nhóm"
        APPEAL_ACCEPTED = "appeal_accepted", "Chấp nhận kháng nghị"
        APPEAL_REJECTED = "appeal_rejected", "Từ chối kháng nghị"

    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="moderation_actions"
    )
    target_user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="moderation_received"
    )

    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE, null=True, blank=True)
    object_id = models.PositiveIntegerField(null=True, blank=True)
    content_object = GenericForeignKey("content_type", "object_id")

    action = models.CharField(max_length=30, choices=Action.choices)
    reason = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.get_action_display()} - {self.actor} - {self.created_at:%Y-%m-%d %H:%M}"


class AccountAppeal(models.Model):
    """Khang nghi cua user bi khoa tai khoan (CLAUDE.md muc 5)."""

    class Status(models.TextChoices):
        PENDING = "pending", "Chờ xử lý"
        ACCEPTED = "accepted", "Chấp nhận"
        REJECTED = "rejected", "Từ chối"

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="appeals")
    reason = models.TextField()
    extra_info = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)

    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="appeals_reviewed"
    )
    review_note = models.TextField(blank=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Appeal#{self.pk} - {self.user} - {self.status}"
