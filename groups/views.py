from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import get_object_or_404, redirect, render
from django.views.generic import DetailView, ListView
from django_ratelimit.decorators import ratelimit

from accounts.models import User
from config.mixins import ContentStatus
from interactions.utils import annotate_interaction_counts

from . import services
from .forms import (
    BulkInviteMemberForm,
    GroupCreateForm,
    GroupDisableForm,
    GroupEditForm,
    GroupJoinRequestForm,
    GroupPostForm,
    GroupPostRejectForm,
    GroupRejectForm,
    InviteMemberForm,
    JoinRequestRejectForm,
    MemberRoleForm,
    TransferLeadershipForm,
)
from .models import Group, GroupJoinRequest, GroupMembership, GroupPost


class GroupListView(ListView):
    model = Group
    template_name = "groups/group_list.html"
    context_object_name = "groups"
    paginate_by = 20

    def get_queryset(self):
        return Group.objects.filter(status=Group.Status.ACTIVE)


class GroupDetailView(DetailView):
    model = Group
    template_name = "groups/group_detail.html"
    context_object_name = "group"
    slug_field = "slug"
    slug_url_kwarg = "slug"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        posts = annotate_interaction_counts(
            self.object.posts.filter(status=ContentStatus.PUBLISHED), GroupPost
        )
        current_sort = self.request.GET.get("sort", "new")
        posts = posts.order_by("-last_activity_at" if current_sort == "activity" else "-created_at")
        ctx["posts"] = posts
        ctx["current_sort"] = current_sort
        user = self.request.user
        my_membership = self.object.memberships.filter(user=user).first() if user.is_authenticated else None
        ctx["is_member"] = my_membership is not None
        ctx["my_role"] = my_membership.role if my_membership else None
        ctx["is_manager"] = my_membership is not None and my_membership.role in (
            GroupMembership.Role.LEADER, GroupMembership.Role.MODERATOR,
        )
        ctx["memberships"] = self.object.memberships.select_related("user").order_by(
            "role", "user__last_name", "user__first_name",
        )
        ctx["is_staff_user"] = user.is_authenticated and user.role == User.Role.STAFF
        ctx["invite_member_form"] = InviteMemberForm()
        ctx["bulk_invite_form"] = BulkInviteMemberForm()
        if ctx["is_manager"]:
            ctx["pending_join_requests"] = self.object.join_requests.filter(
                status=GroupJoinRequest.Status.PENDING
            ).select_related("user")
            pending_posts = self.object.posts.filter(status=ContentStatus.PENDING_REVIEW).select_related("author")
            for post in pending_posts:
                post.sensitive_keyword_note = services.get_sensitive_keyword_note(post)
            ctx["pending_posts"] = pending_posts
        ctx["has_pending_join_request"] = (
            user.is_authenticated and not ctx["is_member"]
            and self.object.join_requests.filter(user=user, status=GroupJoinRequest.Status.PENDING).exists()
        )
        return ctx


@login_required
def group_create(request):
    if request.method == "POST":
        form = GroupCreateForm(request.POST, request.FILES)
        if form.is_valid():
            group = services.request_create_group(
                creator=request.user, name=form.cleaned_data["name"], description=form.cleaned_data["description"],
                logo=form.cleaned_data.get("logo"), cover_image=form.cleaned_data.get("cover_image"),
            )
            if group.status == Group.Status.PENDING:
                messages.info(request, "Yêu cầu tạo nhóm đã được gửi, chờ Giáo vụ Khoa duyệt.")
            else:
                messages.success(request, "Đã tạo nhóm thành công.")
            return redirect("groups:list")
    else:
        form = GroupCreateForm()
    return render(request, "groups/group_form.html", {"form": form})


def _is_staff(user):
    return user.is_authenticated and user.role == User.Role.STAFF


@user_passes_test(_is_staff, login_url="home")
def pending_group_list(request):
    pending = Group.objects.filter(status=Group.Status.PENDING)
    return render(request, "groups/pending_group_list.html", {"groups": pending})


