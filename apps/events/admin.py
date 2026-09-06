from django.contrib import admin

from apps.events.models import Event, EventGalleryImage


class EventGalleryImageInline(admin.TabularInline):
    model = EventGalleryImage
    extra = 0
    readonly_fields = ("created_at",)


@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "club",
        "status",
        "category",
        "region",
        "start_at",
        "price_type",
    )
    list_filter = ("status", "category", "region", "difficulty", "price_type")
    search_fields = ("title", "club__name")
    readonly_fields = ("sold_count", "cancelled_at", "created_at", "updated_at")
    inlines = [EventGalleryImageInline]
