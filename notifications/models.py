from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models


class Notification(models.Model):
    class Verb(models.TextChoices):
        COMMENT = "comment", "Có bình luận mới"
        LIKE = "like", "Có lượt thích mới"
        NEW_ANNOUNCEMENT = "new_announcement", "Thông báo mới"
        GROUP_APPROVED = "group_approved", "Yêu cầu tạo nhóm được duyệt"
        GROUP_REJECTED = "group_rejected", "Yêu cầu tạo nhóm bị từ chối"
        MODERATION = "moderation", "Cập nhật kiểm duyệt"
        APPEAL_RESULT = "appeal_result", "Kết quả kháng nghị"
        MENTION = "mention", "Được gắn thẻ"

    recipient = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="notifications")
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    verb = models.CharField(max_length=30, choices=Verb.choices)
    message = models.CharField(max_length=255, blank=True)

    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE, null=True, blank=True)
    object_id = models.PositiveIntegerField(null=True, blank=True)
    content_object = GenericForeignKey("content_type", "object_id")

    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.get_verb_display()} -> {self.recipient}"


class NotificationPreference(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="notification_preference")
    notify_on_comment = models.BooleanField(default=True)
    notify_on_like = models.BooleanField(default=True)
    notify_on_announcement = models.BooleanField(default=True)
    notify_on_group_activity = models.BooleanField(default=True)
    notify_on_moderation = models.BooleanField(default=True)
    email_digest = models.BooleanField(default=False)

    def __str__(self):
        return f"Cài đặt thông báo của {self.user}"
