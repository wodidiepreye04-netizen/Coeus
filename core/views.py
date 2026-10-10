import json
import urllib.request
import uuid
from datetime import date, timedelta, time, datetime

from django.conf import settings
from django.contrib import messages
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout, get_user_model
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from django.views.decorators.http import require_POST
from django.http import JsonResponse

from .forms import (
    SignUpForm, SignInForm,
    OnboardingAboutForm, OnboardingCheckinForm,
    JournalForm, SafetyPlanForm,
    REASON_CHOICES,
)
from .models import (
    OnboardingProfile,
    MoodEntry, MOOD_SCORES, MOOD_EMOJIS, MOOD_LABELS,
    TherapyGoal, ReflectionTask,
    Appointment, JournalEntry, SafetyPlan,
    Subscription, PaymentTransaction,
    TherapistAvailability,
)

User = get_user_model()

_MOOD_OPTIONS = [("1", "😢"), ("2", "😟"), ("3", "😐"), ("4", "🙂"), ("5", "😊")]
_SAFETY_CHOICES = [
    ("safe", "Yes, I feel safe"),
    ("unsafe", "No, I don't feel safe"),
    ("unsure", "I'm not sure"),
]
_NEED_CHOICES = [
    ("listen", "Someone to listen"),
    ("coping", "Coping strategies"),
    ("understand", "To understand my feelings"),
    ("crisis", "Crisis help"),
    ("vent", "Just to vent"),
    ("unsure", "Not sure"),
]


# ─── Auth ──────────────────────────────────────────────────────────────────────

def landing(request):
    if request.user.is_authenticated:
        if request.user.is_therapist:
            return redirect("therapist_dashboard")
        return redirect("dashboard")
    return render(request, "core/landing.html")


def signup(request):
    if request.user.is_authenticated:
        if request.user.is_therapist:
            return redirect("therapist_dashboard")
        return redirect("dashboard")
    form = SignUpForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = User.objects.create_user(
            email=form.cleaned_data["email"],
            password=form.cleaned_data["password"],
        )
        login(request, user)
        return redirect("onboarding_welcome")
    return render(request, "core/signup.html", {"form": form})


def signin(request):
    if request.user.is_authenticated:
        if request.user.is_therapist:
            return redirect("therapist_dashboard")
        return redirect("dashboard")
    form = SignInForm(request.POST or None)
    error = None
    if request.method == "POST" and form.is_valid():
        user = authenticate(
            request,
            username=form.cleaned_data["email"].lower(),
            password=form.cleaned_data["password"],
        )
        if user is not None:
            login(request, user)
            default_next = "therapist_dashboard" if user.is_therapist else "/dashboard"
            return redirect(request.GET.get("next", default_next))
        else:
            error = "Invalid credentials. Please try again."
    return render(request, "core/signin.html", {"form": form, "error": error})


def signout(request):
    logout(request)
    return redirect("landing")


def privacy(request):
    return render(request, "core/privacy.html")


# ─── Onboarding ────────────────────────────────────────────────────────────────

@login_required
def onboarding_welcome(request):
    if request.user.onboarding_complete:
        return redirect("dashboard")
    if request.method == "POST":
        return redirect("onboarding_about")
    return render(request, "core/onboarding_welcome.html")


@login_required
def onboarding_about(request):
    if request.user.onboarding_complete:
        return redirect("dashboard")
    form = OnboardingAboutForm(request.POST or None)
    if request.method == "POST":
        if form.is_valid():
            request.session["onboarding_about"] = {
                "display_name": form.cleaned_data["display_name"],
                "age": form.cleaned_data["age"],
                "gender": form.cleaned_data.get("gender", ""),
                "country": form.cleaned_data["country"],
            }
            return redirect("onboarding_checkin")
        age_error = form.errors.get("age")
        if age_error and "under_18" in str(age_error):
            return render(request, "core/onboarding_age_block.html")
    return render(request, "core/onboarding_about.html", {"form": form})


