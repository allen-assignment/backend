import mimetypes
from uuid import uuid4
from django.conf import settings
from azure.storage.blob import BlobServiceClient, ContentSettings

def _client():
    return BlobServiceClient.from_connection_string(settings.AZURE_CONNECTION_STRING)

def _container_client():
    return _client().get_container_client(settings.AZURE_BLOB_CONTAINER)

def build_blob_name(merchant_id: int, filename: str) -> str:
    ext = (filename.rsplit(".", 1)[-1] if "." in filename else "bin").lower()
    return f"merchant/{merchant_id}/menu/{uuid4().hex}.{ext}"

def upload_file(merchant_id: int, file_obj):
    blob_name = build_blob_name(merchant_id, getattr(file_obj, "name", "upload.bin"))
    ctype, _ = mimetypes.guess_type(getattr(file_obj, "name", ""))
    ctype = ctype or getattr(file_obj, "content_type", "application/octet-stream")

    blob_client = _client().get_blob_client(settings.AZURE_BLOB_CONTAINER, blob_name)
    blob_client.upload_blob(
        file_obj,
        overwrite=True,
        content_settings=ContentSettings(content_type=ctype),
    )

    url = blob_client.url
    return { "url": url}
