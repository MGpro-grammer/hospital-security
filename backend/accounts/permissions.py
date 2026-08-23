"""Permissions DRF fondees sur le role porte par le jeton."""

from rest_framework.permissions import BasePermission


class IsPatient(BasePermission):
    """Autorise uniquement les utilisateurs du groupe Keycloak `patients`."""

    message = "Reserve aux patients."

    def has_permission(self, request, view):
        return bool(request.user and getattr(request.user, "is_patient", False))


class IsDoctor(BasePermission):
    """Autorise uniquement les utilisateurs du groupe Keycloak `doctors`."""

    message = "Reserve aux medecins."

    def has_permission(self, request, view):
        return bool(request.user and getattr(request.user, "is_doctor", False))