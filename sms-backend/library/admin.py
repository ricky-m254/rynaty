from django.contrib import admin

from .models import (
    CirculationRule,
    CirculationTransaction,
    FineRecord,
    LibraryCategory,
    LibraryMember,
    LibraryResource,
    Reservation,
    ResourceCopy,
)

admin.site.register(LibraryCategory)
admin.site.register(LibraryResource)
admin.site.register(ResourceCopy)
admin.site.register(LibraryMember)
admin.site.register(CirculationRule)
admin.site.register(CirculationTransaction)
admin.site.register(Reservation)
admin.site.register(FineRecord)

