from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from bookings.models import Counselor, Service, Availability
from datetime import time


class Command(BaseCommand):
    help = 'Load sample data with counselor user accounts'

    def handle(self, *args, **options):
        
        # Create Superuser (if not exists)
        if not User.objects.filter(username='admin').exists():
            User.objects.create_superuser(
                username='admin',
                email='admin@mindcare.com',
                password='admin123',
                first_name='Super',
                last_name='Admin'
            )
            self.stdout.write(self.style.SUCCESS('Created superuser: admin / admin123'))
        
        # Create Global Services (available to all counselors)
        global_services = [
            {
                'name': 'Individual Session',
                'description': 'One-on-one counseling session for personal issues.',
                'duration_minutes': 50,
                'price': 120.00,
                'counselor': None  # Global
            },
            {
                'name': 'Initial Consultation',
                'description': 'First-time meeting to discuss your concerns.',
                'duration_minutes': 30,
                'price': 0.00,
                'counselor': None  # Global
            },
        ]
        
        for service_data in global_services:
            service, created = Service.objects.get_or_create(
                name=service_data['name'],
                counselor__isnull=True,
                defaults=service_data
            )
            if created:
                self.stdout.write(self.style.SUCCESS(f'Created global service: {service.name}'))
        
        # Create Counselor Users with Profiles
        counselors_data = [
            {
                'username': 'sarah',
                'password': 'sarah123',
                'email': 'sarah.johnson@mindcare.com',
                'first_name': 'Sarah',
                'last_name': 'Johnson',
                'profile': {
                    'phone': '+1 234 567 8901',
                    'specialization': 'Anxiety, Depression, Stress Management',
                    'bio': 'Dr. Sarah Johnson has over 15 years of experience helping individuals overcome anxiety and depression.',
                },
                'availability': [
                    (0, '09:00', '17:00'),  # Monday
                    (1, '09:00', '17:00'),  # Tuesday
                    (2, '09:00', '17:00'),  # Wednesday
                    (3, '09:00', '17:00'),  # Thursday
                    (4, '09:00', '14:00'),  # Friday
                ],
                'services': [
                    {'name': 'Anxiety Workshop', 'duration_minutes': 90, 'price': 80.00},
                ]
            },
            {
                'username': 'michael',
                'password': 'michael123',
                'email': 'michael.chen@mindcare.com',
                'first_name': 'Michael',
                'last_name': 'Chen',
                'profile': {
                    'phone': '+1 234 567 8902',
                    'specialization': 'Couples Therapy, Family Counseling',
                    'bio': 'Dr. Michael Chen specializes in relationship counseling and family therapy.',
                },
                'availability': [
                    (0, '10:00', '18:00'),  # Monday
                    (2, '10:00', '18:00'),  # Wednesday
                    (3, '10:00', '18:00'),  # Thursday
                    (5, '10:00', '15:00'),  # Saturday
                ],
                'services': [
                    {'name': 'Couples Therapy', 'duration_minutes': 80, 'price': 180.00},
                    {'name': 'Family Session', 'duration_minutes': 90, 'price': 200.00},
                ]
            },
            {
                'username': 'emily',
                'password': 'emily123',
                'email': 'emily.williams@mindcare.com',
                'first_name': 'Emily',
                'last_name': 'Williams',
                'profile': {
                    'phone': '+1 234 567 8903',
                    'specialization': 'Trauma, PTSD, Grief Counseling',
                    'bio': 'Dr. Emily Williams is a trauma-informed therapist specializing in PTSD and grief.',
                },
                'availability': [
                    (1, '08:00', '16:00'),  # Tuesday
                    (2, '08:00', '16:00'),  # Wednesday
                    (4, '08:00', '16:00'),  # Friday
                ],
                'services': [
                    {'name': 'EMDR Therapy', 'duration_minutes': 60, 'price': 150.00},
                    {'name': 'Grief Support', 'duration_minutes': 50, 'price': 120.00},
                ]
            },
        ]
        
        for data in counselors_data:
            # Create User
            user, user_created = User.objects.get_or_create(
                username=data['username'],
                defaults={
                    'email': data['email'],
                    'first_name': data['first_name'],
                    'last_name': data['last_name'],
                    'is_staff': True,  # Allow admin access
                }
            )
            
            if user_created:
                user.set_password(data['password'])
                user.save()
                self.stdout.write(self.style.SUCCESS(
                    f"Created user: {data['username']} / {data['password']}"
                ))
            
            # Create Counselor Profile
            counselor, profile_created = Counselor.objects.get_or_create(
                user=user,
                defaults=data['profile']
            )
            
            if profile_created:
                self.stdout.write(f"  Created profile for Dr. {counselor.full_name}")
                
                # Create Availability
                for day, start, end in data['availability']:
                    Availability.objects.get_or_create(
                        counselor=counselor,
                        day_of_week=day,
                        defaults={
                            'start_time': time.fromisoformat(start),
                            'end_time': time.fromisoformat(end)
                        }
                    )
                self.stdout.write(f"  Added {len(data['availability'])} availability slots")
                
                # Create Counselor-specific Services
                for svc in data.get('services', []):
                    Service.objects.create(
                        counselor=counselor,
                        name=svc['name'],
                        duration_minutes=svc['duration_minutes'],
                        price=svc['price']
                    )
                self.stdout.write(f"  Added {len(data.get('services', []))} custom services")
        
        self.stdout.write(self.style.SUCCESS('\n✅ Sample data loaded successfully!'))
        self.stdout.write('\n' + '='*60)
        self.stdout.write('LOGIN CREDENTIALS:')
        self.stdout.write('='*60)
        self.stdout.write('\nSuperuser (Full Access):')
        self.stdout.write('  Username: admin')
        self.stdout.write('  Password: admin123')
        self.stdout.write('\nCounselors (Own Data Only):')
        self.stdout.write('  Username: sarah    | Password: sarah123')
        self.stdout.write('  Username: michael  | Password: michael123')
        self.stdout.write('  Username: emily    | Password: emily123')
        self.stdout.write('='*60)
