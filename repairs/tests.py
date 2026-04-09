from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.urls import reverse
from django.utils import timezone
from datetime import timedelta

from .models import (
    Community, Dwelling, TenantProfile, RepairRequest,
    MaintenanceLog, Notification, RepairFeedback
)
from .forms import RegistrationForm, RepairRequestForm


class CommunityModelTest(TestCase):
    """Tests for the Community model."""

    def setUp(self):
        self.community = Community.objects.create(
            name='Wadeye', region='TOP_END', population=2500
        )

    def test_str_representation(self):
        self.assertEqual(str(self.community), 'Wadeye (Top End)')

    def test_dwelling_count_property(self):
        self.assertEqual(self.community.dwelling_count, 0)
        Dwelling.objects.create(
            address='1 Test St', community=self.community,
            dwelling_type='HOUSE', bedrooms=3
        )
        self.assertEqual(self.community.dwelling_count, 1)


class DwellingModelTest(TestCase):
    """Tests for the Dwelling model."""

    def setUp(self):
        self.community = Community.objects.create(
            name='Yuendumu', region='CENTRAL', population=800
        )
        self.dwelling = Dwelling.objects.create(
            address='1 Desert View', community=self.community,
            dwelling_type='HOUSE', bedrooms=3, meets_ncc_standards=False
        )

    def test_str_representation(self):
        self.assertEqual(str(self.dwelling), '1 Desert View, Yuendumu')

    def test_compliance_status_non_compliant(self):
        self.assertEqual(
            self.dwelling.compliance_status, 'Does NOT meet NCC Standards'
        )

    def test_compliance_status_compliant(self):
        self.dwelling.meets_ncc_standards = True
        self.assertEqual(
            self.dwelling.compliance_status, 'Compliant with NCC Standards'
        )

    def test_is_overcrowded(self):
        self.assertFalse(self.dwelling.is_overcrowded(6))  # 3 beds * 2 = 6
        self.assertTrue(self.dwelling.is_overcrowded(7))   # > 6

    def test_active_repair_count(self):
        self.assertEqual(self.dwelling.active_repair_count(), 0)


class TenantProfileModelTest(TestCase):
    """Tests for the TenantProfile model."""

    def setUp(self):
        self.user = User.objects.create_user(
            'testuser', password='testpass',
            first_name='Jane', last_name='Doe'
        )
        # Profile auto-created by signal; update it
        self.profile = self.user.profile
        self.profile.phone = '0400111222'
        self.profile.save()

    def test_full_name(self):
        self.assertEqual(self.profile.full_name, 'Jane Doe')

    def test_full_name_fallback_to_username(self):
        self.user.first_name = ''
        self.user.last_name = ''
        self.user.save()
        self.assertEqual(self.profile.full_name, 'testuser')

    def test_is_tenant_default(self):
        self.assertTrue(self.profile.is_tenant)

    def test_is_staff_member(self):
        self.profile.is_staff_member = True
        self.profile.save()
        self.assertFalse(self.profile.is_tenant)


