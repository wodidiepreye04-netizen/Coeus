from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.db import models
from django.utils import timezone
from django.conf import settings
from datetime import date

import base64
import hashlib
from cryptography.fernet import Fernet


# ─── Fernet Encryption Helpers ─────────────────────────────────────────────────

def _get_fernet():
    """Derive a Fernet key from settings.SECRET_KEY."""
    key_bytes = hashlib.sha256(settings.SECRET_KEY.encode()).digest()
    fernet_key = base64.urlsafe_b64encode(key_bytes)
    return Fernet(fernet_key)


def encrypt_text(plaintext):
    """Encrypt a plaintext string, returning a base64-encoded token string."""
    if not plaintext:
        return ""
    f = _get_fernet()
    return f.encrypt(plaintext.encode("utf-8")).decode("utf-8")


def decrypt_text(token):
    """Decrypt a Fernet token string back to plaintext."""
    if not token:
        return ""
    f = _get_fernet()
    try:
        return f.decrypt(token.encode("utf-8")).decode("utf-8")
    except Exception:
        # If decryption fails (e.g. legacy plaintext data), return raw value
        return token


# ─── User Model ────────────────────────────────────────────────────────────────

class CoeusUserManager(BaseUserManager):
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError("Email is required")
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        return self.create_user(email, password, **extra_fields)


class CoeusUser(AbstractBaseUser, PermissionsMixin):
    ROLE_CHOICES = [
        ("user", "User"),
        ("therapist", "Therapist"),
        ("admin", "Admin"),
    ]

    email = models.EmailField(unique=True)
    role = models.CharField(max_length=10, choices=ROLE_CHOICES, default="user")
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    date_joined = models.DateTimeField(auto_now_add=True)
    onboarding_complete = models.BooleanField(default=False)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []

    objects = CoeusUserManager()

    @property
    def is_therapist(self):
        return self.role in ("therapist", "admin")

    @property
    def has_active_subscription(self):
        now = timezone.now()
        return self.subscriptions.filter(
            status="active"
        ).filter(
            models.Q(end_date__isnull=True) | models.Q(end_date__gte=now)
        ).exists()

    @property
    def active_subscription(self):
        now = timezone.now()
        return self.subscriptions.filter(
            status="active"
        ).filter(
            models.Q(end_date__isnull=True) | models.Q(end_date__gte=now)
        ).order_by("-created_at").first()

    @property
    def sessions_remaining(self):
        """Return sessions_remaining from the user's active subscription, or 0."""
        sub = self.active_subscription
        if sub:
            return sub.sessions_remaining
        return 0

    @property
    def sessions_allocated(self):
        """Return sessions_allocated from the user's active subscription, or 0."""
        sub = self.active_subscription
        if sub:
            return sub.sessions_allocated
        return 0

    def __str__(self):
        return self.email


class OnboardingProfile(models.Model):
    GENDER_CHOICES = [
        ("male", "Male"),
        ("female", "Female"),
        ("nonbinary", "Non-binary / Other"),
        ("prefer_not", "Prefer not to say"),
    ]
    MOOD_CHOICES = [
        (1, "Very Bad"),
        (2, "Struggling"),
        (3, "Okay"),
        (4, "Good"),
        (5, "Great"),
    ]
    TREATMENT_CHOICES = [
        ("yes", "Yes"),
        ("no", "No"),
        ("prefer_not", "Prefer not to say"),
    ]
    SAFETY_CHOICES = [
        ("safe", "Yes, I feel safe"),
        ("unsafe", "No, I don't feel safe"),
        ("unsure", "I'm not sure"),
    ]
    NEED_CHOICES = [
        ("listen", "Someone to listen"),
        ("coping", "Coping strategies"),
        ("understand", "To understand my feelings"),
        ("crisis", "Crisis help"),
        ("vent", "Just to vent"),
        ("unsure", "Not sure"),
    ]
    RISK_CHOICES = [
        ("normal", "Normal"),
        ("high", "High"),
    ]

    user = models.OneToOneField(
        CoeusUser, on_delete=models.CASCADE, related_name="onboarding"
    )
    display_name = models.CharField(max_length=100)
    age = models.PositiveIntegerField()
    gender = models.CharField(max_length=20, choices=GENDER_CHOICES, blank=True)
    country = models.CharField(max_length=100, default="Nigeria")
    mood_score = models.PositiveSmallIntegerField(choices=MOOD_CHOICES)
    has_seen_professional = models.BooleanField()
    current_treatment = models.CharField(
        max_length=20, choices=TREATMENT_CHOICES, blank=True
    )
    reasons = models.JSONField(default=list)
    safety_status = models.CharField(max_length=10, choices=SAFETY_CHOICES)
    immediate_need = models.CharField(max_length=20, choices=NEED_CHOICES)
    risk_level = models.CharField(max_length=10, choices=RISK_CHOICES, default="normal")
    flagged_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Onboarding: {self.user.email}"


