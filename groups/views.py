from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import get_object_or_404, redirect, render
from django.views.generic import DetailView, ListView
from django_ratelimit.decorators import ratelimit

from accounts.models import User
from config.mixins import ContentStatus

from . import services
from .forms import GroupCreateForm, GroupPostForm, GroupRejectForm
from .models import Group, GroupMembership, GroupPost


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
        ctx["posts"] = self.object.posts.filter(status=ContentStatus.PUBLISHED)
        ctx["is_member"] = self.request.user.is_authenticated and self.object.memberships.filter(user=self.request.user).exists()
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
                messages.warning(request, "Bài viết chứa từ khóa nhạy cảm nên đã chuyển sang trạng thái chờ kiểm duyệt.")
            else:
                messages.success(request, "Đã đăng bài trong nhóm.")
            return redirect(post.get_absolute_url())
    else:
        form = GroupPostForm()
        _apply_mention_feed(form, group)
    return render(request, "groups/group_post_form.html", {"form": form, "group": group})


def _can_manage_group_post(user, post):
    return user.is_authenticated and (user == post.author or user.role == User.Role.STAFF)


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
                messages.warning(request, "Bài viết chứa từ khóa nhạy cảm nên đã chuyển sang trạng thái chờ kiểm duyệt.")
            else:
                messages.success(request, "Đã cập nhật bài viết.")
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


class GroupPostDetailView(DetailView):
    model = GroupPost
    template_name = "groups/group_post_detail.html"
    context_object_name = "post"
    pk_url_kwarg = "pk"

    def get_queryset(self):
        return GroupPost.objects.filter(group__slug=self.kwargs["slug"])

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
