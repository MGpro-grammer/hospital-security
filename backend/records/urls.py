from django.urls import path

from . import views

urlpatterns = [
    path("files", views.upload_file, name="upload-file"),
    path("files/<uuid:file_id>", views.get_file, name="get-file"),
    path("record/<str:patient_sub>", views.list_record, name="list-record"),
]