@login_required
def onboarding_checkin(request):
    if request.user.onboarding_complete:
        return redirect("dashboard")
    if "onboarding_about" not in request.session:
        return redirect("onboarding_about")
    form = OnboardingCheckinForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        about = request.session["onboarding_about"]
        cd = form.cleaned_data
        safety = cd["safety_status"]
        need = cd["immediate_need"]
        mood = int(cd["mood_score"])
        is_high_risk = safety in ("unsafe", "unsure") or need == "crisis" or mood == 1
        OnboardingProfile.objects.create(
            user=request.user,
            display_name=about["display_name"],
            age=about["age"],
            gender=about.get("gender", ""),
            country=about["country"],
            mood_score=mood,
            has_seen_professional=cd["has_seen_professional"],
            current_treatment=cd.get("current_treatment", ""),
            reasons=cd["reasons"],
            safety_status=safety,
            immediate_need=need,
            risk_level="high" if is_high_risk else "normal",
            flagged_at=timezone.now() if is_high_risk else None,
        )
        request.user.onboarding_complete = True
        request.user.save(update_fields=["onboarding_complete"])
        del request.session["onboarding_about"]
        if is_high_risk:
            return redirect("onboarding_crisis")
        return redirect("dashboard")
    return render(request, "core/onboarding_checkin.html", {
        "form": form,
        "mood_options": _MOOD_OPTIONS,
        "reason_choices": REASON_CHOICES,
        "safety_choices": _SAFETY_CHOICES,
        "need_choices": _NEED_CHOICES,
    })


@login_required
def onboarding_crisis(request):
    return render(request, "core/onboarding_crisis.html")


# ─── Dashboard ─────────────────────────────────────────────────────────────────

def _get_week_start(d):
    """Return the Monday of the week containing date d."""
    return d - timedelta(days=d.weekday())


def _compute_mood_insight(entries):
    if not entries:
        return None
    scores = [e.score for e in entries]
    avg = sum(scores) / len(scores)
    low_days = sum(1 for s in scores if s <= 2)
    high_days = sum(1 for s in scores if s >= 4)
    if avg <= 2:
        return "You've had a really difficult week. Please consider booking a session — you don't have to carry this alone."
    if low_days >= 4:
        return f"You've had {low_days} tough days this week. Your grounding exercises are here whenever you need them."
    if high_days >= 5:
        return "You've been doing really well this week. Keep up your reflection practice."
    if avg <= 3:
        return "It's been a mixed week. Small steps count — your consistency here matters."
    return "You're holding steady. Keep checking in with yourself — consistency is progress."


def _seed_defaults(user, today):
    week_start = _get_week_start(today)

    # Weekly goals
    if not TherapyGoal.objects.filter(user=user, week_of=week_start).exists():
        defaults = [
            "Practice 5 minutes of deep breathing daily",
            "Write one thing you're grateful for each day",
            "Reach out to one person you trust this week",
        ]
        for text in defaults:
            TherapyGoal.objects.create(user=user, text=text, week_of=week_start, is_default=True)

    # Daily tasks
    if not ReflectionTask.objects.filter(user=user, date=today).exists():
        tasks = [
            ("I am worthy of rest and healing.", "affirmation"),
            ("What's one small thing you're grateful for today?", "reflection"),
            ("Take 3 slow deep breaths before you continue.", "exercise"),
        ]
        for text, task_type in tasks:
            ReflectionTask.objects.create(user=user, text=text, task_type=task_type, date=today)


