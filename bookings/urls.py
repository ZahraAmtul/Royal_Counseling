from django.urls import path
from . import views

urlpatterns = [
    path('', views.HomeView.as_view(), name='home'),
    path('counselors/', views.CounselorListView.as_view(), name='counselor_list'),
    
    # Booking flow
    path('book/', views.BookingStartView.as_view(), name='booking_start'),
    path('book/datetime/', views.BookingDateTimeView.as_view(), name='booking_datetime'),
    path('book/confirm/', views.BookingConfirmView.as_view(), name='booking_confirm'),
    path('book/success/<int:appointment_id>/', views.BookingSuccessView.as_view(), name='booking_success'),
    
    # AJAX endpoints
    path('api/slots/', views.GetAvailableSlotsView.as_view(), name='get_available_slots'),
    
    # Appointment management
    path('appointment/<int:appointment_id>/cancel/', views.AppointmentCancelView.as_view(), name='appointment_cancel'),
]
