from rest_framework import serializers

from .models import ArchiveSection, Figure, Source


class FigureSerializer(serializers.ModelSerializer):
    class Meta:
        model = Figure
        fields = ["id", "number", "caption", "note", "image", "external_url", "order"]


class SourceSerializer(serializers.ModelSerializer):
    class Meta:
        model = Source
        fields = ["id", "kind", "citation", "url", "year"]


class ArchiveSectionListSerializer(serializers.ModelSerializer):
    class Meta:
        model = ArchiveSection
        fields = ["id", "number", "title", "slug", "lead"]


class ArchiveSectionSerializer(serializers.ModelSerializer):
    figures = FigureSerializer(many=True, read_only=True)
    sources = SourceSerializer(many=True, read_only=True)

    class Meta:
        model = ArchiveSection
        fields = [
            "id",
            "number",
            "title",
            "slug",
            "lead",
            "body",
            "care_note",
            "figures",
            "sources",
            "updated_at",
        ]
