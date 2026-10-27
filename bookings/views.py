from datetime import datetime, date, timedelta

from django.contrib import messages
from django.db import transaction
from django.db.models import Case, When, IntegerField, Prefetch
from django.http import Http404, JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.views import View
from django.views.generic import TemplateView, ListView

from .forms import AppointmentBookingForm, ContactMessageForm
from .models import Counselor, Service, Appointment
from .utils import get_available_slots, get_counselor_available_dates, is_slot_available, local_today

BOOKING_KEYS = ['booking_counselor_id', 'booking_service_id', 'booking_date', 'booking_time']
OWNED_KEY = 'booked_appointment_ids'   # appointments this browser created (for success/cancel pages)
DAYS_AHEAD = 30


# -----------------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------------

def bookable_counselors():
    """Counselors allowed in the booking flow (hides e.g. the Admin/Founder)."""
    return Counselor.objects.filter(is_active=True, show_on_booking_page=True)


def services_for(counselor):
    """Active services this counselor offers. If none are assigned yet, all active services."""
    offered = counselor.services.filter(is_active=True)
    return offered if offered.exists() else Service.objects.filter(is_active=True)


def parse_date(value):
    try:
        return datetime.strptime(value or '', '%Y-%m-%d').date()
    except ValueError:
        return None


def parse_time(value):
    try:
        return datetime.strptime(value or '', '%H:%M').time()
    except ValueError:
        return None


def end_time_for(start_time, service):
    return (datetime.combine(date.today(), start_time) + timedelta(minutes=service.duration_minutes)).time()


def owns_appointment(request, appointment):
    return request.user.is_staff or appointment.id in request.session.get(OWNED_KEY, [])


class BookingStateMixin:
    """
    Loads and re-validates the counselor/service (and optionally date/time) stored in the
    session. Returns (data, None) when valid, or (None, redirect_response) when not.
    """

    def load_state(self, request, need_datetime=False):
        counselor_id = request.session.get('booking_counselor_id')
        service_id = request.session.get('booking_service_id')
        if not counselor_id or not service_id:
            messages.warning(request, 'Please start your booking from the first step.')
            return None, redirect('booking_start')

        counselor = bookable_counselors().filter(id=counselor_id).first()
        if counselor is None or not counselor.can_be_booked:
            messages.error(request, 'Sorry, that counselor is no longer accepting bookings. Please choose another.')
            return None, redirect('booking_start')

        service = services_for(counselor).filter(id=service_id).first()
        if service is None:
            messages.error(request, 'That session type is no longer available. Please choose another.')
            return None, redirect('booking_start')

        data = {'counselor': counselor, 'service': service}
        if need_datetime:
            appointment_date = parse_date(request.session.get('booking_date'))
            start_time = parse_time(request.session.get('booking_time'))
            if appointment_date is None or start_time is None:
                messages.warning(request, 'Please pick a date and time.')
                return None, redirect('booking_datetime')
            data.update(
                appointment_date=appointment_date,
                start_time=start_time,
                end_time=end_time_for(start_time, service),
            )
        return data, None


# -----------------------------------------------------------------------------
# Public pages
# -----------------------------------------------------------------------------

class HomeView(TemplateView):
    """Landing page"""
    template_name = 'bookings/home.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['counselors'] = Counselor.objects.filter(is_active=True).select_related('user')[:3]
        context['services'] = Service.objects.filter(is_active=True)
        return context


class CounselorListView(ListView):
    """All active counselors; anyone with a role label (e.g. the founder) is listed first."""
    model = Counselor
    template_name = 'bookings/counselor_list.html'
    context_object_name = 'counselors'

    def get_queryset(self):
        return (
            Counselor.objects.filter(is_active=True)
            .select_related('user')
            .annotate(has_role=Case(When(role_label='', then=1), default=0, output_field=IntegerField()))
            .order_by('has_role', 'user__first_name')
        )


