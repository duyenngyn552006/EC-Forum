from django import forms
from django.utils import timezone

from .models import Group, GroupPost


GROUP_LABELS = {"name": "Tên nhóm", "description": "Mô tả nhóm"}


class GroupCreateForm(forms.ModelForm):
    class Meta:
        model = Group
        fields = ["name", "description", "logo", "cover_image"]
        labels = GROUP_LABELS


class GroupRejectForm(forms.Form):
    reason = forms.CharField(widget=forms.Textarea, label="Lý do từ chối", required=True)


class GroupEditForm(forms.ModelForm):
    class Meta:
        model = Group
        fields = ["name", "description", "logo", "cover_image", "is_recruiting", "recruit_positions", "recruit_deadline"]
        labels = GROUP_LABELS
        widgets = {
            "recruit_positions": forms.Textarea(attrs={"rows": 3, "placeholder": "VD: Thiết kế đồ họa, viết nội dung, chạy quảng cáo..."}),
            "recruit_deadline": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
        }

    def clean(self):
        cleaned = super().clean()
        if cleaned.get("is_recruiting"):
            if not (cleaned.get("recruit_positions") or "").strip():
                self.add_error("recruit_positions", "Hãy mô tả vị trí/kỹ năng đang cần tuyển.")
            deadline = cleaned.get("recruit_deadline")
            if deadline and deadline < timezone.localdate():
                self.add_error("recruit_deadline", "Hạn nhận đăng ký không được ở quá khứ.")
        return cleaned


class GroupDisableForm(forms.Form):
    reason = forms.CharField(widget=forms.Textarea, label="Lý do vô hiệu hóa", required=True)


class InviteMemberForm(forms.Form):
    email = forms.EmailField(label="Email người muốn mời")


class BulkInviteMemberForm(forms.Form):
    csv_file = forms.FileField(label="Tệp CSV danh sách email (mỗi dòng 1 email)")

    def clean_csv_file(self):
        f = self.cleaned_data["csv_file"]
        if not f.name.lower().endswith(".csv"):
            raise forms.ValidationError("Chỉ chấp nhận tệp .csv.")
        return f


class GroupJoinRequestForm(forms.Form):
    message = forms.CharField(
        widget=forms.Textarea, label="Lời nhắn (không bắt buộc)", required=False,
    )


class JoinRequestRejectForm(forms.Form):
    reason = forms.CharField(widget=forms.Textarea, label="Lý do từ chối", required=True)


class MemberRoleForm(forms.Form):
    ROLE_CHOICES = [("member", "Thành viên"), ("moderator", "Phó nhóm / điều hành")]
    role = forms.ChoiceField(choices=ROLE_CHOICES, label="Vai trò mới")


class TransferLeadershipForm(forms.Form):
    new_leader_id = forms.IntegerField(label="Thành viên sẽ làm trưởng nhóm mới")


class GroupPostRejectForm(forms.Form):
    reason = forms.CharField(widget=forms.Textarea, label="Lý do từ chối", required=True)


class GroupPostForm(forms.ModelForm):
    class Meta:
        model = GroupPost
        fields = ["title", "body", "featured_image"]
        labels = {"title": "Tiêu đề", "body": "Nội dung"}
