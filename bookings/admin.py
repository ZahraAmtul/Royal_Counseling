from django import forms
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import User
from datetime import datetime, time, timedelta

from django.db import models
from django.db.models import Q
from django.utils.safestring import mark_safe
from .models import Counselor, Service, Availability, Appointment, ContactMessage


class CounselorFilteredAdmin(admin.ModelAdmin):
    """Filter data based on logged-in counselor"""

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        if hasattr(request.user, 'counselor_profile'):
            return qs.filter(counselor=request.user.counselor_profile)
        return qs.none()

    def save_model(self, request, obj, form, change):
        if not request.user.is_superuser and hasattr(request.user, 'counselor_profile'):
            if hasattr(obj, 'counselor') and not obj.counselor_id:
                obj.counselor = request.user.counselor_profile
        super().save_model(request, obj, form, change)

    def get_form(self, request, obj=None, **kwargs):
        form = super().get_form(request, obj, **kwargs)
        if not request.user.is_superuser and 'counselor' in form.base_fields:
            form.base_fields['counselor'].widget = forms.HiddenInput()
            form.base_fields['counselor'].required = False
        return form

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if not request.user.is_superuser and hasattr(request.user, 'counselor_profile'):
            if db_field.name == 'counselor':
                kwargs['queryset'] = Counselor.objects.filter(id=request.user.counselor_profile.id)
            elif db_field.name == 'service':
                kwargs['queryset'] = request.user.counselor_profile.services.filter(is_active=True)
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    def has_module_permission(self, request):
        if request.user.is_superuser:
            return True
        return hasattr(request.user, 'counselor_profile')

    def has_view_permission(self, request, obj=None):
        if request.user.is_superuser:
            return True
        if not hasattr(request.user, 'counselor_profile'):
            return False
        if obj is None:
            return True
        return obj.counselor_id == request.user.counselor_profile.id

    def has_add_permission(self, request):
        if request.user.is_superuser:
            return True
        return hasattr(request.user, 'counselor_profile')

    def has_change_permission(self, request, obj=None):
        if request.user.is_superuser:
            return True
        if not hasattr(request.user, 'counselor_profile'):
            return False
        if obj is None:
            return True
        return obj.counselor_id == request.user.counselor_profile.id

    def has_delete_permission(self, request, obj=None):
        if request.user.is_superuser:
            return True
        if not hasattr(request.user, 'counselor_profile'):
            return False
        if obj is None:
            return True
        return obj.counselor_id == request.user.counselor_profile.id


# -----------------------------------------------------------------------------
# Friendly date/time widgets
# -----------------------------------------------------------------------------

TIME_STEP_MINUTES = 30  # dropdown interval
DAY_START_HOUR = 6  # first option: 6:00 AM
DAY_END_HOUR = 23  # last option: 11:00 PM


def time_label(t):
    return t.strftime('%I:%M %p').lstrip('0')  # "9:30 AM"


class TimeSelectWidget(forms.Select):
    """Dropdown of times (e.g. 9:00 AM, 9:30 AM ...) instead of typing HH:MM."""

    def __init__(self, attrs=None):
        choices = [('', '— Select time —')]
        current = datetime(2000, 1, 1, DAY_START_HOUR)
        end = datetime(2000, 1, 1, DAY_END_HOUR)
        while current <= end:
            choices.append((current.strftime('%H:%M:%S'), time_label(current)))
            current += timedelta(minutes=TIME_STEP_MINUTES)
        super().__init__(attrs, choices)

    def get_context(self, name, value, attrs):
        # Keep an existing value that isn't on the grid (e.g. 9:15) instead of blanking it.
        if isinstance(value, str) and value:
            try:
                value = datetime.strptime(value[:8], '%H:%M:%S' if value.count(':') == 2 else '%H:%M').time()
            except ValueError:
                value = None
        if isinstance(value, time):
            key = value.strftime('%H:%M:%S')
            if key not in [c[0] for c in self.choices]:
                self.choices = sorted(list(self.choices)[1:] + [(key, time_label(value))])
                self.choices.insert(0, ('', '— Select time —'))
            value = key
        return super().get_context(name, value, attrs)


