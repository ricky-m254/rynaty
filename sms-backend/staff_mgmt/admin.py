from django.contrib import admin
from .models import (
    StaffMember,
    StaffQualification,
    StaffEmergencyContact,
    StaffDepartment,
    StaffRole,
    StaffAssignment,
    StaffAttendance,
    StaffObservation,
    StaffAppraisal,
    StaffDocument,
)

admin.site.register(StaffMember)
admin.site.register(StaffQualification)
admin.site.register(StaffEmergencyContact)
admin.site.register(StaffDepartment)
admin.site.register(StaffRole)
admin.site.register(StaffAssignment)
admin.site.register(StaffAttendance)
admin.site.register(StaffObservation)
admin.site.register(StaffAppraisal)
admin.site.register(StaffDocument)
