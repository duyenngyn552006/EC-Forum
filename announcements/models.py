from django.conf import settings
from django.db import models
from django.urls import reverse
from django_ckeditor_5.fields import CKEditor5Field

from config.mixins import ModeratedContentMixin, PinnableMixin


class Announcement(ModeratedContentMixin, PinnableMixin, models.Model):
    class Kind(models.TextChoices):
        OFFICIAL = "official", "Thông báo chính thức Trường/Khoa"
        EVENT = "event", "Sự kiện / hoạt động phong trào"

    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="announcements")
    kind = models.CharField(max_length=20, choices=Kind.choices, default=Kind.OFFICIAL)

    title = models.CharField(max_length=255)
    body = CKEditor5Field(config_name="default")
    featured_image = models.ImageField("Ảnh đại diện", upload_to="announcements/featured/%Y/%m/", blank=True, null=True)

    # Chi dung cho kind=EVENT (su kien/hoat dong phong trao) - ngay gio dien ra su kien,
    # khac voi created_at/updated_at la thoi diem dang/sua bai
    event_datetime = models.DateTimeField(
        "Thời gian diễn ra sự kiện", null=True, blank=True
    )
    # Thoi diem ket thuc - chi co khi su kien keo dai theo khoang thoi gian;
    # NULL = su kien chi co 1 moc thoi gian (event_datetime)
    event_end_datetime = models.DateTimeField("Thời điểm kết thúc sự kiện", null=True, blank=True)

    class Meta:
        ordering = ["-is_pinned", "-created_at"]

    def __str__(self):
        return self.title

    @property
    def event_time_display(self):
        """Chuoi hien thi gio dien ra: 1 moc, 1 khoang trong ngay, hoac khoang nhieu ngay."""
        from django.utils import timezone

        if not self.event_datetime:
            return ""
        start = timezone.localtime(self.event_datetime)
        if not self.event_end_datetime:
            return f"{start:%d/%m/%Y %H:%M}"
        end = timezone.localtime(self.event_end_datetime)
        if start.date() == end.date():
            return f"{start:%d/%m/%Y}, {start:%H:%M} – {end:%H:%M}"
        return f"{start:%d/%m/%Y %H:%M} – {end:%d/%m/%Y %H:%M}"

    def get_absolute_url(self):
        return reverse("announcements:detail", args=[self.pk])


class AnnouncementAttachment(models.Model):
    announcement = models.ForeignKey(Announcement, on_delete=models.CASCADE, related_name="attachments")
    image = models.ImageField(upload_to="announcements/%Y/%m/")
    caption = models.CharField(max_length=255, blank=True)

    def __str__(self):
        return f"Ảnh đính kèm #{self.pk} - {self.announcement_id}"


class AnnouncementEditHistory(models.Model):
    announcement = models.ForeignKey(Announcement, on_delete=models.CASCADE, related_name="history")
    editor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    title = models.CharField(max_length=255)
    body = models.TextField()
    edited_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-edited_at"]
        verbose_name_plural = "Announcement edit histories"

    def __str__(self):
        return f"{self.announcement_id} @ {self.edited_at:%Y-%m-%d %H:%M}"