@user_passes_test(_is_staff, login_url="home")
def group_approve(request, pk):
    group = get_object_or_404(Group, pk=pk, status=Group.Status.PENDING)
    services.approve_group(group, request.user)
    messages.success(request, f"Đã duyệt nhóm '{group.name}'.")
    return redirect("groups:pending_list")


@user_passes_test(_is_staff, login_url="home")
def group_reject(request, pk):
    group = get_object_or_404(Group, pk=pk, status=Group.Status.PENDING)
    if request.method == "POST":
        form = GroupRejectForm(request.POST)
        if form.is_valid():
            services.reject_group(group, request.user, form.cleaned_data["reason"])
            messages.success(request, f"Đã từ chối nhóm '{group.name}'.")
            return redirect("groups:pending_list")
    else:
        form = GroupRejectForm()
    return render(request, "groups/group_reject_form.html", {"form": form, "group": group})


def _is_group_member(user, group):
    return user.is_authenticated and group.memberships.filter(user=user).exists()


def _apply_mention_feed(form, group):
    """Gan danh sach thanh vien nhom vao CKEditor Mention feed cua field 'body' (@gan the)."""
    from .mentions import build_mention_feed

    form.fields["body"].widget.config = dict(form.fields["body"].widget.config)
    form.fields["body"].widget.config["mention"] = {
        "feeds": [{"marker": "@", "feed": build_mention_feed(group), "minimumCharacters": 0}],
    }


@login_required
@ratelimit(key="user", rate="10/m", block=True)
def group_post_create(request, slug):
    from .mentions import extract_mentioned_user_ids, notify_mentions

    group = get_object_or_404(Group, slug=slug, status=Group.Status.ACTIVE)
    if not _is_group_member(request.user, group):
        messages.error(request, "Bạn phải là thành viên nhóm mới được đăng bài.")
        return redirect(group.get_absolute_url())
    if request.method == "POST":
        form = GroupPostForm(request.POST, request.FILES)
        _apply_mention_feed(form, group)
        if form.is_valid():
            post, keyword = services.create_group_post(
                group, request.user, form.cleaned_data["title"], form.cleaned_data["body"],
                featured_image=form.cleaned_data.get("featured_image"),
            )
            notify_mentions(request.user, extract_mentioned_user_ids(post.body), post)
            if keyword:
                messages.warning(request, "Bài viết chứa từ khóa nhạy cảm, đang chờ trưởng/phó nhóm duyệt.")
            else:
                messages.success(request, "Đã gửi bài viết, đang chờ trưởng/phó nhóm duyệt.")
            return redirect(post.get_absolute_url())
    else:
        form = GroupPostForm()
        _apply_mention_feed(form, group)
    return render(request, "groups/group_post_form.html", {"form": form, "group": group})


def _can_manage_group_post(user, post):
    return user.is_authenticated and (
        user == post.author or user.role == User.Role.STAFF or _is_group_manager(user, post.group)
    )


@login_required
def group_post_edit(request, slug, pk):
    from .mentions import extract_mentioned_user_ids, notify_mentions

    group = get_object_or_404(Group, slug=slug, status=Group.Status.ACTIVE)
    post = get_object_or_404(GroupPost, pk=pk, group=group)
    if not _can_manage_group_post(request.user, post):
        messages.error(request, "Bạn không có quyền sửa bài viết này.")
        return redirect(post.get_absolute_url())
    if request.method == "POST":
        form = GroupPostForm(request.POST, request.FILES, instance=post)
        _apply_mention_feed(form, group)
        if form.is_valid():
            post, keyword = services.update_group_post(
                post=post, editor=request.user,
                title=form.cleaned_data["title"], body=form.cleaned_data["body"],
                featured_image=form.cleaned_data.get("featured_image"),
            )
            notify_mentions(request.user, extract_mentioned_user_ids(post.body), post)
            if keyword:
                messages.warning(request, "Bài viết chứa từ khóa nhạy cảm, đang chờ trưởng/phó nhóm duyệt lại.")
            else:
                messages.success(request, "Đã cập nhật bài viết, đang chờ trưởng/phó nhóm duyệt lại.")
            return redirect(post.get_absolute_url())
    else:
        form = GroupPostForm(instance=post)
        _apply_mention_feed(form, group)
    return render(request, "groups/group_post_form.html", {"form": form, "group": group, "object": post})


