from django import forms

from .models import (
    Announcement,
    AnnouncementReply,
    BudgetCategory,
    Message,
    Profile,
    PurchaseRequest,
    ResourceDocument,
)


class MessageForm(forms.ModelForm):
    class Meta:
        model = Message
        fields = ['body']
        widgets = {
            'body': forms.Textarea(attrs={'rows': 3, 'placeholder': 'Type your message...'}),
        }


class ProfileUpdateForm(forms.ModelForm):
    class Meta:
        model = Profile
        fields = ['profile_image', 'organization_name', 'phone_number', 'bio']
        widgets = {
            'bio': forms.Textarea(attrs={'rows': 4, 'placeholder': 'Tell your organization a little about you...'}),
        }


class BudgetCategoryForm(forms.ModelForm):
    class Meta:
        model = BudgetCategory
        fields = ['name', 'description', 'allocated_amount']
        widgets = {
            'description': forms.Textarea(attrs={'rows': 4}),
        }


class PurchaseRequestForm(forms.ModelForm):
    class Meta:
        model = PurchaseRequest
        fields = ['title', 'description', 'estimated_cost', 'category', 'receipt_file', 'receipt_link']
        widgets = {
            'description': forms.Textarea(attrs={'rows': 5}),
            'receipt_link': forms.URLInput(attrs={'placeholder': 'Optional external receipt or proof link'}),
        }


class PurchaseRequestReviewForm(forms.ModelForm):
    status = forms.ChoiceField(
        choices=[
            (PurchaseRequest.STATUS_APPROVED, 'Approve'),
            (PurchaseRequest.STATUS_DENIED, 'Deny'),
        ]
    )

    class Meta:
        model = PurchaseRequest
        fields = ['status', 'reviewer_notes']
        widgets = {
            'reviewer_notes': forms.Textarea(attrs={'rows': 4, 'placeholder': 'Explain the decision for the officer.'}),
        }


class UserRoleUpdateForm(forms.ModelForm):
    role = forms.ChoiceField(choices=Profile.NON_ADMIN_ROLE_CHOICES)

    class Meta:
        model = Profile
        fields = ['role']


class MembershipStatusUpdateForm(forms.ModelForm):
    class Meta:
        model = Profile
        fields = ['status']


class AnnouncementForm(forms.ModelForm):
    class Meta:
        model = Announcement
        fields = ['title', 'body', 'visibility', 'is_pinned', 'is_locked', 'attachment']
        widgets = {
            'body': forms.Textarea(attrs={'rows': 6}),
        }


class AnnouncementReplyForm(forms.ModelForm):
    class Meta:
        model = AnnouncementReply
        fields = ['body']
        widgets = {
            'body': forms.Textarea(attrs={'rows': 3, 'placeholder': 'Write a reply...'}),
        }


class ResourceDocumentForm(forms.ModelForm):
    class Meta:
        model = ResourceDocument
        fields = ['title', 'description', 'visibility', 'file']
        widgets = {
            'description': forms.Textarea(attrs={'rows': 4}),
        }


class AccountDeleteForm(forms.Form):
    confirm_email = forms.EmailField(
        label='Type your account email to confirm deletion',
        help_text='This permanently deletes your account and profile.',
    )
