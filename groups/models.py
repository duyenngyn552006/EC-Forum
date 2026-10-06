from django.conf import settings
from django.db import models
from django.urls import reverse
from django.utils.text import slugify
from django_ckeditor_5.fields import CKEditor5Field

from config.mixins import ModeratedContentMixin


class Group(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Chờ duyệt"
        ACTIVE = "active", "Đang hoạt động"
        REJECTED = "rejected", "Bị từ chối"
        DISABLED = "disabled", "Đã vô hiệu hóa"

    name = models.CharField(max_length=150)
    slug = models.SlugField(max_length=170, unique=True, blank=True)
    description = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)

    logo = models.ImageField("Logo nhóm", upload_to="groups/logos/", blank=True, null=True)
    cover_image = models.ImageField("Ảnh bìa nhóm", upload_to="groups/covers/", blank=True, null=True)

    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="created_groups")

    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="approved_groups"
    )
    approved_at = models.DateTimeField(null=True, blank=True)
    reject_reason = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            base_slug = slugify(self.name) or "group"
            slug = base_slug
            i = 1
            while Group.objects.exclude(pk=self.pk).filter(slug=slug).exists():
                i += 1
                slug = f"{base_slug}-{i}"
            self.slug = slug
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse("groups:detail", args=[self.slug])


class GroupMembership(models.Model):
    class Role(models.TextChoices):
        LEADER = "leader", "Trưởng nhóm"
        MODERATOR = "moderator", "Phó nhóm / điều hành"
        MEMBER = "member", "Thành viên"

    group = models.ForeignKey(Group, on_delete=models.CASCADE, related_name="memberships")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="group_memberships")
    role = models.CharField(max_length=20, choices=Role.choices, default=Role.MEMBER)
    joined_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ["group", "user"]
        ordering = ["group", "-role"]

    def __str__(self):
        return f"{self.user} @ {self.group} ({self.role})"


class GroupJoinRequest(models.Model):
    """User tu xin vao 1 nhom - cho leader/moderator duyet (nguoc chieu voi GroupInvitation:
    o day nguoi dung la ben chu dong xin, nhom la ben xet duyet)."""

    class Status(models.TextChoices):
        PENDING = "pending", "Chờ duyệt"
        ACCEPTED = "accepted", "Đã chấp nhận"
        REJECTED = "rejected", "Đã từ chối"

    group = models.ForeignKey(Group, on_delete=models.CASCADE, related_name="join_requests")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="group_join_requests")
    message = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)

    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="group_join_requests_reviewed"
    )
    reject_reason = models.CharField(max_length=255, blank=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["group", "user"], condition=models.Q(status="pending"), name="unique_pending_join_request",
            )
        ]

    def __str__(self):
        return f"{self.user} xin vào {self.group} ({self.status})"


class GroupInvitation(models.Model):
    """Leader/moderator moi 1 user vao nhom - nguoc chieu voi GroupJoinRequest: nhom la ben
    chu dong moi, nguoi duoc moi phai dong y (accept) thi moi tao GroupMembership."""

    class Status(models.TextChoices):
        PENDING = "pending", "Chờ phản hồi"
        ACCEPTED = "accepted", "Đã chấp nhận"
        DECLINED = "declined", "Đã từ chối"

    group = models.ForeignKey(Group, on_delete=models.CASCADE, related_name="invitations")
    invited_user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="group_invitations")
    invited_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="group_invitations_sent"
    )
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)

    created_at = models.DateTimeField(auto_now_add=True)
    responded_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["group", "invited_user"], condition=models.Q(status="pending"), name="unique_pending_invitation",
            )
        ]

    def __str__(self):
        return f"{self.group} mời {self.invited_user} ({self.status})"


class GroupPost(ModeratedContentMixin, models.Model):
    group = models.ForeignKey(Group, on_delete=models.CASCADE, related_name="posts")
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="group_posts")
    title = models.CharField(max_length=255)
    body = CKEditor5Field(config_name="default")
    featured_image = models.ImageField("Ảnh đại diện", upload_to="groups/%Y/%m/", blank=True, null=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.title

    def get_absolute_url(self):
        return reverse("groups:post_detail", args=[self.group.slug, self.pk])


class GroupPostEditHistory(models.Model):
    post = models.ForeignKey(GroupPost, on_delete=models.CASCADE, related_name="history")
    editor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    title = models.CharField(max_length=255)
    body = models.TextField()
    edited_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-edited_at"]
        verbose_name_plural = "Group post edit histories"

    def __str__(self):
        return f"{self.post_id} @ {self.edited_at:%Y-%m-%d %H:%M}"
