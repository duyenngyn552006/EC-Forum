from django import forms

from .models import AccountAppeal, Report, SensitiveKeyword


class ReportForm(forms.ModelForm):
    class Meta:
        model = Report
        fields = ["reason"]
        widgets = {"reason": forms.Textarea(attrs={"rows": 3})}


class ReportResolveForm(forms.Form):
    ACTION_CHOICES = [
        ("dismiss", "Bỏ qua báo cáo"),
        ("hide", "Ẩn nội dung"),
        ("delete", "Xóa nội dung"),
    ]
    action = forms.ChoiceField(choices=ACTION_CHOICES)
    resolution_note = forms.CharField(widget=forms.Textarea, required=True, label="Ghi chú xử lý")


class AccountAppealForm(forms.ModelForm):
    class Meta:
        model = AccountAppeal
        fields = ["reason", "extra_info"]
        widgets = {"reason": forms.Textarea(attrs={"rows": 3}), "extra_info": forms.Textarea(attrs={"rows": 3})}


class AppealReviewForm(forms.Form):
    DECISION_CHOICES = [("accept", "Chấp nhận"), ("reject", "Từ chối")]
    decision = forms.ChoiceField(choices=DECISION_CHOICES)
    review_note = forms.CharField(widget=forms.Textarea, required=True, label="Ghi chú")


class ContentRejectForm(forms.Form):
    reason = forms.CharField(widget=forms.Textarea, label="Lý do từ chối", required=True)


class SensitiveKeywordForm(forms.ModelForm):
    class Meta:
        model = SensitiveKeyword
        fields = ["keyword", "is_active", "note"]
        labels = {"keyword": "Từ khóa", "is_active": "Đang áp dụng", "note": "Ghi chú"}
