"""
Phase 18 — Prompts 82-85: Performance optimization.
Add database indexes on frequently queried fields.

STRICT RULE: Do NOT change business logic. Focus on speed.

Targets:
  - students: is_active, admission_number (already unique, has btree), created_at
  - invoices: status, (student_id, status) composite
  - payments: payment_date, is_active
  - attendance_records: date, status
  - store_items: is_active, category_id (already FK, has btree)
  - behavior_incidents: student_id + date
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("school", "0044_phase16_rbac_permission_override"),
    ]

    operations = [
        # ── Student ──────────────────────────────────────────────────────────
        migrations.AddIndex(
            model_name="student",
            index=models.Index(
                fields=["is_active"],
                name="student_is_active_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="student",
            index=models.Index(
                fields=["created_at"],
                name="student_created_at_idx",
            ),
        ),
        # ── Invoice ───────────────────────────────────────────────────────────
        migrations.AddIndex(
            model_name="invoice",
            index=models.Index(
                fields=["status"],
                name="invoice_status_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="invoice",
            index=models.Index(
                fields=["student", "status"],
                name="invoice_student_status_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="invoice",
            index=models.Index(
                fields=["due_date"],
                name="invoice_due_date_idx",
            ),
        ),
        # ── Payment ───────────────────────────────────────────────────────────
        migrations.AddIndex(
            model_name="payment",
            index=models.Index(
                fields=["payment_date"],
                name="payment_date_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="payment",
            index=models.Index(
                fields=["is_active"],
                name="payment_is_active_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="payment",
            index=models.Index(
                fields=["student", "is_active"],
                name="payment_student_active_idx",
            ),
        ),
        # ── AttendanceRecord ─────────────────────────────────────────────────
        # unique_together('student','date') already creates a composite index;
        # add a standalone date index for range queries (e.g. heatmap, term reports)
        migrations.AddIndex(
            model_name="attendancerecord",
            index=models.Index(
                fields=["date"],
                name="attendance_date_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="attendancerecord",
            index=models.Index(
                fields=["status"],
                name="attendance_status_idx",
            ),
        ),
        # ── StoreItem ─────────────────────────────────────────────────────────
        migrations.AddIndex(
            model_name="storeitem",
            index=models.Index(
                fields=["is_active"],
                name="storeitem_is_active_idx",
            ),
        ),
        # ── Enrollment ────────────────────────────────────────────────────────
        migrations.AddIndex(
            model_name="enrollment",
            index=models.Index(
                fields=["status"],
                name="enrollment_status_idx",
            ),
        ),
    ]
