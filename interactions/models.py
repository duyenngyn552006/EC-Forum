from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models


class Comment(models.Model):
    """Binh luan theo luong (threaded), dung chung cho Announcement/ForumPost/GroupPost qua GenericForeignKey."""

    class Status(models.TextChoices):
        PUBLISHED = "published", "Đã đăng"
        PENDING_REVIEW = "pending_review", "Chờ kiểm duyệt"
        HIDDEN = "hidden", "Đã ẩn"
        REMOVED = "removed", "Đã xóa"

    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="comments")

    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveIntegerField()
    content_object = GenericForeignKey("content_type", "object_id")

    parent = models.ForeignKey("self", on_delete=models.CASCADE, null=True, blank=True, related_name="replies")
    body = models.TextField()
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PUBLISHED)
    is_edited = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["created_at"]
        indexes = [models.Index(fields=["content_type", "object_id"])]

    def __str__(self):
        return f"Comment#{self.pk} by {self.author}"


class Like(models.Model):
    """Cam xuc cua 1 user tren 1 noi dung (giu ten Like de khong phai doi du lieu cu).
    Moi user chi co 1 cam xuc / noi dung (unique_together) - doi cam xuc = cap nhat dong cu."""

    class Reaction(models.TextChoices):
        LIKE = "like", "👍 Thích"
        LOVE = "love", "❤️ Yêu thích"
        WOW = "wow", "😮 Ngạc nhiên"
        IDEA = "idea", "💡 Hay"

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="likes")

    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveIntegerField()
    content_object = GenericForeignKey("content_type", "object_id")

    reaction = models.CharField(max_length=10, choices=Reaction.choices, default=Reaction.LIKE)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ["user", "content_type", "object_id"]
        indexes = [models.Index(fields=["content_type", "object_id"])]

    def __str__(self):
        return f"Like#{self.pk} by {self.user}"


class SavedItem(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="saved_items")

    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveIntegerField()
    content_object = GenericForeignKey("content_type", "object_id")

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ["user", "content_type", "object_id"]
        indexes = [models.Index(fields=["content_type", "object_id"])]

    def __str__(self):
        return f"SavedItem#{self.pk} by {self.user}"


class Poll(models.Model):
    """Binh chon gan vao 1 bai (ForumPost/GroupPost) qua GenericForeignKey - moi bai toi da 1 poll.
    Doi lua chon duoc truoc han chot (closes_at), sau han thi khoa."""

    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveIntegerField()
    content_object = GenericForeignKey("content_type", "object_id")

    question = models.CharField(max_length=255)
    closes_at = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="polls")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["content_type", "object_id"], name="unique_poll_per_object"),
        ]

    def __str__(self):
        return self.question

    @property
    def is_closed(self):
        from django.utils import timezone

        return self.closes_at is not None and self.closes_at <= timezone.now()


class PollOption(models.Model):
    poll = models.ForeignKey(Poll, on_delete=models.CASCADE, related_name="options")
    text = models.CharField(max_length=200)
    position = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["position", "pk"]

    def __str__(self):
        return self.text


class PollVote(models.Model):
    poll = models.ForeignKey(Poll, on_delete=models.CASCADE, related_name="votes")
    option = models.ForeignKey(PollOption, on_delete=models.CASCADE, related_name="votes")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="poll_votes")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        # Moi nguoi 1 phieu / poll: doi lua chon = cap nhat option cua dong cu
        unique_together = ["poll", "user"]

    def __str__(self):
        return f"{self.user} -> {self.option}"


class Follow(models.Model):
    """Theo doi chuyen muc/the/bai viet de nhan thong bao khi co noi dung moi (generic).
    Doi tuong duoc phep theo doi gioi han o FOLLOW_ALLOWED_MODELS (interactions/utils.py)."""

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="follows")

    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveIntegerField()
    content_object = GenericForeignKey("content_type", "object_id")

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ["user", "content_type", "object_id"]
        indexes = [models.Index(fields=["content_type", "object_id"])]
        ordering = ["-created_at"]

    def __str__(self):
        return f"Follow#{self.pk} by {self.user}"


def _private_document_storage():
    """Tep tai lieu luu o private_media/ (KHONG anh xa cong khai nhu media/) - chi tai ve qua view
    interactions:download_document (bat buoc dang nhap, luon tai xuong) de tranh tep .html/.svg doc hai
    chay truc tiep tren domain dien dan."""
    import os

    from django.core.files.storage import FileSystemStorage

    class PrivateDocumentStorage(FileSystemStorage):
        # Doc PRIVATE_MEDIA_ROOT moi lan dung (khong chot luc khoi dong) -> override_settings trong test co hieu luc
        @property
        def base_location(self):
            return settings.PRIVATE_MEDIA_ROOT

        @property
        def location(self):
            return os.path.abspath(self.base_location)

    return PrivateDocumentStorage()


class DocumentLink(models.Model):
    """Tai lieu dinh kem cua ForumPost/GroupPost (GenericForeignKey): HOAC link Google Drive/Docs/Sheets dan tay,
    HOAC 1 tep tai len (Word/Excel/PowerPoint/PDF/code..., gioi han dung luong + duoi tep, xem
    interactions/documents.py). Moi dong co dung 1 trong 2."""

    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveIntegerField()
    content_object = GenericForeignKey("content_type", "object_id")

    title = models.CharField("Tên tài liệu", max_length=200)
    url = models.URLField("Link Google Drive / Docs / Sheets", max_length=500, blank=True)
    file = models.FileField("Tệp tải lên", upload_to="documents/%Y/%m/", storage=_private_document_storage, blank=True)
    file_size = models.PositiveIntegerField("Dung lượng (byte)", default=0)
    position = models.PositiveSmallIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["position", "pk"]
        indexes = [models.Index(fields=["content_type", "object_id"])]

    def __str__(self):
        return self.title

    @property
    def is_upload(self):
        return bool(self.file)

    @property
    def kind(self):
        from .documents import detect_kind, detect_upload_kind

        return detect_upload_kind(self.file.name) if self.file else detect_kind(self.url)

    @property
    def file_extension(self):
        return self.file.name.rsplit(".", 1)[-1].lower() if self.file and "." in self.file.name else ""

    def get_download_url(self):
        from django.urls import reverse

        return reverse("interactions:download_document", args=[self.pk]) if self.file else self.url


# Don tep tren o dia khi xoa tai lieu (ke ca xoa day chuyen theo bai) hoac thay tep moi khi sua
from django.db.models.signals import post_delete, pre_save  # noqa: E402
from django.dispatch import receiver  # noqa: E402


@receiver(post_delete, sender=DocumentLink)
def _delete_document_file(sender, instance, **kwargs):
    if instance.file:
        instance.file.delete(save=False)


@receiver(pre_save, sender=DocumentLink)
def _delete_replaced_document_file(sender, instance, **kwargs):
    if not instance.pk:
        return
    old = DocumentLink.objects.filter(pk=instance.pk).only("file").first()
    if old and old.file and old.file.name != (instance.file.name if instance.file else ""):
        old.file.delete(save=False)
