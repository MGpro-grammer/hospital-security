from django.urls import path

from . import views

urlpatterns = [
    path("health", views.health, name="health"),
    path("me", views.me, name="me"),
    path("users/keys", views.create_keys, name="create-keys"),
    path("users/keys/me", views.my_keys, name="my-keys"),
    path("profile", views.create_profile, name="create-profile"),
    path("profile/me", views.my_profile, name="my-profile"),
    path("doctors", views.list_doctors, name="list-doctors"),
    path("patients", views.list_patients, name="list-patients"),
    path("links", views.list_links, name="list-links"),
    path("links/create", views.create_link, name="create-link"),
    path("links/<int:link_id>/approve", views.approve_link, name="approve-link"),
    path("links/<int:link_id>", views.delete_link, name="delete-link"),
]