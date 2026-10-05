from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse_lazy
from django.utils.decorators import method_decorator
from django.views.generic import CreateView, DeleteView, DetailView, ListView, UpdateView
from django_ratelimit.decorators import ratelimit

from accounts.models import User
from config.mixins import ContentStatus, PinLimitExceeded

from interactions.utils import annotate_interaction_counts

from . import services
from .forms import CategoryForm, ForumPostForm, TagForm
from .models import Category, ForumPost, Tag


def _is_staff(user):
    return user.is_authenticated and user.role == User.Role.STAFF


class _StaffRequiredMixin:
    """Chi Giao vu Khoa duoc quan ly Tag - giong cach lam voi
    accounts.views.UserListView va moderation.views keyword CRUD."""

    def dispatch(self, request, *args, **kwargs):
        if not _is_staff(request.user):
            messages.error(request, "Chỉ Giáo vụ Khoa mới có quyền quản lý thẻ.")
            return redirect("home")
        return super().dispatch(request, *args, **kwargs)


class PostListView(ListView):
    model = ForumPost
    template_name = "forum/post_list.html"
    context_object_name = "posts"
    paginate_by = 20

    def get_queryset(self):
        qs = ForumPost.objects.filter(status=ContentStatus.PUBLISHED).select_related("author", "category")
        category_slug = self.kwargs.get("category_slug")
        if category_slug:
            qs = qs.filter(category__slug=category_slug)
        query = self.request.GET.get("q")
        if query:
            from django.db.models import Q

            qs = qs.filter(Q(title__icontains=query) | Q(body__icontains=query))
        tag_slug = self.request.GET.get("tag")
        if tag_slug:
            qs = qs.filter(tags__slug=tag_slug)

        qs = annotate_interaction_counts(qs, ForumPost)
        # Ghim van uu tien len dau; "hoat dong gan nhat" = binh luan moi nhat dua bai
        # len lai dau danh sach, giup bai dang thao luan soi noi khong bi chim
        if self.request.GET.get("sort") == "activity":
            qs = qs.order_by("-is_pinned", "-last_activity_at")
        else:
            qs = qs.order_by("-is_pinned", "-created_at")
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["categories"] = Category.objects.all()
        ctx["tags"] = Tag.objects.all()
        ctx["current_tag"] = self.request.GET.get("tag", "")
        ctx["current_sort"] = self.request.GET.get("sort", "new")
        return ctx


class PostDetailView(DetailView):
    model = ForumPost
    template_name = "forum/post_detail.html"
    context_object_name = "post"

    def get_object(self, queryset=None):
        from interactions.utils import increment_view_count

        obj = super().get_object(queryset)
        increment_view_count(obj)
        return obj

    def get_context_data(self, **kwargs):
        from django.contrib.contenttypes.models import ContentType

        from interactions.utils import get_interaction_context, get_top_level_comments

        ctx = super().get_context_data(**kwargs)
        content_type = ContentType.objects.get_for_model(ForumPost)
        ctx["model_key"] = "forumpost"
        ctx["comments"] = get_top_level_comments(content_type, self.object.pk)
        ctx.update(get_interaction_context(self.request.user, self.object))
        return ctx


@method_decorator(ratelimit(key="user", rate="10/m", block=True), name="post")
class PostCreateView(LoginRequiredMixin, CreateView):
    model = ForumPost
    form_class = ForumPostForm
    template_name = "forum/post_form.html"

    def form_valid(self, form):
        post, keyword = services.create_post(
            author=self.request.user,
            category=form.cleaned_data["category"],
            title=form.cleaned_data["title"],
            body=form.cleaned_data["body"],
            tags=form.cleaned_data.get("tags"),
            featured_image=form.cleaned_data.get("featured_image"),
        )
        self.object = post
        if keyword:
            messages.warning(
                self.request,
                "Bài viết chứa từ khóa nhạy cảm nên đã chuyển sang trạng thái chờ kiểm duyệt. "
                "Giáo vụ Khoa sẽ xem xét trước khi đăng công khai.",
            )
        else:
            messages.success(self.request, "Đã đăng bài viết.")
        return redirect(self.object.get_absolute_url())


