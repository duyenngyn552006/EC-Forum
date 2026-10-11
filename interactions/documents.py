"""Tai lieu dinh kem cua bai dien dan / bai nhom: link Google Drive HOAC tep tai len.

- Link: chi nhan https cua drive.google.com / docs.google.com (khong nhan link tuy y de tranh lua dao/ma doc).
- Tep: chi nhan duoi trong ALLOWED_UPLOAD_EXTENSIONS, toi da settings.DOCUMENT_MAX_UPLOAD_MB; luu o
  private_media/ va chi tai ve qua view (xem interactions.views.download_document).
- Ten tai lieu van quet tu khoa nhay cam nhu noi dung bai viet.
"""
import os
from urllib.parse import urlparse

from django import forms
from django.conf import settings
from django.contrib.contenttypes.forms import generic_inlineformset_factory
from django.contrib.contenttypes.models import ContentType

from moderation.services import find_sensitive_keyword

from .models import DocumentLink

ALLOWED_HOSTS = {"drive.google.com", "docs.google.com"}
MAX_DOCUMENTS = 10

# (dieu kien tren duong dan) -> loai hien thi; thu tu = uu tien so khop
_KINDS = [
    ("docs.google.com", "/document/", {"key": "doc", "label": "Tài liệu (Docs / Word)", "icon": "📄"}),
    ("docs.google.com", "/spreadsheets/", {"key": "sheet", "label": "Bảng tính (Sheets / Excel)", "icon": "📊"}),
    ("docs.google.com", "/presentation/", {"key": "slide", "label": "Trình chiếu (Slides / PowerPoint)", "icon": "📽️"}),
    ("docs.google.com", "/forms/", {"key": "form", "label": "Biểu mẫu (Google Forms)", "icon": "📝"}),
    ("drive.google.com", "/folders/", {"key": "folder", "label": "Thư mục Drive", "icon": "📁"}),
]
_DEFAULT_KIND = {"key": "file", "label": "Tệp trên Google Drive", "icon": "📎"}

# Duoi tep duoc phep tai len -> loai hien thi. KHONG co .html/.htm/.svg/.js chay duoc trong trinh duyet
# o dang tai len truc tiep (code JS/HTML nen nen .zip hoac dan vao khoi code trong bai).
_UPLOAD_KINDS = {
    "doc": ("doc", "Word", "📄"), "docx": ("doc", "Word", "📄"), "odt": ("doc", "Tài liệu", "📄"),
    "xls": ("sheet", "Excel", "📊"), "xlsx": ("sheet", "Excel", "📊"), "csv": ("sheet", "CSV", "📊"),
    "ppt": ("slide", "PowerPoint", "📽️"), "pptx": ("slide", "PowerPoint", "📽️"),
    "pdf": ("pdf", "PDF", "📕"), "txt": ("file", "Văn bản", "📃"), "md": ("file", "Markdown", "📃"),
    "zip": ("folder", "Tệp nén", "🗜️"), "rar": ("folder", "Tệp nén", "🗜️"), "7z": ("folder", "Tệp nén", "🗜️"),
    "py": ("code", "Python", "💻"), "ipynb": ("code", "Jupyter Notebook", "💻"), "java": ("code", "Java", "💻"),
    "c": ("code", "C", "💻"), "cpp": ("code", "C++", "💻"), "cs": ("code", "C#", "💻"), "php": ("code", "PHP", "💻"),
    "sql": ("code", "SQL", "💻"), "json": ("code", "JSON", "💻"), "css": ("code", "CSS", "💻"), "r": ("code", "R", "💻"),
}
ALLOWED_UPLOAD_EXTENSIONS = sorted(_UPLOAD_KINDS)


def detect_upload_kind(filename):
    ext = os.path.splitext(filename or "")[1].lstrip(".").lower()
    key, label, icon = _UPLOAD_KINDS.get(ext, ("file", "Tệp", "📎"))
    return {"key": key, "label": f"{label} (.{ext})" if ext else label, "icon": icon}


def is_google_drive_url(url):
    parsed = urlparse(url or "")
    return parsed.scheme == "https" and (parsed.hostname or "").lower() in ALLOWED_HOSTS


def detect_kind(url):
    parsed = urlparse(url or "")
    host, path = (parsed.hostname or "").lower(), parsed.path
    for kind_host, marker, kind in _KINDS:
        if host == kind_host and marker in path:
            return kind
    return _DEFAULT_KIND


def get_documents(obj):
    return DocumentLink.objects.filter(content_type=ContentType.objects.get_for_model(obj), object_id=obj.pk)


