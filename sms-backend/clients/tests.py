import json
from datetime import timedelta
from unittest.mock import patch, MagicMock

from django.core.management import call_command
from django.core.files.uploadedfile import SimpleUploadedFile
from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIRequestFactory, force_authenticate

from clients.models import (
    BackupJob,
    BackupExecutionRun,
    DeploymentHookRun,
    DeploymentRelease,
    Domain,
    FeatureFlag,
    GlobalSuperAdmin,
    SubscriptionInvoice,
    SubscriptionPayment,
    SubscriptionPlan,
    TenantSubscription,
    ImpersonationSession,
    MaintenanceWindow,
    MonitoringAlert,
    MonitoringSnapshot,
    PlatformApiKey,
    PlatformNotificationDispatch,
    PlatformActionLog,
    PlatformSetting,
    RestoreJob,
    SupportTicket,
    TenantDataImportFile,
    TenantDataImportRequest,
    Tenant,
)
from clients.platform_views import (
    PlatformActionLogViewSet,
    PlatformAnalyticsViewSet,
    PlatformBackupJobViewSet,
    PlatformDeploymentReleaseViewSet,
    PlatformFeatureFlagViewSet,
    PlatformImpersonationSessionViewSet,
    PlatformMaintenanceWindowViewSet,
    PlatformMonitoringAlertViewSet,
    PlatformAdminUserViewSet,
    PlatformApiKeyViewSet,
    PlatformIntegrationViewSet,
    PlatformSettingViewSet,
    PlatformRestoreJobViewSet,
    PlatformSupportTicketViewSet,
    PlatformSubscriptionInvoiceViewSet,
    PlatformSubscriptionPaymentViewSet,
    PlatformSubscriptionPaymentMpesaCallbackView,
    PlatformTenantDataImportRequestViewSet,
)
from clients.platform_urls import platform_login_view

User = get_user_model()


