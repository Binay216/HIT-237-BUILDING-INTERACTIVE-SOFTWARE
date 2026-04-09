from django import template

register = template.Library()


@register.filter
def status_class(status):
    """Return a CSS class name based on repair request status."""
    mapping = {
        'PENDING': 'status-pending',
        'IN_REVIEW': 'status-review',
        'IN_PROGRESS': 'status-progress',
        'COMPLETED': 'status-completed',
        'CANCELLED': 'status-cancelled',
    }
    return mapping.get(status, '')


@register.filter
def priority_class(priority):
    """Return a CSS class name based on priority level."""
    mapping = {
        'LOW': 'priority-low',
        'MEDIUM': 'priority-medium',
        'HIGH': 'priority-high',
        'EMERGENCY': 'priority-emergency',
    }
    return mapping.get(priority, '')


@register.inclusion_tag('components/status_badge.html')
def status_badge(status, display_text):
    """Render a status badge component."""
    return {
        'status': status,
        'display_text': display_text,
        'css_class': status_class(status),
    }


@register.inclusion_tag('components/priority_badge.html')
def priority_badge(priority, display_text):
    """Render a priority badge component."""
    return {
        'priority': priority,
        'display_text': display_text,
        'css_class': priority_class(priority),
    }


@register.filter
def days_label(days):
    """Return a human-readable label for number of days."""
    if days == 0:
        return 'Today'
    elif days == 1:
        return '1 day ago'
    return f'{days} days ago'
