from django.urls import path

from . import views

urlpatterns = [
    path("health", views.health, name="health"),
    path("me", views.me, name="me"),
    path("users/keys", views.create_keys, name="create-keys"),
    path("users/keys/me", views.my_keys, name="my-keys"),
    path("profile", views.create_profile, name="create-profile"),
    path("profile/me", views.my_profile, name="my-profile"),
]