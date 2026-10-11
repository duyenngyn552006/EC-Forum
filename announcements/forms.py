from django import forms
from django.forms import inlineformset_factory

from .models import Announcement, AnnouncementAttachment


EVENT_MODE_SINGLE = "single"
EVENT_MODE_RANGE = "range"


class AnnouncementForm(forms.ModelForm):
    # Thoi gian dien ra su kien: 1 moc (chi event_datetime) hoac 1 khoang (event_datetime -> event_end_datetime).
    # Chi bat buoc khi kind=EVENT (xem clean())
    event_time_mode = forms.ChoiceField(
        label="Kiểu thời gian",
        choices=[(EVENT_MODE_SINGLE, "Một mốc thời gian"), (EVENT_MODE_RANGE, "Khoảng thời gian")],
        widget=forms.RadioSelect,
        initial=EVENT_MODE_SINGLE,
        required=False,
    )
    event_datetime = forms.SplitDateTimeField(
        label="Thời điểm diễn ra / bắt đầu",
        widget=forms.SplitDateTimeWidget(
            date_attrs={"type": "date", "aria-label": "Ngày bắt đầu"},
            time_attrs={"type": "time", "aria-label": "Giờ bắt đầu"},
        ),
        required=False,
    )
    event_end_datetime = forms.SplitDateTimeField(
        label="Kết thúc",
        widget=forms.SplitDateTimeWidget(
            date_attrs={"type": "date", "aria-label": "Ngày kết thúc"},
            time_attrs={"type": "time", "aria-label": "Giờ kết thúc"},
        ),
        required=False,
    )

    class Meta:
        model = Announcement
        fields = ["kind", "title", "body", "featured_image", "event_datetime", "event_end_datetime"]
        labels = {"kind": "Loại thông báo", "title": "Tiêu đề", "body": "Nội dung"}

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        from accounts.models import User

        # Sua bai da co khoang thoi gian -> mo san o che do "Khoang thoi gian"
        if self.instance.pk and self.instance.event_end_datetime:
            self.initial["event_time_mode"] = EVENT_MODE_RANGE

        # Giao vu Khoa, Giang vien/BCN Khoa va BCH Khoa deu dang duoc ca thong bao chinh thuc lan su kien.
        # Bai moi cua BCH mac dinh chon san "Su kien" (viec chinh cua BCH), cac vai tro khac mac dinh "Chinh thuc".
        if user and user.role == User.Role.BCH and not self.instance.pk:
            self.fields["kind"].initial = Announcement.Kind.EVENT

    def clean(self):
        cleaned_data = super().clean()
        is_event = cleaned_data.get("kind") == Announcement.Kind.EVENT
        start = cleaned_data.get("event_datetime")
        end = cleaned_data.get("event_end_datetime")

        if is_event and not start:
            self.add_error("event_datetime", "Bắt buộc nhập thời gian diễn ra sự kiện đối với thông báo loại sự kiện.")

        if is_event and cleaned_data.get("event_time_mode") == EVENT_MODE_RANGE:
            if start and not end:
                self.add_error("event_end_datetime", "Vui lòng nhập thời điểm kết thúc (hoặc chuyển sang “Một mốc thời gian”).")
            elif start and end and end <= start:
                self.add_error("event_end_datetime", "Thời điểm kết thúc phải sau thời điểm bắt đầu.")
        else:
            # Che do 1 moc (hoac khong phai su kien): bo gio ket thuc con sot lai tu lan chon truoc
            cleaned_data["event_end_datetime"] = None
        return cleaned_data


MAX_ATTACHMENTS = 10

# Mac dinh 1 o anh trong; them o bang nut "+ Them anh" (JS nhan ban formset.empty_form).
# O "Xoa" chi co o anh da luu (can_delete_extra=False), anh moi chua tai len thi khong can xoa.
AnnouncementAttachmentFormSet = inlineformset_factory(
    Announcement, AnnouncementAttachment, fields=["image", "caption"],
    extra=1, can_delete=True, can_delete_extra=False, max_num=MAX_ATTACHMENTS, validate_max=True,
    labels={"image": "Ảnh", "caption": "Chú thích"},
    widgets={
        "image": forms.FileInput(attrs={"accept": "image/*"}),
        "caption": forms.TextInput(attrs={"placeholder": "Chú thích (không bắt buộc)"}),
    },
)
