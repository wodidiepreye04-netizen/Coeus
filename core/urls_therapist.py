from django.urls import path
from . import views_therapist as views

urlpatterns = [
    path("login/", views.therapist_login, name="therapist_login"),
    path("dashboard/", views.therapist_dashboard, name="therapist_dashboard"),
    path("patients/", views.therapist_patients, name="therapist_patients"),
    path(
        "patient/<int:patient_id>/",
        views.therapist_patient_detail,
        name="therapist_patient_detail",
    ),
    path(
        "appointment/<int:appointment_id>/action/",
        views.therapist_appointment_action,
        name="therapist_appointment_action",
    ),
    path(
        "subscription/<int:subscription_id>/action/",
        views.therapist_subscription_action,
        name="therapist_subscription_action",
    ),
    # Availability management
    path(
        "availability/<int:slot_id>/toggle/",
        views.therapist_availability_toggle,
        name="therapist_availability_toggle",
    ),
    path(
        "availability/add/",
        views.therapist_availability_add,
        name="therapist_availability_add",
    ),
    path(
        "availability/<int:slot_id>/delete/",
        views.therapist_availability_delete,
        name="therapist_availability_delete",
    ),
]