class PostUpdateView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    model = ForumPost
    form_class = ForumPostForm
    template_name = "forum/post_form.html"

    def test_func(self):
        post = self.get_object()
        return self.request.user == post.author or self.request.user.role == User.Role.STAFF

    def form_valid(self, form):
        post, keyword = services.update_post(
            post=self.get_object(),
            editor=self.request.user,
            title=form.cleaned_data["title"],
            body=form.cleaned_data["body"],
            tags=form.cleaned_data.get("tags"),
            featured_image=form.cleaned_data.get("featured_image"),
        )
        self.object = post
        if keyword:
            messages.warning(self.request, "Bài viết chứa từ khóa nhạy cảm nên đã chuyển sang trạng thái chờ kiểm duyệt.")
        else:
            messages.success(self.request, "Đã cập nhật bài viết.")
        return redirect(self.object.get_absolute_url())


class PostDeleteView(LoginRequiredMixin, UserPassesTestMixin, DeleteView):
    model = ForumPost
    template_name = "forum/post_confirm_delete.html"
    success_url = "/forum/"

    def test_func(self):
        post = self.get_object()
        return self.request.user == post.author or self.request.user.role == User.Role.STAFF


def _can_pin(user):
    return user.is_authenticated and user.role in (User.Role.LECTURER, User.Role.BCH, User.Role.STAFF)


def pin_post(request, pk):
    post = get_object_or_404(ForumPost, pk=pk)
    if not _can_pin(request.user):
        messages.error(request, "Bạn không có quyền ghim bài trong chuyên mục này.")
        return redirect(post.get_absolute_url())
    try:
        services.pin_post(post, request.user)
        messages.success(request, "Đã ghim bài viết.")
    except PinLimitExceeded as exc:
        messages.error(request, str(exc))
    return redirect(post.get_absolute_url())


def unpin_post(request, pk):
    post = get_object_or_404(ForumPost, pk=pk)
    if not _can_pin(request.user):
        messages.error(request, "Bạn không có quyền bỏ ghim bài viết này.")
        return redirect(post.get_absolute_url())
    services.unpin_post(post, request.user)
    messages.success(request, "Đã bỏ ghim bài viết.")
    return redirect(post.get_absolute_url())


class TagListView(_StaffRequiredMixin, ListView):
    model = Tag
    template_name = "forum/tag_list.html"
    context_object_name = "tags"


class TagCreateView(_StaffRequiredMixin, CreateView):
    model = Tag
    form_class = TagForm
    template_name = "forum/tag_form.html"
    success_url = reverse_lazy("forum:tag_list")

    def form_valid(self, form):
        messages.success(self.request, "Đã thêm thẻ.")
        return super().form_valid(form)


class TagUpdateView(_StaffRequiredMixin, UpdateView):
    model = Tag
    form_class = TagForm
    template_name = "forum/tag_form.html"
    success_url = reverse_lazy("forum:tag_list")

    def form_valid(self, form):
        messages.success(self.request, "Đã cập nhật thẻ.")
        return super().form_valid(form)


class TagDeleteView(_StaffRequiredMixin, DeleteView):
    model = Tag
    template_name = "forum/tag_confirm_delete.html"
    success_url = reverse_lazy("forum:tag_list")

    def form_valid(self, form):
        messages.success(self.request, "Đã xóa thẻ.")
        return super().form_valid(form)


class CategoryListView(_StaffRequiredMixin, ListView):
    model = Category
    template_name = "forum/category_list.html"
    context_object_name = "categories_manage"


class CategoryCreateView(_StaffRequiredMixin, CreateView):
    model = Category
    form_class = CategoryForm
    template_name = "forum/category_form.html"
    success_url = reverse_lazy("forum:category_list")

    def form_valid(self, form):
        messages.success(self.request, "Đã thêm chuyên mục.")
        return super().form_valid(form)


class CategoryUpdateView(_StaffRequiredMixin, UpdateView):
    model = Category
    form_class = CategoryForm
    template_name = "forum/category_form.html"
    success_url = reverse_lazy("forum:category_list")

    def form_valid(self, form):
        messages.success(self.request, "Đã cập nhật chuyên mục.")
        return super().form_valid(form)


class CategoryDeleteView(_StaffRequiredMixin, DeleteView):
    model = Category
    template_name = "forum/category_confirm_delete.html"
    success_url = reverse_lazy("forum:category_list")

    def form_valid(self, form):
        from django.db.models import ProtectedError

        try:
            response = super().form_valid(form)
        except ProtectedError:
            messages.error(
                self.request,
                "Không thể xóa chuyên mục này vì đang có bài viết thuộc chuyên mục đó. "
                "Hãy chuyển/xóa các bài viết trước.",
            )
            return redirect("forum:category_list")
        messages.success(self.request, "Đã xóa chuyên mục.")
        return response
