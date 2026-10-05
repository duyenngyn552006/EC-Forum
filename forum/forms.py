from django import forms

from .models import Category, ForumPost, Tag


class ForumPostForm(forms.ModelForm):
    tags = forms.ModelMultipleChoiceField(queryset=Tag.objects.all(), required=False, widget=forms.CheckboxSelectMultiple)

    class Meta:
        model = ForumPost
        fields = ["category", "title", "body", "featured_image", "tags"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["category"].queryset = Category.objects.all()


class TagForm(forms.ModelForm):
    class Meta:
        model = Tag
        fields = ["name"]
        labels = {"name": "Tên thẻ"}


class CategoryForm(forms.ModelForm):
    class Meta:
        model = Category
        fields = ["name", "description", "max_pinned"]
        labels = {"name": "Tên chuyên mục", "description": "Mô tả", "max_pinned": "Số bài ghim tối đa (để trống = dùng mặc định hệ thống)"}
        widgets = {"description": forms.Textarea(attrs={"rows": 3})}