class FriendlyDateTimeMixin:
    """Calendar date picker and time dropdowns in the admin."""
    formfield_overrides = {
        models.TimeField: {'widget': TimeSelectWidget},
        models.DateField: {'widget': forms.DateInput(attrs={'type': 'date'}, format='%Y-%m-%d')},
    }


# -----------------------------------------------------------------------------
# Inlines
# -----------------------------------------------------------------------------

class AvailabilityInline(FriendlyDateTimeMixin, admin.TabularInline):
    model = Availability
    extra = 1
    fields = ['day_of_week', 'start_time', 'end_time']


class CounselorInline(admin.StackedInline):
    model = Counselor
    can_delete = False
    verbose_name_plural = 'Counselor Profile'
    fields = ['phone', 'photo', 'specialization', 'role_label', 'bio', 'services', 'is_active', 'is_accepting_bookings',
              'show_on_booking_page']
    filter_horizontal = ['services']


# -----------------------------------------------------------------------------
# User Admin
# -----------------------------------------------------------------------------

class UserAdmin(BaseUserAdmin):
    inlines = [CounselorInline]
    list_display = ['username', 'email', 'first_name', 'last_name', 'is_staff', 'is_counselor']

    def is_counselor(self, obj):
        return hasattr(obj, 'counselor_profile')

    is_counselor.boolean = True
    is_counselor.short_description = 'Counselor'

    def get_inline_instances(self, request, obj=None):
        if not obj:
            return []
        return super().get_inline_instances(request, obj)


admin.site.unregister(User)
admin.site.register(User, UserAdmin)


# -----------------------------------------------------------------------------
# Service Admin
# -----------------------------------------------------------------------------

@admin.register(Service)
class ServiceAdmin(admin.ModelAdmin):
    list_display = ['name', 'duration_minutes', 'price', 'is_active', 'counselor_count']
    list_filter = ['is_active']
    search_fields = ['name', 'description']

    fieldsets = (
        (None, {
            'fields': ('name', 'description', 'image')
        }),
        ('Pricing & Duration', {
            'fields': ('duration_minutes', 'price')
        }),
        ('Status', {
            'fields': ('is_active',)
        }),
    )

    def counselor_count(self, obj):
        return obj.counselors.count()

    counselor_count.short_description = 'Counselors'

    def has_module_permission(self, request):
        return request.user.is_superuser

    def has_view_permission(self, request, obj=None):
        return request.user.is_superuser

    def has_add_permission(self, request):
        return request.user.is_superuser

    def has_change_permission(self, request, obj=None):
        return request.user.is_superuser

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser


# -----------------------------------------------------------------------------
# Counselor Admin
# -----------------------------------------------------------------------------