@login_required
def dashboard(request):
    if not request.user.onboarding_complete:
        return redirect("onboarding_welcome")

    today = date.today()
    week_start = _get_week_start(today)
    _seed_defaults(request.user, today)

    # Mood
    today_mood = MoodEntry.objects.filter(user=request.user, date=today).first()
    mood_history_qs = MoodEntry.objects.filter(
        user=request.user,
        date__gte=today - timedelta(days=6),
    ).order_by("date")

    # Build 7-day chart data (fill gaps with None)
    mood_chart = []
    for i in range(6, -1, -1):
        d = today - timedelta(days=i)
        entry = next((e for e in mood_history_qs if e.date == d), None)
        mood_chart.append({
            "date": d,
            "day": d.strftime("%a"),
            "entry": entry,
            "height": f"{(entry.score / 5) * 100:.0f}%" if entry else "0%",
            "color": entry.bar_color if entry else "#1f2937",
        })

    mood_insight = _compute_mood_insight(list(mood_history_qs))

    # Goals & tasks
    goals = TherapyGoal.objects.filter(user=request.user, week_of=week_start)
    tasks = ReflectionTask.objects.filter(user=request.user, date=today)

    # Appointments — upcoming (pending + confirmed)
    upcoming_qs = Appointment.objects.filter(
        user=request.user,
        status__in=("pending", "confirmed"),
    ).order_by("appointment_date", "appointment_time")
    upcoming = list(upcoming_qs[:5])

    # Past appointments (completed + cancelled)
    past_appointments = Appointment.objects.filter(
        user=request.user,
        status__in=("completed", "cancelled"),
    ).order_by("-created_at")[:5]

    # Journal — decrypt all entries for historical browsing and reading
    all_journal_entries_qs = JournalEntry.objects.filter(user=request.user).order_by("-date", "-created_at")
    journal_history = []
    total_journal_words = 0
    for entry in all_journal_entries_qs:
        content = entry.get_content()
        words = len(content.split()) if content else 0
        total_journal_words += words
        journal_history.append({
            "id": entry.id,
            "date": entry.date,
            "content": content,
            "word_count": words,
            "created_at": entry.created_at,
            "updated_at": entry.updated_at,
        })

    today_entry_data = next((e for e in journal_history if e["date"] == today), None)
    journal_content = today_entry_data["content"] if today_entry_data else ""
    journal_entry = JournalEntry.objects.filter(user=request.user, date=today).first()
    journal_form = JournalForm(initial={"content": journal_content} if journal_content else {})

    # Safety plan
    safety_plan = SafetyPlan.objects.filter(user=request.user).first()
    safety_form = SafetyPlanForm(initial={
        "warning_signs": safety_plan.warning_signs if safety_plan else "",
        "coping_strategies": safety_plan.coping_strategies if safety_plan else "",
        "support_people": safety_plan.support_people if safety_plan else "",
        "reasons_to_live": safety_plan.reasons_to_live if safety_plan else "",
        "safe_environment": safety_plan.safe_environment if safety_plan else "",
    })

    # Profile
    try:
        profile = request.user.onboarding
    except OnboardingProfile.DoesNotExist:
        profile = None

    # Mood options for check-in
    mood_checkin_options = [
        {"value": k, "emoji": v, "label": MOOD_LABELS[k]}
        for k, v in MOOD_EMOJIS.items()
    ]

    # Subscription & session quota
    active_sub = request.user.active_subscription

    return render(request, "core/dashboard.html", {
        "profile": profile,
        "today": today,
        "today_mood": today_mood,
        "mood_chart": mood_chart,
        "mood_insight": mood_insight,
        "mood_checkin_options": mood_checkin_options,
        "goals": goals,
        "tasks": tasks,
        "upcoming": upcoming,
        "past_appointments": past_appointments,
        "journal_entry": journal_entry,
        "journal_content": journal_content,
        "journal_form": journal_form,
        "journal_history": journal_history,
        "total_journal_words": total_journal_words,
        "safety_plan": safety_plan,
        "safety_form": safety_form,
        "has_active_subscription": request.user.has_active_subscription,
        "active_subscription": active_sub,
        "sessions_remaining": request.user.sessions_remaining,
        "sessions_allocated": request.user.sessions_allocated,
    })


@login_required
@require_POST
def mood_checkin(request):
    mood = request.POST.get("mood")
    if mood and mood in MOOD_SCORES:
        MoodEntry.objects.update_or_create(
            user=request.user,
            date=date.today(),
            defaults={"mood": mood, "score": MOOD_SCORES[mood]},
        )
    return redirect("dashboard")


@login_required
@require_POST
def goal_toggle(request, goal_id):
    goal = get_object_or_404(TherapyGoal, id=goal_id, user=request.user)
    goal.completed = not goal.completed
    goal.save(update_fields=["completed"])
    return redirect("dashboard")


