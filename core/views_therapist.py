from datetime import time, timedelta

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, get_user_model
from django.views.decorators.http import require_POST
from django.contrib import messages
from django.conf import settings
from django.utils import timezone

from .decorators import therapist_required
from .forms import SignInForm
from .models import (
    OnboardingProfile,
    MoodEntry,
    TherapyGoal,
    Appointment,
    SessionNote,
    TherapistProfile,
    TherapistAvailability,
    Subscription,
    PaymentTransaction,
    MOOD_EMOJIS,
    MOOD_LABELS,
)

User = get_user_model()

DAY_NAMES = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

# Default working hours to seed for new therapists
DEFAULT_HOURS = [
    # Mon-Fri, 9AM-5PM
    (0, time(9, 0), time(17, 0)),
    (1, time(9, 0), time(17, 0)),
    (2, time(9, 0), time(17, 0)),
    (3, time(9, 0), time(17, 0)),
    (4, time(9, 0), time(17, 0)),
]


def _ensure_default_availability(therapist_user):
    """Seed default Mon-Fri 9-5 slots if therapist has none yet."""
    if not TherapistAvailability.objects.filter(therapist=therapist_user).exists():
        for day, start, end in DEFAULT_HOURS:
            TherapistAvailability.objects.create(
                therapist=therapist_user,
                day_of_week=day,
                start_time=start,
                end_time=end,
                is_active=True,
            )


# ─── Auth ──────────────────────────────────────────────────────────────────────

def therapist_login(request):
    """Separate login page for therapists."""
    if request.user.is_authenticated and request.user.is_therapist:
        return redirect("therapist_dashboard")

    form = SignInForm(request.POST or None)
    error = None

    if request.method == "POST" and form.is_valid():
        user = authenticate(
            request,
            username=form.cleaned_data["email"].lower(),
            password=form.cleaned_data["password"],
        )
        if user is not None and user.is_therapist:
            login(request, user)
            return redirect("therapist_dashboard")
        elif user is not None:
            error = "This account does not have therapist access."
        else:
            error = "Invalid credentials. Please try again."

    return render(request, "core/therapist/login.html", {"form": form, "error": error})


# ─── Dashboard (Triage) ───────────────────────────────────────────────────────

@therapist_required
def therapist_dashboard(request):
    """Main triage dashboard — flagged patients + today's appointments + availability."""
    _ensure_default_availability(request.user)

    # High-risk / flagged patients
    flagged_profiles = (
        OnboardingProfile.objects.filter(risk_level="high")
        .select_related("user")
        .order_by("-flagged_at")[:20]
    )

    # Upcoming appointments (pending + confirmed)
    upcoming_appointments = (
        Appointment.objects.filter(status__in=("pending", "confirmed"))
        .select_related("user", "therapist")
        .order_by("appointment_date", "appointment_time")[:20]
    )

    # Pending subscriptions (e.g. Bank transfers awaiting review)
    pending_subscriptions = (
        Subscription.objects.filter(status="pending")
        .select_related("user")
        .order_by("-created_at")[:10]
    )

    # Therapist's availability
    availability = (
        TherapistAvailability.objects.filter(therapist=request.user)
        .order_by("day_of_week", "start_time")
    )

    # Quick stats
    total_patients = User.objects.filter(role="user", onboarding_complete=True).count()
    pending_count = Appointment.objects.filter(status="pending").count()
    flagged_count = OnboardingProfile.objects.filter(risk_level="high").count()
    active_sub_count = Subscription.objects.filter(status="active").count()
    pending_sub_count = pending_subscriptions.count()

    # Build availability display grouped by day
    avail_by_day = {}
    for slot in availability:
        day_name = DAY_NAMES[slot.day_of_week]
        avail_by_day.setdefault(day_name, []).append(slot)

    plans = getattr(settings, "SUBSCRIPTION_PLANS", {})

    return render(request, "core/therapist/dashboard.html", {
        "active_page": "dashboard",
        "flagged_profiles": flagged_profiles,
        "upcoming_appointments": upcoming_appointments,
        "pending_subscriptions": pending_subscriptions,
        "total_patients": total_patients,
        "pending_count": pending_count,
        "flagged_count": flagged_count,
        "active_sub_count": active_sub_count,
        "pending_sub_count": pending_sub_count,
        "availability": availability,
        "avail_by_day": avail_by_day,
        "plans": plans,
    })