class PlatformStep4HardeningTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.tenant = Tenant.objects.create(
            schema_name="platform_step4",
            name="Platform Step4 School",
            paid_until="2030-01-01",
            is_active=True,
        )
        Domain.objects.create(domain="platform-step4.localhost", tenant=cls.tenant, is_primary=True)

    def setUp(self):
        self.factory = APIRequestFactory()
        self.admin = User.objects.create_user(username="platform_admin", password="test123")
        self.second_admin = User.objects.create_user(username="platform_admin_2", password="test123")
        self.requester = User.objects.create_user(username="platform_requester", password="test123")
        self.assignee = User.objects.create_user(username="support_agent", password="test123")
        GlobalSuperAdmin.objects.create(user=self.admin, is_active=True)
        GlobalSuperAdmin.objects.create(user=self.second_admin, is_active=True)
        GlobalSuperAdmin.objects.create(user=self.requester, is_active=True)

    def test_platform_login_self_heals_missing_public_admin_account(self):
        GlobalSuperAdmin.objects.filter(user__username="platform_admin")._raw_delete(GlobalSuperAdmin.objects.db)
        User.objects.filter(username="platform_admin")._raw_delete(User.objects.db)

        request = self.factory.post(
            "/api/platform/auth/login/",
            {"username": "platform_admin", "password": "PlatformAdmin#2025"},
            format="json",
        )
        response = platform_login_view(request)

        self.assertEqual(response.status_code, 200)
        payload = json.loads(response.content.decode("utf-8"))
        self.assertEqual(payload["role"], GlobalSuperAdmin.ROLE_OWNER)
        self.assertEqual(payload["redirect_to"], "/platform")
        self.assertEqual(payload["tenant_id"], "public")
        self.assertTrue(User.objects.filter(username="platform_admin", is_active=True).exists())

    def test_platform_login_accepts_riqs_alias_without_trailing_period(self):
        riqs_user = User.objects.create_user(username="Riqs#.", password="Ointment.54.#")
        GlobalSuperAdmin.objects.create(user=riqs_user, role=GlobalSuperAdmin.ROLE_OWNER, is_active=True)

        request = self.factory.post(
            "/api/platform/auth/login/",
            {"username": "Riqs#", "password": "Ointment.54.#"},
            format="json",
        )
        response = platform_login_view(request)

        self.assertEqual(response.status_code, 200)
        payload = json.loads(response.content.decode("utf-8"))
        self.assertEqual(payload["role"], GlobalSuperAdmin.ROLE_OWNER)
        self.assertEqual(payload["redirect_to"], "/platform")
        self.assertEqual(payload["tenant_id"], "public")

    def test_platform_login_accepts_exact_riqs_username(self):
        riqs_user = User.objects.create_user(username="Riqs#", password="Ointment.54.#")
        GlobalSuperAdmin.objects.create(user=riqs_user, role=GlobalSuperAdmin.ROLE_OWNER, is_active=True)

        request = self.factory.post(
            "/api/platform/auth/login/",
            {"username": "Riqs#", "password": "Ointment.54.#"},
            format="json",
        )
        response = platform_login_view(request)

        self.assertEqual(response.status_code, 200)
        payload = json.loads(response.content.decode("utf-8"))
        self.assertEqual(payload["role"], GlobalSuperAdmin.ROLE_OWNER)
        self.assertEqual(payload["redirect_to"], "/platform")
        self.assertEqual(payload["tenant_id"], "public")

    def test_data_import_request_create_and_attach_files(self):
        create_request = self.factory.post(
            "/api/platform/data-import-requests/",
            {
                "tenant": self.tenant.id,
                "import_profile": TenantDataImportRequest.PROFILE_LEGACY_WORKBOOK_BUNDLE,
                "source_system": "Legacy workbook bundle",
                "source_reference": "April handoff",
                "files": [
                    SimpleUploadedFile(
                        "Transact 2026_Backup.xlsx",
                        b"sheet-a",
                        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    )
                ],
            },
            format="multipart",
        )
        force_authenticate(create_request, user=self.admin)
        create_response = PlatformTenantDataImportRequestViewSet.as_view({"post": "create"})(create_request)

        self.assertEqual(create_response.status_code, 201)
        self.assertEqual(create_response.data["status"], TenantDataImportRequest.STATUS_READY)
        self.assertEqual(create_response.data["files_total"], 1)
        self.assertIn("Transact 2023_Backup.xlsx", create_response.data["missing_required_files"])
        self.assertEqual(create_response.data["command_preview"], "")

        request_id = create_response.data["id"]
        attach_request = self.factory.post(
            f"/api/platform/data-import-requests/{request_id}/attach-files/",
            {
                "files": [
                    SimpleUploadedFile(
                        "Transact 2023_Backup.xlsx",
                        b"sheet-b",
                        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    )
                ]
            },
            format="multipart",
        )
        force_authenticate(attach_request, user=self.admin)
        attach_response = PlatformTenantDataImportRequestViewSet.as_view({"post": "attach_files"})(
            attach_request,
            pk=request_id,
        )

        self.assertEqual(attach_response.status_code, 200)
        self.assertEqual(attach_response.data["files_total"], 2)
        self.assertTrue(attach_response.data["automation_ready"])
        self.assertIn("run_platform_data_import_request --request-id", attach_response.data["command_preview"])

    def test_run_platform_data_import_request_marks_request_completed(self):
        import_request = TenantDataImportRequest.objects.create(
            tenant=self.tenant,
            import_profile=TenantDataImportRequest.PROFILE_LEGACY_WORKBOOK_BUNDLE,
            status=TenantDataImportRequest.STATUS_READY,
            requested_by=self.admin,
            archive_raw_to_media=True,
        )
        for file_name, payload in (
            ("Transact 2023_Backup.xlsx", b"payload-2023"),
            ("Transact 2026_Backup.xlsx", b"payload-2026"),
        ):
            TenantDataImportFile.objects.create(
                import_request=import_request,
                file=SimpleUploadedFile(
                    file_name,
                    payload,
                    content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                ),
                original_name=file_name,
                content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                size_bytes=len(payload),
                checksum_sha256="a" * 64,
                uploaded_by=self.admin,
            )

        def fake_import_command(name, **kwargs):
            self.assertEqual(name, "import_olom_legacy_data")
            self.assertEqual(kwargs["schema_name"], self.tenant.schema_name)
            self.assertTrue(kwargs["archive_raw"])
            kwargs["stdout"].write(json.dumps({"students_created": 2, "payments_created": 4}))

        with patch("clients.management.commands.run_platform_data_import_request.call_command") as mocked_call:
            mocked_call.side_effect = fake_import_command
            call_command("run_platform_data_import_request", request_id=import_request.id)

        import_request.refresh_from_db()
        self.assertEqual(import_request.status, TenantDataImportRequest.STATUS_COMPLETED)
        self.assertEqual(import_request.result_payload["command"], "import_olom_legacy_data")
        self.assertEqual(import_request.result_payload["import_summary"]["students_created"], 2)

    def test_support_ticket_forbids_closing_before_resolve(self):
        create_request = self.factory.post(
            "/api/platform/support-tickets/",
            {
                "tenant": self.tenant.id,
                "category": SupportTicket.CATEGORY_TECHNICAL,
                "priority": SupportTicket.PRIORITY_NORMAL,
                "status": SupportTicket.STATUS_CLOSED,
                "subject": "Printer issue",
                "description": "Lab printer offline",
                "assigned_to": self.assignee.id,
            },
            format="json",
        )
        force_authenticate(create_request, user=self.admin)
        create_response = PlatformSupportTicketViewSet.as_view({"post": "create"})(create_request)
        self.assertEqual(create_response.status_code, 201)
        self.assertEqual(create_response.data["status"], SupportTicket.STATUS_OPEN)
        self.assertIsNone(create_response.data["assigned_to"])

        ticket_id = create_response.data["id"]
        close_request = self.factory.post(f"/api/platform/support-tickets/{ticket_id}/close/", {}, format="json")
        force_authenticate(close_request, user=self.admin)
        close_response = PlatformSupportTicketViewSet.as_view({"post": "close"})(close_request, pk=ticket_id)
        self.assertEqual(close_response.status_code, 400)

    def test_support_ticket_resolve_then_close(self):
        ticket = SupportTicket.objects.create(
            ticket_number="TKT-TEST-0001",
            tenant=self.tenant,
            category=SupportTicket.CATEGORY_TECHNICAL,
            priority=SupportTicket.PRIORITY_HIGH,
            status=SupportTicket.STATUS_OPEN,
            subject="WiFi issue",
            description="Campus WiFi intermittent",
        )
        resolve_request = self.factory.post(f"/api/platform/support-tickets/{ticket.id}/resolve/", {}, format="json")
        force_authenticate(resolve_request, user=self.admin)
        resolve_response = PlatformSupportTicketViewSet.as_view({"post": "resolve"})(resolve_request, pk=ticket.id)
        self.assertEqual(resolve_response.status_code, 200)
        self.assertEqual(resolve_response.data["status"], SupportTicket.STATUS_RESOLVED)

        close_request = self.factory.post(f"/api/platform/support-tickets/{ticket.id}/close/", {}, format="json")
        force_authenticate(close_request, user=self.admin)
        close_response = PlatformSupportTicketViewSet.as_view({"post": "close"})(close_request, pk=ticket.id)
        self.assertEqual(close_response.status_code, 200)
        self.assertEqual(close_response.data["status"], SupportTicket.STATUS_CLOSED)
        self.assertTrue(
            PlatformActionLog.objects.filter(
                action="RESOLVE",
                model_name="PlatformSupportTicket",
                object_id=str(ticket.id),
                tenant=self.tenant,
            ).exists()
        )
        self.assertTrue(
            PlatformActionLog.objects.filter(
                action="CLOSE",
                model_name="PlatformSupportTicket",
                object_id=str(ticket.id),
                tenant=self.tenant,
            ).exists()
        )

    def test_impersonation_create_forces_requested_and_validates_duration(self):
        create_request = self.factory.post(
            "/api/platform/impersonation-sessions/",
            {
                "tenant": self.tenant.id,
                "target_username": "school_admin",
                "duration_minutes": 241,
                "status": ImpersonationSession.STATUS_ACTIVE,
            },
            format="json",
        )
        force_authenticate(create_request, user=self.requester)
        create_response = PlatformImpersonationSessionViewSet.as_view({"post": "create"})(create_request)
        self.assertEqual(create_response.status_code, 400)
        self.assertIn("duration_minutes", create_response.data["error"]["details"])

        valid_request = self.factory.post(
            "/api/platform/impersonation-sessions/",
            {
                "tenant": self.tenant.id,
                "target_username": "school_admin",
                "duration_minutes": 60,
                "status": ImpersonationSession.STATUS_ACTIVE,
            },
            format="json",
        )
        force_authenticate(valid_request, user=self.requester)
        valid_response = PlatformImpersonationSessionViewSet.as_view({"post": "create"})(valid_request)
        self.assertEqual(valid_response.status_code, 201)
        self.assertEqual(valid_response.data["status"], ImpersonationSession.STATUS_REQUESTED)

    def test_impersonation_requires_second_admin_approval(self):
        session = ImpersonationSession.objects.create(
            tenant=self.tenant,
            target_username="school_admin",
            requested_by=self.requester,
            status=ImpersonationSession.STATUS_REQUESTED,
            duration_minutes=30,
        )

        requester_approve = self.factory.post(
            f"/api/platform/impersonation-sessions/{session.id}/approve/",
            {"approval_notes": "self-approve"},
            format="json",
        )
        force_authenticate(requester_approve, user=self.requester)
        requester_response = PlatformImpersonationSessionViewSet.as_view({"post": "approve"})(
            requester_approve, pk=session.id
        )
        self.assertEqual(requester_response.status_code, 400)

        approve_request = self.factory.post(
            f"/api/platform/impersonation-sessions/{session.id}/approve/",
            {"approval_notes": "approved"},
            format="json",
        )
        force_authenticate(approve_request, user=self.second_admin)
        approve_response = PlatformImpersonationSessionViewSet.as_view({"post": "approve"})(approve_request, pk=session.id)
        self.assertEqual(approve_response.status_code, 200)
        self.assertEqual(approve_response.data["status"], ImpersonationSession.STATUS_APPROVED)

        duplicate_approve_request = self.factory.post(
            f"/api/platform/impersonation-sessions/{session.id}/approve/",
            {"approval_notes": "again"},
            format="json",
        )
        force_authenticate(duplicate_approve_request, user=self.admin)
        duplicate_approve_response = PlatformImpersonationSessionViewSet.as_view({"post": "approve"})(
            duplicate_approve_request, pk=session.id
        )
        self.assertEqual(duplicate_approve_response.status_code, 400)

    def test_impersonation_end_only_active(self):
        session = ImpersonationSession.objects.create(
            tenant=self.tenant,
            target_username="school_admin",
            requested_by=self.requester,
            approved_by=self.second_admin,
            status=ImpersonationSession.STATUS_APPROVED,
            duration_minutes=30,
        )
        end_request = self.factory.post(f"/api/platform/impersonation-sessions/{session.id}/end/", {}, format="json")
        force_authenticate(end_request, user=self.admin)
        end_response = PlatformImpersonationSessionViewSet.as_view({"post": "end"})(end_request, pk=session.id)
        self.assertEqual(end_response.status_code, 400)

    def test_monitoring_alert_ack_and_resolve_guards(self):
        alert = MonitoringAlert.objects.create(
            title="High error rate",
            metric_key="api.error.rate",
            tenant=self.tenant,
            severity=MonitoringAlert.SEVERITY_CRITICAL,
            status=MonitoringAlert.STATUS_OPEN,
        )

        ack_request = self.factory.post(f"/api/platform/monitoring/alerts/{alert.id}/acknowledge/", {}, format="json")
        force_authenticate(ack_request, user=self.admin)
        ack_response = PlatformMonitoringAlertViewSet.as_view({"post": "acknowledge"})(ack_request, pk=alert.id)
        self.assertEqual(ack_response.status_code, 200)
        self.assertEqual(ack_response.data["status"], MonitoringAlert.STATUS_ACKNOWLEDGED)

        ack_again_request = self.factory.post(
            f"/api/platform/monitoring/alerts/{alert.id}/acknowledge/",
            {},
            format="json",
        )
        force_authenticate(ack_again_request, user=self.admin)
        ack_again_response = PlatformMonitoringAlertViewSet.as_view({"post": "acknowledge"})(
            ack_again_request, pk=alert.id
        )
        self.assertEqual(ack_again_response.status_code, 400)

        resolve_request = self.factory.post(f"/api/platform/monitoring/alerts/{alert.id}/resolve/", {}, format="json")
        force_authenticate(resolve_request, user=self.admin)
        resolve_response = PlatformMonitoringAlertViewSet.as_view({"post": "resolve"})(resolve_request, pk=alert.id)
        self.assertEqual(resolve_response.status_code, 200)
        self.assertEqual(resolve_response.data["status"], MonitoringAlert.STATUS_RESOLVED)

        resolve_again_request = self.factory.post(
            f"/api/platform/monitoring/alerts/{alert.id}/resolve/",
            {},
            format="json",
        )
        force_authenticate(resolve_again_request, user=self.admin)
        resolve_again_response = PlatformMonitoringAlertViewSet.as_view({"post": "resolve"})(
            resolve_again_request, pk=alert.id
        )
        self.assertEqual(resolve_again_response.status_code, 400)

    def test_platform_action_log_list_filters(self):
        PlatformActionLog.objects.create(
            actor=self.admin,
            tenant=self.tenant,
            action="RESOLVE",
            model_name="PlatformSupportTicket",
            object_id="11",
            details="ok",
        )
        PlatformActionLog.objects.create(
            actor=self.admin,
            tenant=self.tenant,
            action="ACKNOWLEDGE",
            model_name="PlatformMonitoringAlert",
            object_id="12",
            details="ok",
        )
        request = self.factory.get("/api/platform/action-logs/?action=RESOLVE&model_name=PlatformSupportTicket")
        force_authenticate(request, user=self.admin)
        response = PlatformActionLogViewSet.as_view({"get": "list"})(request)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]["action"], "RESOLVE")


class PlatformDeploymentHardeningTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.tenant = Tenant.objects.create(
            schema_name="platform_deployment",
            name="Platform Deployment School",
            paid_until="2030-01-01",
            is_active=True,
        )
        Domain.objects.create(domain="platform-deployment.localhost", tenant=cls.tenant, is_primary=True)

    def setUp(self):
        self.factory = APIRequestFactory()
        self.admin = User.objects.create_user(username="platform_deploy_admin", password="test123")
        GlobalSuperAdmin.objects.create(user=self.admin, is_active=True)

    def test_release_start_requires_active_maintenance_window(self):
        release = DeploymentRelease.objects.create(version="v2.1.0", environment="production", status=DeploymentRelease.STATUS_PLANNED)
        request = self.factory.post(f"/api/platform/deployment/releases/{release.id}/start/", {}, format="json")
        force_authenticate(request, user=self.admin)
        response = PlatformDeploymentReleaseViewSet.as_view({"post": "start"})(request, pk=release.id)
        self.assertEqual(response.status_code, 400)
        self.assertIn("maintenance", str(response.data).lower())

    def test_release_start_blocks_parallel_environment_deployments(self):
        now = timezone.now()
        MaintenanceWindow.objects.create(
            title="Prod Window",
            starts_at=now - timedelta(minutes=10),
            ends_at=now + timedelta(minutes=60),
            status=MaintenanceWindow.STATUS_ACTIVE,
            created_by=self.admin,
        )
        DeploymentRelease.objects.create(version="v2.1.0", environment="production", status=DeploymentRelease.STATUS_DEPLOYING)
        release = DeploymentRelease.objects.create(version="v2.2.0", environment="production", status=DeploymentRelease.STATUS_PLANNED)
        request = self.factory.post(f"/api/platform/deployment/releases/{release.id}/start/", {}, format="json")
        force_authenticate(request, user=self.admin)
        response = PlatformDeploymentReleaseViewSet.as_view({"post": "start"})(request, pk=release.id)
        self.assertEqual(response.status_code, 400)
        self.assertIn("already running", str(response.data).lower())

    def test_release_complete_blocks_unhealthy_or_critical_alerts_unless_forced(self):
        now = timezone.now()
        MaintenanceWindow.objects.create(
            title="Prod Window",
            starts_at=now - timedelta(minutes=10),
            ends_at=now + timedelta(minutes=60),
            status=MaintenanceWindow.STATUS_ACTIVE,
            created_by=self.admin,
        )
        release = DeploymentRelease.objects.create(
            version="v2.3.0",
            environment="production",
            status=DeploymentRelease.STATUS_DEPLOYING,
            started_at=now,
            created_by=self.admin,
        )
        MonitoringAlert.objects.create(
            title="API 5xx spike",
            metric_key="api.error.rate",
            tenant=self.tenant,
            severity=MonitoringAlert.SEVERITY_CRITICAL,
            status=MonitoringAlert.STATUS_OPEN,
        )

        first_attempt = self.factory.post(
            f"/api/platform/deployment/releases/{release.id}/complete/",
            {"health_summary": {"status": "failed"}},
            format="json",
        )
        force_authenticate(first_attempt, user=self.admin)
        first_response = PlatformDeploymentReleaseViewSet.as_view({"post": "complete"})(first_attempt, pk=release.id)
        self.assertEqual(first_response.status_code, 400)

        forced_attempt = self.factory.post(
            f"/api/platform/deployment/releases/{release.id}/complete/",
            {"health_summary": {"status": "failed"}, "force": True},
            format="json",
        )
        force_authenticate(forced_attempt, user=self.admin)
        forced_response = PlatformDeploymentReleaseViewSet.as_view({"post": "complete"})(forced_attempt, pk=release.id)
        self.assertEqual(forced_response.status_code, 200)
        self.assertEqual(forced_response.data["status"], DeploymentRelease.STATUS_SUCCESS)

    @override_settings(DEPLOYMENT_CALLBACK_TOKEN="pipeline-token-1")
    def test_deployment_callback_updates_release_status(self):
        release = DeploymentRelease.objects.create(
            version="v2.4.0",
            environment="production",
            status=DeploymentRelease.STATUS_DEPLOYING,
            started_at=timezone.now(),
            created_by=self.admin,
        )
        request = self.factory.post(
            "/api/platform/deployment/releases/callbacks/status/",
            {"release_id": release.id, "event": "success"},
            format="json",
            HTTP_X_PLATFORM_HOOK_TOKEN="pipeline-token-1",
        )
        force_authenticate(request, user=self.admin)
        response = PlatformDeploymentReleaseViewSet.as_view({"post": "callback_status"})(request)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["status"], DeploymentRelease.STATUS_SUCCESS)
        self.assertEqual(response.data["health_summary"]["release_id"], release.id)

    @override_settings(DEPLOYMENT_CALLBACK_TOKEN="pipeline-token-2")
    def test_deployment_callback_rejects_invalid_token(self):
        release = DeploymentRelease.objects.create(
            version="v2.5.0",
            environment="production",
            status=DeploymentRelease.STATUS_DEPLOYING,
            started_at=timezone.now(),
            created_by=self.admin,
        )
        request = self.factory.post(
            "/api/platform/deployment/releases/callbacks/status/",
            {"release_id": release.id, "event": "failed"},
            format="json",
        )
        force_authenticate(request, user=self.admin)
        response = PlatformDeploymentReleaseViewSet.as_view({"post": "callback_status"})(request)
        self.assertEqual(response.status_code, 403)

    def test_run_health_checks_persists_summary(self):
        release = DeploymentRelease.objects.create(
            version="v2.6.0",
            environment="production",
            status=DeploymentRelease.STATUS_DEPLOYING,
            started_at=timezone.now(),
            created_by=self.admin,
        )
        MonitoringAlert.objects.create(
            title="Critical latency",
            metric_key="api.p99",
            tenant=self.tenant,
            severity=MonitoringAlert.SEVERITY_CRITICAL,
            status=MonitoringAlert.STATUS_OPEN,
        )
        request = self.factory.post(
            f"/api/platform/deployment/releases/{release.id}/run-health-checks/",
            {},
            format="json",
        )
        force_authenticate(request, user=self.admin)
        response = PlatformDeploymentReleaseViewSet.as_view({"post": "run_health_checks"})(request, pk=release.id)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["status"], "failed")
        release.refresh_from_db()
        self.assertEqual(release.health_summary.get("status"), "failed")


