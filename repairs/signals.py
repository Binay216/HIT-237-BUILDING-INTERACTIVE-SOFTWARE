from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from django.contrib.auth.models import User

from .models import TenantProfile, RepairRequest, Notification


@receiver(post_save, sender=User)
def create_tenant_profile(sender, instance, created, **kwargs):
    """Auto-create a TenantProfile whenever a new User is created."""
    if created and not hasattr(instance, 'profile'):
        TenantProfile.objects.create(user=instance)


@receiver(pre_save, sender=RepairRequest)
def notify_on_status_change(sender, instance, **kwargs):
    """Create notifications when a repair request's status changes."""
    if not instance.pk:
        return
    try:
        old = RepairRequest.objects.get(pk=instance.pk)
    except RepairRequest.DoesNotExist:
        return

    if old.status != instance.status:
        Notification.objects.create(
            recipient=instance.tenant,
            title=f'Request "{instance.title}" updated',
            message=(
                f'Status changed from {old.get_status_display()} '
                f'to {instance.get_status_display()}.'
            ),
            notification_type='STATUS_CHANGE',
            related_request=instance,
        )
        if instance.assigned_to and instance.assigned_to != instance.tenant:
            Notification.objects.create(
                recipient=instance.assigned_to,
                title=f'Assigned request "{instance.title}" updated',
                message=f'Status changed to {instance.get_status_display()}.',
                notification_type='STATUS_CHANGE',
                related_request=instance,
            )
