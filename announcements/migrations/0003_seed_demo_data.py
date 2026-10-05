from datetime import timedelta

from django.db import migrations
from django.utils import timezone


def seed_announcements_data(apps, schema_editor):
    Announcement = apps.get_model("announcements", "Announcement")
    User = apps.get_model("accounts", "User")

    staff = User.objects.filter(email="giaovu1@due.udn.vn").first()
    bch = User.objects.filter(email="bch1@due.udn.vn").first()
    now = timezone.now()

    official_announcements = [
        (
            "Thông báo lịch nghỉ Tết Nguyên Đán",
            "Khoa Thương mại điện tử - Marketing và Công nghệ số thông báo lịch nghỉ Tết Nguyên Đán "
            "cho toàn thể sinh viên và giảng viên. Chi tiết lịch nghỉ sẽ được cập nhật trên website Trường.",
        ),
        (
            "Thông báo kế hoạch đăng ký học phần học kỳ mới",
            "Phòng Đào tạo thông báo kế hoạch đăng ký học phần cho học kỳ mới. Sinh viên vui lòng theo dõi "
            "thời gian đăng ký để đảm bảo quyền lợi học tập.",
        ),
    ]

    event_announcements = [
        (
            "Ngày hội việc làm Khoa TMĐT-Marketing-CNS 2026",
            "BCH Khoa tổ chức Ngày hội việc làm với sự tham gia của nhiều doanh nghiệp trong lĩnh vực "
            "thương mại điện tử và marketing số. Mời các bạn sinh viên tham gia đông đủ!",
            now + timedelta(days=14),
        ),
        (
            "Cuộc thi Ý tưởng khởi nghiệp số 2026",
            "BCH Khoa phát động cuộc thi Ý tưởng khởi nghiệp số dành cho sinh viên toàn Khoa. "
            "Đăng ký đội thi ngay để nhận nhiều phần thưởng hấp dẫn.",
            now + timedelta(days=30),
        ),
    ]

    if staff:
        for title, body in official_announcements:
            Announcement.objects.get_or_create(
                title=title,
                defaults={
                    "author": staff,
                    "kind": "official",
                    "body": body,
                    "status": "published",
                },
            )

    if bch:
        for title, body, event_datetime in event_announcements:
            Announcement.objects.get_or_create(
                title=title,
                defaults={
                    "author": bch,
                    "kind": "event",
                    "body": body,
                    "status": "published",
                    "event_datetime": event_datetime,
                },
            )


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):
    dependencies = [
        ("announcements", "0002_announcement_event_datetime"),
        ("accounts", "0006_seed_demo_accounts"),
    ]

    operations = [
        migrations.RunPython(seed_announcements_data, noop),
    ]
