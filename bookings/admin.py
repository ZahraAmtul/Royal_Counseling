from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import User
from django.db.models import Q
from django import forms
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
        # Filter by counselor's own data
        if hasattr(request.user, 'counselor_profile'):
            return qs.filter(counselor=request.user.counselor_profile)
        return qs.none()
    
    def save_model(self, request, obj, form, change):
        # Auto-assign counselor if not superuser
        if not request.user.is_superuser and hasattr(request.user, 'counselor_profile'):
            if hasattr(obj, 'counselor') and not obj.counselor_id:
                obj.counselor = request.user.counselor_profile
        super().save_model(request, obj, form, change)
    
    def get_form(self, request, obj=None, **kwargs):
        form = super().get_form(request, obj, **kwargs)
        # Hide counselor field for non-superusers (auto-assigned)
        if not request.user.is_superuser and 'counselor' in form.base_fields:
            form.base_fields['counselor'].widget = forms.HiddenInput()
            form.base_fields['counselor'].required = False
        return form
    
    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        # Filter foreign key dropdowns to only show counselor's own data
        if not request.user.is_superuser and hasattr(request.user, 'counselor_profile'):
            if db_field.name == 'counselor':
                kwargs['queryset'] = Counselor.objects.filter(id=request.user.counselor_profile.id)
            elif db_field.name == 'service':
                # Show global services + counselor's own services
                kwargs['queryset'] = Service.objects.filter(
                    Q(counselor__isnull=True) | 
                    Q(counselor=request.user.counselor_profile)
                )
        return super().formfield_for_foreignkey(db_field, request, **kwargs)
    
    # -------------------------------------------------------------------------
    # PERMISSIONS - Allow counselors to manage their own data
    # -------------------------------------------------------------------------
    
    def has_module_permission(self, request):
        """Allow counselors to see the module in admin."""
        if request.user.is_superuser:
            return True
        return hasattr(request.user, 'counselor_profile')
    
    def has_view_permission(self, request, obj=None):
        """Allow counselors to view records."""
        if request.user.is_superuser:
            return True
        if not hasattr(request.user, 'counselor_profile'):
            return False
        if obj is None:
            return True
        # Check if this object belongs to the counselor
        return obj.counselor_id == request.user.counselor_profile.id
    
    def has_add_permission(self, request):
        """Allow counselors to add records."""
        if request.user.is_superuser:
            return True
        return hasattr(request.user, 'counselor_profile')
    
    def has_change_permission(self, request, obj=None):
        """Allow counselors to edit their own records."""
        if request.user.is_superuser:
            return True
        if not hasattr(request.user, 'counselor_profile'):
            return False
        if obj is None:
            return True
        return obj.counselor_id == request.user.counselor_profile.id
    
    def has_delete_permission(self, request, obj=None):
        """Allow counselors to delete their own records."""
        if request.user.is_superuser:
            return True
        if not hasattr(request.user, 'counselor_profile'):
            return False
        if obj is None:
            return True
        return obj.counselor_id == request.user.counselor_profile.id


# -----------------------------------------------------------------------------
# Inline for Counselor's Availability
# -----------------------------------------------------------------------------

class AvailabilityInline(admin.TabularInline):
    model = Availability
    extra = 1
    fields = ['day_of_week', 'start_time', 'end_time']


# -----------------------------------------------------------------------------
# Counselor Profile Inline (shown in User admin)
# -----------------------------------------------------------------------------

class CounselorInline(admin.StackedInline):
    model = Counselor
    can_delete = False
    verbose_name_plural = 'Counselor Profile'
    fields = ['phone', 'photo', 'specialization', 'bio', 'is_active']


# -----------------------------------------------------------------------------
# Extended User Admin
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


# Re-register User with custom admin
admin.site.unregister(User)
admin.site.register(User, UserAdmin)


# -----------------------------------------------------------------------------
# Counselor Admin (for superusers to manage all counselors)
# -----------------------------------------------------------------------------

@admin.register(Counselor)
class CounselorAdmin(admin.ModelAdmin):
    list_display = ['full_name', 'email', 'specialization', 'is_active', 'created_at']
    list_filter = ['is_active', 'specialization']
    search_fields = ['user__first_name', 'user__last_name', 'user__email', 'specialization']
    inlines = [AvailabilityInline]
    
    fieldsets = (
        ('User Account', {
            'fields': ('user',)
        }),
        ('Profile Information', {
            'fields': ('phone', 'photo', 'specialization', 'bio')
        }),
        ('Status', {
            'fields': ('is_active',)
        }),
    )
    
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        # Counselors can only see their own profile
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
        # Only superusers can add new counselors
        return request.user.is_superuser
    
    def has_delete_permission(self, request, obj=None):
        # Only superusers can delete counselors
        return request.user.is_superuser


# -----------------------------------------------------------------------------
# Service Admin
# -----------------------------------------------------------------------------

@admin.register(Service)
class ServiceAdmin(CounselorFilteredAdmin):
    list_display = ['name', 'counselor_display', 'duration_minutes', 'price', 'is_active']
    list_filter = ['is_active', 'counselor']
    search_fields = ['name', 'description']
    
    fieldsets = (
        (None, {
            'fields': ('name', 'description', 'image')
        }),
        ('Pricing & Duration', {
            'fields': ('duration_minutes', 'price')
        }),
        ('Ownership', {
            'fields': ('counselor',),
            'description': 'Leave empty for global service available to all counselors.'
        }),
        ('Status', {
            'fields': ('is_active',)
        }),
    )
    
    def counselor_display(self, obj):
        return obj.counselor if obj.counselor else "Global (All)"
    counselor_display.short_description = 'Counselor'
    
    def get_queryset(self, request):
        qs = super(admin.ModelAdmin, self).get_queryset(request)
        if request.user.is_superuser:
            return qs
        if hasattr(request.user, 'counselor_profile'):
            # Show global services + own services
            return qs.filter(
                Q(counselor__isnull=True) | 
                Q(counselor=request.user.counselor_profile)
            )
        return qs.none()
    
    def has_view_permission(self, request, obj=None):
        if request.user.is_superuser:
            return True
        if not hasattr(request.user, 'counselor_profile'):
            return False
        if obj is None:
            return True
        # Can view global services or own services
        return obj.counselor is None or obj.counselor_id == request.user.counselor_profile.id
    
    def has_change_permission(self, request, obj=None):
        if request.user.is_superuser:
            return True
        if not hasattr(request.user, 'counselor_profile'):
            return False
        if obj is None:
            return True
        # Can only edit own services, not global ones
        if obj.counselor is None:
            return False
        return obj.counselor_id == request.user.counselor_profile.id
    
    def has_delete_permission(self, request, obj=None):
        if request.user.is_superuser:
            return True
        if not hasattr(request.user, 'counselor_profile'):
            return False
        if obj is None:
            return True
        # Can only delete own services, not global ones
        if obj.counselor is None:
            return False
        return obj.counselor_id == request.user.counselor_profile.id


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
        # Remove counselor filter for non-superusers
        return ['status', 'service', 'appointment_date']


# -----------------------------------------------------------------------------
# Customize Admin Site
# -----------------------------------------------------------------------------

admin.site.site_header = "MindCare Counseling Admin"
admin.site.site_title = "MindCare Admin"
admin.site.index_title = "Welcome to MindCare Management Portal"