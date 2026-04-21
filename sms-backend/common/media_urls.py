from __future__ import annotations

import re
from os.path import basename

from rest_framework import serializers


_STORAGE_SUFFIX_PATTERN = re.compile(
    r"^(?P<base>.+)_[A-Za-z0-9]{7}(?P<ext>\.[^./\\]+)$"
)


def build_absolute_media_url(request, value) -> str:
    url = extract_media_url(value)
    if not url:
        return ""
    if url.startswith(("http://", "https://")):
        return url
    if request is None:
        return url
    if not url.startswith("/"):
        url = f"/{url}"
    return request.build_absolute_uri(url)


def extract_media_url(value) -> str:
    if not value:
        return ""
    if isinstance(value, str):
        return value
    return str(getattr(value, "url", "") or "")


def display_media_name(value) -> str:
    if not value:
        return ""
    raw_name = getattr(value, "name", value)
    normalized = str(raw_name or "").replace("\\", "/")
    clean_name = basename(normalized)
    match = _STORAGE_SUFFIX_PATTERN.match(clean_name)
    if match:
        return f"{match.group('base')}{match.group('ext')}"
    return clean_name


def is_image_file(value, mime_type: str = "") -> bool:
    normalized_mime = str(mime_type or "").strip().lower()
    if normalized_mime.startswith("image/"):
        return True

    file_name = str(getattr(value, "name", value) or "").lower()
    return file_name.endswith(
        (".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp", ".svg", ".avif")
    )


class AbsoluteURLFileField(serializers.FileField):
    def to_representation(self, value):
        data = super().to_representation(value)
        return build_absolute_media_url(self.context.get("request"), data)