@admin.register(Counselor)
class CounselorAdmin(admin.ModelAdmin):
    list_display = ['full_name', 'email', 'specialization', 'role_label', 'booking_status', 'show_on_booking_page',
                    'is_active', 'created_at']
    list_filter = ['is_active', 'is_accepting_bookings', 'show_on_booking_page', 'services']
    search_fields = ['user__first_name', 'user__last_name', 'user__email', 'specialization']
    filter_horizontal = ['services']
    inlines = [AvailabilityInline]
    list_editable = ['is_active']  # Quick toggle from list view

    # Custom action to toggle booking status
    actions = ['enable_bookings', 'disable_bookings']

    fieldsets = (
        ('User Account', {'fields': ('user',)}),
        ('Profile Information', {'fields': ('phone', 'photo', 'specialization', 'role_label', 'bio')}),
        ('Services Offered', {'fields': ('services',)}),
        ('Booking Status', {
            'fields': ('is_active', 'is_accepting_bookings', 'show_on_booking_page'),
            'description': 'Control whether this counselor appears on the site and can accept bookings.'
        }),)

    def get_readonly_fields(self, request, obj=None):
        if not request.user.is_superuser:
            # Counselors can't hide themselves from booking or give themselves a role label
            return ['user', 'services', 'is_accepting_bookings', 'show_on_booking_page', 'role_label']
        return []

    def booking_status(self, obj):
        if obj.is_accepting_bookings:
            return mark_safe('<span style="color: green; font-weight: bold;">✓ Accepting</span>')
        return mark_safe('<span style="color: red;">✗ Not Accepting</span>')

    booking_status.short_description = 'Booking Status'

    @admin.action(description='Enable bookings for selected counselors')
    def enable_bookings(self, request, queryset):
        updated = queryset.update(is_accepting_bookings=True)
        self.message_user(request, f'{updated} counselor(s) are now accepting bookings.')

    @admin.action(description='Disable bookings for selected counselors')
    def disable_bookings(self, request, queryset):
        updated = queryset.update(is_accepting_bookings=False)
        self.message_user(request, f'{updated} counselor(s) are no longer accepting bookings.')

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        if hasattr(request.user, 'counselor_profile'):
            return qs.filter(id=request.user.counselor_profile.id)
        return qs.none()

    def has_module_permission(self, request):
        if request.user.is_superuser:
            return True
        return hasattr(request.user, 'counselor_profile')

    def has_view_permission(self, request, obj=None):
        if request.user.is_superuser:
            return True
        if obj is None:
            return hasattr(request.user, 'counselor_profile')
        return hasattr(request.user, 'counselor_profile') and obj.id == request.user.counselor_profile.id

    def has_change_permission(self, request, obj=None):
        if request.user.is_superuser:
            return True
        if obj is None:
            return hasattr(request.user, 'counselor_profile')
        return hasattr(request.user, 'counselor_profile') and obj.id == request.user.counselor_profile.id

    def has_add_permission(self, request):
        return request.user.is_superuser

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser


# -----------------------------------------------------------------------------
# Availability Admin
# -----------------------------------------------------------------------------

@admin.register(Availability)
class AvailabilityAdmin(FriendlyDateTimeMixin, CounselorFilteredAdmin):
    list_display = ['counselor', 'day_of_week', 'start', 'end']

    @admin.display(description='Start', ordering='start_time')
    def start(self, obj):
        return time_label(obj.start_time)

    @admin.display(description='End', ordering='end_time')
    def end(self, obj):
        return time_label(obj.end_time)

    list_filter = ['day_of_week']
    ordering = ['counselor', 'day_of_week', 'start_time']

    def get_list_filter(self, request):
        if request.user.is_superuser:
            return ['counselor', 'day_of_week']
        return ['day_of_week']


# -----------------------------------------------------------------------------
# Appointment Admin
# -----------------------------------------------------------------------------

@admin.register(Appointment)
class AppointmentAdmin(FriendlyDateTimeMixin, CounselorFilteredAdmin):
    list_display = ['client_name', 'counselor', 'service', 'appointment_date', 'start_time', 'status', 'created_at']
    list_filter = ['status', 'appointment_date']
    search_fields = ['client_name', 'client_email', 'client_phone']
    date_hierarchy = 'appointment_date'
    readonly_fields = ['created_at', 'updated_at']

    fieldsets = (
        ('Client Information', {
            'fields': ('client_name', 'client_email', 'client_phone', 'notes')
        }),
        ('Appointment Details', {
            'fields': ('counselor', 'service', 'appointment_date', 'start_time', 'end_time', 'status')
        }),
        ('Metadata', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    def get_list_filter(self, request):
        if request.user.is_superuser:
            return ['status', 'counselor', 'service', 'appointment_date']
        return ['status', 'service', 'appointment_date']


@admin.register(ContactMessage)
class ContactMessageAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "email",
        "subject",
        "created_at",
        "is_responded",
    )

    list_filter = ("is_responded", "created_at")
    search_fields = ("name", "email", "subject", "message")
    list_editable = ("is_responded",)
    readonly_fields = ("created_at",)
    ordering = ("-created_at",)

    fieldsets = (
        ("Contact Details", {
            "fields": ("name", "email", "subject", "message", "created_at")
        }),
        ("Response Tracking", {
            "fields": ("is_responded", "response")
        }),
    )


# -----------------------------------------------------------------------------
# Admin Site Customization
# -----------------------------------------------------------------------------

admin.site.site_header = "STU Counseling Admin"
admin.site.site_title = "STU Admin"
admin.site.index_title = "Welcome to STU Management Portal"