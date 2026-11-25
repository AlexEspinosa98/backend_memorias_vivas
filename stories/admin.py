from django.contrib import admin

from .models import (
    Comment,
    Consent,
    MediaItem,
    Promotion,
    Reaction,
    Report,
    Story,
    StoryAccessGrant,
    Tag,
    Visit,
)


class MediaInline(admin.TabularInline):
    model = MediaItem
    extra = 0


class ConsentInline(admin.StackedInline):
    model = Consent
    extra = 0
    raw_id_fields = ("recorded_by",)


class AccessGrantInline(admin.TabularInline):
    model = StoryAccessGrant
    extra = 0
    raw_id_fields = ("user", "granted_by")


class VisitInline(admin.StackedInline):
    model = Visit
    extra = 0


class PromotionInline(admin.StackedInline):
    model = Promotion
    extra = 0


@admin.register(Story)
class StoryAdmin(admin.ModelAdmin):
    list_display = (
        "title", "kind", "community", "author", "visibility", "status",
        "is_sensitive", "like_count", "comment_count", "published_at",
    )
    list_filter = ("status", "visibility", "kind", "is_sensitive", "community")
    search_fields = ("title", "summary", "body", "place_name")
    raw_id_fields = ("author", "reviewed_by")
    filter_horizontal = ("tags",)
    date_hierarchy = "created_at"
    inlines = [ConsentInline, MediaInline, VisitInline, PromotionInline, AccessGrantInline]
    readonly_fields = ("like_count", "comment_count", "view_count")

    fieldsets = (
        (None, {"fields": ("title", "summary", "body", "kind", "language")}),
        ("Autoría y comunidad", {"fields": ("author", "community")}),
        ("Acceso y cuidado cultural", {
            "fields": ("visibility", "is_sensitive", "allow_comments"),
            "description": "El contenido sensible no puede ser de uso abierto.",
        }),
        ("Ubicación", {"fields": ("place_name", "latitude", "longitude")}),
        ("Publicación", {"fields": ("status", "is_featured", "published_at", "reviewed_by", "review_note")}),
        ("Etiquetas", {"fields": ("tags",)}),
        ("Métricas", {"fields": ("like_count", "comment_count", "view_count")}),
    )

    @admin.action(description="Publicar (verifica autorización)")
    def publicar(self, request, queryset):
        ok, fail = 0, 0
        for story in queryset:
            try:
                story.publish(by=request.user)
                ok += 1
            except Exception:
                fail += 1
        self.message_user(
            request,
            f"{ok} publicada(s). {fail} sin autorización registrada." if fail else f"{ok} publicada(s).",
        )

    actions = ["publicar"]


@admin.register(Consent)
class ConsentAdmin(admin.ModelAdmin):
    list_display = ("story", "granted_by_name", "granted_by_role", "scope", "granted_on")
    list_filter = ("scope", "community")
    search_fields = ("granted_by_name", "story__title")
    raw_id_fields = ("story", "recorded_by")


@admin.register(Comment)
class CommentAdmin(admin.ModelAdmin):
    list_display = ("story", "author", "created_at", "is_hidden")
    list_filter = ("is_hidden",)
    search_fields = ("body", "author__email", "story__title")
    raw_id_fields = ("story", "author", "parent")


@admin.register(Report)
class ReportAdmin(admin.ModelAdmin):
    list_display = ("reason", "status", "story", "reporter", "created_at")
    list_filter = ("status", "reason")
    raw_id_fields = ("story", "comment", "reporter")


admin.site.register([Tag, Reaction, MediaItem, Visit, Promotion, StoryAccessGrant])

admin.site.site_header = "Memorias Vivas · administración"
admin.site.site_title = "Memorias Vivas"
admin.site.index_title = "Archivo digital y muro comunitario"
