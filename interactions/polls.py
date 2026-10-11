"""Quy tac nghiep vu cho binh chon (Poll) - gan vao ForumPost/GroupPost.

Ai duoc tao:
  - Giao vu Khoa: moi bai.
  - Bai dien dan: chi tac gia la Giang vien/BCH.
  - Bai trong nhom: truong/pho nhom.
Sinh vien thuong chi duoc binh chon. Bai trong nhom chi thanh vien nhom moi duoc binh chon.
"""
from django.contrib.contenttypes.models import ContentType
from django.db.models import Count

from .models import Poll

POLLABLE_MODELS = ("forumpost", "grouppost")


def get_poll(obj):
    content_type = ContentType.objects.get_for_model(obj)
    return Poll.objects.filter(content_type=content_type, object_id=obj.pk).first()


def _is_group_manager(user, group):
    from groups.models import GroupMembership

    return group.memberships.filter(
        user=user, role__in=[GroupMembership.Role.LEADER, GroupMembership.Role.MODERATOR],
    ).exists()


def can_create_poll(user, obj):
    if not user.is_authenticated or obj._meta.model_name not in POLLABLE_MODELS:
        return False
    if user.role == "staff":
        return True
    if obj._meta.model_name == "forumpost":
        return user == obj.author and user.role in ("lecturer", "bch")
    return _is_group_manager(user, obj.group)


def can_vote(user, poll):
    """Dang nhap + poll chua dong + (bai nhom -> phai la thanh vien nhom)."""
    if not user.is_authenticated or poll.is_closed:
        return False
    target = poll.content_object
    if target is not None and target._meta.model_name == "grouppost":
        return user.role == "staff" or target.group.memberships.filter(user=user).exists()
    return True


def can_delete_poll(user, poll):
    return user.is_authenticated and (user == poll.created_by or user.role == "staff")


def build_poll_context(user, obj):
    """Du lieu hien thi poll cho partial _poll.html (poll=None neu bai chua co)."""
    poll = get_poll(obj)
    context = {"poll": None, "can_create_poll": False}
    if poll is None:
        context["can_create_poll"] = can_create_poll(user, obj)
        return context

    options = list(poll.options.annotate(vote_count=Count("votes")))
    total = sum(o.vote_count for o in options)
    my_vote = poll.votes.filter(user=user).first() if user.is_authenticated else None
    for option in options:
        option.percent = round(option.vote_count * 100 / total) if total else 0
        option.is_mine = my_vote is not None and my_vote.option_id == option.pk
    context["poll"] = poll
    context["poll_options"] = options
    context["poll_total_votes"] = total
    context["poll_my_option_id"] = my_vote.option_id if my_vote else None
    context["poll_can_vote"] = can_vote(user, poll)
    context["poll_can_delete"] = can_delete_poll(user, poll)
    return context