class PlatformDeploymentIntegrationStep1Tests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.tenant = Tenant.objects.create(
            schema_name="platform_deploy_step1",
            name="Platform Deploy Step1 School",
            paid_until="2030-01-01",
            is_active=True,
        )
        Domain.objects.create(domain="platform-deploy-step1.localhost", tenant=cls.tenant, is_primary=True)

    def setUp(self):
        self.factory = APIRequestFactory()
        self.admin = User.objects.create_user(username="platform_step1_admin", password="test123")
        GlobalSuperAdmin.objects.create(user=self.admin, is_active=True)

    def test_maintenance_start_queues_notifications(self):
        now = timezone.now()
        window = MaintenanceWindow.objects.create(
            title="Planned maintenance",
            starts_at=now - timedelta(minutes=1),
            ends_at=now + timedelta(minutes=30),
            status=MaintenanceWindow.STATUS_SCHEDULED,
            notify_tenants=True,
            created_by=self.admin,
        )
        request = self.factory.post(f"/api/platform/maintenance/windows/{window.id}/start/", {}, format="json")
        force_authenticate(request, user=self.admin)
        response = PlatformMaintenanceWindowViewSet.as_view({"post": "start"})(request, pk=window.id)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(
            PlatformNotificationDispatch.objects.filter(
                maintenance_window=window,
                event_type=PlatformNotificationDispatch.EVENT_MAINTENANCE_STARTED,
            ).exists()
        )

    def test_trigger_pipeline_records_failed_hook_when_endpoint_missing(self):
        release = DeploymentRelease.objects.create(
            version="v3.0.0",
            environment="production",
            status=DeploymentRelease.STATUS_PLANNED,
            created_by=self.admin,
        )
        request = self.factory.post(f"/api/platform/deployment/releases/{release.id}/trigger-pipeline/", {}, format="json")
        force_authenticate(request, user=self.admin)
        response = PlatformDeploymentReleaseViewSet.as_view({"post": "trigger_pipeline"})(request, pk=release.id)
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.data["status"], DeploymentHookRun.STATUS_FAILED)

    @override_settings(DEPLOYMENT_TRIGGER_HOOK_URL="http://example.hook.local/deploy", DEPLOYMENT_CALLBACK_TOKEN="hook-token")
    @patch("clients.platform_views.urlopen")
    def test_trigger_pipeline_records_success_hook(self, mock_urlopen):
        release = DeploymentRelease.objects.create(
            version="v3.1.0",
            environment="staging",
            status=DeploymentRelease.STATUS_PLANNED,
            created_by=self.admin,
        )
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.read.return_value = b'{"ok":true}'
        mock_urlopen.return_value.__enter__.return_value = mock_response
        request = self.factory.post(f"/api/platform/deployment/releases/{release.id}/trigger-pipeline/", {}, format="json")
        force_authenticate(request, user=self.admin)
        response = PlatformDeploymentReleaseViewSet.as_view({"post": "trigger_pipeline"})(request, pk=release.id)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["status"], DeploymentHookRun.STATUS_SUCCESS)
        self.assertEqual(response.data["response_status"], 200)

    def test_feature_flag_evaluate_runtime(self):
        flag = FeatureFlag.objects.create(
            key="platform.new.dashboard",
            description="test",
            is_enabled=True,
            rollout_percent=100,
            updated_by=self.admin,
        )
        flag.target_tenants.add(self.tenant)
        request = self.factory.get(f"/api/platform/deployment/feature-flags/evaluate/?key={flag.key}&tenant_id={self.tenant.id}&actor_id=77")
        force_authenticate(request, user=self.admin)
        response = PlatformFeatureFlagViewSet.as_view({"get": "evaluate"})(request)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data["enabled"])


class PlatformBackupRestoreHardeningTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.tenant = Tenant.objects.create(
            schema_name="platform_backup",
            name="Platform Backup School",
            paid_until="2030-01-01",
            is_active=True,
        )
        Domain.objects.create(domain="platform-backup.localhost", tenant=cls.tenant, is_primary=True)

    def setUp(self):
        self.factory = APIRequestFactory()
        self.requester = User.objects.create_user(username="platform_backup_requester", password="test123")
        self.approver = User.objects.create_user(username="platform_backup_approver", password="test123")
        GlobalSuperAdmin.objects.create(user=self.requester, is_active=True)
        GlobalSuperAdmin.objects.create(user=self.approver, is_active=True)

    def test_tenant_backup_requires_tenant(self):
        request = self.factory.post(
            "/api/platform/backup/jobs/",
            {"scope": BackupJob.SCOPE_TENANT, "backup_type": BackupJob.TYPE_FULL},
            format="json",
        )
        force_authenticate(request, user=self.requester)
        response = PlatformBackupJobViewSet.as_view({"post": "create"})(request)
        self.assertEqual(response.status_code, 400)
        self.assertIn("tenant", str(response.data).lower())

    def test_backup_complete_requires_storage_checksum_and_size(self):
        job = BackupJob.objects.create(
            scope=BackupJob.SCOPE_TENANT,
            tenant=self.tenant,
            backup_type=BackupJob.TYPE_INCREMENTAL,
            status=BackupJob.STATUS_RUNNING,
            created_by=self.requester,
        )
        request = self.factory.post(
            f"/api/platform/backup/jobs/{job.id}/complete/",
            {"storage_path": "", "checksum": "", "size_bytes": 0},
            format="json",
        )
        force_authenticate(request, user=self.requester)
        response = PlatformBackupJobViewSet.as_view({"post": "complete"})(request, pk=job.id)
        self.assertEqual(response.status_code, 400)

    def test_restore_requires_successful_backup_and_second_admin_approval(self):
        failed_backup = BackupJob.objects.create(
            scope=BackupJob.SCOPE_TENANT,
            tenant=self.tenant,
            backup_type=BackupJob.TYPE_FULL,
            status=BackupJob.STATUS_FAILED,
            created_by=self.requester,
        )
        create_request = self.factory.post(
            "/api/platform/backup/restores/",
            {"backup": failed_backup.id, "tenant": self.tenant.id, "notes": "restore failed backup"},
            format="json",
        )
        force_authenticate(create_request, user=self.requester)
        create_response = PlatformRestoreJobViewSet.as_view({"post": "create"})(create_request)
        self.assertEqual(create_response.status_code, 400)

        good_backup = BackupJob.objects.create(
            scope=BackupJob.SCOPE_TENANT,
            tenant=self.tenant,
            backup_type=BackupJob.TYPE_FULL,
            status=BackupJob.STATUS_SUCCESS,
            created_by=self.requester,
        )
        ok_create = self.factory.post(
            "/api/platform/backup/restores/",
            {"backup": good_backup.id, "tenant": self.tenant.id, "notes": "restore good backup"},
            format="json",
        )
        force_authenticate(ok_create, user=self.requester)
        ok_response = PlatformRestoreJobViewSet.as_view({"post": "create"})(ok_create)
        self.assertEqual(ok_response.status_code, 201)

        restore_id = ok_response.data["id"]
        self_approve = self.factory.post(f"/api/platform/backup/restores/{restore_id}/approve/", {}, format="json")
        force_authenticate(self_approve, user=self.requester)
        self_approve_response = PlatformRestoreJobViewSet.as_view({"post": "approve"})(self_approve, pk=restore_id)
        self.assertEqual(self_approve_response.status_code, 400)

        approve = self.factory.post(f"/api/platform/backup/restores/{restore_id}/approve/", {}, format="json")
        force_authenticate(approve, user=self.approver)
        approve_response = PlatformRestoreJobViewSet.as_view({"post": "approve"})(approve, pk=restore_id)
        self.assertEqual(approve_response.status_code, 200)
        self.assertEqual(approve_response.data["status"], RestoreJob.STATUS_APPROVED)

    def test_verify_integrity_requires_matching_checksum(self):
        backup = BackupJob.objects.create(
            scope=BackupJob.SCOPE_TENANT,
            tenant=self.tenant,
            backup_type=BackupJob.TYPE_FULL,
            status=BackupJob.STATUS_SUCCESS,
            checksum="sha256-good",
            created_by=self.requester,
            completed_at=timezone.now(),
        )
        mismatch_request = self.factory.post(
            f"/api/platform/backup/jobs/{backup.id}/verify-integrity/",
            {"expected_checksum": "sha256-bad"},
            format="json",
        )
        force_authenticate(mismatch_request, user=self.requester)
        mismatch_response = PlatformBackupJobViewSet.as_view({"post": "verify_integrity"})(mismatch_request, pk=backup.id)
        self.assertEqual(mismatch_response.status_code, 400)

        ok_request = self.factory.post(
            f"/api/platform/backup/jobs/{backup.id}/verify-integrity/",
            {"expected_checksum": "sha256-good"},
            format="json",
        )
        force_authenticate(ok_request, user=self.requester)
        ok_response = PlatformBackupJobViewSet.as_view({"post": "verify_integrity"})(ok_request, pk=backup.id)
        self.assertEqual(ok_response.status_code, 200)
        self.assertTrue(ok_response.data["verified"])

    def test_enforce_retention_supports_dry_run_and_apply(self):
        expired = BackupJob.objects.create(
            scope=BackupJob.SCOPE_TENANT,
            tenant=self.tenant,
            backup_type=BackupJob.TYPE_INCREMENTAL,
            status=BackupJob.STATUS_SUCCESS,
            checksum="sha256-old",
            retention_days=1,
            created_by=self.requester,
            completed_at=timezone.now() - timedelta(days=5),
        )
        dry_run_request = self.factory.post(
            "/api/platform/backup/jobs/enforce-retention/",
            {"dry_run": True},
            format="json",
        )
        force_authenticate(dry_run_request, user=self.requester)
        dry_run_response = PlatformBackupJobViewSet.as_view({"post": "enforce_retention"})(dry_run_request)
        self.assertEqual(dry_run_response.status_code, 200)
        self.assertEqual(dry_run_response.data["candidate_count"], 1)
        self.assertEqual(dry_run_response.data["deleted_count"], 0)
        self.assertTrue(BackupJob.objects.filter(id=expired.id).exists())

        apply_request = self.factory.post(
            "/api/platform/backup/jobs/enforce-retention/",
            {"dry_run": False},
            format="json",
        )
        force_authenticate(apply_request, user=self.requester)
        apply_response = PlatformBackupJobViewSet.as_view({"post": "enforce_retention"})(apply_request)
        self.assertEqual(apply_response.status_code, 200)
        self.assertEqual(apply_response.data["deleted_count"], 1)
        self.assertFalse(BackupJob.objects.filter(id=expired.id).exists())

    def test_run_restore_drill_requires_dual_admin_and_creates_success_restore(self):
        backup = BackupJob.objects.create(
            scope=BackupJob.SCOPE_TENANT,
            tenant=self.tenant,
            backup_type=BackupJob.TYPE_FULL,
            status=BackupJob.STATUS_SUCCESS,
            checksum="sha256-drill",
            created_by=self.requester,
            completed_at=timezone.now(),
        )
        request = self.factory.post(
            f"/api/platform/backup/jobs/{backup.id}/run-restore-drill/",
            {"approver_id": self.approver.id},
            format="json",
        )
        force_authenticate(request, user=self.requester)
        response = PlatformBackupJobViewSet.as_view({"post": "run_restore_drill"})(request, pk=backup.id)
        self.assertEqual(response.status_code, 201)
        self.assertTrue(response.data["drill"])
        restore = RestoreJob.objects.get(id=response.data["restore_job_id"])
        self.assertEqual(restore.status, RestoreJob.STATUS_SUCCESS)
        self.assertEqual(restore.approved_by_id, self.approver.id)

    @override_settings(BACKUP_ENGINE_MODE="mock")
    def test_backup_execute_engine_generates_artifact_and_marks_success(self):
        backup = BackupJob.objects.create(
            scope=BackupJob.SCOPE_TENANT,
            tenant=self.tenant,
            backup_type=BackupJob.TYPE_FULL,
            status=BackupJob.STATUS_QUEUED,
            created_by=self.requester,
        )
        request = self.factory.post(f"/api/platform/backup/jobs/{backup.id}/execute-engine/", {}, format="json")
        force_authenticate(request, user=self.requester)
        response = PlatformBackupJobViewSet.as_view({"post": "execute_engine"})(request, pk=backup.id)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["backup"]["status"], BackupJob.STATUS_SUCCESS)
        self.assertTrue(response.data["backup"]["storage_path"])
        execution = BackupExecutionRun.objects.get(id=response.data["execution"]["id"])
        self.assertEqual(execution.status, BackupExecutionRun.STATUS_SUCCESS)

    @override_settings(BACKUP_ENGINE_MODE="mock")
    def test_restore_execute_completes_from_approved_state(self):
        backup = BackupJob.objects.create(
            scope=BackupJob.SCOPE_TENANT,
            tenant=self.tenant,
            backup_type=BackupJob.TYPE_FULL,
            status=BackupJob.STATUS_SUCCESS,
            storage_path="mock://backups/tenant.dump",
            checksum="abc123",
            size_bytes=100,
            created_by=self.requester,
            completed_at=timezone.now(),
        )
        restore = RestoreJob.objects.create(
            backup=backup,
            tenant=self.tenant,
            status=RestoreJob.STATUS_APPROVED,
            requested_by=self.requester,
            approved_by=self.approver,
        )
        request = self.factory.post(f"/api/platform/backup/restores/{restore.id}/execute/", {"notes": "run now"}, format="json")
        force_authenticate(request, user=self.requester)
        response = PlatformRestoreJobViewSet.as_view({"post": "execute"})(request, pk=restore.id)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["status"], RestoreJob.STATUS_SUCCESS)


class PlatformAnalyticsDeepIntegrationTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.tenant = Tenant.objects.create(
            schema_name="platform_analytics",
            name="Platform Analytics School",
            status=Tenant.STATUS_ACTIVE,
            paid_until="2030-01-01",
            is_active=True,
        )
        Domain.objects.create(domain="platform-analytics.localhost", tenant=cls.tenant, is_primary=True)
        cls.plan = SubscriptionPlan.objects.create(
            name="Analytics Plan",
            monthly_price="200.00",
            annual_price="2000.00",
            max_students=500,
            max_storage_gb=20,
            enabled_modules=["FINANCE", "STUDENTS"],
        )

    def setUp(self):
        self.factory = APIRequestFactory()
        self.admin = User.objects.create_user(username="platform_analytics_admin", password="test123")
        GlobalSuperAdmin.objects.create(user=self.admin, is_active=True)

    def test_business_kpis_and_storage_usage_endpoints(self):
        TenantSubscription.objects.create(
            tenant=self.tenant,
            plan=self.plan,
            status=TenantSubscription.STATUS_ACTIVE,
            billing_cycle=TenantSubscription.BILLING_MONTHLY,
            starts_on=timezone.now().date(),
            is_current=True,
        )
        MonitoringSnapshot.objects.create(metric_key="storage.used.gb", value="12.50", payload={})

        kpi_request = self.factory.get("/api/platform/analytics/business-kpis/")
        force_authenticate(kpi_request, user=self.admin)
        kpi_response = PlatformAnalyticsViewSet.as_view({"get": "business_kpis"})(kpi_request)
        self.assertEqual(kpi_response.status_code, 200)
        self.assertIn("kpis", kpi_response.data)
        self.assertEqual(kpi_response.data["kpis"]["mrr"], "200.00")

        storage_request = self.factory.get("/api/platform/analytics/storage-usage/")
        force_authenticate(storage_request, user=self.admin)
        storage_response = PlatformAnalyticsViewSet.as_view({"get": "storage_usage"})(storage_request)
        self.assertEqual(storage_response.status_code, 200)
        self.assertIn("points", storage_response.data)

    def test_revenue_analytics_projection_and_risk_signals(self):
        today = timezone.now().date()
        current_month_start = today.replace(day=1)
        previous_month_start = (current_month_start - timedelta(days=1)).replace(day=1)

        primary_subscription = TenantSubscription.objects.create(
            tenant=self.tenant,
            plan=self.plan,
            status=TenantSubscription.STATUS_ACTIVE,
            billing_cycle=TenantSubscription.BILLING_MONTHLY,
            starts_on=previous_month_start,
            next_billing_date=today + timedelta(days=5),
            is_current=True,
        )

        risk_tenant = Tenant.objects.create(
            schema_name="platform_analytics_risk",
            name="Platform Analytics Risk School",
            status=Tenant.STATUS_ACTIVE,
            paid_until=today - timedelta(days=2),
            is_active=True,
        )
        risk_plan = SubscriptionPlan.objects.create(
            code="PRO",
            name="Pro",
            monthly_price="120.00",
            annual_price="1200.00",
            max_students=500,
            max_storage_gb=20,
            enabled_modules=["FINANCE", "STUDENTS"],
        )
        risk_subscription = TenantSubscription.objects.create(
            tenant=risk_tenant,
            plan=risk_plan,
            status=TenantSubscription.STATUS_ACTIVE,
            billing_cycle=TenantSubscription.BILLING_MONTHLY,
            starts_on=previous_month_start,
            next_billing_date=today - timedelta(days=2),
            is_current=True,
        )

        first_paid_invoice = SubscriptionInvoice.objects.create(
            tenant=self.tenant,
            subscription=primary_subscription,
            invoice_number="AN-REV-001",
            billing_cycle=TenantSubscription.BILLING_MONTHLY,
            status=SubscriptionInvoice.STATUS_PAID,
            currency="USD",
            amount="150.00",
            tax_amount="0.00",
            discount_amount="0.00",
            total_amount="150.00",
            period_start=previous_month_start,
            period_end=current_month_start - timedelta(days=1),
            due_date=previous_month_start + timedelta(days=10),
        )
        SubscriptionInvoice.objects.filter(id=first_paid_invoice.id).update(
            issued_at=timezone.now() - timedelta(days=40),
            paid_at=timezone.now() - timedelta(days=39),
        )

        second_paid_invoice = SubscriptionInvoice.objects.create(
            tenant=self.tenant,
            subscription=primary_subscription,
            invoice_number="AN-REV-002",
            billing_cycle=TenantSubscription.BILLING_MONTHLY,
            status=SubscriptionInvoice.STATUS_PAID,
            currency="USD",
            amount="200.00",
            tax_amount="0.00",
            discount_amount="0.00",
            total_amount="200.00",
            period_start=current_month_start,
            period_end=current_month_start + timedelta(days=27),
            due_date=current_month_start + timedelta(days=10),
        )
        SubscriptionInvoice.objects.filter(id=second_paid_invoice.id).update(
            issued_at=timezone.now() - timedelta(days=10),
            paid_at=timezone.now() - timedelta(days=9),
        )

        overdue_invoice = SubscriptionInvoice.objects.create(
            tenant=risk_tenant,
            subscription=risk_subscription,
            invoice_number="AN-OVD-001",
            billing_cycle=TenantSubscription.BILLING_MONTHLY,
            status=SubscriptionInvoice.STATUS_OVERDUE,
            currency="USD",
            amount="120.00",
            tax_amount="0.00",
            discount_amount="0.00",
            total_amount="120.00",
            period_start=previous_month_start,
            period_end=current_month_start - timedelta(days=1),
            due_date=today - timedelta(days=2),
        )
        SubscriptionInvoice.objects.filter(id=overdue_invoice.id).update(
            issued_at=timezone.now() - timedelta(days=2),
        )

        kpi_request = self.factory.get("/api/platform/analytics/business-kpis/")
        force_authenticate(kpi_request, user=self.admin)
        kpi_response = PlatformAnalyticsViewSet.as_view({"get": "business_kpis"})(kpi_request)
        self.assertEqual(kpi_response.status_code, 200)
        self.assertIn("forecast", kpi_response.data)
        self.assertIn("risk_summary", kpi_response.data)
        self.assertGreaterEqual(int(kpi_response.data["risk_summary"]["total"]), 1)
        self.assertEqual(kpi_response.data["forecast"]["trend"], "growing")

        revenue_request = self.factory.get("/api/platform/analytics/revenue/")
        force_authenticate(revenue_request, user=self.admin)
        revenue_response = PlatformAnalyticsViewSet.as_view({"get": "revenue"})(revenue_request)
        self.assertEqual(revenue_response.status_code, 200)
        self.assertIn("monthly_paid_trend", revenue_response.data)
        self.assertIn("plan_breakdown", revenue_response.data)
        self.assertIn("risk_signals", revenue_response.data)
        self.assertGreaterEqual(len(revenue_response.data["risk_signals"]), 1)

        growth_request = self.factory.get("/api/platform/analytics/tenant-growth/")
        force_authenticate(growth_request, user=self.admin)
        growth_response = PlatformAnalyticsViewSet.as_view({"get": "tenant_growth"})(growth_request)
        self.assertEqual(growth_response.status_code, 200)
        self.assertIn("by_month", growth_response.data)


