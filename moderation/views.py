from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.utils import timezone
from django.views.generic import CreateView, DeleteView, ListView, UpdateView

from accounts.models import User
from config.mixins import ContentStatus
from interactions.utils import resolve_target
from notifications.models import Notification
from notifications.services import notify

from .forms import (
    AccountAppealForm,
    AppealReviewForm,
    ContentRejectForm,
    ReportForm,
    ReportResolveForm,
    SensitiveKeywordForm,
)
from .models import AccountAppeal, ModerationLog, Report, SensitiveKeyword
from .services import log_action


def _is_staff(user):
    return user.is_authenticated and user.role == User.Role.STAFF


class _StaffRequiredMixin:
    """Chi Giao vu Khoa duoc vao - dung chung cach lam voi accounts.views.UserListView
    (redirect ve home + bao loi) thay vi de UserPassesTestMixin tra ve 403 mac dinh."""

    def dispatch(self, request, *args, **kwargs):
        if not _is_staff(request.user):
            messages.error(request, "Chỉ Giáo vụ Khoa mới có quyền quản lý từ khóa nhạy cảm.")
            return redirect("home")
        return super().dispatch(request, *args, **kwargs)


class SensitiveKeywordListView(_StaffRequiredMixin, ListView):
    """Quan ly tu khoa nhay cam ngay trong giao dien EC Forum - thay the cho viec phai
    vao Django Admin (/admin/) de lam viec nay."""

    model = SensitiveKeyword
    template_name = "moderation/keyword_list.html"
    context_object_name = "keywords"


class SensitiveKeywordCreateView(_StaffRequiredMixin, CreateView):
    model = SensitiveKeyword
    form_class = SensitiveKeywordForm
    template_name = "moderation/keyword_form.html"
    success_url = reverse_lazy("moderation:keyword_list")

    def form_valid(self, form):
        messages.success(self.request, "Đã thêm từ khóa nhạy cảm.")
        return super().form_valid(form)


class SensitiveKeywordUpdateView(_StaffRequiredMixin, UpdateView):
    model = SensitiveKeyword
    form_class = SensitiveKeywordForm
    template_name = "moderation/keyword_form.html"
    success_url = reverse_lazy("moderation:keyword_list")

    def form_valid(self, form):
        messages.success(self.request, "Đã cập nhật từ khóa nhạy cảm.")
        return super().form_valid(form)


class SensitiveKeywordDeleteView(_StaffRequiredMixin, DeleteView):
    model = SensitiveKeyword
    template_name = "moderation/keyword_confirm_delete.html"
    success_url = reverse_lazy("moderation:keyword_list")

    def form_valid(self, form):
        messages.success(self.request, "Đã xóa từ khóa nhạy cảm.")
        return super().form_valid(form)


@login_required
def create_report(request, model_key, object_id):
    content_type, obj = resolve_target(model_key, object_id)
    if request.method == "POST":
        form = ReportForm(request.POST)
        if form.is_valid():
            Report.objects.create(
                reporter=request.user, content_type=content_type, object_id=obj.pk,
                reason=form.cleaned_data["reason"],
            )
            messages.success(request, "Đã gửi báo cáo vi phạm, Giáo vụ Khoa sẽ xem xét.")
            return redirect(getattr(obj, "get_absolute_url", lambda: "/")())
    else:
        form = ReportForm()
    return render(request, "moderation/report_form.html", {"form": form, "object": obj})


@user_passes_test(_is_staff, login_url="home")
def report_list(request):
    reports = Report.objects.filter(status__in=[Report.Status.PENDING, Report.Status.REVIEWING]).select_related("reporter")
    return render(request, "moderation/report_list.html", {"reports": reports})


@user_passes_test(_is_staff, login_url="home")
def report_resolve(request, pk):
    report = get_object_or_404(Report, pk=pk)
    if request.method == "POST":
        form = ReportResolveForm(request.POST)
        if form.is_valid():
            action = form.cleaned_data["action"]
            note = form.cleaned_data["resolution_note"]
            obj = report.content_object

            if action == "hide" and obj is not None and hasattr(obj, "status"):
                obj.status = ContentStatus.HIDDEN if hasattr(ContentStatus, "HIDDEN") else obj.status
                obj.status = "hidden"
                obj.save(update_fields=["status"])
                log_action(actor=request.user, action=ModerationLog.Action.HIDE, reason=note, content_object=obj)
            elif action == "delete" and obj is not None and hasattr(obj, "status"):
                obj.status = "removed"
                obj.save(update_fields=["status"])
                log_action(actor=request.user, action=ModerationLog.Action.DELETE, reason=note, content_object=obj)

            report.status = Report.Status.RESOLVED if action != "dismiss" else Report.Status.DISMISSED
            report.handled_by = request.user
            report.resolution_note = note
            report.handled_at = timezone.now()
            report.save()
            messages.success(request, "Đã xử lý báo cáo.")
            return redirect("moderation:report_list")
    else:
        form = ReportResolveForm()
    return render(request, "moderation/report_resolve_form.html", {"form": form, "report": report})


