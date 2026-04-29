from django.shortcuts import render, redirect, get_object_or_404
from django.views import View
from django.views.generic import TemplateView, ListView
from django.http import JsonResponse
from django.contrib import messages
from django.core.mail import send_mail
from django.conf import settings
from django.db import transaction
from datetime import datetime, date, timedelta

from .models import Counselor, Service, Appointment, Availability
from .forms import AppointmentBookingForm
from .utils import get_available_slots, get_counselor_available_dates, is_slot_available


class HomeView(TemplateView):
    """Landing page"""
    template_name = 'bookings/home.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['counselors'] = Counselor.objects.filter(is_active=True)[:3]
        context['services'] = Service.objects.filter(is_active=True)
        return context


class CounselorListView(ListView):
    """List all counselors"""
    model = Counselor
    template_name = 'bookings/counselor_list.html'
    context_object_name = 'counselors'
    queryset = Counselor.objects.filter(is_active=True)

class ContactView(TemplateView):
    """Contact page"""
    template_name = 'bookings/contact.html'


class BookingStartView(View):
    """Step 1: Select counselor and service"""
    template_name = 'bookings/booking_step1.html'

    def get(self, request):
        for key in ['booking_counselor_id', 'booking_service_id', 'booking_date', 'booking_time']:
            request.session.pop(key, None)
        
        counselors = Counselor.objects.filter(is_active=True)
        services = Service.objects.filter(is_active=True)
        
        return render(request, self.template_name, {
            'counselors': counselors,
            'services': services,
        })

    def post(self, request):
        counselor_id = request.POST.get('counselor')
        service_id = request.POST.get('service')
        
        if not counselor_id or not service_id:
            messages.error(request, 'Please select both a counselor and a service.')
            return redirect('booking_start')
        
        request.session['booking_counselor_id'] = counselor_id
        request.session['booking_service_id'] = service_id
        
        return redirect('booking_datetime')


class BookingDateTimeView(View):
    """Step 2: Select date and time"""
    template_name = 'bookings/booking_step2.html'

    def get(self, request):
        counselor_id = request.session.get('booking_counselor_id')
        service_id = request.session.get('booking_service_id')
        
        if not counselor_id or not service_id:
            messages.warning(request, 'Please start the booking process from the beginning.')
            return redirect('booking_start')
        
        counselor = get_object_or_404(Counselor, id=counselor_id, is_active=True)
        service = get_object_or_404(Service, id=service_id, is_active=True)
        
        available_dates = get_counselor_available_dates(counselor, days_ahead=30)
        
        return render(request, self.template_name, {
            'counselor': counselor,
            'service': service,
            'available_dates': available_dates,
        })

    def post(self, request):
        appointment_date = request.POST.get('appointment_date')
        start_time = request.POST.get('start_time')
        
        if not appointment_date or not start_time:
            messages.error(request, 'Please select a date and time.')
            return redirect('booking_datetime')
        
        request.session['booking_date'] = appointment_date
        request.session['booking_time'] = start_time
        
        return redirect('booking_confirm')


class GetAvailableSlotsView(View):
    """AJAX endpoint to get available slots for a specific date"""
    
    def get(self, request):
        counselor_id = request.GET.get('counselor_id')
        service_id = request.GET.get('service_id')
        date_str = request.GET.get('date')
        
        if not all([counselor_id, service_id, date_str]):
            return JsonResponse({'error': 'Missing parameters'}, status=400)
        
        try:
            counselor = Counselor.objects.get(id=counselor_id, is_active=True)
            service = Service.objects.get(id=service_id, is_active=True)
            selected_date = datetime.strptime(date_str, '%Y-%m-%d').date()
        except (Counselor.DoesNotExist, Service.DoesNotExist, ValueError):
            return JsonResponse({'error': 'Invalid data'}, status=400)
        
        if selected_date < date.today():
            return JsonResponse({'slots': []})
        
        slots = get_available_slots(counselor, selected_date, service)
        
        slots_data = [
            {
                'start': slot[0].strftime('%H:%M'),
                'end': slot[1].strftime('%H:%M'),
                'display': f"{slot[0].strftime('%I:%M %p')} - {slot[1].strftime('%I:%M %p')}"
            }
            for slot in slots
        ]
        
        return JsonResponse({'slots': slots_data})


