import datetime
from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.db import IntegrityError

from core.models import (
    OnboardingProfile,
    TherapistProfile,
    SessionNote,
    MoodEntry,
    TherapyGoal,
    ReflectionTask,
    Appointment,
    JournalEntry,
    SafetyPlan,
    Subscription,
    PaymentTransaction,
)

User = get_user_model()


class ModelTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="patient@example.com",
            password="patientpassword123",
        )

    def test_coeus_user_creation_and_defaults(self):
        self.assertEqual(self.user.email, "patient@example.com")
        self.assertEqual(self.user.role, "user")
        self.assertFalse(self.user.is_therapist)
        self.assertFalse(self.user.is_staff)
        self.assertFalse(self.user.is_superuser)
        self.assertFalse(self.user.onboarding_complete)
        self.assertTrue(self.user.check_password("patientpassword123"))
        self.assertEqual(str(self.user), "patient@example.com")

    def test_coeus_user_roles(self):
        therapist_user = User.objects.create_user(
            email="therapist@example.com",
            password="password123",
            role="therapist",
        )
        admin_user = User.objects.create_user(
            email="admin@example.com",
            password="password123",
            role="admin",
        )
        self.assertTrue(therapist_user.is_therapist)
        self.assertTrue(admin_user.is_therapist)

    def test_coeus_superuser_creation(self):
        admin = User.objects.create_superuser(
            email="super@example.com",
            password="adminpassword123",
        )
        self.assertTrue(admin.is_staff)
        self.assertTrue(admin.is_superuser)

    def test_user_requires_email(self):
        with self.assertRaises(ValueError):
            User.objects.create_user(email="")

    def test_user_email_uniqueness(self):
        with self.assertRaises(IntegrityError):
            User.objects.create_user(
                email="patient@example.com",
                password="anotherpassword",
            )

    def test_onboarding_profile(self):
        profile = OnboardingProfile.objects.create(
            user=self.user,
            display_name="Jane Doe",
            age=25,
            gender="female",
            country="Nigeria",
            mood_score=3,
            has_seen_professional=False,
            current_treatment="no",
            reasons=["anxiety"],
            safety_status="safe",
            immediate_need="listen",
            risk_level="normal",
        )
        self.assertEqual(str(profile), "Onboarding: patient@example.com")
        self.assertEqual(self.user.onboarding.display_name, "Jane Doe")

    def test_therapist_profile(self):
        therapist = User.objects.create_user(
            email="dr.smith@example.com",
            password="password123",
            role="therapist",
        )
        tp = TherapistProfile.objects.create(
            user=therapist,
            bio="Licensed therapist with 10 years experience",
            credentials="MSc Clinical Psychology",
        )
        self.assertEqual(str(tp), "Therapist: dr.smith@example.com")
        self.assertTrue(tp.is_active)

    def test_session_note(self):
        therapist = User.objects.create_user(
            email="therapist@example.com",
            password="password123",
            role="therapist",
        )
        note = SessionNote.objects.create(
            therapist=therapist,
            patient=self.user,
            content="Patient reported improvement with anxiety management.",
        )
        self.assertIn("Note by therapist@example.com on patient@example.com", str(note))
        self.assertEqual(SessionNote.objects.filter(patient=self.user).count(), 1)

    def test_mood_entry_properties_and_constraints(self):
        today = datetime.date.today()
        entry = MoodEntry.objects.create(
            user=self.user,
            mood="happy",
            score=5,
            date=today,
        )
        self.assertEqual(entry.emoji, "😊")
        self.assertEqual(entry.label, "Happy")
        self.assertEqual(entry.bar_color, "#2dd4bf")
        self.assertIn("patient@example.com — happy", str(entry))

        # Test unique_together on user and date
        with self.assertRaises(IntegrityError):
            MoodEntry.objects.create(
                user=self.user,
                mood="sad",
                score=2,
                date=today,
            )

    def test_appointment_model(self):
        appt = Appointment.objects.create(
            user=self.user,
            presenting_concern="Feeling overwhelmed with work stress",
            support_type="therapy",
            appointment_date=datetime.date.today() + datetime.timedelta(days=2),
            appointment_time=datetime.time(14, 0),
        )
        self.assertEqual(appt.status, "pending")
        self.assertIn("patient@example.com — therapy (pending)", str(appt))

    def test_subscription_and_user_property(self):
        # User initially has no subscription
        self.assertFalse(self.user.has_active_subscription)
        self.assertIsNone(self.user.active_subscription)

        # Create active subscription
        sub = Subscription.objects.create(
            user=self.user,
            plan="basic",
            status="active",
            amount=25000,
            payment_method="paystack",
            reference="TEST-REF-001",
            start_date=timezone.now(),
            end_date=timezone.now() + datetime.timedelta(days=30),
            sessions_allocated=4,
            sessions_remaining=4,
        )
        self.assertTrue(self.user.has_active_subscription)
        self.assertEqual(self.user.active_subscription.id, sub.id)
        self.assertIn("patient@example.com", str(sub))

        # Test payment transaction model
        tx = PaymentTransaction.objects.create(
            user=self.user,
            subscription=sub,
            reference="TEST-REF-001",
            amount=25000,
            channel="paystack",
            status="success",
        )
        self.assertIn("TEST-REF-001 — 25000 NGN (success)", str(tx))

    def test_journal_entry_unique_together(self):
        today = datetime.date.today()
        JournalEntry.objects.create(
            user=self.user,
            content="Today was a productive day.",
            date=today,
        )
        with self.assertRaises(IntegrityError):
            JournalEntry.objects.create(
                user=self.user,
                content="Another entry today.",
                date=today,
            )

    def test_therapy_goal_and_reflection_task(self):
        today = datetime.date.today()
        goal = TherapyGoal.objects.create(
            user=self.user,
            text="Practice deep breathing daily",
            week_of=today,
        )
        self.assertIn("Practice deep breathing daily", str(goal))
        self.assertFalse(goal.completed)

        task = ReflectionTask.objects.create(
            user=self.user,
            text="Take 3 slow deep breaths.",
            task_type="exercise",
            date=today,
        )
        self.assertIn("Take 3 slow deep breaths.", str(task))
        self.assertFalse(task.completed)


class TherapistAccessControlTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.patient = User.objects.create_user(
            email="patient@example.com",
            password="password123",
            role="user",
        )
        self.therapist = User.objects.create_user(
            email="therapist@example.com",
            password="password123",
            role="therapist",
        )
        self.admin = User.objects.create_user(
            email="admin@example.com",
            password="password123",
            role="admin",
        )

    def test_anonymous_redirected_to_therapist_login(self):
        response = self.client.get(reverse("therapist_dashboard"))
        self.assertRedirects(response, reverse("therapist_login"))

    def test_regular_user_redirected_to_therapist_login(self):
        self.client.login(username="patient@example.com", password="password123")
        response = self.client.get(reverse("therapist_dashboard"))
        self.assertRedirects(response, reverse("therapist_login"))

    def test_therapist_allowed_access(self):
        self.client.login(username="therapist@example.com", password="password123")
        response = self.client.get(reverse("therapist_dashboard"))
        self.assertEqual(response.status_code, 200)

    def test_admin_allowed_access(self):
        self.client.login(username="admin@example.com", password="password123")
        response = self.client.get(reverse("therapist_dashboard"))
        self.assertEqual(response.status_code, 200)


class TherapistViewsTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.therapist = User.objects.create_user(
            email="therapist@coeus.ng",
            password="therapistpass",
            role="therapist",
        )
        self.patient = User.objects.create_user(
            email="patient1@example.com",
            password="patientpass",
            role="user",
            onboarding_complete=True,
        )
        self.onboarding = OnboardingProfile.objects.create(
            user=self.patient,
            display_name="Patient One",
            age=28,
            country="Nigeria",
            mood_score=1,
            has_seen_professional=False,
            safety_status="unsafe",
            immediate_need="crisis",
            risk_level="high",
            flagged_at=timezone.now(),
        )

    def test_therapist_login_get(self):
        response = self.client.get(reverse("therapist_login"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "core/therapist/login.html")

    def test_therapist_login_redirect_when_already_authenticated(self):
        self.client.login(username="therapist@coeus.ng", password="therapistpass")
        response = self.client.get(reverse("therapist_login"))
        self.assertRedirects(response, reverse("therapist_dashboard"))

    def test_therapist_login_invalid_credentials(self):
        response = self.client.post(
            reverse("therapist_login"),
            {"email": "therapist@coeus.ng", "password": "wrongpassword"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Invalid credentials. Please try again.")

    def test_therapist_login_patient_rejected(self):
        response = self.client.post(
            reverse("therapist_login"),
            {"email": "patient1@example.com", "password": "patientpass"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "This account does not have therapist access.")

    def test_therapist_login_success(self):
        response = self.client.post(
            reverse("therapist_login"),
            {"email": "therapist@coeus.ng", "password": "therapistpass"},
        )
        self.assertRedirects(response, reverse("therapist_dashboard"))

    def test_therapist_dashboard_content_and_stats(self):
        # Create an appointment
        Appointment.objects.create(
            user=self.patient,
            presenting_concern="Crisis concern",
            support_type="crisis",
            appointment_date=datetime.date.today() + datetime.timedelta(days=1),
            appointment_time=datetime.time(10, 0),
            status="pending",
        )

        self.client.login(username="therapist@coeus.ng", password="therapistpass")
        response = self.client.get(reverse("therapist_dashboard"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["total_patients"], 1)
        self.assertEqual(response.context["pending_count"], 1)
        self.assertEqual(response.context["flagged_count"], 1)
        self.assertContains(response, "Patient One")
        self.assertContains(response, "patient1@example.com")

    def test_therapist_patients_directory_and_search(self):
        patient2 = User.objects.create_user(
            email="alice@example.com",
            password="password",
            role="user",
            onboarding_complete=True,
        )
        OnboardingProfile.objects.create(
            user=patient2,
            display_name="Alice Smith",
            age=32,
            country="Nigeria",
            mood_score=4,
            has_seen_professional=True,
            safety_status="safe",
            immediate_need="listen",
            risk_level="normal",
        )

        self.client.login(username="therapist@coeus.ng", password="therapistpass")

        # Full list
        response = self.client.get(reverse("therapist_patients"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context["patients"]), 2)

        # Search by display name
        response_search = self.client.get(reverse("therapist_patients"), {"q": "Alice"})
        self.assertEqual(len(response_search.context["patients"]), 1)
        self.assertEqual(response_search.context["patients"][0].email, "alice@example.com")

        # Search by email
        response_search_email = self.client.get(
            reverse("therapist_patients"), {"q": "patient1@example.com"}
        )
        self.assertEqual(len(response_search_email.context["patients"]), 1)
        self.assertEqual(response_search_email.context["patients"][0].email, "patient1@example.com")

    def test_therapist_patient_detail_view_and_confidentiality(self):
        # Patient writes a journal entry (which should remain private from therapist)
        JournalEntry.objects.create(
            user=self.patient,
            content="SUPER_CONFIDENTIAL_JOURNAL_CONTENT_12345",
            date=datetime.date.today(),
        )

        self.client.login(username="therapist@coeus.ng", password="therapistpass")
        response = self.client.get(
            reverse("therapist_patient_detail", kwargs={"patient_id": self.patient.id})
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Patient One")
        # Ensure confidential journal entries are NOT exposed to therapist
        self.assertNotContains(response, "SUPER_CONFIDENTIAL_JOURNAL_CONTENT_12345")

    def test_therapist_patient_detail_add_session_note(self):
        self.client.login(username="therapist@coeus.ng", password="therapistpass")

        # Empty note submission fails with error
        response_empty = self.client.post(
            reverse("therapist_patient_detail", kwargs={"patient_id": self.patient.id}),
            {"note_content": "   "},
        )
        self.assertEqual(response_empty.status_code, 200)
        self.assertEqual(response_empty.context["note_error"], "Note content cannot be empty.")
        self.assertEqual(SessionNote.objects.count(), 0)

        # Valid note submission succeeds
        response_valid = self.client.post(
            reverse("therapist_patient_detail", kwargs={"patient_id": self.patient.id}),
            {"note_content": "Discussed grounding techniques for crisis moments."},
        )
        self.assertRedirects(
            response_valid,
            reverse("therapist_patient_detail", kwargs={"patient_id": self.patient.id}),
        )
        self.assertEqual(SessionNote.objects.count(), 1)
        note = SessionNote.objects.first()
        self.assertEqual(note.therapist, self.therapist)
        self.assertEqual(note.patient, self.patient)
        self.assertEqual(note.content, "Discussed grounding techniques for crisis moments.")

    def test_therapist_appointment_action_confirm_and_cancel(self):
        appt = Appointment.objects.create(
            user=self.patient,
            presenting_concern="Need counseling",
            support_type="therapy",
            appointment_date=datetime.date.today() + datetime.timedelta(days=1),
            appointment_time=datetime.time(11, 0),
            status="pending",
        )

        self.client.login(username="therapist@coeus.ng", password="therapistpass")

        # GET request should be rejected (require_POST)
        get_resp = self.client.get(
            reverse("therapist_appointment_action", kwargs={"appointment_id": appt.id})
        )
        self.assertEqual(get_resp.status_code, 405)

        # Confirm action
        post_confirm = self.client.post(
            reverse("therapist_appointment_action", kwargs={"appointment_id": appt.id}),
            {
                "action": "confirm",
                "therapist_name": "Dr. Sarah",
                "next": reverse("therapist_dashboard"),
            },
        )
        self.assertRedirects(post_confirm, reverse("therapist_dashboard"))
        appt.refresh_from_db()
        self.assertEqual(appt.status, "confirmed")

        # Cancel action
        post_cancel = self.client.post(
            reverse("therapist_appointment_action", kwargs={"appointment_id": appt.id}),
            {
                "action": "cancel",
                "admin_notes": "Therapist unavailable at requested time.",
                "next": reverse("therapist_dashboard"),
            },
        )
        self.assertRedirects(post_cancel, reverse("therapist_dashboard"))
        appt.refresh_from_db()
        self.assertEqual(appt.status, "cancelled")
        self.assertEqual(appt.admin_notes, "Therapist unavailable at requested time.")

    def test_therapist_dashboard_ui_structure_and_action_buttons(self):
        # Create a confirmed appointment
        Appointment.objects.create(
            user=self.patient,
            presenting_concern="Follow-up counseling",
            support_type="therapy",
            appointment_date=datetime.date.today() + datetime.timedelta(days=1),
            appointment_time=datetime.time(15, 0),
            status="confirmed",
        )

        self.client.login(username="therapist@coeus.ng", password="therapistpass")
        response = self.client.get(reverse("therapist_dashboard"))
        self.assertEqual(response.status_code, 200)

        # Check page header is present
        self.assertContains(response, "Clinical Triage & Schedule Dashboard")

        # Check sidebar structure contains both navigation links
        self.assertContains(response, 'class="tp-sidebar-nav"')
        self.assertContains(response, "Dashboard")
        self.assertContains(response, "Patients")
        self.assertContains(response, "Sign out")

        # Check action buttons
        self.assertContains(response, "Cancel & Refund Quota")
        self.assertContains(response, "Clinical File →")

    def test_therapist_directory_search_clear_button(self):
        self.client.login(username="therapist@coeus.ng", password="therapistpass")
        # Search without q should not show Clear button
        resp_no_q = self.client.get(reverse("therapist_patients"))
        self.assertNotContains(resp_no_q, "Clear</a>")

        # Search with q should show Clear button
        resp_with_q = self.client.get(reverse("therapist_patients"), {"q": "patient"})
        self.assertContains(resp_with_q, "Clear</a>")

    def test_therapist_landing_and_signin_redirects(self):
        self.client.login(username="therapist@coeus.ng", password="therapistpass")
        # Landing redirects to therapist_dashboard
        resp_landing = self.client.get(reverse("landing"))
        self.assertRedirects(resp_landing, reverse("therapist_dashboard"))

        # Signin redirects to therapist_dashboard
        resp_signin = self.client.get(reverse("signin"))
        self.assertRedirects(resp_signin, reverse("therapist_dashboard"))

    def test_therapist_dashboard_shows_pending_bank_transfers(self):
        Subscription.objects.create(
            user=self.patient,
            plan="basic",
            status="pending",
            amount=25000,
            payment_method="bank_transfer",
            sender_name="Jane Doe",
            sender_bank="Zenith Bank",
            reference="ZEN-9988",
        )
        self.client.login(username="therapist@coeus.ng", password="therapistpass")
        response = self.client.get(reverse("therapist_dashboard"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Pending Bank Transfers & Subscriptions")
        self.assertContains(response, "Jane Doe")
        self.assertContains(response, "Zenith Bank")
        self.assertContains(response, "Activate")

    def test_therapist_subscription_action_confirm_and_decline(self):
        sub = Subscription.objects.create(
            user=self.patient,
            plan="basic",
            status="pending",
            amount=25000,
            payment_method="bank_transfer",
            sender_name="Jane Doe",
            sender_bank="Zenith Bank",
            reference="ZEN-9988",
        )
        self.client.login(username="therapist@coeus.ng", password="therapistpass")

        # Confirm
        post_confirm = self.client.post(
            reverse("therapist_subscription_action", kwargs={"subscription_id": sub.id}),
            {"action": "confirm", "admin_notes": "Transfer verified in Kuda.", "confirmed_plan": "basic"},
        )
        self.assertRedirects(post_confirm, reverse("therapist_dashboard"))
        sub.refresh_from_db()
        self.assertEqual(sub.status, "active")
        self.assertEqual(sub.sessions_remaining, 4)
        self.assertTrue(self.patient.has_active_subscription)

        # Decline / cancel
        sub2 = Subscription.objects.create(
            user=self.patient,
            plan="basic",
            status="pending",
            amount=25000,
            payment_method="bank_transfer",
            reference="ZEN-9989",
        )
        post_decline = self.client.post(
            reverse("therapist_subscription_action", kwargs={"subscription_id": sub2.id}),
            {"action": "decline", "admin_notes": "No payment received."},
        )
        self.assertRedirects(post_decline, reverse("therapist_dashboard"))
        sub2.refresh_from_db()
        self.assertEqual(sub2.status, "cancelled")
        sub.status = "expired"
        sub.save()
        self.assertFalse(self.patient.has_active_subscription)

    def test_therapist_patients_and_detail_subscription_display(self):
        self.client.login(username="therapist@coeus.ng", password="therapistpass")
        # Patient initially has no active plan
        resp_p = self.client.get(reverse("therapist_patients"))
        self.assertContains(resp_p, "No Active Plan")

        # Activate subscription
        Subscription.objects.create(
            user=self.patient,
            plan="pro",
            status="active",
            amount=45000,
            payment_method="paystack",
            start_date=timezone.now(),
            end_date=timezone.now() + datetime.timedelta(days=30),
            sessions_allocated=8,
            sessions_remaining=8,
        )

        resp_p2 = self.client.get(reverse("therapist_patients"))
        self.assertContains(resp_p2, "Pro")

        resp_detail = self.client.get(reverse("therapist_patient_detail", kwargs={"patient_id": self.patient.id}))
        self.assertContains(resp_detail, "Pro")


class PatientAuthAndOnboardingTests(TestCase):
    def setUp(self):
        self.client = Client()

    def test_landing_and_privacy_pages(self):
        response_landing = self.client.get(reverse("landing"))
        self.assertEqual(response_landing.status_code, 200)

        response_privacy = self.client.get(reverse("privacy"))
        self.assertEqual(response_privacy.status_code, 200)

    def test_patient_signup_flow(self):
        response = self.client.get(reverse("signup"))
        self.assertEqual(response.status_code, 200)

        # Successful signup
        post_resp = self.client.post(
            reverse("signup"),
            {
                "email": "newpatient@example.com",
                "password": "StrongPassword123!",
                "confirm_password": "StrongPassword123!",
                "agree_privacy": True,
            },
        )
        self.assertRedirects(post_resp, reverse("onboarding_welcome"))

        created_user = User.objects.get(email="newpatient@example.com")
        self.assertEqual(created_user.role, "user")
        self.assertFalse(created_user.onboarding_complete)

    def test_signin_page_contains_therapist_login_link(self):
        response = self.client.get(reverse("signin"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "/therapist/login/")
        self.assertContains(response, "Login as Therapist / Admin")

    def test_patient_signin_and_signout(self):
        user = User.objects.create_user(
            email="existing@example.com",
            password="ValidPassword123",
            onboarding_complete=True,
        )

        login_resp = self.client.post(
            reverse("signin"),
            {"email": "existing@example.com", "password": "ValidPassword123"},
        )
        self.assertRedirects(login_resp, reverse("dashboard"))

        signout_resp = self.client.get(reverse("signout"))
        self.assertRedirects(signout_resp, reverse("landing"))

    def test_onboarding_flow_and_high_risk_flagging(self):
        user = User.objects.create_user(
            email="onboardinguser@example.com",
            password="Password123",
        )
        self.client.login(username="onboardinguser@example.com", password="Password123")

        # Step 1: Welcome POST
        step1_resp = self.client.post(reverse("onboarding_welcome"))
        self.assertRedirects(step1_resp, reverse("onboarding_about"))

        # Step 2: About POST with age < 18
        age_under_resp = self.client.post(
            reverse("onboarding_about"),
            {
                "display_name": "Minor User",
                "age": 16,
                "gender": "male",
                "country": "Nigeria",
            },
        )
        self.assertEqual(age_under_resp.status_code, 200)
        self.assertTemplateUsed(age_under_resp, "core/onboarding_age_block.html")

        # Step 2: About POST valid
        step2_resp = self.client.post(
            reverse("onboarding_about"),
            {
                "display_name": "Valid User",
                "age": 22,
                "gender": "female",
                "country": "Nigeria",
            },
        )
        self.assertRedirects(step2_resp, reverse("onboarding_checkin"))

        # Step 3: Checkin POST - high risk scenario (safety_status = unsafe)
        step3_resp = self.client.post(
            reverse("onboarding_checkin"),
            {
                "mood_score": "1",
                "has_seen_professional": "no",
                "current_treatment": "no",
                "reasons": ["health", "work_school"],
                "safety_status": "unsafe",
                "immediate_need": "crisis",
            },
        )
        self.assertRedirects(step3_resp, reverse("onboarding_crisis"))

        user.refresh_from_db()
        self.assertTrue(user.onboarding_complete)
        self.assertEqual(user.onboarding.risk_level, "high")
        self.assertIsNotNone(user.onboarding.flagged_at)


class PatientDashboardAndFeaturesTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            email="patient@example.com",
            password="password123",
            onboarding_complete=True,
        )
        self.onboarding = OnboardingProfile.objects.create(
            user=self.user,
            display_name="Patient Test",
            age=24,
            country="Nigeria",
            mood_score=4,
            has_seen_professional=False,
            safety_status="safe",
            immediate_need="listen",
            risk_level="normal",
        )
        self.client.login(username="patient@example.com", password="password123")

    def test_dashboard_seeds_defaults_and_loads(self):
        response = self.client.get(reverse("dashboard"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(TherapyGoal.objects.filter(user=self.user).count(), 3)
        self.assertEqual(ReflectionTask.objects.filter(user=self.user).count(), 3)

    def test_mood_checkin(self):
        response = self.client.post(
            reverse("mood_checkin"),
            {"mood": "calm"},
        )
        self.assertRedirects(response, reverse("dashboard"))
        entry = MoodEntry.objects.filter(user=self.user, date=datetime.date.today()).first()
        self.assertIsNotNone(entry)
        self.assertEqual(entry.mood, "calm")
        self.assertEqual(entry.score, 4)

    def test_goal_and_task_toggle(self):
        # Trigger seeding
        self.client.get(reverse("dashboard"))
        goal = TherapyGoal.objects.filter(user=self.user).first()
        self.assertFalse(goal.completed)

        response_goal = self.client.post(
            reverse("goal_toggle", kwargs={"goal_id": goal.id}),
        )
        self.assertRedirects(response_goal, reverse("dashboard"))
        goal.refresh_from_db()
        self.assertTrue(goal.completed)

        task = ReflectionTask.objects.filter(user=self.user).first()
        self.assertFalse(task.completed)
        response_task = self.client.post(
            reverse("task_toggle", kwargs={"task_id": task.id}),
        )
        self.assertRedirects(response_task, reverse("dashboard"))
        task.refresh_from_db()
        self.assertTrue(task.completed)

    def test_journal_save(self):
        response = self.client.post(
            reverse("journal_save"),
            {"content": "Reflecting on positive moments today."},
        )
        self.assertRedirects(response, reverse("dashboard"))
        entry = JournalEntry.objects.filter(user=self.user, date=datetime.date.today()).first()
        self.assertIsNotNone(entry)
        self.assertEqual(entry.decrypted_content, "Reflecting on positive moments today.")

    def test_safety_plan_save(self):
        response = self.client.post(
            reverse("safety_plan"),
            {
                "warning_signs": "Restlessness, pacing",
                "coping_strategies": "Box breathing, going for a walk",
                "support_people": "Sibling, Best Friend",
                "reasons_to_live": "Family, future goals",
                "safe_environment": "Quiet room without sharp items",
            },
        )
        self.assertRedirects(response, reverse("dashboard"))
        plan = SafetyPlan.objects.get(user=self.user)
        self.assertEqual(plan.warning_signs, "Restlessness, pacing")
        self.assertEqual(plan.coping_strategies, "Box breathing, going for a walk")

    def test_appointment_book_redirects_if_unsubscribed(self):
        # User has no active subscription, should redirect to subscribe
        response = self.client.get(reverse("appointment_book"))
        self.assertRedirects(response, reverse("subscribe"))

        response_post = self.client.post(
            reverse("appointment_book"),
            {"presenting_concern": "Need help"},
        )
        self.assertRedirects(response_post, reverse("subscribe"))

    def test_appointment_booking(self):
        # Activate subscription first
        Subscription.objects.create(
            user=self.user,
            plan="basic",
            status="active",
            amount=25000,
            payment_method="paystack",
            start_date=timezone.now(),
            end_date=timezone.now() + datetime.timedelta(days=30),
            sessions_allocated=4,
            sessions_remaining=4,
        )

        therapist = User.objects.create_user(
            email="therapist_slot_test@coeus.ng",
            password="docpass",
            role="therapist",
        )

        response = self.client.post(
            reverse("appointment_book"),
            {
                "therapist": str(therapist.id),
                "appointment_date": str(datetime.date.today() + datetime.timedelta(days=2)),
                "appointment_time": "14:00",
                "presenting_concern": "Need someone to speak with regarding career transitions.",
                "support_type": "therapy",
            },
        )
        self.assertRedirects(response, reverse("dashboard"))
        appt = Appointment.objects.filter(user=self.user).first()
        self.assertIsNotNone(appt)
        self.assertEqual(appt.status, "pending")
        self.assertEqual(appt.support_type, "therapy")

    def test_appointment_book_get_renders_booking_form(self):
        # Activate subscription first
        Subscription.objects.create(
            user=self.user,
            plan="basic",
            status="active",
            amount=25000,
            payment_method="paystack",
            start_date=timezone.now(),
            end_date=timezone.now() + datetime.timedelta(days=30),
            sessions_allocated=4,
            sessions_remaining=4,
        )

        response = self.client.get(reverse("appointment_book"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Schedule Therapy Session")
        self.assertContains(response, "Sessions Remaining in Your Quota")

    def test_subscribe_page_renders_plans_and_bank_details(self):
        response = self.client.get(reverse("subscribe"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Basic")
        self.assertContains(response, "Pro")
        self.assertContains(response, "Max")
        self.assertContains(response, "2019284756")
        self.assertContains(response, "Kuda Microfinance Bank")
        self.assertContains(response, "Pay with Paystack")

    def test_instant_test_activate(self):
        response = self.client.post(
            reverse("instant_test_activate"),
            {"plan": "basic"},
        )
        self.assertRedirects(response, reverse("appointment_book"))
        self.user.refresh_from_db()
        self.assertTrue(self.user.has_active_subscription)
        self.assertEqual(self.user.active_subscription.plan, "basic")
        self.assertEqual(self.user.active_subscription.sessions_remaining, 4)

    def test_bank_transfer_submission(self):
        response = self.client.post(
            reverse("bank_transfer_submit"),
            {
                "plan": "basic",
                "sender_name": "Samuel Jackson",
                "sender_bank": "Access Bank",
                "reference": "ACC-998811",
            },
        )
        self.assertRedirects(response, reverse("subscribe"))
        sub = Subscription.objects.filter(user=self.user, payment_method="bank_transfer").first()
        self.assertIsNotNone(sub)
        self.assertEqual(sub.status, "pending")
        self.assertEqual(sub.sender_name, "Samuel Jackson")
        self.assertEqual(sub.sender_bank, "Access Bank")
        self.assertEqual(sub.amount, 25000)
        # Pending does not grant active access yet
        self.user.refresh_from_db()
        self.assertFalse(self.user.has_active_subscription)

