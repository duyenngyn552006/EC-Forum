from django import forms

from .models import Group, GroupPost


class GroupCreateForm(forms.ModelForm):
    class Meta:
        model = Group
        fields = ["name", "description", "logo", "cover_image"]


class GroupRejectForm(forms.Form):
    reason = forms.CharField(widget=forms.Textarea, label="Lý do từ chối", required=True)


class GroupPostForm(forms.ModelForm):
    class Meta:
        model = GroupPost
        fields = ["title", "body", "featured_image"]