class BookingConfirmView(View):
    """Step 3: Confirm details and complete booking"""
    template_name = 'bookings/booking_step3.html'

    def get(self, request):
        counselor_id = request.session.get('booking_counselor_id')
        service_id = request.session.get('booking_service_id')
        booking_date = request.session.get('booking_date')
        booking_time = request.session.get('booking_time')
        
        if not all([counselor_id, service_id, booking_date, booking_time]):
            messages.warning(request, 'Please start the booking process from the beginning.')
            return redirect('booking_start')
        
        counselor = get_object_or_404(Counselor, id=counselor_id, is_active=True)
        service = get_object_or_404(Service, id=service_id, is_active=True)
        
        appointment_date = datetime.strptime(booking_date, '%Y-%m-%d').date()
        start_time = datetime.strptime(booking_time, '%H:%M').time()
        
        end_time = (datetime.combine(date.today(), start_time) + 
                   timedelta(minutes=service.duration_minutes)).time()
        
        form = AppointmentBookingForm()
        
        return render(request, self.template_name, {
            'form': form,
            'counselor': counselor,
            'service': service,
            'appointment_date': appointment_date,
            'start_time': start_time,
            'end_time': end_time,
        })

    def post(self, request):
        counselor_id = request.session.get('booking_counselor_id')
        service_id = request.session.get('booking_service_id')
        booking_date = request.session.get('booking_date')
        booking_time = request.session.get('booking_time')
        
        if not all([counselor_id, service_id, booking_date, booking_time]):
            messages.warning(request, 'Session expired. Please start over.')
            return redirect('booking_start')
        
        counselor = get_object_or_404(Counselor, id=counselor_id, is_active=True)
        service = get_object_or_404(Service, id=service_id, is_active=True)
        
        appointment_date = datetime.strptime(booking_date, '%Y-%m-%d').date()
        start_time = datetime.strptime(booking_time, '%H:%M').time()
        
        form = AppointmentBookingForm(request.POST)
        
        if form.is_valid():
            with transaction.atomic():
                if not is_slot_available(counselor, appointment_date, start_time, service):
                    messages.error(request, 'Sorry, this slot has just been booked. Please select another time.')
                    return redirect('booking_datetime')
                
                appointment = form.save(commit=False)
                appointment.counselor = counselor
                appointment.service = service
                appointment.appointment_date = appointment_date
                appointment.start_time = start_time
                appointment.status = 'confirmed'
                appointment.save()
                
                for key in ['booking_counselor_id', 'booking_service_id', 'booking_date', 'booking_time']:
                    request.session.pop(key, None)
                
                messages.success(request, 'Your appointment has been booked successfully!')
                return redirect('booking_success', appointment_id=appointment.id)
        
        end_time = (datetime.combine(date.today(), start_time) + 
                   timedelta(minutes=service.duration_minutes)).time()
        
        return render(request, self.template_name, {
            'form': form,
            'counselor': counselor,
            'service': service,
            'appointment_date': appointment_date,
            'start_time': start_time,
            'end_time': end_time,
        })


class BookingSuccessView(View):
    """Booking confirmation page"""
    template_name = 'bookings/booking_success.html'

    def get(self, request, appointment_id):
        appointment = get_object_or_404(Appointment, id=appointment_id)
        return render(request, self.template_name, {
            'appointment': appointment,
        })


class AppointmentCancelView(View):
    """Cancel an appointment"""
    
    def post(self, request, appointment_id):
        appointment = get_object_or_404(Appointment, id=appointment_id)
        
        if appointment.appointment_date < date.today():
            messages.error(request, 'Cannot cancel past appointments.')
            return redirect('home')
        
        appointment.status = 'cancelled'
        appointment.save()
        
        messages.success(request, 'Your appointment has been cancelled.')
        return redirect('home')
