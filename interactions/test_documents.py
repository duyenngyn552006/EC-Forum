"""Test tai lieu dinh kem (link Drive / tep tai len) cho bai dien dan + bai nhom, va khoi code trong bai."""
import os
import shutil
import tempfile

from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse

from accounts.models import User
from config.sanitize import sanitize_html
from forum.models import Category, ForumPost
from groups.models import Group, GroupMembership, GroupPost
from moderation.models import SensitiveKeyword

from .documents import detect_kind, is_google_drive_url
from .models import DocumentLink

PRIVATE_TMP = tempfile.mkdtemp(prefix="ecforum-private-")
DOCX = "https://docs.google.com/document/d/abc123/edit"


def _upload(name="baitap.docx", content=b"PK\x03\x04 fake docx", size=None):
    data = content if size is None else b"x" * size
    return SimpleUploadedFile(name, data, content_type="application/octet-stream")


class DriveUrlTests(TestCase):
    def test_only_google_https_links(self):
        self.assertTrue(is_google_drive_url("https://drive.google.com/file/d/1/view"))
        self.assertTrue(is_google_drive_url(DOCX))
        for bad in ("http://drive.google.com/file/d/1", "https://evil.com/drive.google.com", "https://drive.google.com.evil.com/x",
                    "javascript:alert(1)", ""):
            self.assertFalse(is_google_drive_url(bad), bad)

    def test_kind_detection(self):
        self.assertEqual(detect_kind(DOCX)["key"], "doc")
        self.assertEqual(detect_kind("https://docs.google.com/spreadsheets/d/1/edit")["key"], "sheet")
        self.assertEqual(detect_kind("https://docs.google.com/presentation/d/1/edit")["key"], "slide")
        self.assertEqual(detect_kind("https://drive.google.com/drive/folders/1")["key"], "folder")
        self.assertEqual(detect_kind("https://drive.google.com/file/d/1/view")["key"], "file")


