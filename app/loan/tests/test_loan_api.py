"""
Test loan api
"""

import json

from django.contrib.auth import get_user_model
from django.test import override_settings
from django.urls import reverse
from django.utils import timezone

from rest_framework import status
from rest_framework.test import APIClient, APITestCase

from app import settings
from core.models import (Application, Deceased, Loan, Team, CommitteeApproval, Notification, )

from loan.serializers import (LoanSerializer, )

from decimal import Decimal


def get_detail_url(loan_id):
    """create the detail url"""
    return reverse('loans:loan-detail', args=[loan_id])


def create_application(user, **params):
    """create and return a new application object"""

    deceased = Deceased.objects.create(first_name="John", last_name="Doe")
    defaults = {
        'amount': 1000.00,
        'term': 12,

        'deceased': deceased,

    }
    defaults.update(params)
    application = Application.objects.create(user=user, **defaults)
    return application


def create_test_loan(user, application):
    # Now create a Loan
    loan = Loan.objects.create(
        application=application,
        amount_agreed=50000.00,
        fee_agreed=2000.00,
        term_agreed=12,
        approved_date=timezone.now(),
        is_settled=False,
        settled_date=None,
        # approved_by=user,
        # last_updated_by=user
    )
    return loan


class PublicLoanAPI(APITestCase):
    """Unauthenticated API tests"""

    def setUp(self):
        self.client = APIClient()
        self.LOANS_URL = reverse('loans:loan-list')

    def test_login_required(self):
        """test that login is required"""
        response = self.client.get(self.LOANS_URL)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_authenticated_non_staff_requests_returns_error(self):
        """Test that authentication is required for non-staff users"""
        user = get_user_model().objects.create_user(
            email='test@example.com',
            password='testpass'
        )
        self.client.force_authenticate(user=user)

        response = self.client.get(self.LOANS_URL)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)


