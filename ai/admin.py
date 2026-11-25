from django.contrib import admin

from .models import AiAuditLog, AiSuggestion, AssistantQuery, CareTerm


@admin.register(AssistantQuery)
class AssistantQueryAdmin(admin.ModelAdmin):
    """Lo que la gente le pregunta al archivo, y qué respondió el sistema."""

    list_display = ("created_at", "status", "short_question", "blocked_by", "asked_by")
    list_filter = ("status", "provider")
    search_fields = ("question", "answer")
    raw_id_fields = ("asked_by",)
    readonly_fields = (
        "question", "answer", "status", "blocked_by", "sources", "provider",
        "asked_by", "created_at",
    )

    @admin.display(description="pregunta")
    def short_question(self, obj):
        return obj.question[:80]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(CareTerm)
class CareTermAdmin(admin.ModelAdmin):
    """
    La lista de términos es, en sí misma, información sensible: se edita aquí
    y no se expone por la API.
    """

    list_display = ("term", "kind", "community", "is_active")
    list_filter = ("kind", "is_active", "community")
    search_fields = ("term", "note")
    list_editable = ("is_active",)


@admin.register(AiSuggestion)
class AiSuggestionAdmin(admin.ModelAdmin):
    list_display = ("kind", "story", "provider", "status", "created_at")
    list_filter = ("kind", "status", "provider")
    search_fields = ("story__title",)
    raw_id_fields = ("story", "decided_by")
    readonly_fields = ("created_at",)


@admin.register(AiAuditLog)
class AiAuditLogAdmin(admin.ModelAdmin):
    list_display = ("created_at", "function", "provider", "story", "outcome")
    list_filter = ("function", "provider")
    search_fields = ("story__title", "outcome")
    raw_id_fields = ("story", "requested_by")
    readonly_fields = (
        "story", "function", "provider", "outcome", "requested_by", "detail",
        "created_at",
    )

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        # La auditoría no se edita: su valor está en que nadie la retoque.
        return False
