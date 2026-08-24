from django.urls import path

from . import views

urlpatterns = [
    path("files", views.upload_file, name="upload-file"),
    path("files/<uuid:file_id>", views.get_file, name="get-file"),
    path("files/<uuid:file_id>/approve", views.approve_file, name="approve-file"),
    path("files/<uuid:file_id>/reject", views.reject_file, name="reject-file"),
    path("files/<uuid:file_id>/request-deletion", views.request_deletion, name="request-deletion"),
    path("files/<uuid:file_id>/keep", views.keep_file, name="keep-file"),
    path("files/<uuid:file_id>/delete", views.delete_file, name="delete-file"),
    path("record/<str:patient_sub>", views.list_record, name="list-record"),
]