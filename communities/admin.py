from django.contrib import admin

from .models import Community, Membership


class MembershipInline(admin.TabularInline):
    model = Membership
    extra = 0
    fk_name = "community"
    raw_id_fields = ("user", "decided_by")


@admin.register(Community)
class CommunityAdmin(admin.ModelAdmin):
    list_display = ("name", "people", "territory", "department", "member_count", "is_open_to_requests")
    list_filter = ("people", "department", "is_open_to_requests")
    search_fields = ("name", "territory", "municipality", "department")
    prepopulated_fields = {"slug": ("name",)}
    inlines = [MembershipInline]


@admin.register(Membership)
class MembershipAdmin(admin.ModelAdmin):
    list_display = ("user", "community", "role", "status", "created_at")
    list_filter = ("status", "role", "community")
    search_fields = ("user__email", "user__display_name", "community__name")
    raw_id_fields = ("user", "decided_by")
