from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import (
    CoeusUser, OnboardingProfile, TherapistProfile,
    TherapistAvailability, SessionNote, Appointment, MoodEntry,
    Subscription, PaymentTransaction,
)


@admin.register(CoeusUser)
class CoeusUserAdmin(UserAdmin):
    model = CoeusUser
    list_display = ("email", "role", "is_active", "is_staff", "date_joined")
    list_filter = ("is_active", "is_staff", "role")
    search_fields = ("email",)
    ordering = ("-date_joined",)
    fieldsets = (
        (None, {"fields": ("email", "password")}),
        ("Role", {"fields": ("role",)}),
        ("Permissions", {"fields": ("is_active", "is_staff", "is_superuser", "groups", "user_permissions")}),
    )
    add_fieldsets = (
        (None, {"classes": ("wide",), "fields": ("email", "password1", "password2", "role")}),
    )


@admin.register(OnboardingProfile)
class OnboardingProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "display_name", "age", "risk_level", "safety_status", "created_at")
    list_filter = ("risk_level", "safety_status")
    search_fields = ("user__email", "display_name")


@admin.register(TherapistProfile)
class TherapistProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "credentials", "is_active", "created_at")
    list_filter = ("is_active",)
    search_fields = ("user__email",)


@admin.register(TherapistAvailability)
class TherapistAvailabilityAdmin(admin.ModelAdmin):
    list_display = ("therapist", "day_of_week", "start_time", "end_time", "is_active")
    list_filter = ("day_of_week", "is_active")
    search_fields = ("therapist__email",)


@admin.register(SessionNote)
class SessionNoteAdmin(admin.ModelAdmin):
    list_display = ("therapist", "patient", "created_at")
    list_filter = ("created_at",)
    search_fields = ("therapist__email", "patient__email")
    readonly_fields = ("created_at",)


@admin.register(Appointment)
class AppointmentAdmin(admin.ModelAdmin):
    list_display = ("user", "therapist", "support_type", "status", "appointment_date", "appointment_time", "created_at")
    list_filter = ("status", "support_type")
    search_fields = ("user__email",)


@admin.register(MoodEntry)
class MoodEntryAdmin(admin.ModelAdmin):
    list_display = ("user", "mood", "score", "date")
    list_filter = ("mood", "date")
    search_fields = ("user__email",)


@admin.register(Subscription)
class SubscriptionAdmin(admin.ModelAdmin):
    list_display = ("user", "plan", "status", "amount", "sessions_allocated", "sessions_remaining", "payment_method", "start_date", "end_date", "created_at")
    list_filter = ("status", "plan", "payment_method")
    search_fields = ("user__email", "reference", "sender_name")


@admin.register(PaymentTransaction)
class PaymentTransactionAdmin(admin.ModelAdmin):
    list_display = ("reference", "user", "amount", "currency", "channel", "status", "created_at")
    list_filter = ("status", "channel", "currency")
    search_fields = ("reference", "user__email")