class RepairRequestModelTest(TestCase):
    """Tests for the RepairRequest model and its custom manager."""

    def setUp(self):
        self.community = Community.objects.create(
            name='Borroloola', region='BIG_RIVERS', population=900
        )
        self.dwelling = Dwelling.objects.create(
            address='3 Coastal Drive', community=self.community,
            dwelling_type='HOUSE', bedrooms=4
        )
        self.user = User.objects.create_user('tenant1', password='pass1234')
        self.tenant = self.user.profile
        self.tenant.dwelling = self.dwelling
        self.tenant.save()
        self.staff_user = User.objects.create_user('staff1', password='pass1234')
        self.staff = self.staff_user.profile
        self.staff.is_staff_member = True
        self.staff.save()
        self.request = RepairRequest.objects.create(
            tenant=self.tenant, dwelling=self.dwelling,
            title='Broken AC', description='AC not working',
            issue_type='AC', priority='HIGH',
        )

    def test_str_representation(self):
        self.assertEqual(str(self.request), 'Broken AC [Pending]')

    def test_default_status_is_pending(self):
        self.assertEqual(self.request.status, 'PENDING')

    def test_mark_in_review(self):
        self.request.mark_in_review()
        self.request.refresh_from_db()
        self.assertEqual(self.request.status, 'IN_REVIEW')

    def test_mark_in_progress_assigns_staff(self):
        self.request.mark_in_progress(self.staff)
        self.request.refresh_from_db()
        self.assertEqual(self.request.status, 'IN_PROGRESS')
        self.assertEqual(self.request.assigned_to, self.staff)

    def test_mark_completed_sets_timestamp(self):
        self.request.mark_completed()
        self.request.refresh_from_db()
        self.assertEqual(self.request.status, 'COMPLETED')
        self.assertIsNotNone(self.request.completed_at)

    def test_cancel(self):
        self.request.cancel()
        self.request.refresh_from_db()
        self.assertEqual(self.request.status, 'CANCELLED')

    def test_can_edit_only_when_pending(self):
        self.assertTrue(self.request.can_edit)
        self.request.mark_in_review()
        self.assertFalse(self.request.can_edit)

    def test_is_active(self):
        self.assertTrue(self.request.is_active)
        self.request.mark_completed()
        self.assertFalse(self.request.is_active)

    def test_is_overdue(self):
        self.assertFalse(self.request.is_overdue(days=14))
        # Manually set created_at to 20 days ago
        RepairRequest.objects.filter(pk=self.request.pk).update(
            created_at=timezone.now() - timedelta(days=20)
        )
        self.request.refresh_from_db()
        self.assertTrue(self.request.is_overdue(days=14))

    def test_days_open(self):
        self.assertEqual(self.request.days_open, 0)

    # ── Manager / QuerySet tests ──

    def test_manager_pending(self):
        self.assertEqual(RepairRequest.objects.pending().count(), 1)

    def test_manager_completed(self):
        self.assertEqual(RepairRequest.objects.completed().count(), 0)
        self.request.mark_completed()
        self.assertEqual(RepairRequest.objects.completed().count(), 1)

    def test_manager_active(self):
        self.assertEqual(RepairRequest.objects.active().count(), 1)
        self.request.cancel()
        self.assertEqual(RepairRequest.objects.active().count(), 0)

    def test_manager_overdue(self):
        self.assertEqual(RepairRequest.objects.overdue().count(), 0)

    def test_stats_by_issue_type(self):
        stats = list(RepairRequest.objects.stats_by_issue_type())
        self.assertEqual(len(stats), 1)
        self.assertEqual(stats[0]['issue_type'], 'AC')
        self.assertEqual(stats[0]['count'], 1)

    def test_stats_by_status(self):
        stats = list(RepairRequest.objects.stats_by_status())
        self.assertEqual(stats[0]['status'], 'PENDING')


class RegistrationFormTest(TestCase):
    """Tests for the RegistrationForm."""

    def test_valid_form(self):
        form = RegistrationForm(data={
            'username': 'newuser',
            'first_name': 'New',
            'last_name': 'User',
            'password': 'securepass123',
            'password_confirm': 'securepass123',
        })
        self.assertTrue(form.is_valid())

    def test_password_mismatch(self):
        form = RegistrationForm(data={
            'username': 'newuser',
            'first_name': 'New',
            'last_name': 'User',
            'password': 'pass1',
            'password_confirm': 'pass2',
        })
        self.assertFalse(form.is_valid())

    def test_duplicate_username(self):
        User.objects.create_user('existing', password='pass')
        form = RegistrationForm(data={
            'username': 'existing',
            'first_name': 'New',
            'last_name': 'User',
            'password': 'securepass123',
            'password_confirm': 'securepass123',
        })
        self.assertFalse(form.is_valid())
        self.assertIn('username', form.errors)


class RepairRequestFormTest(TestCase):
    """Tests for the RepairRequestForm."""

    def test_valid_form(self):
        form = RepairRequestForm(data={
            'title': 'Broken window',
            'description': 'Window is cracked and letting in dust.',
            'issue_type': 'OTHER',
            'priority': 'MEDIUM',
            'location_in_dwelling': 'BEDROOM',
        })
        self.assertTrue(form.is_valid())

    def test_missing_required_fields(self):
        form = RepairRequestForm(data={})
        self.assertFalse(form.is_valid())
        self.assertIn('title', form.errors)
        self.assertIn('description', form.errors)