@override_settings(PRIVATE_MEDIA_ROOT=PRIVATE_TMP)
class ForumDocumentTests(TestCase):
    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(PRIVATE_TMP, ignore_errors=True)

    def setUp(self):
        cache.clear()
        self.addCleanup(cache.clear)
        self.user = User.objects.create_user(email="doc-user@due.udn.vn", password="Pass1234!")
        self.other = User.objects.create_user(email="doc-other@due.udn.vn", password="Pass1234!")
        self.category = Category.objects.create(name="DocCat")
        self.client.force_login(self.user)

    def _payload(self, docs=(), **extra):
        data = {
            "category": self.category.pk, "title": "Hoi ve bai tap", "body": "<p>Giup minh voi</p>",
            "documents-TOTAL_FORMS": str(max(len(docs), 1)), "documents-INITIAL_FORMS": "0",
            "documents-MIN_NUM_FORMS": "0", "documents-MAX_NUM_FORMS": "10",
        }
        for i, doc in enumerate(docs):
            for key, value in doc.items():
                data[f"documents-{i}-{key}"] = value
        data.update(extra)
        return data

    def _create(self, docs=(), **extra):
        return self.client.post(reverse("forum:post_create"), self._payload(docs, **extra))

    def test_create_post_with_drive_link_and_uploaded_file(self):
        response = self._create([{"title": "De bai", "url": DOCX}, {"title": "Code cua em", "file": _upload("main.py", b"print(1)")}])
        self.assertEqual(response.status_code, 302)
        post = ForumPost.objects.get(title="Hoi ve bai tap")
        docs = list(post.documents.order_by("position"))
        self.assertEqual([d.title for d in docs], ["De bai", "Code cua em"])
        self.assertEqual(docs[0].kind["key"], "doc")
        self.assertTrue(docs[1].is_upload)
        self.assertEqual(docs[1].file_size, len(b"print(1)"))
        # Tep nam trong private_media, khong nam trong MEDIA_ROOT cong khai
        self.assertTrue(os.path.abspath(docs[1].file.path).startswith(os.path.abspath(PRIVATE_TMP)))

    def test_post_without_documents_still_works(self):
        self.assertEqual(self._create().status_code, 302)
        self.assertFalse(DocumentLink.objects.exists())

    def test_non_google_link_rejected_and_post_not_created(self):
        response = self._create([{"title": "Link la", "url": "https://evil.example.com/file.docx"}])
        self.assertEqual(response.status_code, 200)
        self.assertFalse(ForumPost.objects.filter(title="Hoi ve bai tap").exists())

    def test_disallowed_extension_rejected(self):
        for name in ("hack.html", "x.svg", "run.exe", "a.js"):
            response = self._create([{"title": "Tep", "file": _upload(name)}])
            self.assertEqual(response.status_code, 200, name)
        self.assertFalse(DocumentLink.objects.exists())

    @override_settings(DOCUMENT_MAX_UPLOAD_MB=1)
    def test_file_too_large_rejected(self):
        response = self._create([{"title": "Lon", "file": _upload("big.pdf", size=1024 * 1024 + 1)}])
        self.assertEqual(response.status_code, 200)
        self.assertFalse(DocumentLink.objects.exists())

    def test_link_and_file_together_rejected(self):
        response = self._create([{"title": "Ca hai", "url": DOCX, "file": _upload()}])
        self.assertEqual(response.status_code, 200)

    def test_title_without_link_or_file_rejected(self):
        response = self._create([{"title": "Chi co ten"}])
        self.assertEqual(response.status_code, 200)
        self.assertFalse(ForumPost.objects.filter(title="Hoi ve bai tap").exists())

    def test_sensitive_keyword_in_document_title_rejected(self):
        SensitiveKeyword.objects.create(keyword="camtu")
        response = self._create([{"title": "tai lieu camtu", "url": DOCX}])
        self.assertEqual(response.status_code, 200)
        self.assertFalse(DocumentLink.objects.exists())

    # --- tai ve ---
    def _post_with_file(self, status="published"):
        self._create([{"title": "Bai tap.docx", "file": _upload()}])
        post = ForumPost.objects.get(title="Hoi ve bai tap")
        ForumPost.objects.filter(pk=post.pk).update(status=status)
        return post, post.documents.get()

    def test_download_forces_attachment_with_octet_stream(self):
        _, doc = self._post_with_file()
        self.client.force_login(self.other)
        response = self.client.get(reverse("interactions:download_document", args=[doc.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/octet-stream")
        self.assertIn("attachment", response["Content-Disposition"])
        self.assertEqual(b"".join(response.streaming_content), b"PK\x03\x04 fake docx")

    def test_download_requires_login(self):
        _, doc = self._post_with_file()
        self.client.logout()
        response = self.client.get(reverse("interactions:download_document", args=[doc.pk]))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("account_login"), response["Location"])

    def test_pending_post_file_only_for_author(self):
        _, doc = self._post_with_file(status="pending_review")
        url = reverse("interactions:download_document", args=[doc.pk])
        self.assertEqual(self.client.get(url).status_code, 200)  # tac gia
        self.client.force_login(self.other)
        self.assertEqual(self.client.get(url).status_code, 404)

    def test_detail_page_shows_document_cards(self):
        self._create([{"title": "De bai", "url": DOCX}, {"title": "Code", "file": _upload("main.py", b"print(1)")}])
        post = ForumPost.objects.get(title="Hoi ve bai tap")
        response = self.client.get(post.get_absolute_url())
        self.assertContains(response, "Tài liệu đính kèm (2)")
        self.assertContains(response, DOCX)
        self.assertContains(response, reverse("interactions:download_document", args=[post.documents.get(title="Code").pk]))

    # --- sua / xoa ---
    def test_edit_can_delete_document_and_file_removed_from_disk(self):
        post, doc = self._post_with_file()
        path = doc.file.path
        self.assertTrue(os.path.exists(path))
        self.client.post(reverse("forum:post_edit", args=[post.pk]), self._payload([{
            "id": doc.pk, "title": doc.title, "DELETE": "on",
        }], **{"documents-INITIAL_FORMS": "1"}))
        self.assertFalse(DocumentLink.objects.filter(pk=doc.pk).exists())
        self.assertFalse(os.path.exists(path))

    def test_deleting_post_deletes_its_documents_and_files(self):
        post, doc = self._post_with_file()
        path = doc.file.path
        post.delete()
        self.assertFalse(DocumentLink.objects.filter(pk=doc.pk).exists())
        self.assertFalse(os.path.exists(path))

    def test_request_without_document_block_keeps_existing_documents(self):
        post, doc = self._post_with_file()
        payload = self._payload(title="Hoi ve bai tap (sua)")
        for key in [k for k in payload if k.startswith("documents-")]:
            payload.pop(key)
        response = self.client.post(reverse("forum:post_edit", args=[post.pk]), payload)
        self.assertEqual(response.status_code, 302)
        self.assertTrue(DocumentLink.objects.filter(pk=doc.pk).exists())

    def test_form_page_has_document_section(self):
        response = self.client.get(reverse("forum:post_create"))
        self.assertContains(response, "Tài liệu đính kèm")
        self.assertContains(response, 'name="documents-0-file"')
        self.assertContains(response, 'name="documents-__prefix__-url"')


@override_settings(PRIVATE_MEDIA_ROOT=PRIVATE_TMP)
class GroupDocumentTests(TestCase):
    def setUp(self):
        cache.clear()
        self.addCleanup(cache.clear)
        self.leader = User.objects.create_user(email="gdoc-leader@due.udn.vn", password="Pass1234!", role=User.Role.LECTURER)
        self.member = User.objects.create_user(email="gdoc-member@due.udn.vn", password="Pass1234!")
        self.group = Group.objects.create(name="Nhom tai lieu", created_by=self.leader, status=Group.Status.ACTIVE)
        GroupMembership.objects.create(group=self.group, user=self.leader, role=GroupMembership.Role.LEADER)
        GroupMembership.objects.create(group=self.group, user=self.member, role=GroupMembership.Role.MEMBER)

    def test_member_posts_question_with_file_and_leader_can_download_while_pending(self):
        self.client.force_login(self.member)
        self.client.post(reverse("groups:post_create", args=[self.group.slug]), {
            "title": "Cau hoi nhom", "body": "<p>Loi code</p>",
            "documents-TOTAL_FORMS": "1", "documents-INITIAL_FORMS": "0",
            "documents-MIN_NUM_FORMS": "0", "documents-MAX_NUM_FORMS": "10",
            "documents-0-title": "loi.py", "documents-0-file": _upload("loi.py", b"x = 1/0"),
        })
        post = GroupPost.objects.get(title="Cau hoi nhom")
        doc = post.documents.get()
        self.assertEqual(doc.kind["key"], "code")
        # Bai nhom cho truong/pho nhom duyet -> truong nhom van tai duoc de xem xet
        self.client.force_login(self.leader)
        url = reverse("interactions:download_document", args=[doc.pk])
        self.assertEqual(post.status, "pending_review")
        self.assertEqual(self.client.get(url).status_code, 200)


class CodeBlockSanitizeTests(TestCase):
    def test_code_block_kept_with_language_and_indentation(self):
        html = '<pre><code class="language-python">def f():\n    return 1</code></pre>'
        self.assertEqual(sanitize_html(html), html)

    def test_code_block_strips_unsafe_attributes_and_scripts(self):
        cleaned = sanitize_html('<pre><code class="x" onclick="a()">ok</code></pre><script>alert(1)</script>')
        self.assertEqual(cleaned, "<pre><code>ok</code></pre>alert(1)")

    def test_inline_code_allowed(self):
        self.assertEqual(sanitize_html("<p>Dung <code>print()</code></p>"), "<p>Dung <code>print()</code></p>")