# ─── Dashboard Models ──────────────────────────────────────────────────────────

MOOD_SCORES = {
    "happy": 5,
    "calm": 4,
    "neutral": 3,
    "confused": 3,
    "anxious": 2,
    "sad": 2,
    "angry": 2,
    "depressed": 1,
}

MOOD_EMOJIS = {
    "happy": "😊",
    "calm": "😌",
    "neutral": "😐",
    "confused": "😕",
    "anxious": "😟",
    "sad": "😢",
    "angry": "😠",
    "depressed": "😞",
}

MOOD_LABELS = {
    "happy": "Happy",
    "calm": "Calm",
    "neutral": "Neutral",
    "confused": "Confused",
    "anxious": "Anxious",
    "sad": "Sad",
    "angry": "Angry",
    "depressed": "Depressed",
}


class MoodEntry(models.Model):
    MOOD_CHOICES = [(k, v) for k, v in MOOD_LABELS.items()]

    user = models.ForeignKey(CoeusUser, on_delete=models.CASCADE, related_name="mood_entries")
    mood = models.CharField(max_length=20, choices=MOOD_CHOICES)
    score = models.PositiveSmallIntegerField()
    date = models.DateField(default=date.today)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("user", "date")
        ordering = ["-date"]

    def __str__(self):
        return f"{self.user.email} — {self.mood} on {self.date}"

    @property
    def emoji(self):
        return MOOD_EMOJIS.get(self.mood, "😐")

    @property
    def label(self):
        return MOOD_LABELS.get(self.mood, self.mood.capitalize())

    @property
    def bar_color(self):
        colors = {5: "#2dd4bf", 4: "#6ee7b7", 3: "#fbbf24", 2: "#f97316", 1: "#f87171"}
        return colors.get(self.score, "#6b7280")


class TherapyGoal(models.Model):
    user = models.ForeignKey(CoeusUser, on_delete=models.CASCADE, related_name="therapy_goals")
    text = models.CharField(max_length=200)
    completed = models.BooleanField(default=False)
    week_of = models.DateField()
    is_default = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]

    def __str__(self):
        return f"{self.user.email}: {self.text[:40]}"


class ReflectionTask(models.Model):
    TASK_TYPE_CHOICES = [
        ("affirmation", "Affirmation"),
        ("reflection", "Reflection"),
        ("exercise", "Exercise"),
    ]

    user = models.ForeignKey(CoeusUser, on_delete=models.CASCADE, related_name="reflection_tasks")
    text = models.CharField(max_length=200)
    task_type = models.CharField(max_length=20, choices=TASK_TYPE_CHOICES)
    completed = models.BooleanField(default=False)
    date = models.DateField(default=date.today)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]

    def __str__(self):
        return f"{self.user.email}: {self.text[:40]}"


