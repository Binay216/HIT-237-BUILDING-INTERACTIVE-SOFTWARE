class ProfileEnforcementMiddleware:
    """
    Ensure every authenticated user has a TenantProfile.
    Handles edge cases like superusers created via createsuperuser.
    """

    EXEMPT_PREFIXES = ['/admin/', '/login/', '/logout/', '/register/']

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if (
            request.user.is_authenticated
            and not hasattr(request.user, 'profile')
            and not any(request.path.startswith(p) for p in self.EXEMPT_PREFIXES)
        ):
            from .models import TenantProfile
            TenantProfile.objects.get_or_create(
                user=request.user,
                defaults={'is_staff_member': request.user.is_staff}
            )
            # Clear cached profile lookup so it's fresh
            try:
                del request.user.__dict__['profile']
            except KeyError:
                pass
        return self.get_response(request)
