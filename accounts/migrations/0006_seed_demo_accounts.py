from django.contrib.auth.hashers import make_password
from django.db import migrations

# Mat khau demo dung chung cho ca 8 tai khoan - CHI DUNG CHO MOI TRUONG DEV/DEMO LOCAL,
# doi mat khau that truoc khi dua ra ngoai pham vi noi bo.
DEMO_PASSWORD = "Test@12345"

# (email, ho, ten, role, extra_fields)
DEMO_USERS = [
    ("240101000001@due.udn.vn", "Nguyễn", "Văn An", "student", {"class_name": "24K1"}),
    ("240101000002@due.udn.vn", "Trần", "Thị Bình", "student", {"class_name": "24K2"}),
    ("giangvien1@due.udn.vn", "Lê", "Văn Cường", "lecturer", {}),
    ("giangvien2@due.udn.vn", "Phạm", "Thị Dung", "lecturer", {}),
    # BCH Khoa la sinh vien kiem nhiem nen van co "Lop"
    ("bch1@due.udn.vn", "Hoàng", "Văn Em", "bch", {"class_name": "23K5"}),
    ("bch2@due.udn.vn", "Vũ", "Thị Phương", "bch", {"class_name": "23K6"}),
    ("giaovu1@due.udn.vn", "Đặng", "Văn Giang", "staff", {}),
    ("giaovu2@due.udn.vn", "Bùi", "Thị Hà", "staff", {}),
]


def seed_accounts(apps, schema_editor):
    User = apps.get_model("accounts", "User")
    EmailAddress = apps.get_model("account", "EmailAddress")

    # Xoa toan bo tai khoan hien co (va moi du lieu lien quan qua CASCADE) truoc khi seed lai
    User.objects.all().delete()

    for email, last_name, first_name, role, extra in DEMO_USERS:
        is_staff_role = role == "staff"
        # Historical model (qua apps.get_model) khong giu lai AbstractBaseUser.set_password()
        # -> tu hash mat khau bang make_password() roi gan thang vao field password.
        user = User.objects.create(
            email=email,
            password=make_password(DEMO_PASSWORD),
            username=email,
            last_name=last_name,
            first_name=first_name,
            role=role,
            is_staff=is_staff_role,
            is_superuser=is_staff_role,
            is_active=True,
            **extra,
        )
        EmailAddress.objects.create(user=user, email=email, verified=True, primary=True)


def noop(apps, schema_editor):
    # Khong hoan tac - day la du lieu seed cho dev/demo, khong can rollback that su
    pass


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0005_user_cover_image"),
        ("account", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(seed_accounts, noop),
    ]
