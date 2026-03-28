from decimal import Decimal

from django.contrib.auth.models import User
from django.db import models
from django.db.models import Sum
from django.db.models.signals import post_save
from django.dispatch import receiver


class Profile(models.Model):
    ROLE_MEMBER = 'member'
    ROLE_OFFICER = 'officer'
    ROLE_TREASURER = 'treasurer'
    ROLE_USER_ADMIN = 'user_admin'

    STATUS_PENDING = 'pending'
    STATUS_ACTIVE = 'active'
    STATUS_BANNED = 'banned'

    ROLE_CHOICES = [
        (ROLE_MEMBER, 'Member'),
        (ROLE_OFFICER, 'Officer'),
        (ROLE_TREASURER, 'Treasurer'),
        (ROLE_USER_ADMIN, 'User Administrator'),
    ]

    NON_ADMIN_ROLE_CHOICES = [
        (ROLE_MEMBER, 'Member'),
        (ROLE_OFFICER, 'Officer'),
        (ROLE_TREASURER, 'Treasurer'),
    ]

    STATUS_CHOICES = [
        (STATUS_PENDING, 'Pending Approval'),
        (STATUS_ACTIVE, 'Active'),
        (STATUS_BANNED, 'Banned'),
    ]

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default=ROLE_MEMBER)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)
    google_sub = models.CharField(max_length=255, blank=True, null=True, unique=True)
    google_picture_url = models.URLField(blank=True)
    profile_image = models.FileField(upload_to='profile-images/', blank=True, null=True)
    organization_name = models.CharField(max_length=150, blank=True)
    phone_number = models.CharField(max_length=30, blank=True)
    bio = models.TextField(blank=True)
    join_date = models.DateField(auto_now_add=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['user__email']

    def __str__(self):
        return f"{self.user.email or self.user.username} ({self.role})"

    @property
    def display_name(self):
        full_name = self.user.get_full_name().strip()
        return full_name or self.user.username

    @property
    def avatar_url(self):
        if self.profile_image:
            return self.profile_image.url
        return self.google_picture_url or ''

    @property
    def is_user_admin(self):
        return self.role == self.ROLE_USER_ADMIN

    @property
    def is_active_member(self):
        return self.status == self.STATUS_ACTIVE

    @property
    def role_label(self):
        return dict(self.ROLE_CHOICES).get(self.role, self.role)

    @property
    def status_label(self):
        return dict(self.STATUS_CHOICES).get(self.status, self.status)


class BudgetCategory(models.Model):
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    allocated_amount = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='created_budget_categories')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name

    @property
    def approved_total(self):
        total = self.purchase_requests.filter(status=PurchaseRequest.STATUS_APPROVED).aggregate(total=Sum('estimated_cost'))['total']
        return total or Decimal('0.00')

    @property
    def remaining_amount(self):
        return self.allocated_amount - self.approved_total


class PurchaseRequest(models.Model):
    STATUS_PENDING = 'pending'
    STATUS_APPROVED = 'approved'
    STATUS_DENIED = 'denied'

    STATUS_CHOICES = [
        (STATUS_PENDING, 'Pending'),
        (STATUS_APPROVED, 'Approved'),
        (STATUS_DENIED, 'Denied'),
    ]

    title = models.CharField(max_length=150)
    description = models.TextField()
    estimated_cost = models.DecimalField(max_digits=10, decimal_places=2)
    category = models.ForeignKey(BudgetCategory, on_delete=models.CASCADE, related_name='purchase_requests')
    requested_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='purchase_requests')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)
    reviewer_notes = models.TextField(blank=True)
    reviewed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='reviewed_purchase_requests')
    reviewed_at = models.DateTimeField(null=True, blank=True)
    receipt_link = models.URLField(blank=True)
    receipt_file = models.FileField(upload_to='receipts/', blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.title} ({self.get_status_display()})"


class Conversation(models.Model):
    participants = models.ManyToManyField(User, related_name='conversations')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        usernames = ', '.join(self.participants.values_list('username', flat=True))
        return f"Conversation: {usernames}"


class Message(models.Model):
    conversation = models.ForeignKey(Conversation, on_delete=models.CASCADE, related_name='messages')
    sender = models.ForeignKey(User, on_delete=models.CASCADE, related_name='sent_messages')
    body = models.TextField()
    sent_at = models.DateTimeField(auto_now_add=True)
    is_read = models.BooleanField(default=False)

    class Meta:
        ordering = ['sent_at']

    def __str__(self):
        return f"{self.sender.username}: {self.body[:30]}"


class VisibilityMixin(models.Model):
    VISIBILITY_MEMBER = 'member'
    VISIBILITY_OFFICER = 'officer'
    VISIBILITY_TREASURER = 'treasurer'

    VISIBILITY_CHOICES = [
        (VISIBILITY_MEMBER, 'Visible to all active members'),
        (VISIBILITY_OFFICER, 'Visible only to officers and treasurers'),
        (VISIBILITY_TREASURER, 'Visible only to treasurers'),
    ]

    visibility = models.CharField(max_length=20, choices=VISIBILITY_CHOICES, default=VISIBILITY_MEMBER)

    class Meta:
        abstract = True


class Announcement(VisibilityMixin):
    title = models.CharField(max_length=200)
    body = models.TextField()
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='announcements')
    is_pinned = models.BooleanField(default=False)
    is_locked = models.BooleanField(default=False)
    attachment = models.FileField(upload_to='announcements/', blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-is_pinned', '-created_at']

    def __str__(self):
        return self.title


class AnnouncementReply(models.Model):
    announcement = models.ForeignKey(Announcement, on_delete=models.CASCADE, related_name='replies')
    author = models.ForeignKey(User, on_delete=models.CASCADE, related_name='announcement_replies')
    body = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']

    def __str__(self):
        return f"Reply by {self.author.username}"


class ResourceDocument(VisibilityMixin):
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    file = models.FileField(upload_to='documents/')
    uploaded_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='uploaded_documents')
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-uploaded_at']

    def __str__(self):
        return self.title


@receiver(post_save, sender=User)
def create_profile_for_new_user(sender, instance, created, **kwargs):
    if created:
        Profile.objects.get_or_create(user=instance)
