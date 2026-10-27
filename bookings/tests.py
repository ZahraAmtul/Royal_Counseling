from datetime import date, datetime, time, timedelta
from unittest import mock

from django.contrib.auth.models import User
from django.test import Client, TestCase
from django.urls import reverse

from .models import Appointment, Availability, ContactMessage, Counselor, Service
from . import utils


def next_weekday(weekday, start=None):
    d = (start or utils.local_today()) + timedelta(days=1)
    while d.weekday() != weekday:
        d += timedelta(days=1)
    return d


class BookingFlowTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = User.objects.create_superuser('admin', 'a@x.com', 'pw')
        cls.therapy = Service.objects.create(name='Individual', duration_minutes=50)
        cls.couples = Service.objects.create(name='Couples', duration_minutes=60)
        u = User.objects.create_user('sarah', password='pw', is_staff=True, first_name='Sarah')
        cls.sarah = Counselor.objects.create(user=u, specialization='Anxiety', is_accepting_bookings=True)
        cls.sarah.services.set([cls.therapy])
        f = User.objects.create_user('founder', password='pw', is_staff=True, first_name='Founder')
        cls.founder = Counselor.objects.create(user=f, specialization='x', is_accepting_bookings=True,
                                               show_on_booking_page=False, role_label='Admin and Founder')
        cls.monday = next_weekday(0)
        Availability.objects.create(counselor=cls.sarah, day_of_week=0, start_time=time(9), end_time=time(12))

    def start(self, client=None, service=None):
        c = client or self.client
        return c.post(reverse('booking_start'), {'counselor': self.sarah.id, 'service': (service or self.therapy).id})

    def pick(self, t='09:00', client=None):
        c = client or self.client
        return c.post(reverse('booking_datetime'), {'appointment_date': self.monday.isoformat(), 'start_time': t})

    def confirm(self, client=None, **extra):
        c = client or self.client
        data = {'client_name': 'Ali Khan', 'client_email': 'ali@example.com', 'client_phone': '+92 300 1234567', 'notes': ''}
        data.update(extra)
        return c.post(reverse('booking_confirm'), data)

    def test_full_flow_and_privacy(self):
        res = self.client.get(reverse('booking_start'))
        self.assertContains(res, 'Sarah')
        self.assertNotContains(res, 'Founder')
        self.assertRedirects(self.start(), reverse('booking_datetime'))

        res = self.client.get(reverse('booking_datetime'))
        self.assertIn(self.monday, res.context['available_dates'])
        self.assertTrue(all(d.weekday() == 0 for d in res.context['available_dates']))

        self.assertRedirects(self.pick('09:00'), reverse('booking_confirm'))
        self.assertEqual(self.client.get(reverse('booking_confirm')).status_code, 200)

        res = self.confirm()
        appt = Appointment.objects.get()
        self.assertRedirects(res, reverse('booking_success', args=[appt.id]))
        self.assertEqual(appt.end_time, time(9, 50))
        self.assertContains(self.client.get(reverse('booking_success', args=[appt.id])), 'Ali Khan')

        # Another visitor can't see or cancel it
        other = Client()
        self.assertEqual(other.get(reverse('booking_success', args=[appt.id])).status_code, 404)
        self.assertEqual(other.post(reverse('appointment_cancel', args=[appt.id])).status_code, 404)
        # The owner can cancel
        self.client.post(reverse('appointment_cancel', args=[appt.id]))
        appt.refresh_from_db()
        self.assertEqual(appt.status, 'cancelled')

    def test_founder_and_wrong_service_rejected(self):
        res = self.client.post(reverse('booking_start'), {'counselor': self.founder.id, 'service': self.therapy.id})
        self.assertRedirects(res, reverse('booking_start'))
        self.assertRedirects(self.start(service=self.couples), reverse('booking_start'))
        self.assertRedirects(self.client.post(reverse('booking_start'), {'counselor': 'abc', 'service': ''}), reverse('booking_start'))

    def test_invalid_or_unavailable_time_rejected(self):
        self.start()
        self.assertRedirects(self.pick('09:05'), reverse('booking_datetime'))   # not a real slot
        self.assertRedirects(self.pick('garbage'), reverse('booking_datetime'))
        # Tampered session never causes a server error
        s = self.client.session
        s['booking_date'], s['booking_time'] = 'bad', 'bad'
        s.save()
        self.assertRedirects(self.client.get(reverse('booking_confirm')), reverse('booking_datetime'))

    def test_double_booking_prevented(self):
        self.start(); self.pick('09:00')
        other = Client()
        self.start(other); self.pick('09:00', other)
        self.confirm()
        res = self.confirm(other)
        self.assertRedirects(res, reverse('booking_datetime'))
        self.assertEqual(Appointment.objects.count(), 1)

    def test_form_validation(self):
        self.start(); self.pick('09:00')
        self.assertEqual(self.confirm(client_phone='abc').status_code, 400)
        self.assertEqual(self.confirm(client_email='nope').status_code, 400)
        self.assertEqual(Appointment.objects.count(), 0)

    def test_slots_api(self):
        url = reverse('get_available_slots')
        ok = {'counselor_id': self.sarah.id, 'service_id': self.therapy.id, 'date': self.monday.isoformat()}
        self.assertEqual([s['start'] for s in self.client.get(url, ok).json()['slots']], ['09:00', '10:00', '11:00'])
        self.assertEqual(self.client.get(url, dict(ok, date='bad')).status_code, 400)
        self.assertEqual(self.client.get(url, dict(ok, counselor_id=self.founder.id)).status_code, 400)
        self.assertEqual(self.client.get(url, dict(ok, date='2000-01-03')).json()['slots'], [])

    def test_fully_booked_and_past_slots_hidden(self):
        for h in (9, 10, 11):
            Appointment.objects.create(client_name='x', client_email='x@x.com', client_phone='1234567',
                                       counselor=self.sarah, service=self.therapy,
                                       appointment_date=self.monday, start_time=time(h), end_time=time(h, 50))
        self.assertNotIn(self.monday, utils.get_counselor_available_dates(self.sarah, 30, self.therapy))
        # Today at 10:30 PKT: only the 11:00 slot of a Monday is left
        fake_now = datetime.combine(self.monday + timedelta(days=7), time(10, 30))
        with mock.patch.object(utils, 'local_now', return_value=fake_now):
            slots = utils.get_available_slots(self.sarah, fake_now.date(), self.therapy)
        self.assertEqual(slots, [(time(11), time(11, 50))])


class AdminAndContactTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        User.objects.create_superuser('admin', 'a@x.com', 'pw')
        u = User.objects.create_user('sarah', password='pw', is_staff=True, first_name='Sarah')
        cls.sarah = Counselor.objects.create(user=u, specialization='Anxiety', is_accepting_bookings=True)
        cls.svc = Service.objects.create(name='Individual', duration_minutes=50)

    def test_admin_pages_load(self):
        self.client.login(username='admin', password='pw')
        for name in ['bookings_appointment', 'bookings_availability', 'bookings_counselor',
                     'bookings_service', 'bookings_contactmessage']:
            self.assertEqual(self.client.get(reverse(f'admin:{name}_changelist')).status_code, 200, name)
        self.assertEqual(self.client.get(reverse('admin:bookings_appointment_add')).status_code, 200)

    def test_counselor_cannot_see_contact_messages(self):
        self.client.login(username='sarah', password='pw')
        self.assertEqual(self.client.get(reverse('admin:bookings_contactmessage_changelist')).status_code, 403)
        self.assertEqual(self.client.get(reverse('admin:bookings_availability_changelist')).status_code, 200)

    def test_availability_validation(self):
        Availability.objects.create(counselor=self.sarah, day_of_week=1, start_time=time(9), end_time=time(12))
        self.client.login(username='admin', password='pw')
        url = reverse('admin:bookings_availability_add')
        res = self.client.post(url, {'counselor': self.sarah.id, 'day_of_week': 1, 'start_time': '11:00:00', 'end_time': '13:00:00'})
        self.assertContains(res, 'overlaps')
        res = self.client.post(url, {'counselor': self.sarah.id, 'day_of_week': 2, 'start_time': '13:00:00', 'end_time': '12:00:00'})
        self.assertContains(res, 'End time must be after')
        self.assertEqual(Availability.objects.count(), 1)

    def test_admin_appointment_end_time_and_clash(self):
        self.client.login(username='admin', password='pw')
        url = reverse('admin:bookings_appointment_add')
        data = {'client_name': 'A', 'client_email': 'a@a.com', 'client_phone': '1234567', 'notes': '',
                'counselor': self.sarah.id, 'service': self.svc.id, 'appointment_date': '2030-01-07',
                'start_time': '10:00:00', 'status': 'confirmed'}
        self.assertEqual(self.client.post(url, data).status_code, 302)
        self.assertEqual(Appointment.objects.get().end_time, time(10, 50))
        res = self.client.post(url, dict(data, start_time='10:30:00'))
        self.assertContains(res, 'already has an appointment')

    def test_contact_form(self):
        url = reverse('contact')
        self.assertEqual(self.client.post(url, {'name': 'A', 'email': 'bad', 'message': 'Hello there'}).status_code, 400)
        self.assertRedirects(self.client.post(url, {'name': 'Ali', 'email': 'a@a.com', 'subject': '', 'message': 'Hello there'}), url)
        self.assertEqual(ContactMessage.objects.count(), 1)