class PlatformSettingsAndAdminUsersTests(TestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.owner = User.objects.create_user(username="platform_owner", password="test123")
        GlobalSuperAdmin.objects.create(user=self.owner, role=GlobalSuperAdmin.ROLE_OWNER, is_active=True)

    def test_platform_settings_create_and_update(self):
        create_request = self.factory.post(
            "/api/platform/settings/",
            {"key": "maintenance.notice.hours", "value": {"hours": 24}, "description": "notice lead time", "is_secret": False},
            format="json",
        )
        force_authenticate(create_request, user=self.owner)
        create_response = PlatformSettingViewSet.as_view({"post": "create"})(create_request)
        self.assertEqual(create_response.status_code, 201)
        setting_id = create_response.data["id"]

        patch_request = self.factory.patch(
            f"/api/platform/settings/{setting_id}/",
            {"value": {"hours": 12}},
            format="json",
        )
        force_authenticate(patch_request, user=self.owner)
        patch_response = PlatformSettingViewSet.as_view({"patch": "partial_update"})(patch_request, pk=setting_id)
        self.assertEqual(patch_response.status_code, 200)
        self.assertEqual(patch_response.data["value"]["hours"], 12)

    def test_platform_admin_user_grant_update_revoke(self):
        grant_request = self.factory.post(
            "/api/platform/admin-users/",
            {"username": "ops_admin", "email": "ops@example.com", "password": "test123", "role": "SUPPORT", "is_active": True},
            format="json",
        )
        force_authenticate(grant_request, user=self.owner)
        grant_response = PlatformAdminUserViewSet.as_view({"post": "create"})(grant_request)
        self.assertEqual(grant_response.status_code, 201)
        admin_id = grant_response.data["id"]
        self.assertEqual(grant_response.data["role"], GlobalSuperAdmin.ROLE_SUPPORT)

        update_request = self.factory.patch(
            f"/api/platform/admin-users/{admin_id}/update/",
            {"role": "ADMIN"},
            format="json",
        )
        force_authenticate(update_request, user=self.owner)
        update_response = PlatformAdminUserViewSet.as_view({"patch": "update_admin"})(update_request, pk=admin_id)
        self.assertEqual(update_response.status_code, 200)
        self.assertEqual(update_response.data["role"], GlobalSuperAdmin.ROLE_ADMIN)

        revoke_request = self.factory.post(f"/api/platform/admin-users/{admin_id}/revoke/", {}, format="json")
        force_authenticate(revoke_request, user=self.owner)
        revoke_response = PlatformAdminUserViewSet.as_view({"post": "revoke"})(revoke_request, pk=admin_id)
        self.assertEqual(revoke_response.status_code, 200)
        self.assertFalse(revoke_response.data["is_active"])

    def test_platform_api_key_create_and_revoke(self):
        tenant = Tenant.objects.create(
            schema_name="platform_key_school",
            name="Platform Key School",
            paid_until="2030-01-01",
            is_active=True,
        )

        create_request = self.factory.post(
            "/api/platform/api-keys/",
            {"tenant": tenant.id, "label": "Primary API Key"},
            format="json",
        )
        force_authenticate(create_request, user=self.owner)
        create_response = PlatformApiKeyViewSet.as_view({"post": "create"})(create_request)
        self.assertEqual(create_response.status_code, 201)
        self.assertIn("raw_key", create_response.data)
        self.assertTrue(create_response.data["key"].startswith("sk_live_"))

        row = PlatformApiKey.objects.get(id=create_response.data["id"])
        self.assertTrue(row.is_active)
        self.assertEqual(row.tenant_id, tenant.id)

        revoke_request = self.factory.post(f"/api/platform/api-keys/{row.id}/revoke/", {}, format="json")
        force_authenticate(revoke_request, user=self.owner)
        revoke_response = PlatformApiKeyViewSet.as_view({"post": "revoke"})(revoke_request, pk=row.id)
        self.assertEqual(revoke_response.status_code, 200)
        row.refresh_from_db()
        self.assertFalse(row.is_active)
        self.assertIsNotNone(row.revoked_at)

    def test_platform_integrations_catalog_reflects_saved_settings(self):
        PlatformSetting.objects.create(
            key="integrations.stripe",
            value={"enabled": True, "secret_key": "sk_live_demo"},
            description="Stripe integration",
            updated_by=self.owner,
        )
        PlatformSetting.objects.create(
            key="integrations.sendgrid",
            value={"enabled": True, "last_error": "Invalid credentials"},
            description="SendGrid integration",
            updated_by=self.owner,
        )

        request = self.factory.get("/api/platform/integrations/")
        force_authenticate(request, user=self.owner)
        response = PlatformIntegrationViewSet.as_view({"get": "list"})(request)
        self.assertEqual(response.status_code, 200)

        rows = {item["code"]: item for item in response.data}
        self.assertEqual(rows["stripe"]["status"], "connected")
        self.assertEqual(rows["sendgrid"]["status"], "error")
        self.assertEqual(rows["zoom"]["status"], "disconnected")


class PlatformTenantBillingLifecycleTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.tenant = Tenant.objects.create(
            schema_name="platform_billing_school",
            name="Platform Billing School",
            status=Tenant.STATUS_ACTIVE,
            paid_until=timezone.now().date() - timedelta(days=1),
            is_active=True,
        )
        Domain.objects.create(domain="platform-billing.localhost", tenant=cls.tenant, is_primary=True)
        cls.plan = SubscriptionPlan.objects.create(
            code="BUSINESS",
            name="Business",
            monthly_price="500.00",
            annual_price="5000.00",
            max_students=300,
            max_storage_gb=20,
            is_active=True,
        )
        cls.subscription = TenantSubscription.objects.create(
            tenant=cls.tenant,
            plan=cls.plan,
            billing_cycle=TenantSubscription.BILLING_MONTHLY,
            status=TenantSubscription.STATUS_ACTIVE,
            starts_on=timezone.now().date() - timedelta(days=30),
            ends_on=timezone.now().date() - timedelta(days=1),
            next_billing_date=timezone.now().date() - timedelta(days=1),
            grace_period_days=7,
            is_current=True,
        )
        cls.invoice = SubscriptionInvoice.objects.create(
            tenant=cls.tenant,
            subscription=cls.subscription,
            invoice_number="SC-2026-0001",
            billing_cycle=TenantSubscription.BILLING_MONTHLY,
            status=SubscriptionInvoice.STATUS_PENDING,
            currency="USD",
            amount="500.00",
            tax_amount="0.00",
            discount_amount="0.00",
            total_amount="500.00",
            period_start=timezone.now().date() - timedelta(days=30),
            period_end=timezone.now().date() - timedelta(days=1),
            due_date=timezone.now().date() - timedelta(days=1),
        )

    def setUp(self):
        self.factory = APIRequestFactory()
        self.admin = User.objects.create_user(username="platform_billing_admin", password="test123")
        GlobalSuperAdmin.objects.create(user=self.admin, is_active=True)

    def test_subscription_payment_create_approve_and_reactivate_tenant(self):
        create_request = self.factory.post(
            "/api/platform/subscription-payments/",
            {
                "invoice": self.invoice.id,
                "amount": "500.00",
                "method": "M-Pesa",
                "status": "PENDING",
                "transaction_id": "MPESA-TXN-001",
                "metadata": {"source": "callback"},
            },
            format="json",
        )
        force_authenticate(create_request, user=self.admin)
        create_response = PlatformSubscriptionPaymentViewSet.as_view({"post": "create"})(create_request)
        self.assertEqual(create_response.status_code, 201)
        self.assertEqual(create_response.data["status"], SubscriptionPayment.STATUS_PENDING)
        payment_id = create_response.data["id"]
        self.assertEqual(SubscriptionPayment.objects.filter(invoice=self.invoice).count(), 1)

        approve_request = self.factory.post(f"/api/platform/subscription-payments/{payment_id}/approve/", {}, format="json")
        force_authenticate(approve_request, user=self.admin)
        approve_response = PlatformSubscriptionPaymentViewSet.as_view({"post": "approve"})(approve_request, pk=payment_id)
        self.assertEqual(approve_response.status_code, 200)
        self.assertEqual(approve_response.data["status"], SubscriptionPayment.STATUS_PAID)

        self.tenant.refresh_from_db()
        self.subscription.refresh_from_db()
        self.invoice.refresh_from_db()
        payment = SubscriptionPayment.objects.get(id=payment_id)
        self.assertEqual(payment.status, SubscriptionPayment.STATUS_PAID)
        self.assertEqual(self.invoice.status, SubscriptionInvoice.STATUS_PAID)
        self.assertEqual(self.subscription.status, TenantSubscription.STATUS_ACTIVE)
        self.assertEqual(self.tenant.status, Tenant.STATUS_ACTIVE)
        self.assertTrue(self.tenant.is_active)
        self.assertEqual(self.tenant.paid_until, self.invoice.period_end)

    def test_subscription_payment_reject_and_retry_verification(self):
        payment = SubscriptionPayment.objects.create(
            invoice=self.invoice,
            amount="500.00",
            method="M-Pesa",
            status=SubscriptionPayment.STATUS_PENDING,
            transaction_id="MPESA-TXN-RETRY",
            metadata={"source": "callback"},
        )

        reject_request = self.factory.post(
            f"/api/platform/subscription-payments/{payment.id}/reject/",
            {"reason": "Amount mismatch"},
            format="json",
        )
        force_authenticate(reject_request, user=self.admin)
        reject_response = PlatformSubscriptionPaymentViewSet.as_view({"post": "reject"})(reject_request, pk=payment.id)
        self.assertEqual(reject_response.status_code, 200)
        self.assertEqual(reject_response.data["status"], SubscriptionPayment.STATUS_FAILED)

        retry_request = self.factory.post(
            f"/api/platform/subscription-payments/{payment.id}/retry-verification/",
            {"reason": "Re-check gateway callback"},
            format="json",
        )
        force_authenticate(retry_request, user=self.admin)
        retry_response = PlatformSubscriptionPaymentViewSet.as_view({"post": "retry_verification"})(retry_request, pk=payment.id)
        self.assertEqual(retry_response.status_code, 200)
        self.assertEqual(retry_response.data["status"], SubscriptionPayment.STATUS_PENDING)
        payment.refresh_from_db()
        self.assertEqual(payment.metadata["verification_retry_count"], 1)

    def test_subscription_payment_create_is_idempotent_for_transaction_code(self):
        payload = {
            "invoice": self.invoice.id,
            "amount": "500.00",
            "method": "M-Pesa",
            "status": "PENDING",
            "transaction_id": "MPESA-TXN-IDEMPOTENT",
        }
        request1 = self.factory.post("/api/platform/subscription-payments/", payload, format="json")
        force_authenticate(request1, user=self.admin)
        response1 = PlatformSubscriptionPaymentViewSet.as_view({"post": "create"})(request1)
        self.assertEqual(response1.status_code, 201)

        request2 = self.factory.post("/api/platform/subscription-payments/", payload, format="json")
        force_authenticate(request2, user=self.admin)
        response2 = PlatformSubscriptionPaymentViewSet.as_view({"post": "create"})(request2)
        self.assertEqual(response2.status_code, 201)
        self.assertEqual(response1.data["id"], response2.data["id"])
        self.assertEqual(SubscriptionPayment.objects.filter(transaction_id="MPESA-TXN-IDEMPOTENT").count(), 1)

    def _mpesa_callback_payload(
        self,
        *,
        transaction_id: str,
        amount: str,
        result_code: int = 0,
        result_desc: str = "The service request is processed successfully.",
        reference: str | None = None,
    ):
        return {
            "ResultCode": result_code,
            "ResultDesc": result_desc,
            "TransID": transaction_id,
            "TransAmount": amount,
            "BillRefNumber": reference or self.invoice.invoice_number,
            "MSISDN": "254700000001",
            "TransTime": "20260423123045",
        }

    def test_platform_mpesa_callback_settles_invoice_and_tenant(self):
        payload = self._mpesa_callback_payload(transaction_id="MPESA-CALLBACK-001", amount="500.00")
        request = self.factory.post("/api/platform/subscription-payments/mpesa/callback/", payload, format="json")
        response = PlatformSubscriptionPaymentMpesaCallbackView.as_view()(request)

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data["processed"])

        payment = SubscriptionPayment.objects.get(transaction_id="MPESA-CALLBACK-001")
        self.invoice.refresh_from_db()
        self.subscription.refresh_from_db()
        self.tenant.refresh_from_db()

        self.assertEqual(payment.status, SubscriptionPayment.STATUS_PAID)
        self.assertEqual(self.invoice.status, SubscriptionInvoice.STATUS_PAID)
        self.assertEqual(self.invoice.external_reference, "MPESA-CALLBACK-001")
        self.assertEqual(self.subscription.status, TenantSubscription.STATUS_ACTIVE)
        self.assertEqual(self.tenant.status, Tenant.STATUS_ACTIVE)
        self.assertTrue(self.tenant.is_active)
        self.assertEqual(self.tenant.paid_until, self.invoice.period_end)

    def test_platform_mpesa_callback_is_idempotent_for_replay(self):
        payload = self._mpesa_callback_payload(transaction_id="MPESA-CALLBACK-REPLAY", amount="500.00")

        request1 = self.factory.post("/api/platform/subscription-payments/mpesa/callback/", payload, format="json")
        response1 = PlatformSubscriptionPaymentMpesaCallbackView.as_view()(request1)
        self.assertEqual(response1.status_code, 200)
        self.assertTrue(response1.data["processed"])

        request2 = self.factory.post("/api/platform/subscription-payments/mpesa/callback/", payload, format="json")
        response2 = PlatformSubscriptionPaymentMpesaCallbackView.as_view()(request2)
        self.assertEqual(response2.status_code, 200)
        self.assertTrue(response2.data["processed"])
        self.assertTrue(response2.data.get("duplicate"))

        self.assertEqual(SubscriptionPayment.objects.filter(transaction_id="MPESA-CALLBACK-REPLAY").count(), 1)

    def test_platform_mpesa_callback_rejects_amount_mismatch(self):
        payload = self._mpesa_callback_payload(transaction_id="MPESA-CALLBACK-MISMATCH", amount="250.00")
        request = self.factory.post("/api/platform/subscription-payments/mpesa/callback/", payload, format="json")
        response = PlatformSubscriptionPaymentMpesaCallbackView.as_view()(request)

        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.data["processed"])

        payment = SubscriptionPayment.objects.get(transaction_id="MPESA-CALLBACK-MISMATCH")
        self.invoice.refresh_from_db()

        self.assertEqual(payment.status, SubscriptionPayment.STATUS_FAILED)
        self.assertEqual(self.invoice.status, SubscriptionInvoice.STATUS_OVERDUE)

    def test_subscription_expiry_command_suspends_overdue_tenant(self):
        call_command("check_subscription_expiry", force=True)
        self.tenant.refresh_from_db()
        self.subscription.refresh_from_db()
        self.assertEqual(self.tenant.status, Tenant.STATUS_SUSPENDED)
        self.assertFalse(self.tenant.is_active)
        self.assertEqual(self.subscription.status, TenantSubscription.STATUS_SUSPENDED)
        self.assertTrue(
            PlatformActionLog.objects.filter(
                action="SUSPEND",
                model_name="Tenant",
                object_id=str(self.tenant.id),
            ).exists()
        )


