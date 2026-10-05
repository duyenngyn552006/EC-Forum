from django.db import migrations


def seed_forum_data(apps, schema_editor):
    Category = apps.get_model("forum", "Category")
    ForumPost = apps.get_model("forum", "ForumPost")
    User = apps.get_model("accounts", "User")

    category, _ = Category.objects.get_or_create(
        slug="thao-luan-chung",
        defaults={"name": "Thảo luận chung", "description": "Chuyên mục thảo luận chung cho sinh viên và giảng viên."},
    )

    student = User.objects.filter(email="240101000001@due.udn.vn").first()
    lecturer = User.objects.filter(email="giangvien1@due.udn.vn").first()

    if student:
        ForumPost.objects.get_or_create(
            title="Chào mừng tân sinh viên khóa 24",
            defaults={
                "author": student,
                "category": category,
                "body": "Xin chào mọi người, mình là sinh viên khóa 24, rất vui được tham gia diễn đàn của Khoa!",
                "status": "published",
            },
        )

    if lecturer:
        ForumPost.objects.get_or_create(
            title="Chia sẻ tài liệu ôn tập môn Marketing số",
            defaults={
                "author": lecturer,
                "category": category,
                "body": "Thầy/cô chia sẻ bộ tài liệu ôn tập môn Marketing số cho các bạn sinh viên, các em xem trong nhóm học tập nhé.",
                "status": "published",
            },
        )


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):
    dependencies = [
        ("forum", "0001_initial"),
        ("accounts", "0006_seed_demo_accounts"),
    ]

    operations = [
        migrations.RunPython(seed_forum_data, noop),
    ]
