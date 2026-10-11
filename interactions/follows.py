"""Theo doi (Follow) chuyen muc/the/bai viet - tim nguoi theo doi de gui thong bao."""
from django.contrib.contenttypes.models import ContentType
from django.db.models import Q

from accounts.models import User
from notifications.models import Notification
from notifications.services import notify

from .models import Follow


def get_followers(*targets):
    """Nguoi dung (is_active) dang theo doi it nhat 1 trong cac doi tuong `targets`."""
    query = Q()
    for target in targets:
        query |= Q(content_type=ContentType.objects.get_for_model(target), object_id=target.pk)
    if not query:
        return User.objects.none()
    user_ids = Follow.objects.filter(query).values_list("user_id", flat=True)
    return User.objects.filter(pk__in=user_ids, is_active=True)


def is_following(user, target):
    return user.is_authenticated and Follow.objects.filter(
        user=user, content_type=ContentType.objects.get_for_model(target), object_id=target.pk,
    ).exists()


def notify_followers(targets, message, link_object, exclude_user_ids=()):
    """Moi nguoi theo doi nhan toi da 1 thong bao du theo doi nhieu `targets` cung luc."""
    for follower in get_followers(*targets).exclude(pk__in=set(exclude_user_ids)):
        notify(
            recipient=follower, verb=Notification.Verb.FOLLOW_UPDATE,
            message=message, content_object=link_object,
        )