@login_required
def group_post_delete(request, slug, pk):
    group = get_object_or_404(Group, slug=slug, status=Group.Status.ACTIVE)
    post = get_object_or_404(GroupPost, pk=pk, group=group)
    if not _can_manage_group_post(request.user, post):
        messages.error(request, "Bạn không có quyền xóa bài viết này.")
        return redirect(post.get_absolute_url())
    if request.method == "POST":
        post.delete()
        messages.success(request, "Đã xóa bài viết.")
        return redirect(group.get_absolute_url())
    return render(request, "groups/group_post_confirm_delete.html", {"post": post, "group": group})


@login_required
def group_post_approve(request, slug, pk):
    group = get_object_or_404(Group, slug=slug, status=Group.Status.ACTIVE)
    post = get_object_or_404(GroupPost, pk=pk, group=group, status=ContentStatus.PENDING_REVIEW)
    if not _is_group_manager(request.user, group):
        messages.error(request, "Bạn không có quyền duyệt bài viết trong nhóm.")
        return redirect(group.get_absolute_url())
    if request.method == "POST":
        services.approve_group_post(post, request.user)
        messages.success(request, "Đã duyệt và đăng bài viết.")
    return redirect(group.get_absolute_url())


@login_required
def group_post_reject(request, slug, pk):
    group = get_object_or_404(Group, slug=slug, status=Group.Status.ACTIVE)
    post = get_object_or_404(GroupPost, pk=pk, group=group, status=ContentStatus.PENDING_REVIEW)
    if not _is_group_manager(request.user, group):
        messages.error(request, "Bạn không có quyền từ chối bài viết trong nhóm.")
        return redirect(group.get_absolute_url())
    if request.method == "POST":
        form = GroupPostRejectForm(request.POST)
        if form.is_valid():
            try:
                services.reject_group_post(post, request.user, form.cleaned_data["reason"])
            except ValueError as exc:
                messages.error(request, str(exc))
            else:
                messages.success(request, "Đã từ chối bài viết.")
                return redirect(group.get_absolute_url())
    else:
        form = GroupPostRejectForm()
    return render(
        request, "groups/group_post_reject_form.html",
        {"form": form, "group": group, "post": post, "sensitive_keyword_note": services.get_sensitive_keyword_note(post)},
    )


def _is_group_manager(user, group):
    return user.is_authenticated and group.memberships.filter(
        user=user, role__in=[GroupMembership.Role.LEADER, GroupMembership.Role.MODERATOR],
    ).exists()


@login_required
def group_edit(request, slug):
    group = get_object_or_404(Group, slug=slug)
    is_leader = group.memberships.filter(user=request.user, role=GroupMembership.Role.LEADER).exists()
    if not (is_leader or request.user.role == User.Role.STAFF):
        messages.error(request, "Bạn không có quyền sửa thông tin nhóm này.")
        return redirect(group.get_absolute_url())
    if request.method == "POST":
        form = GroupEditForm(request.POST, request.FILES, instance=group)
        if form.is_valid():
            services.update_group_info(
                group, form.cleaned_data["name"], form.cleaned_data["description"],
                logo=form.cleaned_data.get("logo"), cover_image=form.cleaned_data.get("cover_image"),
            )
            messages.success(request, "Đã cập nhật thông tin nhóm.")
            return redirect(group.get_absolute_url())
    else:
        form = GroupEditForm(instance=group)
    return render(request, "groups/group_edit_form.html", {"form": form, "group": group})


@user_passes_test(_is_staff, login_url="home")
def group_disable(request, slug):
    group = get_object_or_404(Group, slug=slug, status=Group.Status.ACTIVE)
    if request.method == "POST":
        form = GroupDisableForm(request.POST)
        if form.is_valid():
            try:
                services.disable_group(group, request.user, form.cleaned_data["reason"])
            except ValueError as exc:
                messages.error(request, str(exc))
            else:
                messages.success(request, f"Đã vô hiệu hóa nhóm '{group.name}'.")
            return redirect(group.get_absolute_url())
    else:
        form = GroupDisableForm()
    return render(request, "groups/group_disable_form.html", {"form": form, "group": group})


