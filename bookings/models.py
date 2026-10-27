from django.db import models
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from datetime import datetime, timedelta, date


class Service(models.Model):
    """Types of counseling sessions"""
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    duration_minutes = models.PositiveIntegerField(
        default=50,
        validators=[MinValueValidator(15)],
        help_text="Duration in minutes"
    )
    price = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    image = models.ImageField(
        upload_to='services/',
        blank=True,
        null=True,
        help_text="Service image (recommended: 400x300px)"
    )
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return f"{self.name} ({self.duration_minutes} min)"


class Counselor(models.Model):
    """Psychologist/Counselor profile"""
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='counselor_profile',
        help_text="Link to Django user account for login"
    )
    phone = models.CharField(max_length=20, blank=True)
    photo = models.ImageField(upload_to='counselors/', blank=True, null=True)
    specialization = models.CharField(max_length=200, help_text="e.g., Anxiety, Depression, Couples Therapy")
    bio = models.TextField(blank=True)

    # Many-to-Many: Counselor can offer multiple services
    services = models.ManyToManyField(
        Service,
        related_name='counselors',
        blank=True,
        help_text="Select services this counselor offers"
    )

    is_active = models.BooleanField(default=True)

    # NEW FIELD: Controls if counselor is accepting new bookings
    is_accepting_bookings = models.BooleanField(
        default=False,
        help_text="Enable this to allow clients to book appointments with this counselor"
    )
    role_label = models.CharField(
        max_length=60, blank=True,
        help_text='Optional badge on the counselors page, e.g. "Admin and Founder".'
    )
    show_on_booking_page = models.BooleanField(
        default=True,
        help_text="Uncheck to hide this person from the booking flow (they still appear on the counselors page)."
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['user__first_name', 'user__last_name']

    def __str__(self):
        return f"{self.user.get_full_name() or self.user.username}"

    @property
    def full_name(self):
        return self.user.get_full_name() or self.user.username

    @property
    def email(self):
        return self.user.email

    @property
    def can_be_booked(self):
        """Check if counselor can accept bookings"""
        return self.is_active and self.is_accepting_bookings and self.show_on_booking_page

class ContactMessage(models.Model):
    name = models.CharField(max_length=100)
    email = models.EmailField()
    subject = models.CharField(max_length=200, blank=True)
    message = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    is_responded = models.BooleanField(default=False)
    response = models.TextField(blank=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Contact Message"
        verbose_name_plural = "Contact Messages"

    def __str__(self):
        return f"{self.name} - {self.email}"


class Availability(models.Model):
    """Weekly recurring availability for each counselor"""
    DAYS_OF_WEEK = [
        (0, 'Monday'),
        (1, 'Tuesday'),
        (2, 'Wednesday'),
        (3, 'Thursday'),
        (4, 'Friday'),
        (5, 'Saturday'),
        (6, 'Sunday'),
    ]

    counselor = models.ForeignKey(
        Counselor,
        on_delete=models.CASCADE,
        related_name='availabilities'
    )
    day_of_week = models.IntegerField(choices=DAYS_OF_WEEK)
    start_time = models.TimeField()
    end_time = models.TimeField()

    class Meta:
        ordering = ['day_of_week', 'start_time']
        verbose_name_plural = 'Availabilities'
        unique_together = ['counselor', 'day_of_week', 'start_time']

    def __str__(self):
        return f"{self.counselor} - {self.get_day_of_week_display()} {self.start_time:%H:%M}-{self.end_time:%H:%M}"

    def clean(self):
        """Admin validation: end after start, and no overlapping windows on the same day."""
        if self.start_time and self.end_time and self.end_time <= self.start_time:
            raise ValidationError({'end_time': 'End time must be after the start time.'})
        if self.counselor_id and self.start_time and self.end_time and self.day_of_week is not None:
            overlapping = Availability.objects.filter(
                counselor_id=self.counselor_id,
                day_of_week=self.day_of_week,
                start_time__lt=self.end_time,
                end_time__gt=self.start_time,
            ).exclude(pk=self.pk)
            if overlapping.exists():
                other = overlapping.first()
                raise ValidationError(
                    f"This overlaps with existing hours on {self.get_day_of_week_display()} "
                    f"({other.start_time:%H:%M}-{other.end_time:%H:%M})."
                )


class Appointment(models.Model):
    """Booked appointments"""
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('confirmed', 'Confirmed'),
        ('cancelled', 'Cancelled'),
        ('completed', 'Completed'),
    ]

    # Client info
    client_name = models.CharField(max_length=200)
    client_email = models.EmailField()
    client_phone = models.CharField(max_length=20)
    notes = models.TextField(blank=True, help_text="Any specific concerns or notes")

    # Appointment details
    counselor = models.ForeignKey(
        Counselor,
        on_delete=models.CASCADE,
        related_name='appointments'
    )
    service = models.ForeignKey(
        Service,
        on_delete=models.CASCADE,
        related_name='appointments'
    )
    appointment_date = models.DateField()
    start_time = models.TimeField()
    end_time = models.TimeField()

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-appointment_date', '-start_time']

    def __str__(self):
        return f"{self.client_name} with {self.counselor} on {self.appointment_date} at {self.start_time}"

    def clean(self):
        """Admin validation: the counselor can't be double-booked."""
        if not (self.counselor_id and self.service_id and self.appointment_date and self.start_time):
            return
        if self.status not in ('pending', 'confirmed'):
            return
        start = datetime.combine(self.appointment_date, self.start_time)
        end = start + timedelta(minutes=self.service.duration_minutes)
        clashes = Appointment.objects.filter(
            counselor_id=self.counselor_id,
            appointment_date=self.appointment_date,
            status__in=['pending', 'confirmed'],
            start_time__lt=end.time(),
            end_time__gt=self.start_time,
        ).exclude(pk=self.pk)
        if clashes.exists():
            other = clashes.first()
            raise ValidationError(
                f"{self.counselor} already has an appointment from "
                f"{other.start_time:%I:%M %p} to {other.end_time:%I:%M %p} on this date."
            )

    def save(self, *args, **kwargs):
        # End time always follows the service length, so it stays correct
        # when the start time or service is changed in the admin.
        if self.service_id and self.start_time:
            start_datetime = datetime.combine(date.today(), self.start_time)
            end_datetime = start_datetime + timedelta(minutes=self.service.duration_minutes)
            self.end_time = end_datetime.time()
        super().save(*args, **kwargs)