from functools import wraps
from django.shortcuts import redirect
from django.contrib import messages


def login_required_with_message(view_func):
    """Redirect to login with a message if not authenticated."""
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            messages.warning(request, 'Please log in to access this page.')
            return redirect('login')
        return view_func(request, *args, **kwargs)
    return wrapper


def tenant_required(view_func):
    """Only allow tenants (non-staff) to access this view."""
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            messages.warning(request, 'Please log in to access this page.')
            return redirect('login')
        if not hasattr(request.user, 'profile'):
            messages.error(request, 'No profile found. Please contact admin.')
            return redirect('home')
        if request.user.profile.is_staff_member:
            messages.info(request, 'Staff members should use the staff dashboard.')
            return redirect('staff_dashboard')
        return view_func(request, *args, **kwargs)
    return wrapper


def staff_required(view_func):
    """Only allow maintenance staff to access this view."""
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            messages.warning(request, 'Please log in to access this page.')
            return redirect('login')
        if not hasattr(request.user, 'profile'):
            messages.error(request, 'No profile found. Please contact admin.')
            return redirect('home')
        if not request.user.profile.is_staff_member:
            messages.error(request, 'Access denied. Staff only.')
            return redirect('tenant_dashboard')
        return view_func(request, *args, **kwargs)
    return wrapper
