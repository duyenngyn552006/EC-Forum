"""Test form anh dinh kem: 1 o mac dinh, o "Xoa" chi cho anh da luu, tai/xoa anh qua form."""
import io
import shutil
import tempfile

from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from PIL import Image

from accounts.models import User

from .models import Announcement, AnnouncementAttachment

TEMP_MEDIA = tempfile.mkdtemp(prefix="ecforum-test-media-")


def _png(name="anh.png"):
    buf = io.BytesIO()
    Image.new("RGB", (4, 4), "blue").save(buf, format="PNG")
    return SimpleUploadedFile(name, buf.getvalue(), content_type="image/png")


@override_settings(MEDIA_ROOT=TEMP_MEDIA)
class AttachmentFormTests(TestCase):
    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(TEMP_MEDIA, ignore_errors=True)

    def setUp(self):
        cache.clear()
        self.addCleanup(cache.clear)
        self.staff = User.objects.create_user(email="att-staff@due.udn.vn", password="Pass1234!", role=User.Role.STAFF)
        self.client.force_login(self.staff)

    def _payload(self, **extra):
        payload = {
            "kind": "official", "title": "Thong bao co anh", "body": "noi dung",
            "attachments-TOTAL_FORMS": "1", "attachments-INITIAL_FORMS": "0",
            "attachments-MIN_NUM_FORMS": "0", "attachments-MAX_NUM_FORMS": "10",
        }
        payload.update(extra)
        return payload

    def test_create_page_shows_one_empty_slot_without_delete_box(self):
        response = self.client.get(reverse("announcements:create"))
        formset = response.context["formset"]
        self.assertEqual(len(formset.forms), 1)
        self.assertNotIn("DELETE", formset.forms[0].fields)
        self.assertNotContains(response, "Xóa ảnh này")
        self.assertContains(response, "+ Thêm ảnh")
        self.assertContains(response, 'name="attachments-__prefix__-image"')  # mau cho nut them anh

    def test_labels_are_vietnamese(self):
        form = self.client.get(reverse("announcements:create")).context["formset"].forms[0]
        self.assertEqual((form["image"].label, form["caption"].label), ("Ảnh", "Chú thích"))

    def test_upload_attachment_on_create(self):
        self.client.post(reverse("announcements:create"), self._payload(**{
            "attachments-0-image": _png(), "attachments-0-caption": "Anh 1",
        }))
        attachment = AnnouncementAttachment.objects.get()
        self.assertEqual(attachment.caption, "Anh 1")

    def test_empty_slot_is_ignored(self):
        response = self.client.post(reverse("announcements:create"), self._payload())
        self.assertEqual(response.status_code, 302)
        self.assertFalse(AnnouncementAttachment.objects.exists())

    def test_added_slots_via_total_forms_are_saved(self):
        self.client.post(reverse("announcements:create"), self._payload(**{
            "attachments-TOTAL_FORMS": "3",
            "attachments-0-image": _png("a.png"), "attachments-2-image": _png("c.png"),
        }))
        self.assertEqual(AnnouncementAttachment.objects.count(), 2)

    def _announcement_with_attachment(self):
        a = Announcement.objects.create(author=self.staff, kind="official", title="Co anh", body="x", status="published")
        att = AnnouncementAttachment.objects.create(announcement=a, image=_png(), caption="Anh cu")
        return a, att

    def test_edit_page_shows_existing_image_with_delete_box(self):
        a, att = self._announcement_with_attachment()
        response = self.client.get(reverse("announcements:edit", args=[a.pk]))
        self.assertContains(response, att.image.url)
        self.assertContains(response, "Xóa ảnh này")

    def test_delete_existing_attachment_on_edit(self):
        a, att = self._announcement_with_attachment()
        self.client.post(reverse("announcements:edit", args=[a.pk]), self._payload(**{
            "title": "Co anh", "attachments-TOTAL_FORMS": "1", "attachments-INITIAL_FORMS": "1",
            "attachments-0-id": att.pk, "attachments-0-announcement": a.pk,
            "attachments-0-caption": "Anh cu", "attachments-0-DELETE": "on",
        }))
        self.assertFalse(AnnouncementAttachment.objects.filter(pk=att.pk).exists())

    def test_keep_existing_image_when_no_new_file_chosen(self):
        a, att = self._announcement_with_attachment()
        old_name = att.image.name
        self.client.post(reverse("announcements:edit", args=[a.pk]), self._payload(**{
            "title": "Co anh", "attachments-TOTAL_FORMS": "1", "attachments-INITIAL_FORMS": "1",
            "attachments-0-id": att.pk, "attachments-0-announcement": a.pk, "attachments-0-caption": "Chu thich moi",
        }))
        att.refresh_from_db()
        self.assertEqual((att.image.name, att.caption), (old_name, "Chu thich moi"))