class Appointment(models.Model):
    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("confirmed", "Confirmed"),
        ("cancelled", "Cancelled"),
        ("completed", "Completed"),
    ]
    SUPPORT_TYPE_CHOICES = [
        ("therapy", "Individual Therapy"),
        ("crisis", "Crisis Support"),
        ("checkin", "General Check-in"),
    ]

    user = models.ForeignKey(CoeusUser, on_delete=models.CASCADE, related_name="appointments")
    therapist = models.ForeignKey(
        CoeusUser, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="therapist_appointments",
        limit_choices_to={"role__in": ["therapist", "admin"]},
    )
    presenting_concern = models.TextField()
    support_type = models.CharField(max_length=20, choices=SUPPORT_TYPE_CHOICES)
    appointment_date = models.DateField(null=True, blank=True)
    appointment_time = models.TimeField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    meeting_link = models.URLField(max_length=500, blank=True)
    therapist_notes = models.TextField(blank=True)
    admin_notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.user.email} — {self.support_type} ({self.status})"

    @property
    def appointment_end_time(self):
        """Return end time (1 hour after start)."""
        if self.appointment_time:
            from datetime import datetime, timedelta
            dt = datetime.combine(date.today(), self.appointment_time)
            return (dt + timedelta(hours=1)).time()
        return None


class JournalEntry(models.Model):
    user = models.ForeignKey(CoeusUser, on_delete=models.CASCADE, related_name="journal_entries")
    content = models.TextField()  # Stored encrypted via Fernet
    date = models.DateField(default=date.today)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("user", "date")
        ordering = ["-date"]

    def __str__(self):
        return f"{self.user.email} journal — {self.date}"

    def set_content(self, plaintext):
        """Encrypt and store journal content."""
        self.content = encrypt_text(plaintext)

    def get_content(self):
        """Decrypt and return journal content."""
        return decrypt_text(self.content)

    @property
    def decrypted_content(self):
        """Property wrapper for template access."""
        return self.get_content()


