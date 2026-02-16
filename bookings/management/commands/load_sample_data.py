from django.core.management.base import BaseCommand
from bookings.models import Counselor, Service, Availability
from datetime import time


class Command(BaseCommand):
    help = 'Load sample data for testing'

    def handle(self, *args, **options):
        # Create Services
        services_data = [
            {
                'name': 'Individual Session',
                'description': 'One-on-one counseling session for personal issues, anxiety, depression, or life challenges.',
                'duration_minutes': 50,
                'price': 120.00
            },
            {
                'name': 'Couples Therapy',
                'description': 'Counseling session for couples to work on relationship issues and improve communication.',
                'duration_minutes': 80,
                'price': 180.00
            },
            {
                'name': 'Initial Consultation',
                'description': 'First-time meeting to discuss your concerns and determine the best treatment approach.',
                'duration_minutes': 30,
                'price': 0.00
            },
            {
                'name': 'Group Session',
                'description': 'Small group therapy session focused on shared experiences and mutual support.',
                'duration_minutes': 90,
                'price': 60.00
            },
        ]
        
        for service_data in services_data:
            service, created = Service.objects.get_or_create(
                name=service_data['name'],
                defaults=service_data
            )
            if created:
                self.stdout.write(self.style.SUCCESS(f'Created service: {service.name}'))
            else:
                self.stdout.write(f'Service already exists: {service.name}')
        
        # Create Counselors
        counselors_data = [
            {
                'first_name': 'Sarah',
                'last_name': 'Johnson',
                'email': 'sarah.johnson@mindcare.com',
                'phone': '+1 234 567 8901',
                'specialization': 'Anxiety, Depression, Stress Management',
                'bio': 'Dr. Sarah Johnson has over 15 years of experience helping individuals overcome anxiety and depression. She uses a combination of cognitive-behavioral therapy and mindfulness techniques.',
                'availability': [
                    (0, '09:00', '17:00'),  # Monday
                    (1, '09:00', '17:00'),  # Tuesday
                    (2, '09:00', '17:00'),  # Wednesday
                    (3, '09:00', '17:00'),  # Thursday
                    (4, '09:00', '14:00'),  # Friday
                ]
            },
            {
                'first_name': 'Michael',
                'last_name': 'Chen',
                'email': 'michael.chen@mindcare.com',
                'phone': '+1 234 567 8902',
                'specialization': 'Couples Therapy, Family Counseling',
                'bio': 'Dr. Michael Chen specializes in relationship counseling and family therapy. He has helped hundreds of couples improve their communication and strengthen their bonds.',
                'availability': [
                    (0, '10:00', '18:00'),  # Monday
                    (2, '10:00', '18:00'),  # Wednesday
                    (3, '10:00', '18:00'),  # Thursday
                    (5, '10:00', '15:00'),  # Saturday
                ]
            },
            {
                'first_name': 'Emily',
                'last_name': 'Williams',
                'email': 'emily.williams@mindcare.com',
                'phone': '+1 234 567 8903',
                'specialization': 'Trauma, PTSD, Grief Counseling',
                'bio': 'Dr. Emily Williams is a trauma-informed therapist who specializes in helping individuals heal from traumatic experiences. She uses EMDR and other evidence-based approaches.',
                'availability': [
                    (1, '08:00', '16:00'),  # Tuesday
                    (2, '08:00', '16:00'),  # Wednesday
                    (4, '08:00', '16:00'),  # Friday
                ]
            },
            {
                'first_name': 'James',
                'last_name': 'Anderson',
                'email': 'james.anderson@mindcare.com',
                'phone': '+1 234 567 8904',
                'specialization': 'Addiction, Behavioral Issues',
                'bio': 'Dr. James Anderson has dedicated his career to helping individuals overcome addiction and behavioral challenges. He takes a compassionate, non-judgmental approach to therapy.',
                'availability': [
                    (0, '11:00', '19:00'),  # Monday
                    (1, '11:00', '19:00'),  # Tuesday
                    (3, '11:00', '19:00'),  # Thursday
                    (4, '11:00', '17:00'),  # Friday
                ]
            },
        ]
        
        for counselor_data in counselors_data:
            availability_data = counselor_data.pop('availability')
            
            counselor, created = Counselor.objects.get_or_create(
                email=counselor_data['email'],
                defaults=counselor_data
            )
            
            if created:
                self.stdout.write(self.style.SUCCESS(f'Created counselor: Dr. {counselor.full_name}'))
                
                # Create availability
                for day, start, end in availability_data:
                    Availability.objects.create(
                        counselor=counselor,
                        day_of_week=day,
                        start_time=time.fromisoformat(start),
                        end_time=time.fromisoformat(end)
                    )
                self.stdout.write(f'  Added {len(availability_data)} availability slots')
            else:
                self.stdout.write(f'Counselor already exists: Dr. {counselor.full_name}')
        
        self.stdout.write(self.style.SUCCESS('\nSample data loaded successfully!'))
        self.stdout.write('\nYou can now:')
        self.stdout.write('  1. Run the server: python manage.py runserver')
        self.stdout.write('  2. Visit: http://127.0.0.1:8000/')
        self.stdout.write('  3. Admin: http://127.0.0.1:8000/admin/')
