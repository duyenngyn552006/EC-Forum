from django import forms

from .models import Group, GroupPost


class GroupCreateForm(forms.ModelForm):
    class Meta:
        model = Group
        fields = ["name", "description", "logo", "cover_image"]


class GroupRejectForm(forms.Form):
    reason = forms.CharField(widget=forms.Textarea, label="Lý do từ chối", required=True)


class GroupEditForm(forms.ModelForm):
    class Meta:
        model = Group
        fields = ["name", "description", "logo", "cover_image"]


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