class SafetyPlan(models.Model):
    user = models.OneToOneField(CoeusUser, on_delete=models.CASCADE, related_name="safety_plan")
    warning_signs = models.TextField(blank=True)
    coping_strategies = models.TextField(blank=True)
    support_people = models.TextField(blank=True)
    reasons_to_live = models.TextField(blank=True)
    safe_environment = models.TextField(blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Safety plan: {self.user.email}"


# ─── Therapist Models ──────────────────────────────────────────────────────────

class TherapistProfile(models.Model):
    user = models.OneToOneField(
        CoeusUser, on_delete=models.CASCADE, related_name="therapist_profile"
    )
    bio = models.TextField(blank=True)
    credentials = models.CharField(max_length=255, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Therapist: {self.user.email}"


class TherapistAvailability(models.Model):
    DAY_CHOICES = [
        (0, "Monday"),
        (1, "Tuesday"),
        (2, "Wednesday"),
        (3, "Thursday"),
        (4, "Friday"),
        (5, "Saturday"),
        (6, "Sunday"),
    ]

    therapist = models.ForeignKey(
        CoeusUser, on_delete=models.CASCADE, related_name="availability_slots",
        limit_choices_to={"role__in": ["therapist", "admin"]},
    )
    day_of_week = models.IntegerField(choices=DAY_CHOICES)
    start_time = models.TimeField()
    end_time = models.TimeField()
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["day_of_week", "start_time"]
        unique_together = ("therapist", "day_of_week", "start_time")

    def __str__(self):
        return f"{self.therapist.email} — {self.get_day_of_week_display()} {self.start_time}–{self.end_time}"


class SessionNote(models.Model):
    therapist = models.ForeignKey(
        CoeusUser,
        on_delete=models.CASCADE,
        related_name="authored_notes",
        limit_choices_to={"role__in": ["therapist", "admin"]},
    )
    patient = models.ForeignKey(
        CoeusUser,
        on_delete=models.CASCADE,
        related_name="session_notes",
    )
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Note by {self.therapist.email} on {self.patient.email} — {self.created_at:%Y-%m-%d}"


# ─── Subscription & Payment Models ─────────────────────────────────────────────

class Subscription(models.Model):
    PLAN_CHOICES = [
        ("basic", "Basic (₦25,000 / mo)"),
        ("pro", "Pro (₦45,000 / mo)"),
        ("max", "Max (₦65,000 / mo)"),
    ]
    STATUS_CHOICES = [
        ("active", "Active"),
        ("pending", "Pending Confirmation"),
        ("cancelled", "Cancelled"),
        ("expired", "Expired"),
    ]
    PAYMENT_METHOD_CHOICES = [
        ("paystack", "Paystack"),
        ("bank_transfer", "Bank Transfer / Personal Account"),
        ("test", "Test / Instant"),
    ]

    user = models.ForeignKey(CoeusUser, on_delete=models.CASCADE, related_name="subscriptions")
    plan = models.CharField(max_length=20, choices=PLAN_CHOICES, default="basic")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    amount = models.DecimalField(max_digits=10, decimal_places=2, default=25000.00)
    payment_method = models.CharField(max_length=30, choices=PAYMENT_METHOD_CHOICES, default="paystack")
    reference = models.CharField(max_length=100, unique=True)
    sender_name = models.CharField(max_length=150, blank=True)
    sender_bank = models.CharField(max_length=100, blank=True)
    sessions_allocated = models.PositiveIntegerField(default=4)
    sessions_remaining = models.PositiveIntegerField(default=4)
    start_date = models.DateTimeField(default=timezone.now)
    end_date = models.DateTimeField(null=True, blank=True)
    admin_notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.user.email} — {self.get_plan_display()} ({self.status})"

    @property
    def is_currently_active(self):
        if self.status != "active":
            return False
        if self.end_date and self.end_date < timezone.now():
            return False
        return True


# ─── Chat / Messaging Models ───────────────────────────────────────────────────

class ChatMessage(models.Model):
    sender = models.ForeignKey(
        CoeusUser, on_delete=models.CASCADE, related_name="sent_messages"
    )
    recipient = models.ForeignKey(
        CoeusUser, on_delete=models.CASCADE, related_name="received_messages"
    )
    content = models.TextField()
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]

    def __str__(self):
        return f"{self.sender.email} → {self.recipient.email} ({self.created_at:%H:%M})"


# ─── Assessment Models (PHQ-9, GAD-7) ─────────────────────────────────────────

PHQ9_QUESTIONS = [
    "Little interest or pleasure in doing things",
    "Feeling down, depressed, or hopeless",
    "Trouble falling or staying asleep, or sleeping too much",
    "Feeling tired or having little energy",
    "Poor appetite or overeating",
    "Feeling bad about yourself — or that you are a failure or have let yourself or your family down",
    "Trouble concentrating on things, such as reading or watching television",
    "Moving or speaking so slowly that other people could have noticed — or the opposite — being so fidgety or restless",
    "Thoughts that you would be better off dead, or of hurting yourself in some way",
]

GAD7_QUESTIONS = [
    "Feeling nervous, anxious, or on edge",
    "Not being able to stop or control worrying",
    "Worrying too much about different things",
    "Trouble relaxing",
    "Being so restless that it is hard to sit still",
    "Becoming easily annoyed or irritable",
    "Feeling afraid, as if something awful might happen",
]

ASSESSMENT_ANSWER_CHOICES = [
    (0, "Not at all"),
    (1, "Several days"),
    (2, "More than half the days"),
    (3, "Nearly every day"),
]


def compute_phq9_severity(score):
    if score <= 4:
        return "minimal"
    elif score <= 9:
        return "mild"
    elif score <= 14:
        return "moderate"
    elif score <= 19:
        return "moderately_severe"
    return "severe"


def compute_gad7_severity(score):
    if score <= 4:
        return "minimal"
    elif score <= 9:
        return "mild"
    elif score <= 14:
        return "moderate"
    return "severe"


