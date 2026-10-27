import re

from django import forms
from crispy_forms.helper import FormHelper

from .models import Appointment, ContactMessage

PHONE_RE = re.compile(r'^\+?[\d\s\-()]{7,20}$')


class AppointmentBookingForm(forms.ModelForm):
    """Client details on the last booking step (rendered field by field in booking_step3.html)."""

    class Meta:
        model = Appointment
        fields = ['client_name', 'client_email', 'client_phone', 'notes']
        labels = {
            'client_name': 'Full name',
            'client_email': 'Email',
            'client_phone': 'Phone / WhatsApp',
            'notes': 'Anything you would like your counselor to know?',
        }
        widgets = {
            'notes': forms.Textarea(attrs={'rows': 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_tag = False
        self.fields['client_name'].widget.attrs.update(placeholder='Your full name', autocomplete='name')
        self.fields['client_email'].widget.attrs.update(placeholder='you@example.com', autocomplete='email')
        self.fields['client_phone'].widget.attrs.update(placeholder='+92 300 1234567', autocomplete='tel', type='tel')
        self.fields['notes'].widget.attrs.update(placeholder="Optional. Share only what you're comfortable with.")

    def clean_client_name(self):
        name = ' '.join(self.cleaned_data['client_name'].split())
        if len(name) < 2:
            raise forms.ValidationError('Please enter your full name.')
        return name

    def clean_client_phone(self):
        phone = self.cleaned_data['client_phone'].strip()
        if not PHONE_RE.match(phone) or len(re.sub(r'\D', '', phone)) < 7:
            raise forms.ValidationError('Please enter a valid phone number, e.g. +92 300 1234567.')
        return phone


class ContactMessageForm(forms.ModelForm):
    """Validates the contact page form (lengths, email format) before saving."""

    class Meta:
        model = ContactMessage
        fields = ['name', 'email', 'subject', 'message']

    def clean_message(self):
        message = self.cleaned_data['message'].strip()
        if len(message) < 5:
            raise forms.ValidationError('Please write a little more in your message.')
        return message