@login_required
@require_POST
def task_toggle(request, task_id):
    task = get_object_or_404(ReflectionTask, id=task_id, user=request.user)
    task.completed = not task.completed
    task.save(update_fields=["completed"])
    return redirect("dashboard")


@login_required
def journal_vault(request):
    """Dedicated personal journal vault: browse, read, search, and write private reflections."""
    today = date.today()

    if request.method == "POST":
        content = request.POST.get("content", "").strip()
        date_str = request.POST.get("date", "").strip()
        target_date = today
        if date_str:
            try:
                target_date = date.fromisoformat(date_str)
            except ValueError:
                target_date = today

        if content:
            entry, created = JournalEntry.objects.get_or_create(
                user=request.user,
                date=target_date,
            )
            entry.set_content(content)
            entry.save()
            messages.success(request, f"Reflection for {target_date.strftime('%B %d, %Y')} saved securely.")
        return redirect("journal_vault")

    # Fetch all decrypted entries
    all_entries_qs = JournalEntry.objects.filter(user=request.user).order_by("-date", "-created_at")
    journal_history = []
    total_words = 0
    for entry in all_entries_qs:
        content = entry.get_content()
        words = len(content.split()) if content else 0
        total_words += words
        journal_history.append({
            "id": entry.id,
            "date": entry.date,
            "content": content,
            "word_count": words,
            "created_at": entry.created_at,
            "updated_at": entry.updated_at,
        })

    today_entry_data = next((e for e in journal_history if e["date"] == today), None)
    today_content = today_entry_data["content"] if today_entry_data else ""

    return render(request, "core/journal_vault.html", {
        "today": today,
        "today_content": today_content,
        "today_entry": today_entry_data,
        "journal_history": journal_history,
        "total_entries": len(journal_history),
        "total_words": total_words,
    })


@login_required
@require_POST
def journal_save(request):
    content = request.POST.get("content", "").strip()
    date_str = request.POST.get("date", "").strip()
    target_date = date.today()
    if date_str:
        try:
            target_date = date.fromisoformat(date_str)
        except ValueError:
            target_date = date.today()

    if content:
        entry, created = JournalEntry.objects.get_or_create(
            user=request.user,
            date=target_date,
        )
        entry.set_content(content)
        entry.save()
        messages.success(request, f"Journal entry for {target_date.strftime('%B %d, %Y')} saved securely.")
    next_url = request.POST.get("next", "dashboard")
    return redirect(next_url)


@login_required
def safety_plan_view(request):
    plan = SafetyPlan.objects.filter(user=request.user).first()
    if request.method == "POST":
        form = SafetyPlanForm(request.POST)
        if form.is_valid():
            cd = form.cleaned_data
            SafetyPlan.objects.update_or_create(
                user=request.user,
                defaults={
                    "warning_signs": cd.get("warning_signs", ""),
                    "coping_strategies": cd.get("coping_strategies", ""),
                    "support_people": cd.get("support_people", ""),
                    "reasons_to_live": cd.get("reasons_to_live", ""),
                    "safe_environment": cd.get("safe_environment", ""),
                },
            )
        return redirect("dashboard")
    form = SafetyPlanForm(initial={
        "warning_signs": plan.warning_signs if plan else "",
        "coping_strategies": plan.coping_strategies if plan else "",
        "support_people": plan.support_people if plan else "",
        "reasons_to_live": plan.reasons_to_live if plan else "",
        "safe_environment": plan.safe_environment if plan else "",
    })
    return render(request, "core/safety_plan.html", {"form": form, "plan": plan})


# ─── Appointment Booking (Client Side) ─────────────────────────────────────────

