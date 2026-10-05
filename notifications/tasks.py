from celery import shared_task

from .models import Notification
from .services import notify


@shared_task
def broadcast_notification(recipient_ids, verb, message, actor_id=None):
    """Gui thong bao (vd thong bao chinh thuc moi) cho nhieu nguoi dung o background qua Celery."""
    from accounts.models import User

    actor = User.objects.filter(pk=actor_id).first() if actor_id else None
    for recipient in User.objects.filter(pk__in=recipient_ids, is_active=True):
        notify(recipient=recipient, verb=verb, actor=actor, message=message)
