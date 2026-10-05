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


class AddMemberForm(forms.Form):
    email = forms.EmailField(label="Email thành viên muốn thêm")


class MemberRoleForm(forms.Form):
    ROLE_CHOICES = [("member", "Thành viên"), ("moderator", "Phó nhóm / điều hành")]
    role = forms.ChoiceField(choices=ROLE_CHOICES, label="Vai trò mới")


class GroupPostForm(forms.ModelForm):
    class Meta:
        model = GroupPost
        fields = ["title", "body", "featured_image"]
