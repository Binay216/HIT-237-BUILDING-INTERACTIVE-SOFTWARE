from django.contrib.auth.models import User
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.urls import reverse
from django.utils import timezone

from .managers import RepairRequestManager


class Community(models.Model):
    """Represents a remote NT community."""

    REGION_CHOICES = [
        ('TOP_END', 'Top End'),
        ('CENTRAL', 'Central Australia'),
        ('BARKLY', 'Barkly'),
        ('BIG_RIVERS', 'Big Rivers'),
        ('EAST_ARNHEM', 'East Arnhem'),
    ]

    name = models.CharField(max_length=100)
    region = models.CharField(max_length=20, choices=REGION_CHOICES)
    population = models.PositiveIntegerField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name_plural = 'communities'
        ordering = ['name']

    def __str__(self):
        return f"{self.name} ({self.get_region_display()})"

    @property
    def dwelling_count(self):
        return self.dwellings.count()

    @property
    def active_request_count(self):
        """Total active repair requests across all dwellings in this community."""
        return RepairRequest.objects.filter(
            dwelling__community=self
        ).active().count()


class Dwelling(models.Model):
    """A house or property within a remote community."""

    DWELLING_TYPES = [
        ('HOUSE', 'House'),
        ('UNIT', 'Unit'),
        ('DUPLEX', 'Duplex'),
        ('TOWN_CAMP', 'Town Camp Dwelling'),
    ]

    address = models.CharField(max_length=200)
    community = models.ForeignKey(
        Community, on_delete=models.CASCADE, related_name='dwellings'
    )
    dwelling_type = models.CharField(max_length=20, choices=DWELLING_TYPES)
    bedrooms = models.PositiveIntegerField()
    year_built = models.PositiveIntegerField(blank=True, null=True)
    meets_ncc_standards = models.BooleanField(
        default=False,
        verbose_name='Meets National Construction Code standards'
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['community', 'address']

    def __str__(self):
        return f"{self.address}, {self.community.name}"

    def active_repair_count(self):
        """Number of open or active repair requests for this dwelling."""
        return self.repair_requests.active().count()

    def maintenance_history(self):
        """Return completed repair requests for this dwelling, newest first."""
        return self.repair_requests.completed().order_by('-completed_at')

    def is_overcrowded(self, occupant_count):
        """
        Check whether the dwelling is overcrowded based on the
        Canadian National Occupancy Standard.
        """
        maximum_occupants = self.bedrooms * 2
        return occupant_count > maximum_occupants

    @property
    def compliance_status(self):
        return (
            "Compliant with NCC Standards"
            if self.meets_ncc_standards
            else "Does NOT meet NCC Standards"
        )

    @property
    def total_requests(self):
        return self.repair_requests.count()


class TenantProfile(models.Model):
    """Extends the Django User model with tenant-specific information."""

    user = models.OneToOneField(
        User, on_delete=models.CASCADE, related_name='profile'
    )
    phone = models.CharField(max_length=20, blank=True)
    dwelling = models.ForeignKey(
        Dwelling,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='tenants'
    )
    is_staff_member = models.BooleanField(
        default=False,
        verbose_name='Maintenance staff member'
    )
    date_joined_community = models.DateField(blank=True, null=True)

    def __str__(self):
        role = "Staff" if self.is_staff_member else "Tenant"
        return f"{self.full_name} ({role})"

    @property
    def full_name(self):
        full_name = f"{self.user.first_name} {self.user.last_name}".strip()
        return full_name or self.user.username

    @property
    def open_requests(self):
        """Return this tenant's active requests."""
        return RepairRequest.objects.filter(tenant=self).active()

    @property
    def completed_requests(self):
        return RepairRequest.objects.filter(tenant=self).completed()

    @property
    def is_tenant(self):
        return not self.is_staff_member


class RepairRequest(models.Model):
    """
    Core model for a housing repair request submitted by a tenant.
    Business logic is handled within the model.
    """

    ISSUE_TYPES = [
        ('AC', 'Air Conditioning'),
        ('PLUMBING', 'Plumbing'),
        ('ELECTRICAL', 'Electrical'),
        ('DOOR_LOCK', 'Door / Lock'),
        ('ROOF', 'Roof / Ceiling'),
        ('STRUCTURAL', 'Structural'),
        ('PEST', 'Pest Control'),
        ('OTHER', 'Other'),
    ]

    PRIORITY_CHOICES = [
        ('LOW', 'Low'),
        ('MEDIUM', 'Medium'),
        ('HIGH', 'High'),
        ('EMERGENCY', 'Emergency'),
    ]

    STATUS_CHOICES = [
        ('PENDING', 'Pending'),
        ('IN_REVIEW', 'In Review'),
        ('IN_PROGRESS', 'In Progress'),
        ('COMPLETED', 'Completed'),
        ('CANCELLED', 'Cancelled'),
    ]

    LOCATION_CHOICES = [
        ('KITCHEN', 'Kitchen'),
        ('BATHROOM', 'Bathroom'),
        ('BEDROOM', 'Bedroom'),
        ('LIVING', 'Living Room'),
        ('LAUNDRY', 'Laundry'),
        ('EXTERNAL', 'External / Yard'),
        ('WHOLE', 'Whole House'),
        ('OTHER', 'Other'),
    ]

    tenant = models.ForeignKey(
        TenantProfile, on_delete=models.CASCADE, related_name='requests'
    )
    dwelling = models.ForeignKey(
        Dwelling, on_delete=models.CASCADE, related_name='repair_requests'
    )
    title = models.CharField(max_length=150)
    description = models.TextField()
    issue_type = models.CharField(max_length=20, choices=ISSUE_TYPES)
    priority = models.CharField(
        max_length=20, choices=PRIORITY_CHOICES, default='MEDIUM'
    )
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default='PENDING'
    )
    location_in_dwelling = models.CharField(
        max_length=20, choices=LOCATION_CHOICES, default='OTHER'
    )
    image = models.FileField(upload_to='repairs/%Y/%m/', blank=True, null=True)
    assigned_to = models.ForeignKey(
        TenantProfile,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='assigned_requests'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    completed_at = models.DateTimeField(blank=True, null=True)

    objects = RepairRequestManager()

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.title} [{self.get_status_display()}]"

    def get_absolute_url(self):
        return reverse('request_detail', kwargs={'pk': self.pk})

    def mark_in_review(self):
        """Move the request to in-review status."""
        self.status = 'IN_REVIEW'
        self.save(update_fields=['status', 'updated_at'])

    def mark_in_progress(self, staff_profile):
        """Assign the request to a staff member and mark it in progress."""
        self.status = 'IN_PROGRESS'
        self.assigned_to = staff_profile
        self.save(update_fields=['status', 'assigned_to', 'updated_at'])

    def mark_completed(self):
        """Mark the request as completed and record the completion time."""
        self.status = 'COMPLETED'
        self.completed_at = timezone.now()
        self.save(update_fields=['status', 'completed_at', 'updated_at'])

    def cancel(self):
        """Cancel the repair request."""
        self.status = 'CANCELLED'
        self.save(update_fields=['status', 'updated_at'])

    def is_overdue(self, days=14):
        """Return True if the request has been pending longer than the limit."""
        if self.status != 'PENDING':
            return False
        return (timezone.now() - self.created_at).days > days

    @property
    def days_open(self):
        """Return the number of days the request has been open."""
        end_time = self.completed_at or timezone.now()
        duration = end_time - self.created_at
        return duration.days

    @property
    def is_active(self):
        inactive_statuses = {'COMPLETED', 'CANCELLED'}
        return self.status not in inactive_statuses

    @property
    def can_edit(self):
        """Tenants can only edit pending requests."""
        return self.status == 'PENDING'


