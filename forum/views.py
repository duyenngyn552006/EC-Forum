from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.contrib.contenttypes.models import ContentType
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse_lazy
from django.utils.decorators import method_decorator
from django.views.decorators.http import require_POST
from django.views.generic import CreateView, DeleteView, DetailView, ListView, UpdateView
from django_ratelimit.decorators import ratelimit

from accounts.models import User
from config.mixins import ContentStatus, PinLimitExceeded

from interactions.documents import build_document_formset, get_documents, save_document_formset
from interactions.follows import is_following
from interactions.models import Comment
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
    paginate_by = 10

    def get_queryset(self):
        qs = ForumPost.objects.filter(status=ContentStatus.PUBLISHED).select_related("author", "category")
        category_slug = self.kwargs.get("category_slug")
        if category_slug:
            qs = qs.filter(category__slug=category_slug)
        tag_slug = self.request.GET.get("tag")
        if tag_slug:
            qs = qs.filter(tags__slug=tag_slug)
        # Hoi dap: chi cau hoi / cau hoi chua co cau tra loi duoc chon
        kind = self.request.GET.get("kind")
        if kind == "question":
            qs = qs.filter(is_question=True)
        elif kind == "unsolved":
            qs = qs.filter(is_question=True, accepted_answer__isnull=True)

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
        ctx["current_kind"] = self.request.GET.get("kind", "")

        # Nut "Theo doi" cho chuyen muc / the dang loc (neu co)
        category_slug = self.kwargs.get("category_slug")
        ctx["current_category"] = Category.objects.filter(slug=category_slug).first() if category_slug else None
        ctx["current_tag_obj"] = Tag.objects.filter(slug=ctx["current_tag"]).first() if ctx["current_tag"] else None
        ctx["following_category"] = is_following(self.request.user, ctx["current_category"]) if ctx["current_category"] else False
        ctx["following_tag"] = is_following(self.request.user, ctx["current_tag_obj"]) if ctx["current_tag_obj"] else False
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
        ctx["accepted_answer_id"] = self.object.accepted_answer_id
        ctx["can_accept_answer"] = self.object.is_question and _can_accept_answer(self.request.user, self.object)
        ctx["is_following_post"] = is_following(self.request.user, self.object)
        ctx["documents"] = get_documents(self.object)
        return ctx


class _DocumentFormsetMixin:
    """Formset tai lieu dinh kem (link Google Drive) di kem form tao/sua bai. Formset duoc kiem tra
    TRUOC khi tao/sua bai -> link sai thi bao loi, khong tao ra bai do dang."""

    def _document_formset(self):
        if not hasattr(self, "_doc_formset"):
            self._doc_formset = build_document_formset(self.request, self.object or ForumPost())
        return self._doc_formset

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["document_formset"] = self._document_formset()
        return ctx

    def form_valid(self, form):
        if not self._document_formset().is_valid():
            return self.form_invalid(form)
        return self.save_post(form)


@method_decorator(ratelimit(key="user", rate="10/m", block=True), name="post")
class PostCreateView(LoginRequiredMixin, _DocumentFormsetMixin, CreateView):
    model = ForumPost
    form_class = ForumPostForm
    template_name = "forum/post_form.html"

    def save_post(self, form):
        post, keyword = services.create_post(
            author=self.request.user,
            category=form.cleaned_data["category"],
            title=form.cleaned_data["title"],
            body=form.cleaned_data["body"],
            tags=form.cleaned_data.get("tags"),
            featured_image=form.cleaned_data.get("featured_image"),
            is_question=form.cleaned_data.get("is_question", False),
        )
        self.object = post
        save_document_formset(self._document_formset(), post)
        if keyword:
            messages.warning(
                self.request,
                "Bài viết chứa từ khóa nhạy cảm nên đã chuyển sang trạng thái chờ kiểm duyệt. "
                "Giáo vụ Khoa sẽ xem xét trước khi đăng công khai.",
            )
        else:
            messages.success(self.request, "Đã đăng bài viết.")
        return redirect(self.object.get_absolute_url())


class PostUpdateView(LoginRequiredMixin, UserPassesTestMixin, _DocumentFormsetMixin, UpdateView):
    model = ForumPost
    form_class = ForumPostForm
    template_name = "forum/post_form.html"

    def test_func(self):
        post = self.get_object()
        return self.request.user == post.author or self.request.user.role == User.Role.STAFF

    def save_post(self, form):
        post, keyword = services.update_post(
            post=self.get_object(),
            editor=self.request.user,
            title=form.cleaned_data["title"],
            body=form.cleaned_data["body"],
            tags=form.cleaned_data.get("tags"),
            featured_image=form.cleaned_data.get("featured_image"),
            is_question=form.cleaned_data.get("is_question", False),
        )
        self.object = post
        save_document_formset(self._document_formset(), post)
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


def _can_accept_answer(user, post):
    """Nguoi hoi, giang vien, hoac Giao vu Khoa chon duoc cau tra loi."""
    return user.is_authenticated and (
        user == post.author or user.role in (User.Role.LECTURER, User.Role.STAFF)
    )


@login_required
@require_POST
def accept_answer(request, pk, comment_id):
    post = get_object_or_404(ForumPost, pk=pk)
    if not post.is_question:
        messages.error(request, "Chỉ bài đăng dạng câu hỏi mới chọn được câu trả lời.")
        return redirect(post.get_absolute_url())
    if not _can_accept_answer(request.user, post):
        messages.error(request, "Chỉ người đặt câu hỏi, giảng viên hoặc Giáo vụ Khoa mới chọn được câu trả lời.")
        return redirect(post.get_absolute_url())
    comment = get_object_or_404(
        Comment, pk=comment_id, content_type=ContentType.objects.get_for_model(ForumPost), object_id=post.pk,
        status=Comment.Status.PUBLISHED,
    )
    if services.set_accepted_answer(post, comment, request.user):
        messages.success(request, "Đã chọn câu trả lời. Bài viết được đánh dấu “Đã giải đáp”.")
    else:
        messages.success(request, "Đã bỏ chọn câu trả lời.")
    return redirect(post.get_absolute_url())


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
