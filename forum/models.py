from django.conf import settings
from django.db import models
from django.urls import reverse
from django.utils.text import slugify
from django_ckeditor_5.fields import CKEditor5Field

from config.mixins import ModeratedContentMixin, PinnableMixin


class Category(models.Model):
    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=120, unique=True, blank=True)
    description = models.TextField(blank=True)
    # So luong ghim toi da rieng cho chuyen muc nay; None -> dung MAX_PINNED_PER_CATEGORY mac dinh
    max_pinned = models.PositiveSmallIntegerField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name_plural = "Categories"
        ordering = ["name"]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def get_effective_max_pinned(self):
        from django.conf import settings as dj_settings

        return self.max_pinned if self.max_pinned is not None else dj_settings.MAX_PINNED_PER_CATEGORY


class Tag(models.Model):
    name = models.CharField(max_length=50, unique=True)
    slug = models.SlugField(max_length=60, unique=True, blank=True)

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)


class ForumPost(ModeratedContentMixin, PinnableMixin, models.Model):
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="forum_posts")
    category = models.ForeignKey(Category, on_delete=models.PROTECT, related_name="posts")
    tags = models.ManyToManyField(Tag, blank=True, related_name="posts")

    title = models.CharField(max_length=255)
    body = CKEditor5Field(config_name="default")
    featured_image = models.ImageField("Ảnh đại diện", upload_to="forum/%Y/%m/", blank=True, null=True)

    class Meta:
        ordering = ["-is_pinned", "-created_at"]

    def __str__(self):
        return self.title

    def get_absolute_url(self):
        return reverse("forum:post_detail", args=[self.pk])


class ForumPostEditHistory(models.Model):
    """Phien ban truoc moi lan sua - khong ghi de (CLAUDE.md muc 4)."""

    post = models.ForeignKey(ForumPost, on_delete=models.CASCADE, related_name="history")
    editor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    title = models.CharField(max_length=255)
    body = models.TextField()
    edited_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-edited_at"]
        verbose_name_plural = "Forum post edit histories"

    def __str__(self):
        return f"{self.post_id} @ {self.edited_at:%Y-%m-%d %H:%M}"
