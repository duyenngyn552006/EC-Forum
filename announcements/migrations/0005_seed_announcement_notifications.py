from django.db import migrations


def seed_notifications(apps, schema_editor):
    Announcement = apps.get_model("announcements", "Announcement")
    Notification = apps.get_model("notifications", "Notification")
    ContentType = apps.get_model("contenttypes", "ContentType")
    User = apps.get_model("accounts", "User")

    content_type = ContentType.objects.get_for_model(Announcement)
    all_users = list(User.objects.filter(is_active=True))

    for announcement in Announcement.objects.filter(status="published"):
        for user in all_users:
            if user.pk == announcement.author_id:
                continue
            # get_or_create de idempotent - chay lai (vd tren DB da co seed truoc do) khong bi trung
            Notification.objects.get_or_create(
                recipient=user,
                verb="new_announcement",
                content_type=content_type,
                object_id=announcement.pk,
                defaults={
                    "actor_id": announcement.author_id,
                    "message": f"Thông báo mới: {announcement.title}",
                },
            )


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):
    dependencies = [
        ("announcements", "0004_alter_announcement_body"),
        ("notifications", "0001_initial"),
        ("contenttypes", "0002_remove_content_type_name"),
    ]

    operations = [
        migrations.RunPython(seed_notifications, noop),
    ]
