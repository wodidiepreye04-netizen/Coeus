from django.urls import path
from . import views

urlpatterns = [
    path("", views.landing, name="landing"),
    path("signup", views.signup, name="signup"),
    path("signin", views.signin, name="signin"),
    path("signout", views.signout, name="signout"),
    path("privacy", views.privacy, name="privacy"),

    # Onboarding
    path("onboarding/", views.onboarding_welcome, name="onboarding_welcome"),
    path("onboarding/about/", views.onboarding_about, name="onboarding_about"),
    path("onboarding/checkin/", views.onboarding_checkin, name="onboarding_checkin"),
    path("onboarding/crisis/", views.onboarding_crisis, name="onboarding_crisis"),

    # Dashboard
    path("dashboard", views.dashboard, name="dashboard"),
    path("dashboard/mood/", views.mood_checkin, name="mood_checkin"),
    path("dashboard/goal/<int:goal_id>/toggle/", views.goal_toggle, name="goal_toggle"),
    path("dashboard/task/<int:task_id>/toggle/", views.task_toggle, name="task_toggle"),
    path("dashboard/journal/", views.journal_vault, name="journal_vault"),
    path("dashboard/journal/save/", views.journal_save, name="journal_save"),
    path("dashboard/safety-plan/", views.safety_plan_view, name="safety_plan"),

    # Appointments
    path("appointments/book/", views.appointment_book, name="appointment_book"),
    path("appointments/available-slots/", views.get_available_slots, name="appointments_available_slots"),
    path("api/available-slots/", views.get_available_slots, name="get_available_slots"),

    # Subscriptions & Paywall
    path("subscribe/", views.subscribe_view, name="subscribe"),
    path("subscribe/bank-transfer/", views.bank_transfer_submit, name="bank_transfer_submit"),
    path("subscribe/test-activate/", views.instant_test_activate, name="instant_test_activate"),
]
