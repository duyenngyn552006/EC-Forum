from django import forms
from django.forms import inlineformset_factory

from .models import Announcement, AnnouncementAttachment


class AnnouncementForm(forms.ModelForm):
    # Ngay/gio dien ra su kien - chi bat buoc khi kind=EVENT (xem clean())
    event_datetime = forms.SplitDateTimeField(
        label="Thời gian diễn ra sự kiện",
        widget=forms.SplitDateTimeWidget(date_attrs={"type": "date"}, time_attrs={"type": "time"}),
        required=False,
    )

    class Meta:
        model = Announcement
        fields = ["kind", "title", "body", "featured_image", "event_datetime"]

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        from accounts.models import User

        if user and user.role == User.Role.BCH:
            # BCH Khoa chi dang su kien/hoat dong phong trao, khong dang thong bao chinh thuc
            self.fields["kind"].choices = [(Announcement.Kind.EVENT, Announcement.Kind.EVENT.label)]
            self.fields["kind"].initial = Announcement.Kind.EVENT
        elif user and user.role == "staff":
            self.fields["kind"].choices = [(Announcement.Kind.OFFICIAL, Announcement.Kind.OFFICIAL.label)]
            self.fields["kind"].initial = Announcement.Kind.OFFICIAL

    def clean(self):
        cleaned_data = super().clean()
        if cleaned_data.get("kind") == Announcement.Kind.EVENT and not cleaned_data.get("event_datetime"):
            self.add_error("event_datetime", "Bắt buộc nhập thời gian diễn ra sự kiện đối với thông báo loại sự kiện.")
        return cleaned_data


AnnouncementAttachmentFormSet = inlineformset_factory(
    Announcement, AnnouncementAttachment, fields=["image", "caption"], extra=3, can_delete=True
)
