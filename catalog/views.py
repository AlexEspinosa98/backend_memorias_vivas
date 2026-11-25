from rest_framework import permissions, viewsets

from .models import ArchiveSection, Source
from .serializers import (
    ArchiveSectionListSerializer,
    ArchiveSectionSerializer,
    SourceSerializer,
)


class ArchiveSectionViewSet(viewsets.ReadOnlyModelViewSet):
    """Las secciones del archivo: consulta abierta, sin iniciar sesión."""

    queryset = (
        ArchiveSection.objects.filter(is_published=True)
        .prefetch_related("figures", "sources")
        .order_by("number")
    )
    permission_classes = [permissions.AllowAny]
    lookup_field = "slug"
    pagination_class = None
    search_fields = ["title", "lead", "body"]

    def get_serializer_class(self):
        if self.action == "list":
            return ArchiveSectionListSerializer
        return ArchiveSectionSerializer


class SourceViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Source.objects.all()
    serializer_class = SourceSerializer
    permission_classes = [permissions.AllowAny]
    pagination_class = None
    filterset_fields = ["kind"]
    search_fields = ["citation"]
