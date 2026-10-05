from django.contrib.contenttypes.models import ContentType
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
