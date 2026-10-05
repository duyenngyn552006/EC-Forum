from django.contrib.contenttypes.models import ContentType
from django.db.models import Count, F, IntegerField, Max, OuterRef, Subquery
from django.db.models.functions import Coalesce
from django.http import Http404

# Chi cho phep tuong tac (comment/like/save) tren 3 loai noi dung nay -
# tranh nhan content_type tuy y tu client.
ALLOWED_MODELS = {
    "announcement": ("announcements", "announcement"),
    "forumpost": ("forum", "forumpost"),
    "grouppost": ("groups", "grouppost"),
    "comment": ("interactions", "comment"),
}


def resolve_target(model_key, object_id):
    if model_key not in ALLOWED_MODELS:
        raise Http404("Loại nội dung không hợp lệ.")
    app_label, model = ALLOWED_MODELS[model_key]
    content_type = ContentType.objects.get(app_label=app_label, model=model)
    obj = content_type.get_object_for_this_type(pk=object_id)
    return content_type, obj


def get_top_level_comments(content_type, object_id):
    """Binh luan cap 1 (parent__isnull=True) kem san reply da published - dung chung
    cho forum/announcements/groups de hien thi threaded comment nhu Facebook."""
    from django.db.models import Prefetch

    from .models import Comment

    replies_qs = Comment.objects.filter(status="published").select_related("author").order_by("created_at")
    return (
        Comment.objects.filter(
            content_type=content_type, object_id=object_id, parent__isnull=True, status="published"
        )
        .select_related("author")
        .prefetch_related(Prefetch("replies", queryset=replies_qs))
        .order_by("created_at")
    )


def annotate_interaction_counts(queryset, model):
    """Gan them comment_count/like_count/last_activity_at vao 1 queryset (ForumPost/
    Announcement/GroupPost) bang Subquery theo content_type+object_id - khong can
    GenericRelation tren model (tranh phai them migration), dung cho trang danh sach
    de hien so binh luan/luot thich va sap xep theo "hoat dong gan nhat" (CLAUDE.md:
    giao dien hien thi du lieu tuong tac) ma khong bi N+1 query."""
    from .models import Comment, Like

    content_type = ContentType.objects.get_for_model(model)

    comment_counts = (
        Comment.objects.filter(content_type=content_type, object_id=OuterRef("pk"), status="published")
        .values("object_id")
        .annotate(count=Count("id"))
        .values("count")
    )
    like_counts = (
        Like.objects.filter(content_type=content_type, object_id=OuterRef("pk"))
        .values("object_id")
        .annotate(count=Count("id"))
        .values("count")
    )
    last_comment_at = (
        Comment.objects.filter(content_type=content_type, object_id=OuterRef("pk"), status="published")
        .values("object_id")
        .annotate(latest=Max("created_at"))
        .values("latest")
    )

    return queryset.annotate(
        comment_count=Coalesce(Subquery(comment_counts, output_field=IntegerField()), 0),
        like_count=Coalesce(Subquery(like_counts, output_field=IntegerField()), 0),
        last_activity_at=Coalesce(Subquery(last_comment_at), "created_at"),
    )


def increment_view_count(obj):
    """Tang luot xem khi mo trang chi tiet (ForumPost/Announcement/GroupPost) - dung
    update() truc tiep tren DB de tranh ghi de cac field khac va tranh race condition,
    sau do cap nhat lai gia tri tren object dang giu de hien thi dung ngay lan xem nay."""
    type(obj).objects.filter(pk=obj.pk).update(view_count=F("view_count") + 1)
    obj.view_count += 1


def get_interaction_context(user, obj):
    """Trang thai thich/luu cua user hien tai + tong so luot thich - dung cho 1 noi dung
    bat ky trong 3 loai o ALLOWED_MODELS, hien thi o partial interactions/_interactions.html."""
    from .models import Like, SavedItem

    content_type = ContentType.objects.get_for_model(obj)
    like_qs = Like.objects.filter(content_type=content_type, object_id=obj.pk)
    context = {"like_count": like_qs.count()}
    if user.is_authenticated:
        context["user_has_liked"] = like_qs.filter(user=user).exists()
        context["user_has_saved"] = SavedItem.objects.filter(
            user=user, content_type=content_type, object_id=obj.pk
        ).exists()
    else:
        context["user_has_liked"] = False
        context["user_has_saved"] = False
    return context