class ServicesView(TemplateView):
    """Services page"""
    template_name = 'bookings/services.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['services'] = Service.objects.filter(is_active=True)
        return context


class ContactView(View):
    """Contact page: validates and saves messages (visible in Admin > Contact Messages)."""
    template_name = 'bookings/contact.html'

    def get(self, request):
        return render(request, self.template_name)

    def post(self, request):
        form = ContactMessageForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Thank you! Your message has been sent. We will get back to you soon.')
            return redirect('contact')

        first_error = next(iter(form.errors.values()))[0]
        messages.error(request, f'Please check the form: {first_error}')
        return render(request, self.template_name, {'form': form}, status=400)


# -----------------------------------------------------------------------------
# Booking flow
# -----------------------------------------------------------------------------

class BookingStartView(View):
    """Step 1: Select counselor and service"""
    template_name = 'bookings/booking_step1.html'

    def get(self, request):
        for key in ['booking_date', 'booking_time']:
            request.session.pop(key, None)

        active_services = Service.objects.filter(is_active=True)
        counselors = (
            bookable_counselors()
            .select_related('user')
            .prefetch_related(Prefetch('services', queryset=active_services))
            .order_by('-is_accepting_bookings', 'user__first_name')
        )

        # Preselect from ?counselor=&service= (links on other pages) or from the session
        selected_counselor = request.GET.get('counselor') or request.session.get('booking_counselor_id') or ''
        selected_service = request.GET.get('service') or request.session.get('booking_service_id') or ''

        return render(request, self.template_name, {
            'counselors': counselors,
            'services': active_services,
            'selected_counselor': str(selected_counselor),
            'selected_service': str(selected_service),
        })

    def post(self, request):
        counselor_id = request.POST.get('counselor', '')
        service_id = request.POST.get('service', '')

        if not counselor_id.isdigit() or not service_id.isdigit():
            messages.error(request, 'Please choose a counselor and a session.')
            return redirect('booking_start')

        counselor = bookable_counselors().filter(id=counselor_id).first()
        if counselor is None:
            messages.error(request, 'Please choose a counselor from the list.')
            return redirect('booking_start')
        if not counselor.can_be_booked:
            messages.error(request, f'Sorry, {counselor.full_name} is not accepting bookings right now. Please choose another counselor.')
            return redirect('booking_start')
        if not services_for(counselor).filter(id=service_id).exists():
            messages.error(request, f'{counselor.full_name} does not offer that session. Please choose another.')
            return redirect('booking_start')

        if (request.session.get('booking_counselor_id'), request.session.get('booking_service_id')) != (counselor_id, service_id):
            request.session.pop('booking_date', None)
            request.session.pop('booking_time', None)
        request.session['booking_counselor_id'] = counselor_id
        request.session['booking_service_id'] = service_id
        return redirect('booking_datetime')


class BookingDateTimeView(BookingStateMixin, View):
    """Step 2: Select date and time"""
    template_name = 'bookings/booking_step2.html'

    def get(self, request):
        data, response = self.load_state(request)
        if response:
            return response

        data.update(
            available_dates=get_counselor_available_dates(data['counselor'], DAYS_AHEAD, service=data['service']),
            selected_date=request.session.get('booking_date', ''),
            selected_time=request.session.get('booking_time', ''),
        )
        return render(request, self.template_name, data)

    def post(self, request):
        data, response = self.load_state(request)
        if response:
            return response

        appointment_date = parse_date(request.POST.get('appointment_date'))
        start_time = parse_time(request.POST.get('start_time'))
        if appointment_date is None or start_time is None:
            messages.error(request, 'Please pick a date and a time.')
            return redirect('booking_datetime')

        if not is_slot_available(data['counselor'], appointment_date, start_time, data['service']):
            messages.error(request, 'Sorry, that time is no longer available. Please pick another.')
            return redirect('booking_datetime')

        request.session['booking_date'] = appointment_date.strftime('%Y-%m-%d')
        request.session['booking_time'] = start_time.strftime('%H:%M')
        return redirect('booking_confirm')


