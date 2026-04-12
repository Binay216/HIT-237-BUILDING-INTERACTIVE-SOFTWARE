"""
Custom access-control mixins for class-based views.

These mixins replace the function-based decorators (@staff_required,
@tenant_required) with a composable, object-oriented equivalent that
plugs into Django's CBV dispatch chain via the standard
AccessMixin pattern.
"""

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import redirect


class LoginRequiredWithMessageMixin(LoginRequiredMixin):
    """Redirect to login with a user-friendly flash message."""

    login_url = 'login'

    def handle_no_permission(self):
        messages.warning(self.request, 'Please log in to access this page.')
        return redirect(self.login_url)


class StaffRequiredMixin(LoginRequiredWithMessageMixin):
    """Only allow maintenance staff to access this view."""

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()
        if not hasattr(request.user, 'profile'):
            messages.error(request, 'No profile found. Please contact admin.')
            return redirect('home')
        if not request.user.profile.is_staff_member:
            messages.error(request, 'Access denied. Staff only.')
            return redirect('tenant_dashboard')
        return super().dispatch(request, *args, **kwargs)


class TenantRequiredMixin(LoginRequiredWithMessageMixin):
    """Only allow tenants (non-staff) to access this view."""

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()
        if not hasattr(request.user, 'profile'):
            messages.error(request, 'No profile found. Please contact admin.')
            return redirect('home')
        if request.user.profile.is_staff_member:
            messages.info(request, 'Staff members should use the staff dashboard.')
            return redirect('staff_dashboard')
        return super().dispatch(request, *args, **kwargs)
