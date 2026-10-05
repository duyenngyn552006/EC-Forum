from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.shortcuts import get_object_or_404, redirect, render
from django.views.generic import DetailView, ListView
from django_ratelimit.decorators import ratelimit

from accounts.models import User
from config.mixins import ContentStatus, PinLimitExceeded

from . import services
from .forms import AnnouncementAttachmentFormSet, AnnouncementForm
from .models import Announcement


def _can_post_announcement(user):
    return user.is_authenticated and user.role in (User.Role.STAFF, User.Role.BCH)


class AnnouncementListView(ListView):
    model = Announcement
    template_name = "announcements/announcement_list.html"
    context_object_name = "announcements"
    paginate_by = 20

    def get_queryset(self):
        qs = Announcement.objects.filter(status=ContentStatus.PUBLISHED).select_related("author")
        kind = self.request.GET.get("kind")
        if kind:
            qs = qs.filter(kind=kind)
        return qs


class AnnouncementDetailView(DetailView):
    model = Announcement
    template_name = "announcements/announcement_detail.html"
    context_object_name = "announcement"

    def get_context_data(self, **kwargs):
        from django.contrib.contenttypes.models import ContentType

        from interactions.utils import get_interaction_context, get_top_level_comments

        ctx = super().get_context_data(**kwargs)
        content_type = ContentType.objects.get_for_model(Announcement)
        ctx["model_key"] = "announcement"
        ctx["comments"] = get_top_level_comments(content_type, self.object.pk)
        ctx.update(get_interaction_context(self.request.user, self.object))
        return ctx


class _StaffOrBchRequiredMixin(LoginRequiredMixin, UserPassesTestMixin):
    def test_func(self):
        return _can_post_announcement(self.request.user)


@ratelimit(key="user", rate="10/m", block=True)
def announcement_create(request):
    if not _can_post_announcement(request.user):
        messages.error(request, "Chỉ Giáo vụ Khoa hoặc BCH Khoa mới được đăng thông tin/thông báo.")
        return redirect("announcements:list")

    if request.method == "POST":
        form = AnnouncementForm(request.POST, request.FILES, user=request.user)
        if form.is_valid():
            announcement, keyword = services.create_announcement(
                author=request.user,
                kind=form.cleaned_data["kind"],
                title=form.cleaned_data["title"],
                body=form.cleaned_data["body"],
                event_datetime=form.cleaned_data.get("event_datetime"),
                featured_image=form.cleaned_data.get("featured_image"),
            )
            formset = AnnouncementAttachmentFormSet(request.POST, request.FILES, instance=announcement)
            if formset.is_valid():
                formset.save()
            if keyword:
                messages.warning(request, "Nội dung chứa từ khóa nhạy cảm nên đã chuyển sang trạng thái chờ kiểm duyệt.")
            else:
                messages.success(request, "Đã đăng thông báo.")
            return redirect(announcement.get_absolute_url())
    else:
        form = AnnouncementForm(user=request.user)
    formset = AnnouncementAttachmentFormSet()
    return render(request, "announcements/announcement_form.html", {"form": form, "formset": formset})


def announcement_edit(request, pk):
    announcement = get_object_or_404(Announcement, pk=pk)
    if not (request.user == announcement.author or request.user.role == User.Role.STAFF):
        messages.error(request, "Bạn không có quyền sửa thông báo này.")
        return redirect(announcement.get_absolute_url())

    if request.method == "POST":
        form = AnnouncementForm(request.POST, request.FILES, instance=announcement, user=request.user)
        formset = AnnouncementAttachmentFormSet(request.POST, request.FILES, instance=announcement)
        if form.is_valid() and formset.is_valid():
            announcement, keyword = services.update_announcement(
                announcement=announcement,
                editor=request.user,
                title=form.cleaned_data["title"],
                body=form.cleaned_data["body"],
                event_datetime=form.cleaned_data.get("event_datetime"),
                featured_image=form.cleaned_data.get("featured_image"),
            )
            formset.save()
            if keyword:
                messages.warning(request, "Nội dung chứa từ khóa nhạy cảm nên đã chuyển sang trạng thái chờ kiểm duyệt.")
            else:
                messages.success(request, "Đã cập nhật thông báo.")
            return redirect(announcement.get_absolute_url())
    else:
        form = AnnouncementForm(instance=announcement, user=request.user)
        formset = AnnouncementAttachmentFormSet(instance=announcement)
    return render(request, "announcements/announcement_form.html", {"form": form, "formset": formset})


def _can_pin(user):
    return user.is_authenticated and user.role in (User.Role.LECTURER, User.Role.BCH, User.Role.STAFF)


def announcement_pin(request, pk):
    announcement = get_object_or_404(Announcement, pk=pk)
    if not _can_pin(request.user):
        messages.error(request, "Bạn không có quyền ghim thông báo này.")
        return redirect(announcement.get_absolute_url())
    try:
        services.pin_announcement(announcement, request.user)
        messages.success(request, "Đã ghim thông báo.")
    except PinLimitExceeded as exc:
        messages.error(request, str(exc))
    return redirect(announcement.get_absolute_url())


def announcement_unpin(request, pk):
    announcement = get_object_or_404(Announcement, pk=pk)
    if not _can_pin(request.user):
        messages.error(request, "Bạn không có quyền bỏ ghim thông báo này.")
        return redirect(announcement.get_absolute_url())
    services.unpin_announcement(announcement, request.user)
    messages.success(request, "Đã bỏ ghim thông báo.")
    return redirect(announcement.get_absolute_url())
