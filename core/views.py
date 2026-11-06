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
    ChatMessage, Assessment, SessionRating, Notification,
    PHQ9_QUESTIONS, GAD7_QUESTIONS, ASSESSMENT_ANSWER_CHOICES,
    compute_phq9_severity, compute_gad7_severity,
    create_notification,
)

User = get_user_model()

# ─── Affirmation Pool ──────────────────────────────────────────────────────────
AFFIRMATIONS = [
    "I am worthy of rest and healing.",
    "I deserve to take up space in this world.",
    "My feelings are valid, even the uncomfortable ones.",
    "I am more than my worst day.",
    "Healing is not linear, and that's okay.",
    "I choose to be gentle with myself today.",
    "I am allowed to set boundaries without guilt.",
    "My mental health matters just as much as my physical health.",
    "I am doing the best I can with what I have right now.",
    "Every small step forward is still progress.",
    "I am not defined by my struggles.",
    "It's okay to ask for help. Strength comes in many forms.",
    "I release what I cannot control.",
    "I am enough, exactly as I am.",
    "Today, I choose peace over perfection.",
    "I trust myself to handle whatever comes my way.",
    "My story isn't over yet — there are better chapters ahead.",
    "I am worthy of love and connection.",
    "I give myself permission to feel without judgment.",
    "I am resilient — I have survived 100% of my hardest days.",
    "I don't have to have it all figured out today.",
    "My value is not determined by my productivity.",
    "I am allowed to take things one moment at a time.",
    "I honor my need for rest without shame.",
    "The world is better because I am in it.",
    "I am capable of creating positive change in my life.",
    "I choose to focus on what I can control.",
    "My vulnerability is a form of courage.",
    "I deserve compassion — especially from myself.",
    "I am growing, even when I can't see it.",
    "I release the need to be perfect.",
    "Today is a new opportunity to be kind to myself.",
    "I am worthy of good things happening to me.",
    "My past does not dictate my future.",
    "I am proud of myself for showing up today.",
    "I trust the timing of my life.",
    "I am learning to let go of things that no longer serve me.",
    "Every breath I take is a chance to begin again.",
    "I am stronger than I think I am.",
    "I choose hope, even when it feels hard.",
    "I am surrounded by more support than I realize.",
    "My journey is unique, and I don't need to compare it to anyone else's.",
    "I have the courage to face today with an open heart.",
    "I am allowed to change my mind and change my path.",
    "Asking for help is an act of strength, not weakness.",
    "I deserve moments of joy, peace, and laughter.",
    "I am worthy of the same kindness I give to others.",
    "I am not alone in this — someone cares about me.",
    "Today, I choose to believe in my own potential.",
    "I am healing at my own pace, and that is perfectly fine.",
]

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

    # Affirmations for rotating display
    import json as _json
    affirmations_json = _json.dumps(AFFIRMATIONS)

    # Unread notifications count
    unread_notif_count = Notification.objects.filter(user=request.user, is_read=False).count()

    # Unread messages count
    unread_msg_count = ChatMessage.objects.filter(recipient=request.user, is_read=False).count()

    # Completed appointments without ratings (prompt user to rate)
    unrated_appointments = Appointment.objects.filter(
        user=request.user,
        status="completed",
    ).exclude(rating__isnull=False).order_by("-created_at")[:3]

    # Latest assessment scores
    latest_phq9 = Assessment.objects.filter(user=request.user, assessment_type="phq9").first()
    latest_gad7 = Assessment.objects.filter(user=request.user, assessment_type="gad7").first()

    # Chat: find the therapist this client talks to (from latest appointment)
    chat_therapist = None
    latest_appt = Appointment.objects.filter(
        user=request.user,
        therapist__isnull=False,
        status__in=("pending", "confirmed", "completed"),
    ).order_by("-created_at").first()
    if latest_appt and latest_appt.therapist:
        chat_therapist = latest_appt.therapist

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
        "affirmations_json": affirmations_json,
        "unread_notif_count": unread_notif_count,
        "unread_msg_count": unread_msg_count,
        "unrated_appointments": unrated_appointments,
        "latest_phq9": latest_phq9,
        "latest_gad7": latest_gad7,
        "chat_therapist": chat_therapist,
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


# ─── Chat / Messaging (Client Side) ────────────────────────────────────────────

