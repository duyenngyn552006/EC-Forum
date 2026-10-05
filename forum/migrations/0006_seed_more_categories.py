from django.db import migrations
from django.utils.text import slugify

CATEGORIES = [
    ("Học tập", "Trao đổi kiến thức, kinh nghiệm học tập các môn trong chương trình đào tạo của Khoa."),
    ("Hỏi đáp", "Đặt câu hỏi, nhờ giải đáp thắc mắc liên quan đến học tập, thủ tục, quy định của Khoa/Trường."),
    ("Chia sẻ tài liệu", "Chia sẻ link tài liệu, giáo trình, đề cương ôn tập (đính kèm link Google Drive)."),
    ("Việc làm - Thực tập", "Thông tin tuyển dụng, thực tập, kinh nghiệm phỏng vấn liên quan đến ngành TMĐT-Marketing-CNS."),
    ("Góc giải trí", "Chia sẻ linh tinh, giao lưu ngoài giờ học giữa sinh viên và giảng viên trong Khoa."),
]


def seed_categories(apps, schema_editor):
    Category = apps.get_model("forum", "Category")
    for name, description in CATEGORIES:
        Category.objects.get_or_create(
            name=name, defaults={"slug": slugify(name), "description": description},
        )


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):
    dependencies = [
        ("forum", "0005_seed_tags"),
    ]

    operations = [
        migrations.RunPython(seed_categories, noop),
    ]