class GetAvailableSlotsView(View):
    """AJAX: open slots for a counselor + service on one date."""

    def get(self, request):
        counselor_id = request.GET.get('counselor_id', '')
        service_id = request.GET.get('service_id', '')
        selected_date = parse_date(request.GET.get('date'))

        if not counselor_id.isdigit() or not service_id.isdigit() or selected_date is None:
            return JsonResponse({'error': 'Invalid parameters', 'slots': []}, status=400)

        counselor = bookable_counselors().filter(id=counselor_id).first()
        if counselor is None:
            return JsonResponse({'error': 'Invalid counselor', 'slots': []}, status=400)
        if not counselor.can_be_booked:
            return JsonResponse({'error': 'Counselor not accepting bookings', 'slots': []})

        service = services_for(counselor).filter(id=service_id).first()
        if service is None:
            return JsonResponse({'error': 'Invalid service', 'slots': []}, status=400)

        if selected_date < local_today():
            return JsonResponse({'slots': []})

        slots = get_available_slots(counselor, selected_date, service)
        return JsonResponse({'slots': [
            {
                'start': start.strftime('%H:%M'),
                'end': end.strftime('%H:%M'),
                'display': f"{start.strftime('%I:%M %p')} - {end.strftime('%I:%M %p')}",
            }
            for start, end in slots
        ]})


class BookingConfirmView(BookingStateMixin, View):
    """Step 3: Client details and final confirmation"""
    template_name = 'bookings/booking_step3.html'

    def get(self, request):
        data, response = self.load_state(request, need_datetime=True)
        if response:
            return response
        data['form'] = AppointmentBookingForm()
        return render(request, self.template_name, data)

    def post(self, request):
        data, response = self.load_state(request, need_datetime=True)
        if response:
            return response

        form = AppointmentBookingForm(request.POST)
        if not form.is_valid():
            data['form'] = form
            return render(request, self.template_name, data, status=400)

        with transaction.atomic():
            if not is_slot_available(data['counselor'], data['appointment_date'], data['start_time'], data['service']):
                messages.error(request, 'Sorry, this time was just booked by someone else. Please pick another time.')
                request.session.pop('booking_time', None)
                return redirect('booking_datetime')

            appointment = form.save(commit=False)
            appointment.counselor = data['counselor']
            appointment.service = data['service']
            appointment.appointment_date = data['appointment_date']
            appointment.start_time = data['start_time']
            appointment.status = 'confirmed'
            appointment.save()

        for key in BOOKING_KEYS:
            request.session.pop(key, None)
        owned = request.session.get(OWNED_KEY, [])
        request.session[OWNED_KEY] = (owned + [appointment.id])[-20:]

        messages.success(request, 'Your appointment has been booked successfully!')
        return redirect('booking_success', appointment_id=appointment.id)


class BookingSuccessView(View):
    """Confirmation page. Only the browser that made the booking (or staff) can view it."""
    template_name = 'bookings/booking_success.html'

    def get(self, request, appointment_id):
        appointment = get_object_or_404(
            Appointment.objects.select_related('counselor__user', 'service'), id=appointment_id
        )
        if not owns_appointment(request, appointment):
            raise Http404('Appointment not found')
        return render(request, self.template_name, {'appointment': appointment})


class AppointmentCancelView(View):
    """Cancel an appointment. Only the browser that made the booking (or staff) can cancel it."""

    def post(self, request, appointment_id):
        appointment = get_object_or_404(Appointment, id=appointment_id)
        if not owns_appointment(request, appointment):
            raise Http404('Appointment not found')

        if appointment.appointment_date < local_today():
            messages.error(request, 'Past appointments cannot be cancelled.')
            return redirect('home')

        appointment.status = 'cancelled'
        appointment.save(update_fields=['status', 'updated_at'])
        messages.success(request, 'Your appointment has been cancelled.')
        return redirect('home')