# ─── Availability Management ──────────────────────────────────────────────────

@therapist_required
@require_POST
def therapist_availability_toggle(request, slot_id):
    """Toggle a single availability slot on/off."""
    slot = get_object_or_404(TherapistAvailability, id=slot_id, therapist=request.user)
    slot.is_active = not slot.is_active
    slot.save(update_fields=["is_active"])
    return redirect("therapist_dashboard")


@therapist_required
@require_POST
def therapist_availability_add(request):
    """Add a new availability slot."""
    day = request.POST.get("day_of_week")
    start = request.POST.get("start_time")
    end = request.POST.get("end_time")

    if day is not None and start and end:
        try:
            day_int = int(day)
            start_time = time.fromisoformat(start)
            end_time = time.fromisoformat(end)
            if end_time > start_time:
                TherapistAvailability.objects.get_or_create(
                    therapist=request.user,
                    day_of_week=day_int,
                    start_time=start_time,
                    defaults={"end_time": end_time, "is_active": True},
                )
        except (ValueError, TypeError):
            pass

    return redirect("therapist_dashboard")


@therapist_required
@require_POST
def therapist_availability_delete(request, slot_id):
    """Delete an availability slot."""
    slot = get_object_or_404(TherapistAvailability, id=slot_id, therapist=request.user)
    slot.delete()
    return redirect("therapist_dashboard")


# ─── Patient Directory ─────────────────────────────────────────────────────────

@therapist_required
def therapist_patients(request):
    """List all patients who have completed onboarding."""
    q = request.GET.get("q", "").strip()

    patients = (
        User.objects.filter(role="user", onboarding_complete=True)
        .select_related("onboarding")
        .order_by("-date_joined")
    )

    if q:
        patients = patients.filter(email__icontains=q) | patients.filter(
            onboarding__display_name__icontains=q
        )

    return render(request, "core/therapist/patients.html", {
        "active_page": "patients",
        "patients": patients,
        "q": q,
    })


# ─── Patient Detail ────────────────────────────────────────────────────────────

@therapist_required
def therapist_patient_detail(request, patient_id):
    """Clinical view of a single patient. NO journal access — privacy enforced."""
    patient = get_object_or_404(User, id=patient_id, role="user")

    # Onboarding / intake data
    try:
        profile = patient.onboarding
    except OnboardingProfile.DoesNotExist:
        profile = None

    # Mood history (last 14 days)
    mood_history = MoodEntry.objects.filter(user=patient).order_by("-date")[:14]

    # Therapy goals (current)
    goals = TherapyGoal.objects.filter(user=patient).order_by("-week_of", "created_at")[:10]

    # Appointments with this patient
    appointments = Appointment.objects.filter(user=patient).order_by("-created_at")[:10]

    # Session notes (by any therapist)
    notes = SessionNote.objects.filter(patient=patient).order_by("-created_at")

    # Handle new note submission
    note_error = None
    if request.method == "POST":
        content = request.POST.get("note_content", "").strip()
        if content:
            SessionNote.objects.create(
                therapist=request.user,
                patient=patient,
                content=content,
            )
            return redirect("therapist_patient_detail", patient_id=patient.id)
        else:
            note_error = "Note content cannot be empty."

    # Mood emoji helper for template
    mood_display = []
    for entry in mood_history:
        mood_display.append({
            "date": entry.date,
            "mood": entry.mood,
            "label": MOOD_LABELS.get(entry.mood, entry.mood),
            "emoji": MOOD_EMOJIS.get(entry.mood, "😐"),
            "score": entry.score,
        })

    return render(request, "core/therapist/patient_detail.html", {
        "active_page": "patients",
        "patient": patient,
        "profile": profile,
        "mood_display": mood_display,
        "goals": goals,
        "appointments": appointments,
        "notes": notes,
        "note_error": note_error,
        "active_subscription": patient.active_subscription,
        "has_active_subscription": patient.has_active_subscription,
        "sessions_remaining": patient.sessions_remaining,
        "sessions_allocated": patient.sessions_allocated,
    })


