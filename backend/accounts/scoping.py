"""Who may see which children — in one place.

Before this module the answer was written out by hand in eleven places across
five apps, and the helper that reads a user's role was defined five times,
byte-identical. That is not a tidiness problem. This is the predicate standing
between one psychologist and another psychologist's case notes, and eleven
hand-maintained copies is eleven chances for the twelfth call site to be
written slightly differently, or to forget.

The rule itself is unchanged and deliberately narrow:

* Administrators and Staff see every child.
* A Psychologist sees only the children assigned to them.

`children` is imported inside the functions rather than at module scope: the
children app imports `accounts.permissions`, and a top-level import here would
close that circle.
"""
from accounts.models import Role


def role_of_user(user):
    """A user's role name, or None.

    Tolerates an anonymous user and a user with no role — both of which occur:
    an account awaiting approval has `role = None` by design.

    The request-shaped `role_of` below is what almost every caller wants; this
    exists for the background brief generator, which is handed a user rather
    than a request.
    """
    return getattr(getattr(user, "role", None), "role_name", None)


def role_of(request):
    """The requesting user's role name, or None."""
    return role_of_user(getattr(request, "user", None))


def visible_children(request):
    """The Child queryset this request is allowed to see."""
    from children.models import Child

    qs = Child.objects.all()
    if role_of(request) == Role.PSYCHOLOGIST:
        qs = qs.filter(assigned_psychologist=request.user)
    return qs


def scope_to_visible(qs, request, path="child"):
    """Narrow any child-related queryset to what this request may see.

    `path` is the lookup from the queryset's model to Child — "child" for a
    remark or a consent, and None for a queryset of children themselves.

    Returns the queryset untouched for Administrators and Staff, which is why
    this is safe to apply unconditionally at every call site: the caller no
    longer has to remember to write the role check as well.
    """
    if role_of(request) != Role.PSYCHOLOGIST:
        return qs
    field = "assigned_psychologist" if path is None else f"{path}__assigned_psychologist"
    return qs.filter(**{field: request.user})
