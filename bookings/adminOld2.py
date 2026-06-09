from django import forms
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import User
from django.db.models import Q
from .models import Counselor, Service, Availability, Appointment


# -----------------------------------------------------------------------------
# Helper Mixin for Counselor-based filtering
# -----------------------------------------------------------------------------

class CounselorFilteredAdmin(admin.ModelAdmin):
    """
    Base admin class that filters data based on logged-in counselor.
    - Superusers see all data
    - Counselors only see their own data
    """
    
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
                # Show only services that this counselor offers
                kwargs['queryset'] = request.user.counselor_profile.services.filter(is_active=True)
        return super().formfield_for_foreignkey(db_field, request, **kwargs)
    
    # -------------------------------------------------------------------------
    # PERMISSIONS
    # -------------------------------------------------------------------------
    
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
# Inlines
# -----------------------------------------------------------------------------

class AvailabilityInline(admin.TabularInline):
    model = Availability
    extra = 1
    fields = ['day_of_week', 'start_time', 'end_time']


class CounselorInline(admin.StackedInline):
    model = Counselor
    can_delete = False
    verbose_name_plural = 'Counselor Profile'
    fields = ['phone', 'photo', 'specialization', 'bio', 'services', 'is_active']
    filter_horizontal = ['services']  # Nice widget for selecting multiple services


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
# Service Admin (Only Superuser can manage)
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
    counselor_count.short_description = 'Counselors Offering'
    
    def has_module_permission(self, request):
        # Only superuser can manage services
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
    list_display = ['full_name', 'email', 'specialization', 'services_list', 'is_active', 'created_at']
    list_filter = ['is_active', 'services']
    search_fields = ['user__first_name', 'user__last_name', 'user__email', 'specialization']
    filter_horizontal = ['services']  # Nice widget for Many-to-Many
    inlines = [AvailabilityInline]
    
    fieldsets = (
        ('User Account', {
            'fields': ('user',)
        }),
        ('Profile Information', {
            'fields': ('phone', 'photo', 'specialization', 'bio')
        }),
        ('Services Offered', {
            'fields': ('services',),
            'description': 'Select the services this counselor offers.'
        }),
        ('Status', {
            'fields': ('is_active',)
        }),
    )
    
    def services_list(self, obj):
        return ", ".join([s.name for s in obj.services.all()[:3]])
    services_list.short_description = 'Services'
    
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
    
    def get_readonly_fields(self, request, obj=None):
        """Counselors can't change their own services - only admin can"""
        if not request.user.is_superuser:
            return ['user', 'services']
        return []


# -----------------------------------------------------------------------------
# Availability Admin
# -----------------------------------------------------------------------------

@admin.register(Availability)
class AvailabilityAdmin(CounselorFilteredAdmin):
    list_display = ['counselor', 'day_of_week', 'start_time', 'end_time']
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
class AppointmentAdmin(CounselorFilteredAdmin):
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


# -----------------------------------------------------------------------------
# Admin Site Customization
# -----------------------------------------------------------------------------

admin.site.site_header = "STU Counseling Admin"
admin.site.site_title = "STU Admin"
admin.site.index_title = "Welcome to STU Management Portal"