class Assessment(models.Model):
    TYPE_CHOICES = [
        ("phq9", "PHQ-9 (Depression)"),
        ("gad7", "GAD-7 (Anxiety)"),
    ]
    SEVERITY_CHOICES = [
        ("minimal", "Minimal"),
        ("mild", "Mild"),
        ("moderate", "Moderate"),
        ("moderately_severe", "Moderately severe"),
        ("severe", "Severe"),
    ]

    user = models.ForeignKey(
        CoeusUser, on_delete=models.CASCADE, related_name="assessments"
    )
    assessment_type = models.CharField(max_length=10, choices=TYPE_CHOICES)
    responses = models.JSONField(default=list)
    total_score = models.PositiveIntegerField()
    severity = models.CharField(max_length=20, choices=SEVERITY_CHOICES)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.user.email} — {self.get_assessment_type_display()} ({self.severity}) on {self.created_at:%Y-%m-%d}"

    @property
    def max_score(self):
        return 27 if self.assessment_type == "phq9" else 21

    @property
    def percentage(self):
        return round((self.total_score / self.max_score) * 100)

    @property
    def severity_color(self):
        colors = {
            "minimal": "#10b981",
            "mild": "#6ee7b7",
            "moderate": "#fbbf24",
            "moderately_severe": "#f97316",
            "severe": "#ef4444",
        }
        return colors.get(self.severity, "#6b7280")


# ─── Session Rating ────────────────────────────────────────────────────────────

class SessionRating(models.Model):
    user = models.ForeignKey(
        CoeusUser, on_delete=models.CASCADE, related_name="given_ratings"
    )
    therapist = models.ForeignKey(
        CoeusUser, on_delete=models.CASCADE, related_name="received_ratings"
    )
    appointment = models.OneToOneField(
        Appointment, on_delete=models.CASCADE, related_name="rating"
    )
    rating = models.PositiveSmallIntegerField()  # 1–5
    comment = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.user.email} rated {self.therapist.email}: {self.rating}/5"

    @property
    def stars_display(self):
        return "★" * self.rating + "☆" * (5 - self.rating)


# ─── Notifications ─────────────────────────────────────────────────────────────

class Notification(models.Model):
    TYPE_CHOICES = [
        ("appointment", "Appointment"),
        ("message", "New Message"),
        ("assessment", "Assessment"),
        ("subscription", "Subscription"),
        ("rating", "Rating"),
        ("system", "System"),
    ]

    user = models.ForeignKey(
        CoeusUser, on_delete=models.CASCADE, related_name="notifications"
    )
    notification_type = models.CharField(max_length=20, choices=TYPE_CHOICES)
    title = models.CharField(max_length=200)
    message = models.TextField()
    link = models.CharField(max_length=500, blank=True)
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"[{self.notification_type}] {self.title} → {self.user.email}"


def create_notification(user, notification_type, title, message, link=""):
    """Helper to create a notification and optionally send an email."""
    notif = Notification.objects.create(
        user=user,
        notification_type=notification_type,
        title=title,
        message=message,
        link=link,
    )
    # Attempt email notification (fails gracefully if SMTP not configured)
    try:
        from django.core.mail import send_mail
        send_mail(
            subject=f"COEUS — {title}",
            message=message,
            from_email=None,  # Uses DEFAULT_FROM_EMAIL
            recipient_list=[user.email],
            fail_silently=True,
        )
    except Exception:
        pass
    return notif


# ─── Subscription & Payment Models ─────────────────────────────────────────────

class PaymentTransaction(models.Model):
    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("success", "Success"),
        ("failed", "Failed"),
    ]

    user = models.ForeignKey(CoeusUser, on_delete=models.CASCADE, related_name="payments")
    subscription = models.ForeignKey(
        Subscription,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="transactions",
    )
    reference = models.CharField(max_length=100, unique=True)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=10, default="NGN")
    channel = models.CharField(max_length=50, default="paystack")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    verified_at = models.DateTimeField(null=True, blank=True)
    raw_response = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Payment {self.reference} — {self.amount} {self.currency} ({self.status})"