@login_required
def chat_room(request, therapist_id):
    """Client chat room with their therapist."""
    therapist = get_object_or_404(User, id=therapist_id, role__in=["therapist", "admin"])

    # Verify the client has at least one appointment with this therapist
    has_relationship = Appointment.objects.filter(
        user=request.user,
        therapist=therapist,
    ).exists()
    if not has_relationship:
        messages.error(request, "You can only message therapists you've booked sessions with.")
        return redirect("dashboard")

    # Mark incoming messages as read
    ChatMessage.objects.filter(
        sender=therapist, recipient=request.user, is_read=False
    ).update(is_read=True)

    # Get conversation history
    from django.db.models import Q
    chat_messages = ChatMessage.objects.filter(
        Q(sender=request.user, recipient=therapist) |
        Q(sender=therapist, recipient=request.user)
    ).order_by("created_at")

    # Generate Jitsi room name for video calls
    room_ids = sorted([request.user.id, therapist.id])
    jitsi_room = f"coeus-session-{room_ids[0]}-{room_ids[1]}"

    # Get therapist display info
    try:
        therapist_name = therapist.onboarding.display_name
    except Exception:
        therapist_name = therapist.email

    try:
        profile = request.user.onboarding
    except Exception:
        profile = None

    return render(request, "core/chat.html", {
        "other_user": therapist,
        "other_name": therapist_name,
        "messages_list": chat_messages,
        "jitsi_room": jitsi_room,
        "profile": profile,
    })


@login_required
@require_POST
def chat_send(request, therapist_id):
    """AJAX: send a message to therapist."""
    therapist = get_object_or_404(User, id=therapist_id, role__in=["therapist", "admin"])
    content = request.POST.get("content", "").strip()
    if content:
        ChatMessage.objects.create(
            sender=request.user,
            recipient=therapist,
            content=content,
        )
        # Create notification for therapist
        try:
            display_name = request.user.onboarding.display_name
        except Exception:
            display_name = request.user.email
        create_notification(
            user=therapist,
            notification_type="message",
            title=f"New message from {display_name}",
            message=content[:100],
            link=f"/therapist/chat/{request.user.id}/",
        )

    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return JsonResponse({"status": "ok"})
    return redirect("chat_room", therapist_id=therapist_id)


@login_required
def chat_poll(request, therapist_id):
    """AJAX: poll for new messages from therapist."""
    therapist = get_object_or_404(User, id=therapist_id, role__in=["therapist", "admin"])
    after = request.GET.get("after", "")

    from django.db.models import Q
    qs = ChatMessage.objects.filter(
        Q(sender=request.user, recipient=therapist) |
        Q(sender=therapist, recipient=request.user)
    )

    if after:
        try:
            after_dt = timezone.datetime.fromisoformat(after)
            qs = qs.filter(created_at__gt=after_dt)
        except (ValueError, TypeError):
            pass

    # Mark new incoming as read
    qs.filter(sender=therapist, recipient=request.user, is_read=False).update(is_read=True)

    new_messages = []
    for msg in qs.order_by("created_at"):
        new_messages.append({
            "id": msg.id,
            "sender_id": msg.sender_id,
            "content": msg.content,
            "is_mine": msg.sender_id == request.user.id,
            "created_at": msg.created_at.isoformat(),
            "time": msg.created_at.strftime("%I:%M %p"),
        })

    return JsonResponse({"messages": new_messages})


# ─── Assessments (PHQ-9, GAD-7) ────────────────────────────────────────────────

@login_required
def assessments_home(request):
    """Assessment hub: view history, start new assessment."""
    phq9_history = Assessment.objects.filter(user=request.user, assessment_type="phq9")[:10]
    gad7_history = Assessment.objects.filter(user=request.user, assessment_type="gad7")[:10]

    try:
        profile = request.user.onboarding
    except Exception:
        profile = None

    return render(request, "core/assessments.html", {
        "phq9_history": phq9_history,
        "gad7_history": gad7_history,
        "profile": profile,
    })


