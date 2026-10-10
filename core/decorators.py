from functools import wraps

from django.shortcuts import redirect


def therapist_required(view_func):
    """Allow access only to authenticated users with role 'therapist' or 'admin'."""

    @wraps(view_func)
    def _wrapped(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect("therapist_login")
        if not request.user.is_therapist:
            return redirect("therapist_login")
        return view_func(request, *args, **kwargs)

    return _wrapped