class PrivateLoanAPI(APITestCase):
    """Test authenticated API tests"""

    def setUp(self):
        self.client = APIClient()
        self.LOANS_URL = reverse('loans:loan-list')
        self.user = get_user_model().objects.create_user(
            email='test@example.com',
            password='testpass',
            is_staff=True,
        )
        self.client.force_authenticate(user=self.user)

    def test_retrieve_loans(self):
        """test retrieving loans"""
        app1 = create_application(self.user)
        app2 = create_application(self.user)
        create_test_loan(self.user, app1)
        create_test_loan(self.user, app2)

        response = self.client.get(self.LOANS_URL)
        loans = Loan.objects.all().order_by('-id')
        serializer = LoanSerializer(loans, many=True)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['results'], serializer.data)

    def test_retrieve_loans_list_not_limited_to_authenticated_user(self):
        """Test retrieving loans for all users"""
        other_staff_user = get_user_model().objects.create_user(
            email='test1@example.com',
            password='testpass',
            is_staff=True,
        )
        app1 = create_application(self.user)
        app2 = create_application(other_staff_user)
        create_test_loan(self.user, app1)
        create_test_loan(other_staff_user, app2)

        response = self.client.get(self.LOANS_URL)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["results"]), 2)
        loans = Loan.objects.all().order_by('-id')
        serializer = LoanSerializer(loans, many=True)
        self.assertEqual(response.data["results"], serializer.data)

    def test_retrieve_loan_by_the_id(self):
        """test retrieving loan by id"""
        app1 = create_application(self.user)
        loan1 = create_test_loan(self.user, app1)
        loan_id = loan1.id
        url = get_detail_url(loan_id)
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        loan = Loan.objects.get(id=loan_id)
        serializer = LoanSerializer(loan)
        self.assertEqual(response.data, serializer.data)

    def test_retrieve_loan_created_by_other_user_success(self, ):
        """test retrieving loan created by other user by id is success"""
        other_user = get_user_model().objects.create_user(
            email='test2@example.com',
            password='testpass'
        )
        app = create_application(user=self.user)
        loan = create_test_loan(other_user, application=app)
        response = self.client.get(reverse('loans:loan-detail', args=[loan.id]))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        loan = Loan.objects.get(id=loan.id)
        serializer = LoanSerializer(loan)
        self.assertEqual(response.data, serializer.data)

    def test_delete_loan(self):
        """test deleting loan"""
        app = create_application(user=self.user)
        loan = create_test_loan(self.user, application=app)
        url = get_detail_url(loan.id)
        response = self.client.delete(url)
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Loan.objects.filter(id=loan.id).exists())

    def test_create_loan(self):
        """test creating loan"""
        data = {
            'application': create_application(self.user).id,
            'amount_agreed': 50000.00,
            'fee_agreed': 2000.00,
            'term_agreed': 12,
            'is_settled': False,

        }
        response = self.client.post(self.LOANS_URL, data)

        self.assertEqual(response.status_code, status.HTTP_201_CREATED, f"error: {response.data}")
        loan = Loan.objects.get(id=response.data['id'])
        serializer = LoanSerializer(loan)

        # Checking properties
        self.assertEqual(response.data, serializer.data)

        self.assertEqual(Decimal(serializer.data['amount_agreed']), Decimal(data['amount_agreed']))
        self.assertEqual(serializer.data['term_agreed'], data['term_agreed'])
        self.assertEqual(serializer.data['is_settled'], data['is_settled'])
        self.assertEqual(serializer.data['application'], data['application'])
        self.assertEqual(serializer.data['approved_by_email'], self.user.email)
        self.assertIsNotNone(serializer.data['approved_date'])
        self.assertFalse(serializer.data['is_settled'])
        self.assertIsNone(serializer.data['last_updated_by_email'])

    def test_needs_committee_approval_set_automatically(self):
        """Test that needs_committee_approval is set to True if amount_agreed >= 1,000,000"""
        # print("Test that needs_committee_approval is set to True if amount_agreed >= 1,000,000")
        data = {
            'application': create_application(self.user).id,
            'amount_agreed': settings.ADVANCEMENT_THRESHOLD_FOR_COMMITTEE_APPROVAL,  # threshold amount
            'fee_agreed': 2000.00,
            'term_agreed': 12,
            'is_settled': False,
        }
        response = self.client.post(self.LOANS_URL, data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        loan = Loan.objects.get(id=response.data['id'])
        self.assertTrue(loan.needs_committee_approval)

    def test_needs_committee_approval_set_to_false_below_threshold(self):
        """Test that needs_committee_approval is False if amount_agreed < 1,000,000"""
        # print("Test that needs_committee_approval is False if amount_agreed < 1,000,000")
        data = {
            'application': create_application(self.user).id,
            'amount_agreed': settings.ADVANCEMENT_THRESHOLD_FOR_COMMITTEE_APPROVAL - 100_000,  # below threshold
            'fee_agreed': 2000.00,
            'term_agreed': 12,
            'is_settled': False,
        }
        response = self.client.post(self.LOANS_URL, data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        loan = Loan.objects.get(id=response.data['id'])
        self.assertFalse(loan.needs_committee_approval)

    def test_committee_member_can_approve_loan(self):
        """Test that a committee member can approve a loan that requires committee approval"""
        # print("Test that a committee member can approve a loan that requires committee approval")

        # Create a loan with amount_agreed >= 1,000,000 to trigger committee approval
        data = {
            'application': create_application(self.user).id,
            'amount_agreed': settings.ADVANCEMENT_THRESHOLD_FOR_COMMITTEE_APPROVAL + 100_000,
            'fee_agreed': 2000.00,
            'term_agreed': 12,
            'is_settled': False,
        }
        response = self.client.post(self.LOANS_URL, data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        loan = Loan.objects.get(id=response.data['id'])

        # Simulate a committee member approving the loan
        committee_member = get_user_model().objects.create_user(
            email='damiansoch@hotmail.com',
            password='testpass',
            is_staff=True,
        )
        team = Team.objects.create(name="committee_members")
        committee_member.teams.set([team.id])  # Use .set() for many-to-many assignment
        self.client.force_authenticate(user=committee_member)

        approve_url = reverse('loans:loan-approve-loan', args=[loan.id])
        response = self.client.post(approve_url, {'approved': True})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Check if committee approval status is updated based on the threshold criteria
        loan.refresh_from_db()
        self.assertTrue(loan.is_committee_approved)

    def test_committee_member_can_reject_loan_with_reason(self):
        """Test that a committee member can reject a loan and must provide a rejection reason"""
        # print("Test that a committee member can reject a loan and must provide a rejection reason")

        # Create a loan with amount_agreed >= 1,000,000 to trigger committee approval
        data = {
            'application': create_application(self.user).id,
            'amount_agreed': settings.ADVANCEMENT_THRESHOLD_FOR_COMMITTEE_APPROVAL,
            'fee_agreed': 2000.00,
            'term_agreed': 12,
            'is_settled': False,
        }
        response = self.client.post(self.LOANS_URL, data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        loan = Loan.objects.get(id=response.data['id'])

        # Simulate a committee member rejecting the loan without a reason (should fail)
        committee_member = get_user_model().objects.create_user(
            email='damiansoch@hotmail.com',
            password='testpass',
            is_staff=True,
        )
        team = Team.objects.create(name="committee_members")
        committee_member.teams.set([team.id])  # Use .set() for many-to-many assignment
        self.client.force_authenticate(user=committee_member)

        approve_url = reverse('loans:loan-approve-loan', args=[loan.id])
        response = self.client.post(approve_url, {'approved': False})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        # Retry with a rejection reason
        response = self.client.post(approve_url, {'approved': False, 'rejection_reason': 'Insufficient collateral'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Ensure the loan is not committee-approved due to rejection
        loan.refresh_from_db()
        self.assertFalse(loan.is_committee_approved)

    def test_committee_approvements_status_no_interactions(self):
        """Test that the status message is 'No interactions recorded' when no approvals or rejections exist."""
        # print("Test that the status message is 'No interactions recorded' when no approvals or rejections exist.")
        loan_data = {
            'application': create_application(self.user).id,
            'amount_agreed': settings.ADVANCEMENT_THRESHOLD_FOR_COMMITTEE_APPROVAL + 100_000,
            'fee_agreed': 2000.00,
            'term_agreed': 12,
            'is_settled': False,
        }
        loan_response = self.client.post(self.LOANS_URL, loan_data)
        loan_instance = Loan.objects.get(id=loan_response.data['id'])

        self.assertEqual(loan_instance.committee_approvements_status, "No interactions recorded")

    def test_committee_approvements_status_with_approval(self):
        """Test that the status message reflects approvals by committee members."""
        # print("Test that the status message reflects approvals by committee members.")
        # Create loan that needs committee approval
        loan_data = {
            'application': create_application(self.user).id,
            'amount_agreed': settings.ADVANCEMENT_THRESHOLD_FOR_COMMITTEE_APPROVAL + 100_000,
            'fee_agreed': 2000.00,
            'term_agreed': 12,
            'is_settled': False,
        }
        loan_response = self.client.post(self.LOANS_URL, loan_data)
        loan_instance = Loan.objects.get(id=loan_response.data['id'])

        # Add a committee member and approve the loan
        approving_member = get_user_model().objects.create_user(
            email='committee@example.com',
            password='testpass',
            is_staff=True,
        )
        committee_team = Team.objects.create(name="committee_members")
        approving_member.teams.set([committee_team.id])
        CommitteeApproval.objects.create(loan=loan_instance, member=approving_member, approved=True)

        self.assertIsNotNone(loan_instance.committee_approvements_status)
        self.assertNotEqual(loan_instance.committee_approvements_status, "")

    def test_committee_approvements_status_with_rejection(self):
        """Test that the status message reflects rejections by committee members with reasons."""
        # print("Test that the status message reflects rejections by committee members with reasons.")
        # Create loan that needs committee approval
        loan_data = {
            'application': create_application(self.user).id,
            'amount_agreed': settings.ADVANCEMENT_THRESHOLD_FOR_COMMITTEE_APPROVAL + 100_000,
            'fee_agreed': 2000.00,
            'term_agreed': 12,
            'is_settled': False,
        }
        loan_response = self.client.post(self.LOANS_URL, loan_data)
        loan_instance = Loan.objects.get(id=loan_response.data['id'])

        # Add a committee member and reject the loan with a reason
        rejecting_member = get_user_model().objects.create_user(
            email='committee@example.com',
            password='testpass',
            is_staff=True,
        )
        committee_team = Team.objects.create(name="committee_members")
        rejecting_member.teams.set([committee_team.id])
        CommitteeApproval.objects.create(loan=loan_instance, member=rejecting_member, approved=False,
                                         rejection_reason="Not sufficient")

        self.assertIsNotNone(loan_instance.committee_approvements_status)
        self.assertNotEqual(loan_instance.committee_approvements_status, "")

    def test_committee_approvements_status_pending_responses(self):
        """Test that the status message includes pending committee members."""
        # print("Test that the status message includes pending committee members.")

        # Create loan that needs committee approval
        loan_data = {
            'application': create_application(self.user).id,
            'amount_agreed': settings.ADVANCEMENT_THRESHOLD_FOR_COMMITTEE_APPROVAL + 100_000,
            'fee_agreed': 2000.00,
            'term_agreed': 12,
            'is_settled': False,
        }
        loan_response = self.client.post(self.LOANS_URL, loan_data)
        loan_instance = Loan.objects.get(id=loan_response.data['id'])

        # Add two committee members, one approves and the other does not respond
        approving_member = get_user_model().objects.create_user(
            email='committee1@example.com',
            password='testpass',
            is_staff=True,
        )
        pending_member = get_user_model().objects.create_user(
            email='committee2@example.com',
            password='testpass',
            is_staff=True,
        )
        committee_team = Team.objects.create(name="committee_members")
        approving_member.teams.set([committee_team.id])
        pending_member.teams.set([committee_team.id])

        # First member approves
        CommitteeApproval.objects.create(loan=loan_instance, member=approving_member, approved=True)

        self.assertIsNotNone(loan_instance.committee_approvements_status)
        self.assertNotEqual(loan_instance.committee_approvements_status, "")

    def test_notification_created_on_loan_approval(self):
        """Test that a notification is created when a loan is approved by the committee"""
        # print("Test that a notification is created when a loan is approved by the committee")

        # Create a loan that requires committee approval
        data = {
            'application': create_application(self.user).id,
            'amount_agreed': settings.ADVANCEMENT_THRESHOLD_FOR_COMMITTEE_APPROVAL + 100_000,
            'fee_agreed': 2000.00,
            'term_agreed': 12,
            'is_settled': False,
        }
        response = self.client.post(self.LOANS_URL, data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        loan = Loan.objects.get(id=response.data['id'])

        # Simulate a committee member approving the loan
        committee_member = get_user_model().objects.create_user(
            email='damiansoch@hotmail.com',
            password='testpass',
            is_staff=True,
        )
        team = Team.objects.create(name="committee_members")
        committee_member.teams.set([team.id])  # Assign committee member to team
        self.client.force_authenticate(user=committee_member)

        # Approve the loan
        approve_url = reverse('loans:loan-approve-loan', args=[loan.id])
        response = self.client.post(approve_url, {'approved': True})
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Check that a notification was created
        notification = Notification.objects.filter(application=loan.application,
                                                   text__contains='has been approved').first()
        self.assertIsNotNone(notification)
        self.assertEqual(notification.text, f'Advancement: {loan.id} has been approved by committee members')
        self.assertFalse(notification.seen)
        self.assertEqual(notification.created_by, committee_member)
        self.assertEqual(notification.recipient, loan.application.assigned_to)

    def test_notification_created_on_loan_rejection(self):
        """Test that a notification is created when a loan is rejected by the committee"""
        # print("Test that a notification is created when a loan is rejected by the committee")

        # Create a loan that requires committee approval
        data = {
            'application': create_application(self.user).id,
            'amount_agreed': settings.ADVANCEMENT_THRESHOLD_FOR_COMMITTEE_APPROVAL + 100_000,
            'fee_agreed': 2000.00,
            'term_agreed': 12,
            'is_settled': False,
        }
        response = self.client.post(self.LOANS_URL, data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        loan = Loan.objects.get(id=response.data['id'])

        # Simulate a committee member rejecting the loan
        committee_member = get_user_model().objects.create_user(
            email='damiansoch@hotmail.com',
            password='testpass',
            is_staff=True,
        )
        team = Team.objects.create(name="committee_members")
        committee_member.teams.set([team.id])  # Assign committee member to team
        self.client.force_authenticate(user=committee_member)

        # Reject the loan with a reason
        reject_url = reverse('loans:loan-approve-loan', args=[loan.id])
        response = self.client.post(reject_url, {'approved': False, 'rejection_reason': 'Insufficient collateral'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Check that a notification was created
        notification = Notification.objects.filter(application=loan.application,
                                                   text__contains='has been rejected').first()
        self.assertIsNotNone(notification)
        self.assertEqual(notification.text, f'Advancement: {loan.id} has been rejected by committee members')
        self.assertFalse(notification.seen)
        self.assertEqual(notification.created_by, committee_member)
        self.assertEqual(notification.recipient, loan.application.assigned_to)

    # STEP BACK FUNCTIONALITY TESTING
    def test_committee_member_can_refer_loan_back_to_agent(self):
        """Test that a committee member can refer a loan back to the agent with a comment."""
        # Create a loan that requires committee approval
        application = create_application(self.user)
        loan = create_test_loan(self.user, application)
        application.approved = True
        application.save()

        # Simulate a committee member
        committee_member = get_user_model().objects.create_user(
            email='damiansoch@hotmail.com',
            password='testpass',
            is_staff=True,
        )
        team = Team.objects.create(name="committee_members")
        committee_member.teams.set([team.id])  # Assign committee member to the team
        self.client.force_authenticate(user=committee_member)

        # Refer back to agent with a comment
        refer_back_url = reverse('loans:loan-refer-back-to-agent', args=[loan.id])
        response = self.client.post(refer_back_url, {'comment': 'Incomplete documentation provided'})

        # Assert that the loan has been referred back
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Check that the loan has been deleted
        loan_exists = Loan.objects.filter(id=loan.id).exists()
        self.assertFalse(loan_exists, "Loan should have been deleted after being referred back to the agent.")

        # Check the application approved status
        application.refresh_from_db()
        self.assertFalse(application.approved, "Application should have been set to not approved.")

        # Check the response for the logged comment
        self.assertIn('comment', response.data)
        self.assertEqual(response.data['comment']['text'],
                         'Advancement referred back to the agent assigned. Reason: Incomplete documentation provided. User: damiansoch@hotmail.com')

    def test_refer_back_to_agent_fails_without_comment(self):
        """Test that referring a loan back to the agent fails if no comment is provided."""
        application = create_application(self.user)
        loan = create_test_loan(self.user, application)
        application.approved = True
        application.save()

        # Simulate a committee member
        committee_member = get_user_model().objects.create_user(
            email='committee_member@example.com',
            password='testpass',
            is_staff=True,
        )
        team = Team.objects.create(name="committee_members")
        committee_member.teams.set([team.id])  # Assign committee member to the team
        self.client.force_authenticate(user=committee_member)

        # Refer back without a comment
        refer_back_url = reverse('loans:loan-refer-back-to-agent', args=[loan.id])
        response = self.client.post(refer_back_url, {})

        # Assert that the response is a 400 error
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data['detail'], "A comment is required when referring back a loan.")

        # Ensure the loan is not deleted
        loan_exists = Loan.objects.filter(id=loan.id).exists()
        self.assertTrue(loan_exists, "Loan should not be deleted when comment is missing.")

    def test_non_committee_member_cannot_refer_back_to_agent(self):
        """Test that non-committee members cannot refer a loan back to the agent."""
        application = create_application(self.user)
        loan = create_test_loan(self.user, application)
        application.approved = True
        application.save()

        # Simulate a non-committee member
        non_committee_member = get_user_model().objects.create_user(
            email='non_committee_member@example.com',
            password='testpass',
            is_staff=True,
        )
        self.client.force_authenticate(user=non_committee_member)

        # Attempt to refer back to agent
        refer_back_url = reverse('loans:loan-refer-back-to-agent', args=[loan.id])
        response = self.client.post(refer_back_url, {'comment': 'Incomplete documentation provided'})

        # Assert that the response is a 403 error
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(response.data['detail'], "You are not authorized to perform this action.")

        # Ensure the loan is not deleted
        loan_exists = Loan.objects.filter(id=loan.id).exists()
        self.assertTrue(loan_exists, "Loan should not be deleted by non-committee members.")