class ViewTest(TestCase):
    """Tests for key views."""

    def setUp(self):
        self.client = Client()
        self.community = Community.objects.create(
            name='Wadeye', region='TOP_END', population=2500
        )
        self.dwelling = Dwelling.objects.create(
            address='12 Main Road', community=self.community,
            dwelling_type='HOUSE', bedrooms=3
        )
        self.user = User.objects.create_user('tenant', password='pass1234')
        self.tenant = self.user.profile
        self.tenant.dwelling = self.dwelling
        self.tenant.save()
        self.staff_user = User.objects.create_user('staff', password='pass1234')
        self.staff = self.staff_user.profile
        self.staff.is_staff_member = True
        self.staff.save()

    def test_home_page_loads(self):
        response = self.client.get(reverse('home'))
        self.assertEqual(response.status_code, 200)

    def test_home_no_request_stats_for_anonymous(self):
        response = self.client.get(reverse('home'))
        self.assertNotIn('total_requests', response.context)

    def test_login_page_loads(self):
        response = self.client.get(reverse('login'))
        self.assertEqual(response.status_code, 200)

    def test_register_page_loads(self):
        response = self.client.get(reverse('register'))
        self.assertEqual(response.status_code, 200)

    def test_login_redirects_tenant_to_dashboard(self):
        response = self.client.post(reverse('login'), {
            'username': 'tenant', 'password': 'pass1234'
        })
        self.assertRedirects(response, reverse('tenant_dashboard'))

    def test_login_redirects_staff_to_staff_dashboard(self):
        response = self.client.post(reverse('login'), {
            'username': 'staff', 'password': 'pass1234'
        })
        self.assertRedirects(response, reverse('staff_dashboard'))

    def test_tenant_dashboard_requires_login(self):
        response = self.client.get(reverse('tenant_dashboard'))
        self.assertRedirects(response, reverse('login'))

    def test_staff_dashboard_requires_staff(self):
        self.client.login(username='tenant', password='pass1234')
        response = self.client.get(reverse('staff_dashboard'))
        self.assertRedirects(response, reverse('tenant_dashboard'))

    def test_create_request(self):
        self.client.login(username='tenant', password='pass1234')
        response = self.client.post(reverse('request_create'), {
            'title': 'Test Request',
            'description': 'Test description',
            'issue_type': 'PLUMBING',
            'priority': 'MEDIUM',
            'location_in_dwelling': 'KITCHEN',
        })
        self.assertEqual(RepairRequest.objects.count(), 1)
        req = RepairRequest.objects.first()
        self.assertEqual(req.title, 'Test Request')
        self.assertEqual(req.tenant, self.tenant)
        self.assertEqual(req.dwelling, self.dwelling)

    def test_request_detail_loads(self):
        self.client.login(username='tenant', password='pass1234')
        req = RepairRequest.objects.create(
            tenant=self.tenant, dwelling=self.dwelling,
            title='Test', description='Desc',
            issue_type='AC', priority='LOW',
        )
        response = self.client.get(reverse('request_detail', args=[req.pk]))
        self.assertEqual(response.status_code, 200)

    def test_tenant_cannot_edit_non_pending_request(self):
        self.client.login(username='tenant', password='pass1234')
        req = RepairRequest.objects.create(
            tenant=self.tenant, dwelling=self.dwelling,
            title='Test', description='Desc',
            issue_type='AC', priority='LOW',
        )
        req.mark_in_review()
        response = self.client.get(reverse('request_edit', args=[req.pk]))
        self.assertRedirects(
            response, reverse('request_detail', args=[req.pk])
        )

    def test_dwelling_detail_requires_login(self):
        response = self.client.get(
            reverse('dwelling_detail', args=[self.dwelling.pk])
        )
        self.assertRedirects(response, reverse('login'))

    def test_staff_can_update_status(self):
        self.client.login(username='staff', password='pass1234')
        req = RepairRequest.objects.create(
            tenant=self.tenant, dwelling=self.dwelling,
            title='Test', description='Desc',
            issue_type='AC', priority='LOW',
        )
        response = self.client.post(
            reverse('update_request_status', args=[req.pk]),
            {'status': 'IN_PROGRESS', 'note': 'Starting work'}
        )
        req.refresh_from_db()
        self.assertEqual(req.status, 'IN_PROGRESS')
        self.assertEqual(req.assigned_to, self.staff)


# ── Signal Tests ───────────────────────────────────────────

