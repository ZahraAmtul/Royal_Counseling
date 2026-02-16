from django import forms
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Submit, Row, Column, Div, HTML, Field
from .models import Appointment, Counselor, Service


class CounselorSelectForm(forms.Form):
    """Form to select a counselor"""
    counselor = forms.ModelChoiceField(
        queryset=Counselor.objects.filter(is_active=True),
        widget=forms.RadioSelect,
        empty_label=None
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_method = 'post'
        self.helper.layout = Layout(
            'counselor',
            Submit('submit', 'Continue', css_class='btn btn-primary btn-lg mt-3')
        )


class ServiceSelectForm(forms.Form):
    """Form to select a service type"""
    service = forms.ModelChoiceField(
        queryset=Service.objects.filter(is_active=True),
        widget=forms.RadioSelect,
        empty_label=None
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_method = 'post'
        self.helper.layout = Layout(
            'service',
            Submit('submit', 'Continue', css_class='btn btn-primary btn-lg mt-3')
        )


class DateTimeSelectForm(forms.Form):
    """Form to select date and time slot"""
    appointment_date = forms.DateField(
        widget=forms.HiddenInput()
    )
    start_time = forms.TimeField(
        widget=forms.HiddenInput()
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_method = 'post'
        self.helper.form_id = 'datetime-form'


class AppointmentBookingForm(forms.ModelForm):
    """Form for client details"""
    
    class Meta:
        model = Appointment
        fields = ['client_name', 'client_email', 'client_phone', 'notes']
        widgets = {
            'notes': forms.Textarea(attrs={'rows': 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_method = 'post'
        self.helper.layout = Layout(
            Row(
                Column('client_name', css_class='form-group col-md-6 mb-3'),
                Column('client_email', css_class='form-group col-md-6 mb-3'),
                css_class='row'
            ),
            Row(
                Column('client_phone', css_class='form-group col-md-6 mb-3'),
                css_class='row'
            ),
            'notes',
            Div(
                Submit('submit', 'Confirm Booking', css_class='btn btn-success btn-lg'),
                HTML('<a href="{% url \'booking_start\' %}" class="btn btn-outline-secondary btn-lg ms-2">Start Over</a>'),
                css_class='mt-4'
            )
        )
        
        # Add placeholders
        self.fields['client_name'].widget.attrs['placeholder'] = 'Your full name'
        self.fields['client_email'].widget.attrs['placeholder'] = 'your.email@example.com'
        self.fields['client_phone'].widget.attrs['placeholder'] = '+1 234 567 8900'
        self.fields['notes'].widget.attrs['placeholder'] = 'Any specific concerns or topics you\'d like to discuss...'
