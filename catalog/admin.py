from django.contrib import admin

from .models import ArchiveSection, Figure, Source


class FigureInline(admin.StackedInline):
    model = Figure
    extra = 0


@admin.register(ArchiveSection)
class ArchiveSectionAdmin(admin.ModelAdmin):
    list_display = ("number", "title", "is_published", "updated_at")
    list_editable = ("is_published",)
    prepopulated_fields = {"slug": ("title",)}
    search_fields = ("title", "lead", "body")
    inlines = [FigureInline]


@admin.register(Source)
class SourceAdmin(admin.ModelAdmin):
    list_display = ("citation_short", "kind", "year")
    list_filter = ("kind",)
    search_fields = ("citation",)
    filter_horizontal = ("sections",)

    @admin.display(description="referencia")
    def citation_short(self, obj):
        return obj.citation[:90]


admin.site.register(Figure)
