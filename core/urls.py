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

    # Real-Time Chat & Video Calls
    path("chat/<int:therapist_id>/", views.chat_room, name="chat_room"),
    path("chat/<int:therapist_id>/send/", views.chat_send, name="chat_send"),
    path("chat/<int:therapist_id>/poll/", views.chat_poll, name="chat_poll"),

    # Assessments (PHQ-9 & GAD-7)
    path("assessments/", views.assessments_home, name="assessments"),
    path("assessments/<str:assessment_type>/", views.take_assessment, name="take_assessment"),

    # Notifications
    path("notifications/", views.notifications_view, name="notifications"),
    path("notifications/<int:notification_id>/read/", views.notification_read, name="notification_read"),
    path("notifications/mark-all-read/", views.notification_mark_all_read, name="notification_mark_all_read"),
    path("api/notifications/count/", views.notification_count, name="notification_count"),

    # Ratings
    path("appointments/<int:appointment_id>/rate/", views.rate_session, name="rate_session"),
]
