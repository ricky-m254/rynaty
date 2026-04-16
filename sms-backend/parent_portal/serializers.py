from django.contrib.auth import get_user_model
from rest_framework import serializers
from .models import ParentStudentLink

User = get_user_model()


class ParentProfileSerializer(serializers.ModelSerializer):
    force_password_change = serializers.SerializerMethodField()
    phone = serializers.SerializerMethodField()
    photo_url = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            "id",
            "username",
            "first_name",
            "last_name",
            "email",
            "phone",
            "photo_url",
            "is_active",
            "date_joined",
            "force_password_change",
        ]
        read_only_fields = ["id", "username", "is_active", "date_joined"]

    def get_force_password_change(self, obj):
        profile = getattr(obj, "userprofile", None)
        return bool(getattr(profile, "force_password_change", False))

    def get_phone(self, obj):
        profile = getattr(obj, "userprofile", None)
        return getattr(profile, "phone", "") or ""

    def get_photo_url(self, obj):
        profile = getattr(obj, "userprofile", None)
        if profile and profile.photo:
            request = self.context.get("request")
            try:
                if request:
                    return request.build_absolute_uri(profile.photo.url)
                return profile.photo.url
            except Exception:
                pass
        return None

    def update(self, instance, validated_data):
        for field in ("first_name", "last_name", "email"):
            if field in validated_data:
                setattr(instance, field, validated_data[field])
        instance.save(update_fields=[f for f in ("first_name", "last_name", "email") if f in validated_data] or ["first_name"])
        return instance


class ParentStudentLinkSerializer(serializers.ModelSerializer):
    parent_username = serializers.CharField(source="parent_user.username", read_only=True)
    student_name = serializers.SerializerMethodField()
    guardian_name = serializers.CharField(source="guardian.name", read_only=True)

    class Meta:
        model = ParentStudentLink
        fields = [
            "id",
            "parent_user",
            "parent_username",
            "student",
            "student_name",
            "guardian",
            "guardian_name",
            "relationship",
            "is_primary",
            "is_active",
            "created_at",
        ]
        read_only_fields = ["id", "created_at", "parent_username", "student_name", "guardian_name"]

    def get_student_name(self, obj):
        return f"{obj.student.first_name} {obj.student.last_name}".strip()