class MaintenanceLog(models.Model):
    """Tracks updates and notes on a repair request."""

    repair_request = models.ForeignKey(
        RepairRequest, on_delete=models.CASCADE, related_name='logs'
    )
    author = models.ForeignKey(
        TenantProfile, on_delete=models.CASCADE, related_name='maintenance_logs'
    )
    note = models.TextField()
    status_change = models.CharField(
        max_length=20,
        choices=RepairRequest.STATUS_CHOICES,
        blank=True,
        null=True
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Log by {self.author} on {self.repair_request.title}"


class Notification(models.Model):
    """In-app notification for tenants and staff."""

    NOTIFICATION_TYPES = [
        ('STATUS_CHANGE', 'Status Change'),
        ('NEW_ASSIGNMENT', 'New Assignment'),
        ('FEEDBACK_RECEIVED', 'Feedback Received'),
        ('SYSTEM', 'System'),
    ]

    recipient = models.ForeignKey(
        TenantProfile, on_delete=models.CASCADE, related_name='notifications'
    )
    title = models.CharField(max_length=200)
    message = models.TextField()
    notification_type = models.CharField(
        max_length=20, choices=NOTIFICATION_TYPES, default='SYSTEM'
    )
    related_request = models.ForeignKey(
        RepairRequest,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='notifications'
    )
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.title} → {self.recipient}"

    def mark_read(self):
        """Mark the notification as read."""
        self.is_read = True
        self.save(update_fields=['is_read'])


class RepairFeedback(models.Model):
    """Tenant feedback and rating for a completed repair."""

    repair_request = models.OneToOneField(
        RepairRequest, on_delete=models.CASCADE, related_name='feedback'
    )
    tenant = models.ForeignKey(
        TenantProfile, on_delete=models.CASCADE, related_name='feedbacks'
    )
    rating = models.PositiveIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)]
    )
    comment = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.rating}/5 for {self.repair_request.title}"