# ─── Appointment Management ────────────────────────────────────────────────────

@therapist_required
@require_POST
def therapist_appointment_action(request, appointment_id):
    """Confirm (with meeting link), decline/cancel (refund session), or mark completed."""
    appt = get_object_or_404(Appointment, id=appointment_id)
    action = request.POST.get("action")

    if action == "confirm":
        appt.status = "confirmed"
        appt.meeting_link = request.POST.get("meeting_link", "").strip()
        appt.save(update_fields=["status", "meeting_link"])
        messages.success(request, f"Appointment confirmed for {appt.user.email}.")

    elif action in ("cancel", "decline"):
        appt.status = "cancelled"
        appt.admin_notes = request.POST.get("admin_notes", "").strip()
        appt.save(update_fields=["status", "admin_notes"])

        # Refund 1 session to the client
        active_sub = appt.user.active_subscription
        if active_sub:
            active_sub.sessions_remaining = min(
                active_sub.sessions_allocated,
                active_sub.sessions_remaining + 1
            )
            active_sub.save(update_fields=["sessions_remaining"])
        messages.info(request, f"Appointment cancelled. 1 session refunded to {appt.user.email}.")

    elif action == "completed":
        appt.status = "completed"
        therapist_notes = request.POST.get("therapist_notes", "").strip()
        if therapist_notes:
            appt.therapist_notes = therapist_notes
        appt.save(update_fields=["status", "therapist_notes"])
        messages.success(request, f"Session with {appt.user.email} marked as completed.")

    next_url = request.POST.get("next", "therapist_dashboard")
    return redirect(next_url)


# ─── Subscription Management ───────────────────────────────────────────────────

@therapist_required
@require_POST
def therapist_subscription_action(request, subscription_id):
    """Approve or decline a pending bank transfer / subscription.
    On approval, therapist can verify/select the plan which sets sessions_allocated/remaining.
    """
    sub = get_object_or_404(Subscription, id=subscription_id)
    action = request.POST.get("action")

    if action in ("approve", "confirm"):
        # Allow therapist to verify the plan
        confirmed_plan = request.POST.get("confirmed_plan", sub.plan)
        plans = getattr(settings, "SUBSCRIPTION_PLANS", {})
        plan_info = plans.get(confirmed_plan, plans.get("basic", {"duration_days": 30, "sessions": 4, "price": 25000}))

        now = timezone.now()

        # Deactivate any prior active subs
        sub.user.subscriptions.filter(status="active").update(status="expired")

        sub.plan = confirmed_plan
        sub.status = "active"
        sub.start_date = now
        sub.end_date = now + timedelta(days=plan_info.get("duration_days", 30))
        sub.sessions_allocated = plan_info.get("sessions", 0)
        sub.sessions_remaining = plan_info.get("sessions", 0)
        sub.amount = plan_info.get("price", sub.amount)
        note = request.POST.get("admin_notes", "").strip()
        sub.admin_notes = note or f"Approved by {request.user.email} on {now.strftime('%Y-%m-%d %H:%M')}"
        sub.save()
        sub.transactions.filter(status="pending").update(status="success", verified_at=now)
        messages.success(
            request,
            f"Subscription activated for {sub.user.email}: {plan_info.get('name', confirmed_plan)} with {sub.sessions_allocated} sessions."
        )

    elif action in ("reject", "cancel", "decline"):
        sub.status = "cancelled"
        note = request.POST.get("admin_notes", "").strip()
        sub.admin_notes = note or f"Rejected by {request.user.email}"
        sub.save()
        sub.transactions.filter(status="pending").update(status="failed")
        messages.info(request, f"Subscription for {sub.user.email} has been declined.")

    next_url = request.POST.get("next", "therapist_dashboard")
    return redirect(next_url)
