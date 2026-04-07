"""
Management command: seed_portal_accounts
Creates Django auth login accounts for all students and guardians in a tenant
so they can log in through the Student/Parent portals.

Safe to run multiple times — uses get_or_create.
"""
from django.core.management.base import BaseCommand
from django_tenants.utils import schema_context


class Command(BaseCommand):
    help = "Create portal login accounts for all students and guardians in a tenant schema."

    def add_arguments(self, parser):
        parser.add_argument(
            "--schema_name",
            type=str,
            default="demo_school",
            help="Tenant schema name to operate on",
        )

    def handle(self, *args, **options):
        schema = options["schema_name"]
        self.stdout.write(f"[seed_portal_accounts] Processing schema: {schema}")

        with schema_context(schema):
            from django.contrib.auth.models import User as DjangoUser
            from parent_portal.models import ParentStudentLink
            from school.models import Student, Guardian, Role, UserProfile

            student_role = Role.objects.filter(name="STUDENT").first()
            parent_role = Role.objects.filter(name="PARENT").first()

            if not student_role:
                self.stdout.write(self.style.WARNING("  STUDENT role not found — run seed_roles first"))
            if not parent_role:
                self.stdout.write(self.style.WARNING("  PARENT role not found — run seed_roles first"))

            # ── Students ─────────────────────────────────────────────────────
            student_created = 0
            student_updated = 0
            for student in Student.objects.filter(is_active=True):
                adm = student.admission_number
                user, created = DjangoUser.objects.get_or_create(
                    username=adm,
                    defaults={
                        "first_name": student.first_name,
                        "last_name": student.last_name,
                        "is_active": True,
                    },
                )
                if created:
                    user.set_password(adm)
                    user.save()
                    student_created += 1
                else:
                    # Ensure active and password set
                    if not user.is_active:
                        user.is_active = True
                        user.set_password(adm)
                        user.save()
                        student_updated += 1

                if student_role:
                    profile, _ = UserProfile.objects.get_or_create(
                        user=user,
                        defaults={"role": student_role, "admission_number": adm},
                    )
                    changed = False
                    if profile.role != student_role:
                        profile.role = student_role
                        changed = True
                    if profile.admission_number != adm:
                        profile.admission_number = adm
                        changed = True
                    if profile.force_password_change:
                        profile.force_password_change = False
                        changed = True
                    if changed:
                        profile.save()

            self.stdout.write(
                self.style.SUCCESS(
                    f"  Students: {student_created} created, {student_updated} updated"
                )
            )

            # ── Guardians / Parents ───────────────────────────────────────────
            parent_created = 0
            parent_updated = 0
            for guardian in Guardian.objects.filter(is_active=True):
                if guardian.email:
                    base = (
                        guardian.email.split("@")[0]
                        .lower()
                        .replace(".", "_")
                        .replace("+", "_")
                    )
                else:
                    base = (
                        (guardian.name or "parent")
                        .lower()
                        .replace(" ", "_")
                        .replace(".", "")
                    )
                username = base[:30]

                existing = DjangoUser.objects.filter(username=username).first()
                existing_profile = getattr(existing, "userprofile", None) if existing else None
                existing_role_name = getattr(getattr(existing_profile, "role", None), "name", None)
                if existing:
                    if guardian.email:
                        email_matches = (existing.email or "").strip().lower() == guardian.email.strip().lower()
                        if not email_matches and existing_role_name != "PARENT":
                            existing = None
                    elif existing_role_name != "PARENT":
                        existing = None
                if existing:
                    user = existing
                    created = False
                else:
                    # Ensure unique username
                    suffix = 0
                    candidate = username
                    while DjangoUser.objects.filter(username=candidate).exists():
                        suffix += 1
                        candidate = f"{username}{suffix}"
                    username = candidate

                    user = DjangoUser.objects.create(
                        username=username,
                        first_name=(guardian.name or "").split()[0] if guardian.name else "",
                        email=guardian.email or "",
                        is_active=True,
                    )
                    user.set_password("parent123")
                    user.save()
                    created = True
                    parent_created += 1

                if not created and not user.is_active:
                    user.is_active = True
                    user.save()
                    parent_updated += 1
                elif not created:
                    changed = False
                    desired_first_name = (guardian.name or "").split()[0] if guardian.name else ""
                    if desired_first_name and user.first_name != desired_first_name:
                        user.first_name = desired_first_name
                        changed = True
                    if guardian.email and user.email != guardian.email:
                        user.email = guardian.email
                        changed = True
                    if changed:
                        user.save()

                if parent_role:
                    require_password_change = created or user.check_password("parent123")
                    profile, _ = UserProfile.objects.get_or_create(
                        user=user,
                        defaults={
                            "role": parent_role,
                            "phone": guardian.phone or "",
                            "force_password_change": require_password_change,
                        },
                    )
                    changed = False
                    if profile.role != parent_role:
                        profile.role = parent_role
                        changed = True
                    if guardian.phone and not profile.phone:
                        profile.phone = guardian.phone
                        changed = True
                    if require_password_change and not profile.force_password_change:
                        profile.force_password_change = True
                        changed = True
                    if changed:
                        profile.save()

                link_defaults = {
                    "guardian": guardian,
                    "relationship": guardian.relationship or "",
                    "is_active": True,
                    "is_primary": not ParentStudentLink.objects.filter(
                        parent_user=user,
                        is_active=True,
                        is_primary=True,
                    ).exclude(student=guardian.student).exists(),
                }
                ParentStudentLink.objects.update_or_create(
                    parent_user=user,
                    student=guardian.student,
                    defaults=link_defaults,
                )

            self.stdout.write(
                self.style.SUCCESS(
                    f"  Parents: {parent_created} created, {parent_updated} updated"
                )
            )
            self.stdout.write(
                self.style.SUCCESS(
                    f"[seed_portal_accounts] Done for schema: {schema}"
                )
            )
