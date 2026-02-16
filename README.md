# MindCare Counseling - Appointment Booking System

A simple Django-based appointment booking system for multiple psychologists/counselors.

## Features

- **Multiple Counselors**: Each counselor can have different availability schedules
- **Multiple Services**: Different session types with varying durations and prices
- **Dynamic Slot Generation**: Available time slots are calculated based on counselor availability
- **Calendar View**: FullCalendar.js integration for date selection
- **Responsive Design**: Bootstrap 5 for mobile-friendly UI
- **Admin Panel**: Django admin for managing counselors, services, and appointments
- **No Double Booking**: Slot validation to prevent conflicts

## Tech Stack

- **Backend**: Django 5.x
- **Frontend**: Bootstrap 5, FullCalendar.js
- **Forms**: django-crispy-forms with Bootstrap 5 template pack
- **Database**: SQLite (development) - easily switchable to PostgreSQL

## Quick Start

1. **Clone and Setup**
   ```bash
   cd counseling_booking
   pip install -r requirements.txt
   ```

2. **Run Migrations**
   ```bash
   python manage.py migrate
   ```

3. **Load Sample Data** (Optional)
   ```bash
   python manage.py load_sample_data
   ```

4. **Create Admin User**
   ```bash
   python manage.py createsuperuser
   ```

5. **Run Server**
   ```bash
   python manage.py runserver
   ```

6. **Access the Application**
   - Website: http://127.0.0.1:8000/
   - Admin: http://127.0.0.1:8000/admin/

## Default Admin Credentials (if using sample data)

- Username: `admin`
- Password: `admin123`

## Project Structure

```
counseling_booking/
├── bookings/                   # Main app
│   ├── management/commands/    # Custom commands
│   ├── migrations/             # Database migrations
│   ├── admin.py               # Admin configuration
│   ├── forms.py               # Form definitions
│   ├── models.py              # Database models
│   ├── urls.py                # URL patterns
│   ├── utils.py               # Utility functions
│   └── views.py               # View logic
├── config/                     # Project configuration
│   ├── settings.py
│   ├── urls.py
│   └── wsgi.py
├── templates/                  # HTML templates
│   ├── base.html              # Base template
│   └── bookings/              # App-specific templates
├── static/                     # Static files
├── media/                      # Uploaded files
├── requirements.txt
└── manage.py
```

## Models

### Counselor
- Personal info (name, email, phone)
- Photo (optional)
- Specialization
- Bio
- Active status

### Service
- Name (e.g., "Individual Session")
- Duration (in minutes)
- Price
- Description

### Availability
- Links to Counselor
- Day of week (Monday-Sunday)
- Start and end time

### Appointment
- Client info (name, email, phone)
- Links to Counselor and Service
- Date and time
- Status (pending, confirmed, cancelled, completed)

## Booking Flow

1. **Step 1**: Select Counselor and Service
2. **Step 2**: Pick Date and Time from calendar
3. **Step 3**: Enter client details and confirm

## Customization

### Adding New Counselors
1. Go to Admin → Counselors → Add Counselor
2. Fill in details
3. Add availability slots (inline on the same page)

### Modifying Services
1. Go to Admin → Services
2. Edit duration, price, description as needed

### Email Notifications
Configure SMTP in `config/settings.py`:
```python
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = 'your-smtp-server'
EMAIL_PORT = 587
EMAIL_USE_TLS = True
EMAIL_HOST_USER = 'your-email@example.com'
EMAIL_HOST_PASSWORD = 'your-password'
```

## Production Deployment

1. Set `DEBUG = False` in settings
2. Configure `ALLOWED_HOSTS`
3. Use PostgreSQL instead of SQLite
4. Set up proper `SECRET_KEY`
5. Configure static files serving
6. Use gunicorn/uwsgi behind nginx

## License

MIT License
