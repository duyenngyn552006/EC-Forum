from django.db import migrations
from django.utils import timezone
from django.utils.text import slugify


def seed_groups_data(apps, schema_editor):
    Group = apps.get_model("groups", "Group")
    GroupMembership = apps.get_model("groups", "GroupMembership")
    GroupPost = apps.get_model("groups", "GroupPost")
    User = apps.get_model("accounts", "User")

    lecturer = User.objects.filter(email="giangvien1@due.udn.vn").first()
    bch = User.objects.filter(email="bch1@due.udn.vn").first()
    student1 = User.objects.filter(email="240101000001@due.udn.vn").first()
    student2 = User.objects.filter(email="240101000002@due.udn.vn").first()

    groups_to_create = [
        ("Nhóm học tập Marketing số", "Nhóm trao đổi bài tập, tài liệu môn Marketing số.", lecturer),
        ("CLB Truyền thông Khoa", "Nhóm hoạt động phong trào, sự kiện truyền thông của Khoa.", bch),
    ]

    for name, description, creator in groups_to_create:
        if not creator:
            continue
        group, created = Group.objects.get_or_create(
            name=name,
            defaults={
                "slug": slugify(name),
                "description": description,
                "status": "active",
                "created_by": creator,
                "approved_at": timezone.now(),
            },
        )
        GroupMembership.objects.get_or_create(group=group, user=creator, defaults={"role": "leader"})

        for member in (student1, student2):
            if member:
                GroupMembership.objects.get_or_create(group=group, user=member, defaults={"role": "member"})

        if created:
            GroupPost.objects.get_or_create(
                group=group,
                title="Bài viết chào mừng thành viên mới",
                defaults={
                    "author": creator,
                    "body": f"Chào mừng mọi người đến với '{name}'! Cùng nhau trao đổi và học tập nhé.",
                    "status": "published",
                },
            )


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):
    dependencies = [
        ("groups", "0001_initial"),
        ("accounts", "0006_seed_demo_accounts"),
    ]

    operations = [
        migrations.RunPython(seed_groups_data, noop),
    ]