class SignalTest(TestCase):
    """Tests for Django signals."""

    def test_profile_auto_created_on_user_creation(self):
        user = User.objects.create_user('signaltest', password='pass')
        self.assertTrue(hasattr(user, 'profile'))
        self.assertIsInstance(user.profile, TenantProfile)

    def test_notification_created_on_status_change(self):
        user = User.objects.create_user('tenant_sig', password='pass')
        community = Community.objects.create(name='Test', region='TOP_END')
        dwelling = Dwelling.objects.create(
            address='1 Test St', community=community,
            dwelling_type='HOUSE', bedrooms=2
        )
        user.profile.dwelling = dwelling
        user.profile.save()
        req = RepairRequest.objects.create(
            tenant=user.profile, dwelling=dwelling,
            title='Signal Test', description='Testing',
            issue_type='AC', priority='LOW',
        )
        Notification.objects.all().delete()
        req.mark_in_review()
        self.assertTrue(
            Notification.objects.filter(
                recipient=user.profile,
                notification_type='STATUS_CHANGE'
            ).exists()
        )

    def test_no_duplicate_profile_on_registration(self):
        form = RegistrationForm(data={
            'username': 'newreg',
            'first_name': 'Test',
            'last_name': 'User',
            'password': 'securepass123',
            'password_confirm': 'securepass123',
        })
        self.assertTrue(form.is_valid())
        user = form.save()
        self.assertEqual(
            TenantProfile.objects.filter(user=user).count(), 1
        )


# ── Notification Model Tests ──────────────────────────────

class NotificationModelTest(TestCase):
    """Tests for the Notification model."""

    def setUp(self):
        self.user = User.objects.create_user('nuser', password='pass')
        self.notification = Notification.objects.create(
            recipient=self.user.profile,
            title='Test Notification',
            message='This is a test.',
            notification_type='SYSTEM',
        )

    def test_str_representation(self):
        self.assertIn('Test Notification', str(self.notification))

    def test_default_is_unread(self):
        self.assertFalse(self.notification.is_read)

    def test_mark_read(self):
        self.notification.mark_read()
        self.notification.refresh_from_db()
        self.assertTrue(self.notification.is_read)


# ── RepairFeedback Model Tests ─────────────────────────────

class RepairFeedbackModelTest(TestCase):
    """Tests for the RepairFeedback model."""

    def setUp(self):
        self.user = User.objects.create_user('fuser', password='pass')
        self.community = Community.objects.create(name='FC', region='CENTRAL')
        self.dwelling = Dwelling.objects.create(
            address='1 Feedback St', community=self.community,
            dwelling_type='HOUSE', bedrooms=2
        )
        self.user.profile.dwelling = self.dwelling
        self.user.profile.save()
        self.request = RepairRequest.objects.create(
            tenant=self.user.profile, dwelling=self.dwelling,
            title='Feedback Test', description='Test',
            issue_type='OTHER', priority='LOW',
        )
        self.request.mark_completed()

    def test_str_representation(self):
        feedback = RepairFeedback.objects.create(
            repair_request=self.request, tenant=self.user.profile,
            rating=4, comment='Good'
        )
        self.assertIn('4/5', str(feedback))

    def test_rating_stored(self):
        feedback = RepairFeedback.objects.create(
            repair_request=self.request, tenant=self.user.profile,
            rating=5,
        )
        self.assertEqual(feedback.rating, 5)


# ── Profile View Tests ─────────────────────────────────────

class ProfileViewTest(TestCase):
    """Tests for profile and password change views."""

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            'profuser', password='pass1234',
            first_name='Prof', last_name='User'
        )

    def test_profile_requires_login(self):
        response = self.client.get(reverse('profile'))
        self.assertRedirects(response, reverse('login'))

    def test_profile_page_loads(self):
        self.client.login(username='profuser', password='pass1234')
        response = self.client.get(reverse('profile'))
        self.assertEqual(response.status_code, 200)

    def test_profile_update_saves(self):
        self.client.login(username='profuser', password='pass1234')
        response = self.client.post(reverse('profile'), {
            'first_name': 'Updated',
            'last_name': 'Name',
            'phone': '0411222333',
        })
        self.user.refresh_from_db()
        self.assertEqual(self.user.first_name, 'Updated')

    def test_password_change_page_loads(self):
        self.client.login(username='profuser', password='pass1234')
        response = self.client.get(reverse('password_change'))
        self.assertEqual(response.status_code, 200)

    def test_password_change_success(self):
        self.client.login(username='profuser', password='pass1234')
        response = self.client.post(reverse('password_change'), {
            'old_password': 'pass1234',
            'new_password1': 'newsecurepass456',
            'new_password2': 'newsecurepass456',
        })
        self.assertRedirects(response, reverse('profile'))
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password('newsecurepass456'))


