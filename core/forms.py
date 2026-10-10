from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password

User = get_user_model()

COUNTRY_CHOICES = [
    ("Nigeria", "Nigeria"),
    ("Ghana", "Ghana"),
    ("Kenya", "Kenya"),
    ("South Africa", "South Africa"),
    ("United Kingdom", "United Kingdom"),
    ("United States", "United States"),
    ("Canada", "Canada"),
    ("Other", "Other"),
]

REASON_CHOICES = [
    ("work_school", "Work or school stress"),
    ("relationships", "Relationship issues"),
    ("family", "Family problems"),
    ("financial", "Financial pressure"),
    ("health", "Health concerns"),
    ("loneliness", "Loneliness"),
    ("unsure", "I'm not sure"),
]


class SignUpForm(forms.Form):
    email = forms.EmailField(
        widget=forms.EmailInput(attrs={"placeholder": "you@example.com", "autocomplete": "email"})
    )
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={"placeholder": "Min. 8 characters", "autocomplete": "new-password"})
    )
    confirm_password = forms.CharField(
        widget=forms.PasswordInput(attrs={"placeholder": "Repeat password", "autocomplete": "new-password"})
    )
    agree_privacy = forms.BooleanField(
        required=True,
        error_messages={"required": "You must agree to the Privacy Policy to create an account."},
    )

    def clean_email(self):
        email = self.cleaned_data["email"].lower()
        if User.objects.filter(email=email).exists():
            raise forms.ValidationError("An account with this email already exists.")
        return email

    def clean_password(self):
        password = self.cleaned_data.get("password", "")
        validate_password(password)
        return password

    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get("password")
        confirm = cleaned_data.get("confirm_password")
        if password and confirm and password != confirm:
            self.add_error("confirm_password", "Passwords do not match.")
        return cleaned_data


class SignInForm(forms.Form):
    email = forms.EmailField(
        widget=forms.EmailInput(attrs={"placeholder": "you@example.com", "autocomplete": "email"})
    )
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={"placeholder": "Your password", "autocomplete": "current-password"})
    )


class OnboardingAboutForm(forms.Form):
    display_name = forms.CharField(
        max_length=100,
        widget=forms.TextInput(attrs={"placeholder": "Your name or nickname"}),
    )
    age = forms.IntegerField(
        min_value=1,
        max_value=120,
        widget=forms.NumberInput(attrs={"placeholder": "Your age"}),
    )
    gender = forms.ChoiceField(
        choices=[("", "— select —"), ("male", "Male"), ("female", "Female"), ("nonbinary", "Non-binary / Other"), ("prefer_not", "Prefer not to say")],
        required=False,
    )
    country = forms.ChoiceField(choices=COUNTRY_CHOICES)

    def clean_age(self):
        age = self.cleaned_data.get("age")
        if age is not None and age < 18:
            raise forms.ValidationError("under_18")
        return age


class OnboardingCheckinForm(forms.Form):
    mood_score = forms.ChoiceField(
        choices=[("1", "😢"), ("2", "😟"), ("3", "😐"), ("4", "🙂"), ("5", "😊")],
    )
    has_seen_professional = forms.ChoiceField(
        choices=[("yes", "Yes"), ("no", "No")],
        widget=forms.RadioSelect,
    )
    current_treatment = forms.ChoiceField(
        choices=[("yes", "Yes"), ("no", "No"), ("prefer_not", "Prefer not to say")],
        widget=forms.RadioSelect,
        required=False,
    )
    reasons = forms.MultipleChoiceField(
        choices=REASON_CHOICES,
        widget=forms.CheckboxSelectMultiple,
    )
    safety_status = forms.ChoiceField(
        choices=[("safe", "Yes, I feel safe"), ("unsafe", "No, I don't feel safe"), ("unsure", "I'm not sure")],
        widget=forms.RadioSelect,
    )
    immediate_need = forms.ChoiceField(
        choices=[
            ("listen", "Someone to listen"),
            ("coping", "Coping strategies"),
            ("understand", "To understand my feelings"),
            ("crisis", "Crisis help"),
            ("vent", "Just to vent"),
            ("unsure", "Not sure"),
        ],
        widget=forms.RadioSelect,
    )

    def clean_has_seen_professional(self):
        value = self.cleaned_data.get("has_seen_professional")
        return value == "yes"


# ─── Dashboard Forms ───────────────────────────────────────────────────────────

class JournalForm(forms.Form):
    content = forms.CharField(
        widget=forms.Textarea(attrs={
            "placeholder": "Write freely. This is just for you.",
            "rows": 6,
        }),
    )


class SafetyPlanForm(forms.Form):
    warning_signs = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            "placeholder": "e.g. withdrawing from friends, not sleeping, feeling numb...",
            "rows": 3,
        }),
    )
    coping_strategies = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            "placeholder": "e.g. deep breathing, going for a walk, calling a friend...",
            "rows": 3,
        }),
    )
    support_people = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            "placeholder": "Names and numbers of people you can reach out to...",
            "rows": 3,
        }),
    )
    reasons_to_live = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            "placeholder": "The people, things, and dreams that matter to you...",
            "rows": 3,
        }),
    )
    safe_environment = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            "placeholder": "Steps you can take to make your space feel safer...",
            "rows": 3,
        }),
    )
