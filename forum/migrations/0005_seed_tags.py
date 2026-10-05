from django.db import migrations
from django.utils.text import slugify

TAGS = ["Hỏi đáp", "Chia sẻ tài liệu", "Kinh nghiệm học tập", "Thực tập - Việc làm", "Sự kiện"]


def seed_tags(apps, schema_editor):
    Tag = apps.get_model("forum", "Tag")
    ForumPost = apps.get_model("forum", "ForumPost")

    tags = {}
    for name in TAGS:
        tag, _ = Tag.objects.get_or_create(name=name, defaults={"slug": slugify(name)})
        tags[name] = tag

    # Gan tag cho 2 bai viet demo da seed o migration 0002 de minh hoa quan he N-N
    welcome_post = ForumPost.objects.filter(title="Chào mừng tân sinh viên khóa 24").first()
    if welcome_post:
        welcome_post.tags.add(tags["Hỏi đáp"])

    sharing_post = ForumPost.objects.filter(title="Chia sẻ tài liệu ôn tập môn Marketing số").first()
    if sharing_post:
        sharing_post.tags.add(tags["Chia sẻ tài liệu"], tags["Kinh nghiệm học tập"])


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):
    dependencies = [
        ("forum", "0004_forumpost_featured_image"),
    ]

    operations = [
        migrations.RunPython(seed_tags, noop),
    ]
