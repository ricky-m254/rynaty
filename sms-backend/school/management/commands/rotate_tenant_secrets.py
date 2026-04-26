from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = (
        "Re-encrypt tenant-scoped secrets with the current primary tenant secret key. "
        "Use this after adding a new DJANGO_TENANT_SECRET_KEYS primary value."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Report which secrets would rotate without writing changes.",
        )
        parser.add_argument(
            "--key-prefix",
            default="",
            help="Optionally rotate only secret rows whose key starts with this prefix.",
        )
        parser.add_argument(
            "--actor-username",
            default="",
            help="Optional Django username to attribute the rotation audit event to.",
        )

    def handle(self, *args, **options):
        from django.contrib.auth import get_user_model

        from school.models import TenantSecret
        from school.tenant_secrets import (
            current_secret_key_version,
            log_tenant_secret_audit,
            rotate_tenant_secret,
        )

        dry_run = bool(options["dry_run"])
        key_prefix = str(options.get("key_prefix") or "").strip()
        actor_username = str(options.get("actor_username") or "").strip()
        actor = None

        if actor_username:
            actor = get_user_model().objects.filter(username=actor_username).first()
            if actor is None:
                raise CommandError(f"Unknown actor username: {actor_username}")

        queryset = TenantSecret.objects.all().order_by("key")
        if key_prefix:
            queryset = queryset.filter(key__startswith=key_prefix)

        rotated = 0
        skipped = 0
        failures = []
        target_version = current_secret_key_version()

        self.stdout.write(
            f"[tenant-secrets] target_version={target_version} "
            f"dry_run={'yes' if dry_run else 'no'} "
            f"scope={key_prefix or 'all'}"
        )

        for secret in queryset.iterator():
            if secret.key_version == target_version:
                skipped += 1
                continue
            try:
                if dry_run:
                    # Decryptability check before reporting the planned rotation.
                    rotate_needed = True
                    from school.tenant_secrets import decrypt_secret

                    decrypt_secret(secret.ciphertext, secret.key_version)
                else:
                    rotate_needed = rotate_tenant_secret(secret)
                if rotate_needed:
                    rotated += 1
                    self.stdout.write(
                        f"[tenant-secrets] {'would rotate' if dry_run else 'rotated'} "
                        f"{secret.key} {secret.key_version} -> {target_version}"
                    )
            except Exception as exc:
                failures.append((secret.key, str(exc)))
                self.stderr.write(f"[tenant-secrets] failed {secret.key}: {exc}")

        self.stdout.write(
            self.style.SUCCESS(
                f"[tenant-secrets] complete rotated={rotated} skipped={skipped} failures={len(failures)}"
            )
        )

        audit_action = "SECRET_ROTATE_PREVIEW" if dry_run else "SECRET_ROTATE"
        details = (
            f"tenant secret rotation dry_run={dry_run} scope={key_prefix or 'all'} target_version={target_version} "
            f"rotated={rotated} skipped={skipped} failures={len(failures)} "
            f"actor={actor_username or 'system'}"
        )
        if failures:
            details = f"{details} failed_keys={','.join(key for key, _ in failures[:10])}"
        log_tenant_secret_audit(
            action=audit_action,
            object_id=key_prefix or "all",
            details=details,
            user=actor,
        )

        if failures:
            failure_keys = ", ".join(key for key, _ in failures[:10])
            raise CommandError(f"Failed to rotate {len(failures)} secret(s): {failure_keys}")