@login_required
def appointment_book(request):
    """Real slot-based booking: choose therapist → date → available 1-hour slot."""
    # Paywall: Require active subscription before booking
    if not request.user.has_active_subscription:
        messages.warning(
            request,
            "An active subscription is required to book a therapy session. Please select a plan to continue."
        )
        return redirect("subscribe")

    # Check session quota
    active_sub = request.user.active_subscription
    if active_sub and active_sub.sessions_remaining <= 0:
        messages.warning(
            request,
            "You have used all your allocated therapy sessions. Please upgrade or renew your plan."
        )
        return redirect("subscribe")

    # Get all active therapists
    therapists = User.objects.filter(
        role__in=["therapist", "admin"],
        is_active=True,
    ).order_by("email")

    if request.method == "POST":
        therapist_id = request.POST.get("therapist")
        appt_date_str = request.POST.get("appointment_date")
        appt_time_str = request.POST.get("appointment_time")
        presenting_concern = request.POST.get("presenting_concern", "").strip()
        support_type = request.POST.get("support_type", "therapy")

        if not all([therapist_id, appt_date_str, appt_time_str, presenting_concern]):
            messages.error(request, "Please fill in all required fields.")
            return render(request, "core/appointment_book.html", {
                "therapists": therapists,
                "sessions_remaining": active_sub.sessions_remaining if active_sub else 0,
            })

        try:
            therapist_user = User.objects.get(id=therapist_id, role__in=["therapist", "admin"])
            appt_date = date.fromisoformat(appt_date_str)
            appt_time = time.fromisoformat(appt_time_str)
        except (User.DoesNotExist, ValueError):
            messages.error(request, "Invalid therapist or date/time selection.")
            return render(request, "core/appointment_book.html", {
                "therapists": therapists,
                "sessions_remaining": active_sub.sessions_remaining if active_sub else 0,
            })

        # Double-booking check
        existing = Appointment.objects.filter(
            therapist=therapist_user,
            appointment_date=appt_date,
            appointment_time=appt_time,
            status__in=("pending", "confirmed"),
        ).exists()

        if existing:
            messages.error(request, "This time slot is no longer available. Please choose another.")
            return render(request, "core/appointment_book.html", {
                "therapists": therapists,
                "sessions_remaining": active_sub.sessions_remaining if active_sub else 0,
            })

        # Create appointment and deduct session
        Appointment.objects.create(
            user=request.user,
            therapist=therapist_user,
            presenting_concern=presenting_concern,
            support_type=support_type,
            appointment_date=appt_date,
            appointment_time=appt_time,
            status="pending",
        )

        # Deduct 1 session
        if active_sub:
            active_sub.sessions_remaining = max(0, active_sub.sessions_remaining - 1)
            active_sub.save(update_fields=["sessions_remaining"])

        messages.success(request, "Your session has been booked! You'll receive a confirmation from your therapist.")
        return redirect("dashboard")

    return render(request, "core/appointment_book.html", {
        "therapists": therapists,
        "sessions_remaining": active_sub.sessions_remaining if active_sub else 0,
    })


@login_required
def get_available_slots(request):
    """AJAX endpoint: return available 1-hour slots for a therapist on a given date."""
    therapist_id = request.GET.get("therapist_id")
    date_str = request.GET.get("date")

    if not therapist_id or not date_str:
        return JsonResponse({"slots": []})

    try:
        therapist_user = User.objects.get(id=therapist_id, role__in=["therapist", "admin"])
        target_date = date.fromisoformat(date_str)
    except (User.DoesNotExist, ValueError):
        return JsonResponse({"slots": []})

    day_of_week = target_date.weekday()  # 0=Monday

    # Get therapist's availability for that day
    availability = TherapistAvailability.objects.filter(
        therapist=therapist_user,
        day_of_week=day_of_week,
        is_active=True,
    )

    if not availability.exists():
        return JsonResponse({"slots": []})

    # Generate 1-hour slots from availability windows
    all_slots = []
    for avail in availability:
        current = datetime.combine(target_date, avail.start_time)
        end = datetime.combine(target_date, avail.end_time)
        while current + timedelta(hours=1) <= end:
            all_slots.append(current.time())
            current += timedelta(hours=1)

    # Filter out already-booked slots
    booked_times = set(
        Appointment.objects.filter(
            therapist=therapist_user,
            appointment_date=target_date,
            status__in=("pending", "confirmed"),
        ).values_list("appointment_time", flat=True)
    )

    available_slots = [
        {"time": t.strftime("%H:%M"), "label": f"{t.strftime('%I:%M %p')} – {(datetime.combine(target_date, t) + timedelta(hours=1)).time().strftime('%I:%M %p')}"}
        for t in all_slots
        if t not in booked_times
    ]

    return JsonResponse({"slots": available_slots})


