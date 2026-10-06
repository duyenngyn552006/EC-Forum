from .models import Notification, NotificationPreference

_PREF_FIELD_BY_VERB = {
    Notification.Verb.COMMENT: "notify_on_comment",
    Notification.Verb.LIKE: "notify_on_like",
    Notification.Verb.NEW_ANNOUNCEMENT: "notify_on_announcement",
    Notification.Verb.GROUP_APPROVED: "notify_on_group_activity",
    Notification.Verb.GROUP_REJECTED: "notify_on_group_activity",
    Notification.Verb.GROUP_INVITATION: "notify_on_group_activity",
    Notification.Verb.GROUP_JOIN_REQUEST: "notify_on_group_activity",
    Notification.Verb.GROUP_JOIN_APPROVED: "notify_on_group_activity",
    Notification.Verb.GROUP_JOIN_REJECTED: "notify_on_group_activity",
    Notification.Verb.GROUP_LEADERSHIP_TRANSFERRED: "notify_on_group_activity",
    Notification.Verb.MODERATION: "notify_on_moderation",
    Notification.Verb.APPEAL_RESULT: "notify_on_moderation",
    Notification.Verb.MENTION: "notify_on_group_activity",
}


def notify(recipient, verb, actor=None, message="", content_object=None):
    prefs, _ = NotificationPreference.objects.get_or_create(user=recipient)
    pref_field = _PREF_FIELD_BY_VERB.get(verb)
    if pref_field and not getattr(prefs, pref_field):
        return None
    return Notification.objects.create(
        recipient=recipient, actor=actor, verb=verb, message=message, content_object=content_object
    )
