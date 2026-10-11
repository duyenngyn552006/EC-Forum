from django.db import migrations


def set_site_name(apps, schema_editor):
    Site = apps.get_model("sites", "Site")
    Site.objects.update_or_create(
        pk=1,
        defaults={"domain": "127.0.0.1:8000", "name": "EC Forum"},
    )


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0002_alter_user_managers"),
        ("sites", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(set_site_name, noop),
    ]