@user_passes_test(_is_staff, login_url="home")
def pending_content_list(request):
    from announcements.models import Announcement
    from forum.models import ForumPost
    from groups.models import GroupPost
    from interactions.models import Comment

    context = {
        "announcements": Announcement.objects.filter(status=ContentStatus.PENDING_REVIEW),
        "forum_posts": ForumPost.objects.filter(status=ContentStatus.PENDING_REVIEW),
        "group_posts": GroupPost.objects.filter(status=ContentStatus.PENDING_REVIEW),
        "comments": Comment.objects.filter(status=Comment.Status.PENDING_REVIEW),
    }
    return render(request, "moderation/pending_content_list.html", context)


@user_passes_test(_is_staff, login_url="home")
def approve_content(request, model_key, object_id):
    content_type, obj = resolve_target(model_key, object_id)
    obj.status = "published"
    obj.save(update_fields=["status"])
    log_action(actor=request.user, action=ModerationLog.Action.APPROVE_CONTENT, reason="Duyệt nội dung chờ kiểm duyệt", content_object=obj)
    _notify_review_result(request.user, obj, approved=True)
    messages.success(request, "Đã duyệt và đăng nội dung.")
    return redirect("moderation:pending_content_list")


@user_passes_test(_is_staff, login_url="home")
def reject_content(request, model_key, object_id):
    content_type, obj = resolve_target(model_key, object_id)
    if request.method == "POST":
        form = ContentRejectForm(request.POST)
        if form.is_valid():
            reason = form.cleaned_data["reason"]
            obj.status = "removed"
            obj.save(update_fields=["status"])
            log_action(actor=request.user, action=ModerationLog.Action.REJECT_CONTENT, reason=reason, content_object=obj)
            _notify_review_result(request.user, obj, approved=False, reason=reason)
            messages.success(request, "Đã từ chối nội dung.")
            return redirect("moderation:pending_content_list")
    else:
        form = ContentRejectForm()
    return render(
        request, "moderation/reject_content_form.html",
        {"form": form, "object": obj, "is_rich_text": model_key != "comment"},
    )


def _notify_review_result(actor, obj, approved, reason=""):
    """Bao cho nguoi tao biet ket qua duyet/tu choi noi dung cho kiem duyet cua ho."""
    author = getattr(obj, "author", None)
    if not author:
        return
    if approved:
        message = "Nội dung của bạn đã được duyệt và đăng."
    else:
        message = f"Nội dung của bạn đã bị từ chối sau kiểm duyệt. Lý do: {reason}"
    # Comment khong co get_absolute_url rieng - tro ve noi dung cha (content_object cua Comment)
    link_target = obj if hasattr(obj, "get_absolute_url") else getattr(obj, "content_object", None)
    notify(
        recipient=author, verb=Notification.Verb.MODERATION, actor=actor,
        message=message, content_object=link_target,
    )


@login_required
def appeal_create(request):
    if request.user.is_active:
        messages.info(request, "Tài khoản của bạn không bị khóa.")
        return redirect("home")
    if request.method == "POST":
        form = AccountAppealForm(request.POST)
        if form.is_valid():
            appeal = form.save(commit=False)
            appeal.user = request.user
            appeal.save()
            messages.success(request, "Đã gửi kháng nghị, Giáo vụ Khoa sẽ xem xét lịch sử vi phạm trước khi phản hồi.")
            return redirect("home")
    else:
        form = AccountAppealForm()
    return render(request, "moderation/appeal_form.html", {"form": form})


@user_passes_test(_is_staff, login_url="home")
def appeal_list(request):
    appeals = AccountAppeal.objects.filter(status=AccountAppeal.Status.PENDING).select_related("user")
    return render(request, "moderation/appeal_list.html", {"appeals": appeals})


@user_passes_test(_is_staff, login_url="home")
def appeal_review(request, pk):
    appeal = get_object_or_404(AccountAppeal, pk=pk)
    violation_history = ModerationLog.objects.filter(target_user=appeal.user)
    if request.method == "POST":
        form = AppealReviewForm(request.POST)
        if form.is_valid():
            decision = form.cleaned_data["decision"]
            note = form.cleaned_data["review_note"]
            appeal.status = AccountAppeal.Status.ACCEPTED if decision == "accept" else AccountAppeal.Status.REJECTED
            appeal.review_note = note
            appeal.reviewed_by = request.user
            appeal.reviewed_at = timezone.now()
            appeal.save()

            if decision == "accept":
                appeal.user.is_active = True
                appeal.user.locked_reason = ""
                appeal.user.locked_at = None
                appeal.user.save(update_fields=["is_active", "locked_reason", "locked_at"])
                log_action(actor=request.user, action=ModerationLog.Action.APPEAL_ACCEPTED, reason=note, target_user=appeal.user)
            else:
                log_action(actor=request.user, action=ModerationLog.Action.APPEAL_REJECTED, reason=note, target_user=appeal.user)

            notify(
                recipient=appeal.user, verb=Notification.Verb.APPEAL_RESULT, actor=request.user,
                message=f"Kháng nghị của bạn đã được {appeal.get_status_display().lower()}: {note}",
            )
            messages.success(request, "Đã xử lý kháng nghị.")
            return redirect("moderation:appeal_list")
    else:
        form = AppealReviewForm()
    return render(request, "moderation/appeal_review.html", {"form": form, "appeal": appeal, "violation_history": violation_history})
