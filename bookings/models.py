from django.db import models
from django.core.validators import MinValueValidator
from datetime import datetime, timedelta, date


class Counselor(models.Model):
    """Psychologist/Counselor profile"""
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    email = models.EmailField(unique=True)
    phone = models.CharField(max_length=20, blank=True)
    photo = models.ImageField(upload_to='counselors/', blank=True, null=True)
    specialization = models.CharField(max_length=200, help_text="e.g., Anxiety, Depression, Couples Therapy")
    bio = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['first_name', 'last_name']

    def __str__(self):
        return f"Dr. {self.first_name} {self.last_name}"

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}"


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
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return f"{self.name} ({self.duration_minutes} min)"


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
        return f"{self.counselor} - {self.get_day_of_week_display()} {self.start_time}-{self.end_time}"


class Appointment(models.Model):
    """Booked appointments"""
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('confirmed', 'Confirmed'),
        ('cancelled', 'Cancelled'),
        ('completed', 'Completed'),
    ]

    client_name = models.CharField(max_length=200)
    client_email = models.EmailField()
    client_phone = models.CharField(max_length=20)
    notes = models.TextField(blank=True, help_text="Any specific concerns or notes")

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
        ordering = ['appointment_date', 'start_time']

    def __str__(self):
        return f"{self.client_name} with {self.counselor} on {self.appointment_date} at {self.start_time}"

    def save(self, *args, **kwargs):
        if self.service and self.start_time and not self.end_time:
            start_datetime = datetime.combine(date.today(), self.start_time)
            end_datetime = start_datetime + timedelta(minutes=self.service.duration_minutes)
            self.end_time = end_datetime.time()
        super().save(*args, **kwargs)
