from .models import Notification


def global_context(request):
    """Provide user role and notification count to every template."""
    context = {}
    if request.user.is_authenticated and hasattr(request.user, 'profile'):
        profile = request.user.profile
        context['user_role'] = 'staff' if profile.is_staff_member else 'tenant'
        context['user_profile'] = profile
        context['unread_notification_count'] = Notification.objects.filter(
            recipient=profile, is_read=False
        ).count()
    return context