@login_required
def take_assessment(request, assessment_type):
    """Take a PHQ-9 or GAD-7 assessment."""
    if assessment_type not in ("phq9", "gad7"):
        messages.error(request, "Invalid assessment type.")
        return redirect("assessments")

    questions = PHQ9_QUESTIONS if assessment_type == "phq9" else GAD7_QUESTIONS
    type_display = "PHQ-9 (Depression)" if assessment_type == "phq9" else "GAD-7 (Anxiety)"
    answer_choices = ASSESSMENT_ANSWER_CHOICES

    if request.method == "POST":
        responses = []
        total = 0
        for i in range(len(questions)):
            val = request.POST.get(f"q{i}", "0")
            try:
                score = int(val)
            except ValueError:
                score = 0
            score = max(0, min(3, score))
            responses.append(score)
            total += score

        if assessment_type == "phq9":
            severity = compute_phq9_severity(total)
        else:
            severity = compute_gad7_severity(total)

        assessment = Assessment.objects.create(
            user=request.user,
            assessment_type=assessment_type,
            responses=responses,
            total_score=total,
            severity=severity,
        )

        # Create notification
        create_notification(
            user=request.user,
            notification_type="assessment",
            title=f"{type_display} completed",
            message=f"Your score: {total} — {assessment.get_severity_display()}. View your results for more details.",
            link="/assessments/",
        )

        # Notify therapist if score is concerning
        if severity in ("moderate", "moderately_severe", "severe"):
            latest_appt = Appointment.objects.filter(
                user=request.user,
                therapist__isnull=False,
            ).order_by("-created_at").first()
            if latest_appt and latest_appt.therapist:
                try:
                    display_name = request.user.onboarding.display_name
                except Exception:
                    display_name = request.user.email
                create_notification(
                    user=latest_appt.therapist,
                    notification_type="assessment",
                    title=f"⚠ {display_name} scored {severity} on {type_display}",
                    message=f"Score: {total}. This may require follow-up.",
                    link=f"/therapist/patient/{request.user.id}/",
                )

        messages.success(
            request,
            f"Assessment complete. Your {type_display} score: {total} ({assessment.get_severity_display()})."
        )
        return redirect("assessments")

    try:
        profile = request.user.onboarding
    except Exception:
        profile = None

    return render(request, "core/take_assessment.html", {
        "assessment_type": assessment_type,
        "type_display": type_display,
        "questions": questions,
        "answer_choices": answer_choices,
        "profile": profile,
    })


# ─── Notifications ─────────────────────────────────────────────────────────────

@login_required
def notifications_view(request):
    """View all notifications."""
    notifs = Notification.objects.filter(user=request.user)[:50]

    try:
        profile = request.user.onboarding
    except Exception:
        profile = None

    return render(request, "core/notifications.html", {
        "notifications": notifs,
        "profile": profile,
    })


@login_required
@require_POST
def notification_read(request, notification_id):
    """Mark a notification as read."""
    notif = get_object_or_404(Notification, id=notification_id, user=request.user)
    notif.is_read = True
    notif.save(update_fields=["is_read"])
    if notif.link:
        return redirect(notif.link)
    return redirect("notifications")


@login_required
def notification_mark_all_read(request):
    """Mark all notifications as read."""
    Notification.objects.filter(user=request.user, is_read=False).update(is_read=True)
    return redirect("notifications")


@login_required
def notification_count(request):
    """AJAX endpoint: return unread notification count."""
    count = Notification.objects.filter(user=request.user, is_read=False).count()
    msg_count = ChatMessage.objects.filter(recipient=request.user, is_read=False).count()
    return JsonResponse({"unread": count, "messages": msg_count})


# ─── Session Rating ────────────────────────────────────────────────────────────

@login_required
def rate_session(request, appointment_id):
    """Rate a completed therapy session."""
    appt = get_object_or_404(
        Appointment, id=appointment_id, user=request.user, status="completed"
    )

    # Check if already rated
    if hasattr(appt, "rating"):
        messages.info(request, "You've already rated this session.")
        return redirect("dashboard")

    if request.method == "POST":
        rating_val = request.POST.get("rating", "5")
        comment = request.POST.get("comment", "").strip()
        try:
            rating_int = int(rating_val)
            rating_int = max(1, min(5, rating_int))
        except ValueError:
            rating_int = 5

        SessionRating.objects.create(
            user=request.user,
            therapist=appt.therapist,
            appointment=appt,
            rating=rating_int,
            comment=comment,
        )

        # Notify therapist
        if appt.therapist:
            try:
                display_name = request.user.onboarding.display_name
            except Exception:
                display_name = request.user.email
            create_notification(
                user=appt.therapist,
                notification_type="rating",
                title=f"{display_name} rated your session {'★' * rating_int}",
                message=comment[:100] if comment else "No additional comments.",
                link=f"/therapist/patient/{request.user.id}/",
            )

        messages.success(request, "Thank you for your feedback!")
        return redirect("dashboard")

    try:
        profile = request.user.onboarding
    except Exception:
        profile = None

    return render(request, "core/rate_session.html", {
        "appointment": appt,
        "profile": profile,
    })
