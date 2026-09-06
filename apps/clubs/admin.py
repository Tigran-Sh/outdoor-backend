from django.contrib import admin

from apps.clubs.models import Club, TeamMember, TeamMemberCertificate


@admin.register(Club)
class ClubAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "owner",
        "status",
        "entity_type",
        "identity_verified",
        "payment_verified",
        "created_at",
    )
    list_filter = (
        "status",
        "entity_type",
        "base_region",
        "identity_verified",
        "payment_verified",
    )
    search_fields = ("name", "owner__email", "tax_id")
    readonly_fields = ("created_at", "updated_at")


class TeamMemberCertificateInline(admin.TabularInline):
    model = TeamMemberCertificate
    extra = 0
    readonly_fields = ("created_at",)


@admin.register(TeamMember)
class TeamMemberAdmin(admin.ModelAdmin):
    list_display = ("user", "club", "team_role", "is_active", "joined_date")
    list_filter = ("team_role", "is_active")
    search_fields = ("user__email", "user__full_name", "club__name")
    readonly_fields = ("joined_date", "created_at", "updated_at")
    inlines = [TeamMemberCertificateInline]