# ── Community & Dwelling View Tests ────────────────────────

class CommunityViewTest(TestCase):
    """Tests for community and dwelling list views."""

    def setUp(self):
        self.client = Client()
        self.community = Community.objects.create(
            name='TestComm', region='TOP_END', population=1000
        )
        self.staff_user = User.objects.create_user('cstaff', password='pass1234')
        self.staff_user.profile.is_staff_member = True
        self.staff_user.profile.save()
        self.tenant_user = User.objects.create_user('ctenant', password='pass1234')

    def test_community_list_staff_only(self):
        self.client.login(username='ctenant', password='pass1234')
        response = self.client.get(reverse('community_list'))
        self.assertRedirects(response, reverse('tenant_dashboard'))

    def test_community_list_loads(self):
        self.client.login(username='cstaff', password='pass1234')
        response = self.client.get(reverse('community_list'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'TestComm')

    def test_community_detail_loads(self):
        self.client.login(username='cstaff', password='pass1234')
        response = self.client.get(
            reverse('community_detail', args=[self.community.pk])
        )
        self.assertEqual(response.status_code, 200)

    def test_dwelling_list_loads(self):
        self.client.login(username='cstaff', password='pass1234')
        response = self.client.get(reverse('dwelling_list'))
        self.assertEqual(response.status_code, 200)


# ── Analytics & Export Tests ───────────────────────────────

class AnalyticsViewTest(TestCase):
    """Tests for analytics and CSV export views."""

    def setUp(self):
        self.client = Client()
        self.staff_user = User.objects.create_user('astaff', password='pass1234')
        self.staff_user.profile.is_staff_member = True
        self.staff_user.profile.save()
        self.tenant_user = User.objects.create_user('atenant', password='pass1234')

    def test_analytics_staff_only(self):
        self.client.login(username='atenant', password='pass1234')
        response = self.client.get(reverse('analytics'))
        self.assertRedirects(response, reverse('tenant_dashboard'))

    def test_analytics_page_loads(self):
        self.client.login(username='astaff', password='pass1234')
        response = self.client.get(reverse('analytics'))
        self.assertEqual(response.status_code, 200)

    def test_csv_export_staff_only(self):
        self.client.login(username='atenant', password='pass1234')
        response = self.client.get(reverse('export_csv'))
        self.assertRedirects(response, reverse('tenant_dashboard'))

    def test_csv_export_returns_csv(self):
        self.client.login(username='astaff', password='pass1234')
        response = self.client.get(reverse('export_csv'))
        self.assertEqual(response['Content-Type'], 'text/csv')
        self.assertIn('attachment', response['Content-Disposition'])

    def test_csv_export_has_header(self):
        self.client.login(username='astaff', password='pass1234')
        response = self.client.get(reverse('export_csv'))
        content = b''.join(response.streaming_content).decode('utf-8')
        self.assertIn('Title', content)
        self.assertIn('Priority', content)


# ── Feedback View Tests ────────────────────────────────────

class FeedbackViewTest(TestCase):
    """Tests for the feedback submission view."""

    def setUp(self):
        self.client = Client()
        self.community = Community.objects.create(name='FB', region='CENTRAL')
        self.dwelling = Dwelling.objects.create(
            address='1 FB St', community=self.community,
            dwelling_type='HOUSE', bedrooms=2
        )
        self.user = User.objects.create_user('fbtenant', password='pass1234')
        self.user.profile.dwelling = self.dwelling
        self.user.profile.save()
        self.request_obj = RepairRequest.objects.create(
            tenant=self.user.profile, dwelling=self.dwelling,
            title='FB Test', description='Desc',
            issue_type='AC', priority='LOW',
        )

    def test_feedback_only_on_completed(self):
        self.client.login(username='fbtenant', password='pass1234')
        response = self.client.get(
            reverse('submit_feedback', args=[self.request_obj.pk])
        )
        self.assertRedirects(
            response, reverse('request_detail', args=[self.request_obj.pk])
        )

    def test_feedback_submit_success(self):
        self.request_obj.mark_completed()
        self.client.login(username='fbtenant', password='pass1234')
        response = self.client.post(
            reverse('submit_feedback', args=[self.request_obj.pk]),
            {'rating': 5, 'comment': 'Great work!'}
        )
        self.assertEqual(RepairFeedback.objects.count(), 1)
        feedback = RepairFeedback.objects.first()
        self.assertEqual(feedback.rating, 5)

    def test_no_duplicate_feedback(self):
        self.request_obj.mark_completed()
        RepairFeedback.objects.create(
            repair_request=self.request_obj,
            tenant=self.user.profile,
            rating=3,
        )
        self.client.login(username='fbtenant', password='pass1234')
        response = self.client.get(
            reverse('submit_feedback', args=[self.request_obj.pk])
        )
        self.assertRedirects(
            response, reverse('request_detail', args=[self.request_obj.pk])
        )


# ── Notification View Tests ────────────────────────────────

class NotificationViewTest(TestCase):
    """Tests for notification views."""

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user('nviewuser', password='pass1234')
        self.notification = Notification.objects.create(
            recipient=self.user.profile,
            title='View Test',
            message='Testing notification views.',
            notification_type='SYSTEM',
        )

    def test_notification_list_loads(self):
        self.client.login(username='nviewuser', password='pass1234')
        response = self.client.get(reverse('notification_list'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'View Test')

    def test_mark_single_read(self):
        self.client.login(username='nviewuser', password='pass1234')
        self.client.get(
            reverse('mark_notification_read', args=[self.notification.pk])
        )
        self.notification.refresh_from_db()
        self.assertTrue(self.notification.is_read)

    def test_mark_all_read(self):
        Notification.objects.create(
            recipient=self.user.profile,
            title='Second', message='Two',
            notification_type='SYSTEM',
        )
        self.client.login(username='nviewuser', password='pass1234')
        self.client.post(reverse('mark_all_notifications_read'))
        unread = Notification.objects.filter(
            recipient=self.user.profile, is_read=False
        ).count()
        self.assertEqual(unread, 0)


# ── Logout View Tests ─────────────────────────────────────

class LogoutViewTest(TestCase):
    """Tests for POST-only logout."""

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user('logoutuser', password='pass1234')

    def test_logout_get_redirects_home(self):
        self.client.login(username='logoutuser', password='pass1234')
        response = self.client.get(reverse('logout'))
        self.assertRedirects(response, reverse('home'))
        # User should still be logged in after GET
        response = self.client.get(reverse('home'))
        self.assertTrue(response.wsgi_request.user.is_authenticated)

    def test_logout_post_works(self):
        self.client.login(username='logoutuser', password='pass1234')
        response = self.client.post(reverse('logout'))
        self.assertRedirects(response, reverse('home'))


# ── Cancel Request Tests ───────────────────────────────────

class CancelRequestViewTest(TestCase):
    """Tests for request cancellation by tenant."""

    def setUp(self):
        self.client = Client()
        self.community = Community.objects.create(name='CX', region='BARKLY')
        self.dwelling = Dwelling.objects.create(
            address='1 Cancel St', community=self.community,
            dwelling_type='HOUSE', bedrooms=2
        )
        self.user = User.objects.create_user('canceluser', password='pass1234')
        self.user.profile.dwelling = self.dwelling
        self.user.profile.save()
        self.req = RepairRequest.objects.create(
            tenant=self.user.profile, dwelling=self.dwelling,
            title='Cancel Me', description='Test cancel',
            issue_type='OTHER', priority='LOW',
        )

    def test_cancel_request_success(self):
        self.client.login(username='canceluser', password='pass1234')
        response = self.client.post(
            reverse('cancel_request', args=[self.req.pk])
        )
        self.req.refresh_from_db()
        self.assertEqual(self.req.status, 'CANCELLED')

    def test_cannot_cancel_completed_request(self):
        self.req.mark_completed()
        self.client.login(username='canceluser', password='pass1234')
        response = self.client.post(
            reverse('cancel_request', args=[self.req.pk])
        )
        self.req.refresh_from_db()
        self.assertEqual(self.req.status, 'COMPLETED')


# ── Context Processor Tests ────────────────────────────────

class ContextProcessorTest(TestCase):
    """Tests for the global context processor."""

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user('cpuser', password='pass1234')

    def test_unread_count_in_context(self):
        Notification.objects.create(
            recipient=self.user.profile,
            title='CP Test', message='Test',
            notification_type='SYSTEM',
        )
        self.client.login(username='cpuser', password='pass1234')
        response = self.client.get(reverse('home'))
        self.assertEqual(response.context['unread_notification_count'], 1)

    def test_user_role_in_context(self):
        self.client.login(username='cpuser', password='pass1234')
        response = self.client.get(reverse('home'))
        self.assertEqual(response.context['user_role'], 'tenant')
