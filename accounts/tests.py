from unittest.mock import patch

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from .models import Announcement, BudgetCategory, Profile, PurchaseRequest, ResourceDocument


@override_settings(MEDIA_ROOT='/tmp/cio-budget-test-media')
class RoleAccessTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.member = User.objects.create_user(username='member', email='member@example.com')
        self.officer = User.objects.create_user(username='officer', email='officer@example.com')
        self.treasurer = User.objects.create_user(username='treasurer', email='treasurer@example.com')
        self.user_admin = User.objects.create_user(username='adminrole', email='useradmin@example.com')

        self.member.profile.role = Profile.ROLE_MEMBER
        self.member.profile.status = Profile.STATUS_ACTIVE
        self.member.profile.save()

        self.officer.profile.role = Profile.ROLE_OFFICER
        self.officer.profile.status = Profile.STATUS_ACTIVE
        self.officer.profile.save()

        self.treasurer.profile.role = Profile.ROLE_TREASURER
        self.treasurer.profile.status = Profile.STATUS_ACTIVE
        self.treasurer.profile.save()

        self.user_admin.profile.role = Profile.ROLE_USER_ADMIN
        self.user_admin.profile.status = Profile.STATUS_ACTIVE
        self.user_admin.profile.save()

        self.category = BudgetCategory.objects.create(name='Events', allocated_amount='500.00', created_by=self.treasurer)
        self.request_obj = PurchaseRequest.objects.create(
            title='Pizza for event',
            description='Food for club meeting',
            estimated_cost='60.00',
            category=self.category,
            requested_by=self.officer,
        )

    def test_treasurer_can_access_budget_category_create(self):
        self.client.force_login(self.treasurer)
        response = self.client.get(reverse('accounts:budget_category_create'))
        self.assertEqual(response.status_code, 200)

    def test_member_cannot_access_budget_category_create(self):
        self.client.force_login(self.member)
        response = self.client.get(reverse('accounts:budget_category_create'))
        self.assertEqual(response.status_code, 403)

    def test_officer_can_submit_purchase_request(self):
        self.client.force_login(self.officer)
        response = self.client.post(
            reverse('accounts:purchase_request_create'),
            {
                'title': 'Supplies',
                'description': 'Markers and paper',
                'estimated_cost': '25.00',
                'category': self.category.id,
                'receipt_link': '',
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(PurchaseRequest.objects.filter(title='Supplies', requested_by=self.officer).exists())

    def test_user_admin_only_role_management_access(self):
        self.client.force_login(self.user_admin)
        response = self.client.get(reverse('accounts:role_management'))
        self.assertEqual(response.status_code, 200)

    def test_user_admin_cannot_assign_admin_role(self):
        self.client.force_login(self.user_admin)
        response = self.client.post(
            reverse('accounts:role_management'),
            {'profile_id': self.member.profile.id, 'role': Profile.ROLE_USER_ADMIN},
        )
        self.assertEqual(response.status_code, 200)
        self.member.profile.refresh_from_db()
        self.assertEqual(self.member.profile.role, Profile.ROLE_MEMBER)

    def test_treasurer_can_review_purchase_request(self):
        self.client.force_login(self.treasurer)
        response = self.client.post(
            reverse('accounts:purchase_request_review', args=[self.request_obj.id]),
            {'status': PurchaseRequest.STATUS_APPROVED, 'reviewer_notes': 'Looks good'},
        )
        self.assertEqual(response.status_code, 302)
        self.request_obj.refresh_from_db()
        self.assertEqual(self.request_obj.status, PurchaseRequest.STATUS_APPROVED)

    def test_treasurer_can_change_membership_status(self):
        self.client.force_login(self.treasurer)
        response = self.client.post(
            reverse('accounts:membership_management'),
            {'profile_id': self.member.profile.id, 'status': Profile.STATUS_BANNED},
        )
        self.assertEqual(response.status_code, 302)
        self.member.profile.refresh_from_db()
        self.assertEqual(self.member.profile.status, Profile.STATUS_BANNED)

    def test_officer_can_upload_document(self):
        self.client.force_login(self.officer)
        upload = SimpleUploadedFile('agenda.txt', b'agenda contents', content_type='text/plain')
        response = self.client.post(
            reverse('accounts:document_upload'),
            {'title': 'Agenda', 'description': 'Weekly agenda', 'visibility': 'member', 'file': upload},
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(ResourceDocument.objects.filter(title='Agenda').exists())

    def test_member_can_reply_to_announcement(self):
        announcement = Announcement.objects.create(
            title='Meeting Reminder',
            body='Come to the meeting.',
            visibility='member',
            created_by=self.officer,
        )
        self.client.force_login(self.member)
        response = self.client.post(reverse('accounts:announcement_detail', args=[announcement.id]), {'body': 'I will be there.'})
        self.assertEqual(response.status_code, 302)
        announcement.refresh_from_db()
        self.assertEqual(announcement.replies.count(), 1)


class GoogleLoginFlowTests(TestCase):
    @patch('accounts.views.id_token.verify_oauth2_token')
    def test_first_google_user_becomes_active_treasurer(self, mock_verify):
        mock_verify.return_value = {
            'email': 'first@example.com',
            'given_name': 'First',
            'family_name': 'User',
            'picture': 'https://example.com/avatar.png',
        }
        response = self.client.post(reverse('accounts:auth_receiver'), {'credential': 'token'})
        self.assertEqual(response.status_code, 302)
        user = User.objects.get(email='first@example.com')
        self.assertEqual(user.profile.role, Profile.ROLE_TREASURER)
        self.assertEqual(user.profile.status, Profile.STATUS_ACTIVE)

    @patch('accounts.views.id_token.verify_oauth2_token')
    def test_google_login_reuses_primary_duplicate_email_account(self, mock_verify):
        primary = User.objects.create_user(username='primary', email='dup@example.com')
        duplicate = User.objects.create_user(username='duplicate', email='dup@example.com')
        primary.profile.status = Profile.STATUS_ACTIVE
        primary.profile.save()
        duplicate.profile.status = Profile.STATUS_ACTIVE
        duplicate.profile.save()

        mock_verify.return_value = {
            'sub': 'google-sub-123',
            'email': 'dup@example.com',
            'given_name': 'Dup',
            'family_name': 'User',
            'picture': 'https://example.com/dup.png',
        }

        response = self.client.post(reverse('accounts:auth_receiver'), {'credential': 'token'})
        self.assertEqual(response.status_code, 302)
        primary.refresh_from_db()
        duplicate.refresh_from_db()
        self.assertEqual(primary.profile.google_sub, 'google-sub-123')
        self.assertEqual(duplicate.profile.google_sub, None)
        self.assertEqual(int(self.client.session['_auth_user_id']), primary.id)

