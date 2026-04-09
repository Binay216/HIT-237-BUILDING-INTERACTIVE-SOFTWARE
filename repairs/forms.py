from django import forms
from django.contrib.auth.models import User
from .models import RepairRequest, MaintenanceLog, TenantProfile, Dwelling, RepairFeedback


class RegistrationForm(forms.Form):
    """Registration form for new tenants."""

    username = forms.CharField(max_length=150)
    first_name = forms.CharField(max_length=30)
    last_name = forms.CharField(max_length=30)
    password = forms.CharField(widget=forms.PasswordInput)
    password_confirm = forms.CharField(
        widget=forms.PasswordInput, label='Confirm Password'
    )
    phone = forms.CharField(max_length=20, required=False)
    dwelling = forms.ModelChoiceField(
        queryset=Dwelling.objects.select_related('community').all(),
        required=False,
        empty_label='-- Select your dwelling --'
    )

    def clean_username(self):
        username = self.cleaned_data['username']
        if User.objects.filter(username=username).exists():
            raise forms.ValidationError('This username is already taken.')
        return username

    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get('password')
        password_confirm = cleaned_data.get('password_confirm')
        if password and password_confirm and password != password_confirm:
            raise forms.ValidationError('Passwords do not match.')
        return cleaned_data

    def save(self):
        data = self.cleaned_data
        user = User.objects.create_user(
            username=data['username'],
            password=data['password'],
            first_name=data['first_name'],
            last_name=data['last_name'],
        )
        # Profile auto-created by signal; update it with form data
        profile = user.profile
        profile.phone = data.get('phone', '')
        profile.dwelling = data.get('dwelling')
        profile.save()
        return user


class RepairRequestForm(forms.ModelForm):
    """Form for creating and editing repair requests."""

    class Meta:
        model = RepairRequest
        fields = [
            'title', 'description', 'issue_type',
            'priority', 'location_in_dwelling', 'image'
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['description'].widget.attrs['rows'] = 4


class MaintenanceLogForm(forms.ModelForm):
    """Form for staff to add maintenance notes."""

    class Meta:
        model = MaintenanceLog
        fields = ['note', 'status_change']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['status_change'].required = False
        self.fields['note'].widget.attrs['rows'] = 3


class StatusUpdateForm(forms.Form):
    """Quick status update form for staff."""

    status = forms.ChoiceField(choices=RepairRequest.STATUS_CHOICES)


class RequestFilterForm(forms.Form):
    """Filtering form for request lists."""

    STATUS_FILTER = [('', 'All Statuses')] + list(RepairRequest.STATUS_CHOICES)
    ISSUE_FILTER = [('', 'All Issue Types')] + list(RepairRequest.ISSUE_TYPES)
    PRIORITY_FILTER = [('', 'All Priorities')] + list(RepairRequest.PRIORITY_CHOICES)

    status = forms.ChoiceField(choices=STATUS_FILTER, required=False)
    issue_type = forms.ChoiceField(choices=ISSUE_FILTER, required=False)
    priority = forms.ChoiceField(choices=PRIORITY_FILTER, required=False)


class TenantCommentForm(forms.Form):
    """Form for tenants to add comments on their repair requests."""

    comment = forms.CharField(widget=forms.Textarea(attrs={'rows': 3}))


class ProfileEditForm(forms.Form):
    """Hybrid form for editing User + TenantProfile fields."""

    first_name = forms.CharField(max_length=30)
    last_name = forms.CharField(max_length=30)
    phone = forms.CharField(max_length=20, required=False)
    dwelling = forms.ModelChoiceField(
        queryset=Dwelling.objects.select_related('community').all(),
        required=False,
        empty_label='-- Select your dwelling --'
    )

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        if user:
            self.fields['first_name'].initial = user.first_name
            self.fields['last_name'].initial = user.last_name
            if hasattr(user, 'profile'):
                self.fields['phone'].initial = user.profile.phone
                self.fields['dwelling'].initial = user.profile.dwelling

    def save(self, user):
        data = self.cleaned_data
        user.first_name = data['first_name']
        user.last_name = data['last_name']
        user.save(update_fields=['first_name', 'last_name'])
        profile = user.profile
        profile.phone = data.get('phone', '')
        profile.dwelling = data.get('dwelling')
        profile.save(update_fields=['phone', 'dwelling'])
        return user


class RepairFeedbackForm(forms.ModelForm):
    """Form for tenants to rate completed repairs."""

    class Meta:
        model = RepairFeedback
        fields = ['rating', 'comment']
        widgets = {
            'rating': forms.NumberInput(attrs={'min': 1, 'max': 5}),
            'comment': forms.Textarea(attrs={'rows': 3}),
        }