class PlatformSupportImpersonationMonitoringHardeningTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.tenant = Tenant.objects.create(
            schema_name="platform_ops",
            name="Platform Ops School",
            paid_until="2030-01-01",
            is_active=True,
        )
        Domain.objects.create(domain="platform-ops.localhost", tenant=cls.tenant, is_primary=True)

    def setUp(self):
        self.factory = APIRequestFactory()
        self.admin = User.objects.create_user(username="platform_ops_admin", password="test123")
        self.approver = User.objects.create_user(username="platform_ops_approver", password="test123")
        GlobalSuperAdmin.objects.create(user=self.admin, is_active=True)
        GlobalSuperAdmin.objects.create(user=self.approver, is_active=True)

    def test_support_sla_overview_reports_overdue(self):
        ticket = SupportTicket.objects.create(
            ticket_number="TKT-SLA-0001",
            tenant=self.tenant,
            category=SupportTicket.CATEGORY_TECHNICAL,
            priority=SupportTicket.PRIORITY_URGENT,
            status=SupportTicket.STATUS_OPEN,
            subject="Critical outage",
            description="API down",
        )
        SupportTicket.objects.filter(id=ticket.id).update(created_at=timezone.now() - timedelta(hours=2))
        request = self.factory.get("/api/platform/support-tickets/sla-overview/")
        force_authenticate(request, user=self.admin)
        response = PlatformSupportTicketViewSet.as_view({"get": "sla_overview"})(request)
        self.assertEqual(response.status_code, 200)
        self.assertGreaterEqual(response.data["overdue_first_response"], 1)

    def test_impersonation_start_blocks_duplicate_active_target(self):
        active_session = ImpersonationSession.objects.create(
            tenant=self.tenant,
            target_username="school_admin",
            requested_by=self.admin,
            approved_by=self.approver,
            status=ImpersonationSession.STATUS_ACTIVE,
            duration_minutes=30,
            started_at=timezone.now(),
            expires_at=timezone.now() + timedelta(minutes=30),
        )
        pending_session = ImpersonationSession.objects.create(
            tenant=self.tenant,
            target_username=active_session.target_username,
            requested_by=self.admin,
            approved_by=self.approver,
            status=ImpersonationSession.STATUS_APPROVED,
            duration_minutes=30,
        )
        request = self.factory.post(f"/api/platform/impersonation-sessions/{pending_session.id}/start/", {}, format="json")
        force_authenticate(request, user=self.approver)
        response = PlatformImpersonationSessionViewSet.as_view({"post": "start"})(request, pk=pending_session.id)
        self.assertEqual(response.status_code, 400)

    def test_monitoring_summary_endpoint(self):
        MonitoringAlert.objects.create(
            title="Critical error burst",
            metric_key="api.error.rate",
            tenant=self.tenant,
            severity=MonitoringAlert.SEVERITY_CRITICAL,
            status=MonitoringAlert.STATUS_OPEN,
        )
        MonitoringAlert.objects.create(
            title="Recovered latency",
            metric_key="api.latency.p95",
            tenant=self.tenant,
            severity=MonitoringAlert.SEVERITY_WARNING,
            status=MonitoringAlert.STATUS_RESOLVED,
            resolved_at=timezone.now(),
        )
        request = self.factory.get("/api/platform/monitoring/alerts/summary/")
        force_authenticate(request, user=self.admin)
        response = PlatformMonitoringAlertViewSet.as_view({"get": "summary"})(request)
        self.assertEqual(response.status_code, 200)
        self.assertGreaterEqual(response.data["critical_open"], 1)