class DocumentLinkForm(forms.ModelForm):
    class Meta:
        model = DocumentLink
        fields = ["title", "url", "file"]
        widgets = {
            "title": forms.TextInput(attrs={"placeholder": "VD: Bài tập chương 3"}),
            "url": forms.URLInput(attrs={"placeholder": "Dán link https://drive.google.com/... (hoặc chọn tệp bên dưới)"}),
            "file": forms.FileInput(attrs={"accept": ",".join(f".{e}" for e in ALLOWED_UPLOAD_EXTENSIONS)}),
        }

    def clean_url(self):
        url = (self.cleaned_data.get("url") or "").strip()
        if url and not is_google_drive_url(url):
            raise forms.ValidationError(
                "Chỉ nhận link Google Drive / Docs / Sheets / Slides (bắt đầu bằng https://drive.google.com "
                "hoặc https://docs.google.com). Hãy tải tệp Word, Excel, code... lên Drive rồi dán link chia sẻ."
            )
        return url

    def clean_file(self):
        upload = self.cleaned_data.get("file")
        # Tep da luu tu truoc (sua bai, khong chon tep moi) -> khong kiem tra lai
        if not upload or not hasattr(upload, "size") or getattr(upload, "_committed", False):
            return upload
        ext = os.path.splitext(upload.name)[1].lstrip(".").lower()
        if ext not in _UPLOAD_KINDS:
            raise forms.ValidationError(
                f"Không nhận tệp .{ext or '?'}. Chỉ nhận: " + ", ".join(f".{e}" for e in ALLOWED_UPLOAD_EXTENSIONS) + "."
            )
        max_mb = getattr(settings, "DOCUMENT_MAX_UPLOAD_MB", 10)
        if upload.size > max_mb * 1024 * 1024:
            raise forms.ValidationError(f"Tệp vượt quá {max_mb} MB. Tệp lớn hãy tải lên Google Drive rồi dán link.")
        return upload

    def clean(self):
        cleaned = super().clean()
        has_url = bool((cleaned.get("url") or "").strip())
        has_file = bool(cleaned.get("file"))
        if self.errors:
            return cleaned
        if has_url and has_file:
            raise forms.ValidationError("Mỗi tài liệu chỉ chọn 1 trong 2: dán link Drive hoặc tải tệp lên.")
        if not has_url and not has_file:
            raise forms.ValidationError("Hãy dán link Google Drive hoặc chọn tệp để tải lên.")
        upload = cleaned.get("file")
        if has_file and hasattr(upload, "size") and not getattr(upload, "_committed", False):
            self.instance.file_size = upload.size
        if has_url:
            self.instance.file_size = 0
        return cleaned

    def clean_title(self):
        title = self.cleaned_data["title"].strip()
        keyword = find_sensitive_keyword(title)
        if keyword:
            raise forms.ValidationError(f"Tên tài liệu chứa từ khóa nhạy cảm ('{keyword.keyword}').")
        return title


# Mac dinh 1 o trong; them o bang nut "+ Them tai lieu" (JS nhan ban empty_form, giong anh dinh kem thong bao)
DocumentLinkFormSet = generic_inlineformset_factory(
    DocumentLink, form=DocumentLinkForm, fields=["title", "url", "file"],
    extra=1, max_num=MAX_DOCUMENTS, validate_max=True, can_delete=True, can_delete_extra=False,
)
DOCUMENTS_PREFIX = "documents"


def build_document_formset(request, instance):
    """Formset tai lieu cho bai viet (instance co the chua luu khi tao bai moi)."""
    if request.method == "POST":
        data = request.POST
        # Request khong kem khoi tai lieu (form cu dang mo truoc khi deploy, goi API thang...) -> coi nhu khong
        # dinh kem gi va khong dung den tai lieu da co, thay vi bao loi "ManagementForm data is missing".
        if f"{DOCUMENTS_PREFIX}-TOTAL_FORMS" not in data:
            data = data.copy()
            data[f"{DOCUMENTS_PREFIX}-TOTAL_FORMS"] = "0"
            data[f"{DOCUMENTS_PREFIX}-INITIAL_FORMS"] = "0"
        return DocumentLinkFormSet(data, request.FILES, instance=instance, prefix=DOCUMENTS_PREFIX)
    return DocumentLinkFormSet(instance=instance, prefix=DOCUMENTS_PREFIX)


def save_document_formset(formset, saved_instance):
    """Luu sau khi bai viet da co pk (bai moi: formset duoc validate truoc khi tao bai)."""
    formset.instance = saved_instance
    for position, form in enumerate(formset.forms):
        form.instance.position = position
    formset.save()
