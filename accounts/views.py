from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.views.generic import DetailView, ListView, UpdateView

from moderation.models import ModerationLog

from .models import User


class ProfileDetailView(LoginRequiredMixin, DetailView):
    model = User
    template_name = "accounts/profile_detail.html"
    context_object_name = "profile_user"
    slug_field = "username"
    slug_url_kwarg = "username"


class ProfileUpdateView(LoginRequiredMixin, UpdateView):
    model = User
    fields = ["first_name", "last_name", "class_name", "phone", "avatar", "cover_image", "bio"]
    template_name = "accounts/profile_form.html"
    success_url = reverse_lazy("accounts:my_profile")

    def get_object(self, queryset=None):
        return self.request.user

    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        # "Lop" chi danh cho Sinh vien/BCH Khoa (xem User.has_class_name_field)
        if not self.request.user.has_class_name_field:
            form.fields.pop("class_name", None)
        return form


@login_required
def my_profile(request):
    return redirect("accounts:profile_detail", username=request.user.username)


def _is_staff_role(user):
    return user.is_authenticated and user.role == User.Role.STAFF


class UserListView(LoginRequiredMixin, ListView):
    """Danh sach tai khoan - chi Giao vu Khoa duoc xem de gan/thu hoi vai tro."""

    model = User
    template_name = "accounts/user_list.html"
    context_object_name = "users"
    paginate_by = 30

    def dispatch(self, request, *args, **kwargs):
        if not _is_staff_role(request.user):
            messages.error(request, "Chỉ Giáo vụ Khoa mới có quyền quản lý tài khoản.")
            return redirect("home")
        return super().dispatch(request, *args, **kwargs)

    def get_queryset(self):
        return User.objects.all().order_by("-date_joined")


@user_passes_test(_is_staff_role, login_url="home")
def assign_role(request, pk):
    """Gan/thu hoi vai tro cho tai khoan - chi Giao vu Khoa."""
    target = get_object_or_404(User, pk=pk)
    if request.method == "POST":
        new_role = request.POST.get("role")
        if new_role in User.Role.values:
            old_role = target.role
            target.role = new_role
            update_fields = ["role"]
            # "Lop" chi danh cho Sinh vien/BCH Khoa - xoa neu doi sang vai tro khac
            if new_role not in User.ROLES_WITH_CLASS_NAME and target.class_name:
                target.class_name = ""
                update_fields.append("class_name")
            target.save(update_fields=update_fields)
            ModerationLog.objects.create(
                actor=request.user,
                target_user=target,
                action=ModerationLog.Action.ROLE_CHANGE,
                reason=f"Đổi vai trò từ '{old_role}' sang '{new_role}'",
            )
            messages.success(request, f"Đã cập nhật vai trò của {target} thành {target.get_role_display()}.")
        else:
            messages.error(request, "Vai trò không hợp lệ.")
        return redirect("accounts:user_list")
    return render(request, "accounts/assign_role_confirm.html", {"target": target, "roles": User.Role.choices})


@user_passes_test(_is_staff_role, login_url="home")
def toggle_lock_account(request, pk):
    """Khoa/mo khoa tai khoan - ghi ModerationLog, yeu cau nhap ly do khi khoa."""
    target = get_object_or_404(User, pk=pk)
    if request.method == "POST":
        if target.is_active:
            reason = request.POST.get("reason", "").strip()
            if not reason:
                messages.error(request, "Phải nhập lý do khi khóa tài khoản.")
                return redirect("accounts:user_list")
            target.is_active = False
            target.locked_reason = reason
            from django.utils import timezone

            target.locked_at = timezone.now()
            target.save(update_fields=["is_active", "locked_reason", "locked_at"])
            ModerationLog.objects.create(
                actor=request.user, target_user=target,
                action=ModerationLog.Action.LOCK_ACCOUNT, reason=reason,
            )
            messages.success(request, f"Đã khóa tài khoản {target}.")
        else:
            target.is_active = True
            target.locked_reason = ""
            target.locked_at = None
            target.save(update_fields=["is_active", "locked_reason", "locked_at"])
            ModerationLog.objects.create(
                actor=request.user, target_user=target,
                action=ModerationLog.Action.UNLOCK_ACCOUNT, reason="Mở khóa tài khoản",
            )
            messages.success(request, f"Đã mở khóa tài khoản {target}.")
    return redirect("accounts:user_list")