@user_passes_test(_is_staff, login_url="home")
def group_enable(request, slug):
    group = get_object_or_404(Group, slug=slug, status=Group.Status.DISABLED)
    services.enable_group(group, request.user)
    messages.success(request, f"Đã kích hoạt lại nhóm '{group.name}'.")
    return redirect(group.get_absolute_url())


@login_required
def group_member_add(request, slug):
    group = get_object_or_404(Group, slug=slug, status=Group.Status.ACTIVE)
    if not _is_group_manager(request.user, group):
        messages.error(request, "Bạn không có quyền mời thành viên.")
        return redirect(group.get_absolute_url())
    if request.method == "POST":
        form = InviteMemberForm(request.POST)
        if form.is_valid():
            try:
                services.invite_member(group, form.cleaned_data["email"], request.user)
            except ValueError as exc:
                messages.error(request, str(exc))
            else:
                messages.success(request, "Đã thêm thành viên vào nhóm.")
    return redirect(group.get_absolute_url())


@login_required
def group_member_bulk_invite(request, slug):
    group = get_object_or_404(Group, slug=slug, status=Group.Status.ACTIVE)
    if not _is_group_manager(request.user, group):
        messages.error(request, "Bạn không có quyền mời thành viên.")
        return redirect(group.get_absolute_url())
    if request.method == "POST":
        form = BulkInviteMemberForm(request.POST, request.FILES)
        if form.is_valid():
            added, skipped = services.invite_members_bulk(group, form.cleaned_data["csv_file"], request.user)
            if added:
                messages.success(request, f"Đã thêm {len(added)} thành viên: {', '.join(added)}.")
            if skipped:
                detail = "; ".join(f"{email} ({reason})" for email, reason in skipped)
                messages.warning(request, f"Bỏ qua {len(skipped)} dòng: {detail}")
            if not added and not skipped:
                messages.warning(request, "Tệp CSV không có dòng email nào hợp lệ.")
        else:
            for error in form.errors.get("csv_file", []):
                messages.error(request, error)
    return redirect(group.get_absolute_url())


@login_required
def group_join_request_create(request, slug):
    group = get_object_or_404(Group, slug=slug, status=Group.Status.ACTIVE)
    if request.method == "POST":
        form = GroupJoinRequestForm(request.POST)
        if form.is_valid():
            try:
                services.request_to_join_group(group, request.user, form.cleaned_data["message"])
            except ValueError as exc:
                messages.error(request, str(exc))
            else:
                messages.success(request, "Đã gửi yêu cầu tham gia nhóm, chờ trưởng/phó nhóm xét duyệt.")
    return redirect(group.get_absolute_url())


@login_required
def group_join_request_approve(request, slug, request_id):
    group = get_object_or_404(Group, slug=slug, status=Group.Status.ACTIVE)
    if not _is_group_manager(request.user, group):
        messages.error(request, "Bạn không có quyền duyệt yêu cầu tham gia nhóm.")
        return redirect(group.get_absolute_url())
    join_request = get_object_or_404(GroupJoinRequest, pk=request_id, group=group)
    if request.method == "POST":
        try:
            services.approve_join_request(join_request, request.user)
        except ValueError as exc:
            messages.error(request, str(exc))
        else:
            messages.success(request, f"Đã chấp nhận {join_request.user} vào nhóm.")
    return redirect(group.get_absolute_url())


@login_required
def group_join_request_reject(request, slug, request_id):
    group = get_object_or_404(Group, slug=slug, status=Group.Status.ACTIVE)
    if not _is_group_manager(request.user, group):
        messages.error(request, "Bạn không có quyền từ chối yêu cầu tham gia nhóm.")
        return redirect(group.get_absolute_url())
    join_request = get_object_or_404(GroupJoinRequest, pk=request_id, group=group)
    if request.method == "POST":
        form = JoinRequestRejectForm(request.POST)
        if form.is_valid():
            try:
                services.reject_join_request(join_request, request.user, form.cleaned_data["reason"])
            except ValueError as exc:
                messages.error(request, str(exc))
            else:
                messages.success(request, f"Đã từ chối yêu cầu tham gia nhóm của {join_request.user}.")
                return redirect(group.get_absolute_url())
    else:
        form = JoinRequestRejectForm()
    return render(
        request, "groups/join_request_reject_form.html", {"form": form, "group": group, "join_request": join_request},
    )


