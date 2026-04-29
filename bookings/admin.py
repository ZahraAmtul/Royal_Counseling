from django.contrib import admin
from .models import Counselor, Service, Availability, Appointment


class AvailabilityInline(admin.TabularInline):
    model = Availability
    extra = 1


@admin.register(Counselor)
class CounselorAdmin(admin.ModelAdmin):
    list_display = ['full_name', 'email', 'specialization', 'is_active', 'created_at']
    list_filter = ['is_active', 'specialization']
    search_fields = ['first_name', 'last_name', 'email', 'specialization']
    inlines = [AvailabilityInline]
    
    fieldsets = (
        ('Personal Information', {
            'fields': ('first_name', 'last_name', 'email', 'phone', 'photo')
        }),
        ('Professional Details', {
            'fields': ('specialization', 'bio')
        }),
        ('Status', {
            'fields': ('is_active',)
        }),
    )


@admin.register(Service)
class ServiceAdmin(admin.ModelAdmin):
    list_display = ['name', 'duration_minutes', 'price', 'is_active', 'image']
    list_filter = ['is_active']
    search_fields = ['name', 'description']
    fieldsets = (
            ('Service Information', {
                'fields': ('name', 'description', 'duration_minutes', 'price', 'image')
            }),
            ('Status', {
                'fields': ('is_active',)
            }),
        )

@admin.register(Availability)
class AvailabilityAdmin(admin.ModelAdmin):
    list_display = ['counselor', 'day_of_week', 'start_time', 'end_time']
    list_filter = ['counselor', 'day_of_week']
    ordering = ['counselor', 'day_of_week', 'start_time']


@admin.register(Appointment)
class AppointmentAdmin(admin.ModelAdmin):
    list_display = ['client_name', 'counselor', 'service', 'appointment_date', 'start_time', 'status', 'created_at']
    list_filter = ['status', 'counselor', 'service', 'appointment_date']
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
