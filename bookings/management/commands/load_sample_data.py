from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from bookings.models import Counselor, Service, Availability
from datetime import time


class Command(BaseCommand):
    help = 'Load sample data with counselor user accounts'

    def handle(self, *args, **options):
        
        # Create Superuser
        if not User.objects.filter(username='admin').exists():
            User.objects.create_superuser(
                username='admin',
                email='admin@mindcare.com',
                password='admin123',
                first_name='Super',
                last_name='Admin'
            )
            self.stdout.write(self.style.SUCCESS('Created superuser: admin / admin123'))
        
        # Create Services (Global - managed by admin only)
        services_data = [
            {
                'name': 'Individual Session',
                'description': 'One-on-one counseling session for personal issues.',
                'duration_minutes': 50,
                'price': 120.00,
            },
            {
                'name': 'Initial Consultation',
                'description': 'First-time meeting to discuss your concerns.',
                'duration_minutes': 30,
                'price': 0.00,
            },
            {
                'name': 'Couples Therapy',
                'description': 'Counseling session for couples to improve relationships.',
                'duration_minutes': 80,
                'price': 180.00,
            },
            {
                'name': 'Family Session',
                'description': 'Family counseling to resolve conflicts and improve communication.',
                'duration_minutes': 90,
                'price': 200.00,
            },
            {
                'name': 'Group Therapy',
                'description': 'Small group session focused on shared experiences.',
                'duration_minutes': 90,
                'price': 60.00,
            },
            {
                'name': 'EMDR Therapy',
                'description': 'Eye Movement Desensitization and Reprocessing for trauma.',
                'duration_minutes': 60,
                'price': 150.00,
            },
            {
                'name': 'Anxiety Workshop',
                'description': 'Focused session on anxiety management techniques.',
                'duration_minutes': 90,
                'price': 80.00,
            },
        ]
        
        created_services = {}
        for service_data in services_data:
            service, created = Service.objects.get_or_create(
                name=service_data['name'],
                defaults=service_data
            )
            created_services[service.name] = service
            if created:
                self.stdout.write(self.style.SUCCESS(f'Created service: {service.name}'))
        
        # Create Counselor Users with Profiles and Services
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
                'services': ['Individual Session', 'Initial Consultation', 'Anxiety Workshop', 'Group Therapy'],
                'availability': [
                    (0, '09:00', '17:00'),
                    (1, '09:00', '17:00'),
                    (2, '09:00', '17:00'),
                    (3, '09:00', '17:00'),
                    (4, '09:00', '14:00'),
                ],
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
                'services': ['Individual Session', 'Initial Consultation', 'Couples Therapy', 'Family Session'],
                'availability': [
                    (0, '10:00', '18:00'),
                    (2, '10:00', '18:00'),
                    (3, '10:00', '18:00'),
                    (5, '10:00', '15:00'),
                ],
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
                'services': ['Individual Session', 'Initial Consultation', 'EMDR Therapy'],
                'availability': [
                    (1, '08:00', '16:00'),
                    (2, '08:00', '16:00'),
                    (4, '08:00', '16:00'),
                ],
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
                    'is_staff': True,
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
                
                # Add Services (Many-to-Many)
                for service_name in data['services']:
                    if service_name in created_services:
                        counselor.services.add(created_services[service_name])
                self.stdout.write(f"  Assigned {len(data['services'])} services")
                
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
        self.stdout.write('\nServices are assigned to counselors via Many-to-Many.')
        self.stdout.write('Admin can manage services, counselors select which ones they offer.')