@login_required
def group_member_remove(request, slug, user_id):
    group = get_object_or_404(Group, slug=slug, status=Group.Status.ACTIVE)
    if not _is_group_manager(request.user, group):
        messages.error(request, "Bạn không có quyền xóa thành viên.")
        return redirect(group.get_absolute_url())
    target = get_object_or_404(User, pk=user_id)
    if request.method == "POST":
        try:
            services.remove_member(group, target)
        except ValueError as exc:
            messages.error(request, str(exc))
        else:
            messages.success(request, f"Đã xóa {target} khỏi nhóm.")
    return redirect(group.get_absolute_url())


@login_required
def group_member_role(request, slug, user_id):
    group = get_object_or_404(Group, slug=slug, status=Group.Status.ACTIVE)
    if not _is_group_manager(request.user, group):
        messages.error(request, "Bạn không có quyền đổi vai trò thành viên.")
        return redirect(group.get_absolute_url())
    target = get_object_or_404(User, pk=user_id)
    if request.method == "POST":
        form = MemberRoleForm(request.POST)
        if form.is_valid():
            try:
                services.change_member_role(group, target, form.cleaned_data["role"])
            except ValueError as exc:
                messages.error(request, str(exc))
            else:
                messages.success(request, f"Đã đổi vai trò của {target}.")
    return redirect(group.get_absolute_url())


@login_required
def group_leave(request, slug):
    group = get_object_or_404(Group, slug=slug, status=Group.Status.ACTIVE)
    if request.method == "POST":
        try:
            services.leave_group(group, request.user)
        except ValueError as exc:
            messages.error(request, str(exc))
        else:
            messages.success(request, "Bạn đã rời nhóm.")
            return redirect("groups:list")
    return redirect(group.get_absolute_url())


@login_required
def group_transfer_leadership(request, slug):
    group = get_object_or_404(Group, slug=slug, status=Group.Status.ACTIVE)
    is_leader = group.memberships.filter(user=request.user, role=GroupMembership.Role.LEADER).exists()
    if not is_leader:
        messages.error(request, "Chỉ trưởng nhóm mới có quyền chuyển quyền trưởng nhóm.")
        return redirect(group.get_absolute_url())
    if request.method == "POST":
        form = TransferLeadershipForm(request.POST)
        if form.is_valid():
            target = get_object_or_404(User, pk=form.cleaned_data["new_leader_id"])
            try:
                services.transfer_leadership(group, target)
            except ValueError as exc:
                messages.error(request, str(exc))
            else:
                messages.success(request, f"Đã chuyển quyền trưởng nhóm cho {target}.")
    return redirect(group.get_absolute_url())


class GroupPostDetailView(DetailView):
    model = GroupPost
    template_name = "groups/group_post_detail.html"
    context_object_name = "post"
    pk_url_kwarg = "pk"

    def get_queryset(self):
        return GroupPost.objects.filter(group__slug=self.kwargs["slug"])

    def get_object(self, queryset=None):
        from interactions.utils import increment_view_count

        obj = super().get_object(queryset)
        increment_view_count(obj)
        return obj

    def get_context_data(self, **kwargs):
        from django.contrib.contenttypes.models import ContentType

        from interactions.utils import get_interaction_context, get_top_level_comments

        ctx = super().get_context_data(**kwargs)
        content_type = ContentType.objects.get_for_model(GroupPost)
        ctx["model_key"] = "grouppost"
        ctx["comments"] = get_top_level_comments(content_type, self.object.pk)
        ctx.update(get_interaction_context(self.request.user, self.object))

        from .mentions import build_mention_feed

        ctx["mention_feed"] = build_mention_feed(self.object.group)
        return ctx