# ─── Subscription & Payment Views ──────────────────────────────────────────────

@login_required
def subscribe_view(request):
    """Subscription and pricing page with Paystack (Coming Soon), Bank Transfer, and Test modes."""
    plans = getattr(settings, "SUBSCRIPTION_PLANS", {})
    bank_details = getattr(settings, "PERSONAL_BANK_DETAILS", {})

    active_sub = request.user.active_subscription
    pending_sub = request.user.subscriptions.filter(status="pending").first()

    return render(request, "core/subscribe.html", {
        "plans": plans,
        "bank_details": bank_details,
        "active_sub": active_sub,
        "pending_sub": pending_sub,
        "has_active_sub": request.user.has_active_subscription,
    })


@login_required
@require_POST
def bank_transfer_submit(request):
    """Submit details for a direct bank transfer / personal account payment."""
    plan_id = request.POST.get("plan", "basic")
    sender_name = request.POST.get("sender_name", "").strip()
    sender_bank = request.POST.get("sender_bank", "").strip()
    notes = request.POST.get("notes", "").strip()

    if not sender_name:
        messages.error(request, "Please enter the sender account name used for the bank transfer.")
        return redirect("subscribe")

    plans = getattr(settings, "SUBSCRIPTION_PLANS", {})
    plan_info = plans.get(plan_id, plans.get("basic", {"price": 25000, "sessions": 4}))
    amount = plan_info["price"]
    sessions = plan_info.get("sessions", 4)
    ref = f"BT-{uuid.uuid4().hex[:10].upper()}"

    sub = Subscription.objects.create(
        user=request.user,
        plan=plan_id,
        status="pending",
        amount=amount,
        payment_method="bank_transfer",
        reference=ref,
        sender_name=sender_name,
        sender_bank=sender_bank,
        admin_notes=notes,
        sessions_allocated=sessions,
        sessions_remaining=0,  # Will be set on approval
    )
    PaymentTransaction.objects.create(
        user=request.user,
        subscription=sub,
        reference=ref,
        amount=amount,
        currency="NGN",
        channel="bank_transfer",
        status="pending",
    )
    messages.info(
        request,
        f"Thank you! Your transfer notice (Ref: {ref}) has been received and is pending confirmation. Your therapist will review and activate your plan."
    )
    return redirect("subscribe")


@login_required
@require_POST
def instant_test_activate(request):
    """1-Click instant test activation for development and testing."""
    plan_id = request.POST.get("plan", "basic")
    plans = getattr(settings, "SUBSCRIPTION_PLANS", {})
    plan_info = plans.get(plan_id, plans.get("basic", {"price": 25000, "sessions": 4, "name": "Basic", "duration_days": 30}))
    duration_days = plan_info.get("duration_days", 30)
    sessions = plan_info.get("sessions", 4)
    now = timezone.now()
    ref = f"TEST-{uuid.uuid4().hex[:8].upper()}"

    # Deactivate existing active
    request.user.subscriptions.filter(status="active").update(status="expired")

    sub = Subscription.objects.create(
        user=request.user,
        plan=plan_id,
        status="active",
        amount=plan_info["price"],
        payment_method="test",
        reference=ref,
        start_date=now,
        end_date=now + timedelta(days=duration_days),
        admin_notes="Activated via test mode",
        sessions_allocated=sessions,
        sessions_remaining=sessions,
    )
    PaymentTransaction.objects.create(
        user=request.user,
        subscription=sub,
        reference=ref,
        amount=plan_info["price"],
        currency="NGN",
        channel="test",
        status="success",
        verified_at=now,
    )
    messages.success(
        request,
        f"✅ Demo: Your {plan_info['name']} is now active with {sessions} therapy sessions! You can now book."
    )
    return redirect("appointment_book")
