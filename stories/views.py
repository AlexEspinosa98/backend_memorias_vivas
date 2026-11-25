from django.core.exceptions import ValidationError as DjangoValidationError
from django.db.models import F, Prefetch
from django_filters import rest_framework as filters
from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response

from .models import (
    Comment,
    Consent,
    MediaItem,
    Reaction,
    Report,
    Story,
    StoryAccessGrant,
    StoryStatus,
    Tag,
)
from .permissions import CanModerateStory, CommentPermission, StoryPermission
from .serializers import (
    CommentSerializer,
    ConsentSerializer,
    MediaItemSerializer,
    PublishSerializer,
    ReactionSerializer,
    ReportSerializer,
    StoryAccessGrantSerializer,
    StoryDetailSerializer,
    StoryListSerializer,
    StoryWriteSerializer,
    TagSerializer,
)


class StoryFilter(filters.FilterSet):
    comunidad = filters.CharFilter(field_name="community__slug")
    etiqueta = filters.CharFilter(field_name="tags__slug")
    tipo = filters.CharFilter(field_name="kind")
    lugar = filters.CharFilter(field_name="place_name", lookup_expr="icontains")
    autor = filters.NumberFilter(field_name="author_id")
    desde = filters.DateFilter(field_name="published_at", lookup_expr="date__gte")
    hasta = filters.DateFilter(field_name="published_at", lookup_expr="date__lte")
    con_ubicacion = filters.BooleanFilter(
        field_name="latitude", lookup_expr="isnull", exclude=True
    )

    class Meta:
        model = Story
        fields = ["comunidad", "etiqueta", "tipo", "lugar", "autor", "visibility"]


class StoryViewSet(viewsets.ModelViewSet):
    """El muro. `GET /api/historias/` devuelve solo lo que quien consulta puede ver."""

    permission_classes = [StoryPermission]
    filterset_class = StoryFilter
    search_fields = ["title", "summary", "body", "place_name"]
    ordering_fields = ["published_at", "created_at", "like_count", "view_count"]

    # Acciones que trabajan sobre historias aún no publicadas: parten del
    # conjunto que la persona puede administrar, no del muro visible.
    EDIT_ACTIONS = {
        "update",
        "partial_update",
        "destroy",
        "enviar_a_revision",
        "publicar",
        "rechazar",
        "archivar",
        "autorizaciones",
        "accesos",
        "materiales",
    }

    def get_queryset(self):
        base = Story.objects.select_related("author", "community").prefetch_related(
            "tags",
            Prefetch("media", queryset=MediaItem.objects.all()),
            "reactions",
            "consents",
        )
        if self.action in self.EDIT_ACTIONS:
            return base.editable_by(self.request.user)
        if self.action == "mias":
            return base.filter(author=self.request.user)
        if self.action == "por_revisar":
            return base.filter(status=StoryStatus.IN_REVIEW)
        return base.visible_for(self.request.user)

    def get_serializer_class(self):
        if self.action in {"create", "update", "partial_update"}:
            return StoryWriteSerializer
        if self.action in {"retrieve"}:
            return StoryDetailSerializer
        return StoryListSerializer

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        Story.objects.filter(pk=instance.pk).update(view_count=F("view_count") + 1)
        instance.refresh_from_db(fields=["view_count"])
        return Response(self.get_serializer(instance).data)

    def create(self, request, *args, **kwargs):
        write = StoryWriteSerializer(data=request.data, context=self.get_serializer_context())
        write.is_valid(raise_exception=True)
        story = write.save()
        return Response(
            StoryDetailSerializer(story, context=self.get_serializer_context()).data,
            status=status.HTTP_201_CREATED,
        )

    # --- Mis historias y cola de revisión -------------------------------
    @action(detail=False, methods=["get"], permission_classes=[permissions.IsAuthenticated])
    def mias(self, request):
        page = self.paginate_queryset(self.filter_queryset(self.get_queryset()))
        serializer = StoryListSerializer(page, many=True, context=self.get_serializer_context())
        return self.get_paginated_response(serializer.data)

    @action(
        detail=False,
        methods=["get"],
        url_path="por-revisar",
        permission_classes=[permissions.IsAuthenticated],
    )
    def por_revisar(self, request):
        user = request.user
        qs = self.get_queryset()
        if not user.is_staff_role:
            ids = user.authority_community_ids()
            if not ids:
                raise PermissionDenied("No administra ninguna comunidad.")
            qs = qs.filter(community_id__in=ids)
        page = self.paginate_queryset(qs)
        serializer = StoryListSerializer(page, many=True, context=self.get_serializer_context())
        return self.get_paginated_response(serializer.data)

    @action(detail=True, methods=["post"], permission_classes=[permissions.IsAuthenticated])
    def enviar_a_revision(self, request, pk=None):
        story = self.get_object()
        if story.author_id != request.user.id and not request.user.is_staff_role:
            raise PermissionDenied("Solo la autoría puede enviar a revisión.")
        story.status = StoryStatus.IN_REVIEW
        story.save(update_fields=["status", "updated_at"])
        return Response(StoryDetailSerializer(story, context=self.get_serializer_context()).data)

    @action(
        detail=True,
        methods=["post"],
        permission_classes=[permissions.IsAuthenticated, CanModerateStory],
    )
    def publicar(self, request, pk=None):
        story = self.get_object()
        serializer = PublishSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            story.publish(by=request.user, note=serializer.validated_data.get("note", ""))
        except DjangoValidationError as exc:
            raise ValidationError(
                exc.message_dict if hasattr(exc, "message_dict") else exc.messages
            )
        return Response(StoryDetailSerializer(story, context=self.get_serializer_context()).data)

    @action(
        detail=True,
        methods=["post"],
        permission_classes=[permissions.IsAuthenticated, CanModerateStory],
    )
    def rechazar(self, request, pk=None):
        story = self.get_object()
        story.status = StoryStatus.REJECTED
        story.review_note = request.data.get("note", "")
        story.reviewed_by = request.user
        story.save(update_fields=["status", "review_note", "reviewed_by", "updated_at"])
        return Response(StoryDetailSerializer(story, context=self.get_serializer_context()).data)

    @action(
        detail=True,
        methods=["post"],
        permission_classes=[permissions.IsAuthenticated, CanModerateStory],
    )
    def archivar(self, request, pk=None):
        story = self.get_object()
        story.status = StoryStatus.ARCHIVED
        story.save(update_fields=["status", "updated_at"])
        return Response(status=status.HTTP_204_NO_CONTENT)

    # --- Reacciones ------------------------------------------------------
    @action(detail=True, methods=["post", "delete"], permission_classes=[permissions.IsAuthenticated])
    def aprecio(self, request, pk=None):
        story = self.get_object()
        if request.method == "DELETE":
            Reaction.objects.filter(story=story, user=request.user).delete()
        else:
            kind = request.data.get("kind", Reaction.Kind.LIKE)
            Reaction.objects.update_or_create(
                story=story, user=request.user, defaults={"kind": kind}
            )
        story.recount()
        story.refresh_from_db(fields=["like_count", "comment_count"])
        return Response({"like_count": story.like_count})

    # --- Autorizaciones y accesos ---------------------------------------
    @action(
        detail=True,
        methods=["get", "post"],
        url_path="autorizaciones",
        permission_classes=[permissions.IsAuthenticated],
    )
    def autorizaciones(self, request, pk=None):
        story = self.get_object()
        puede = (
            story.author_id == request.user.id
            or request.user.is_staff_role
            or story.community_id in request.user.authority_community_ids()
        )
        if not puede:
            raise PermissionDenied("No puede ver ni registrar autorizaciones de esta historia.")
        if request.method == "GET":
            return Response(ConsentSerializer(story.consents.all(), many=True).data)
        data = {**request.data, "story": story.pk}
        serializer = ConsentSerializer(data=data)
        serializer.is_valid(raise_exception=True)
        serializer.save(recorded_by=request.user)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @action(
        detail=True,
        methods=["get", "post"],
        url_path="accesos",
        permission_classes=[permissions.IsAuthenticated, CanModerateStory],
    )
    def accesos(self, request, pk=None):
        story = self.get_object()
        if request.method == "GET":
            qs = story.access_grants.select_related("user")
            return Response(StoryAccessGrantSerializer(qs, many=True).data)
        data = {**request.data, "story": story.pk}
        serializer = StoryAccessGrantSerializer(data=data)
        serializer.is_valid(raise_exception=True)
        serializer.save(granted_by=request.user)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    # --- Materiales -------------------------------------------------------
    @action(
        detail=True,
        methods=["get", "post"],
        url_path="materiales",
        permission_classes=[permissions.IsAuthenticated],
    )
    def materiales(self, request, pk=None):
        story = self.get_object()
        if request.method == "GET":
            return Response(MediaItemSerializer(story.media.all(), many=True).data)
        if story.author_id != request.user.id and not request.user.is_staff_role:
            raise PermissionDenied("Solo la autoría puede adjuntar materiales.")
        serializer = MediaItemSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save(story=story)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    # --- Mapa -------------------------------------------------------------
    @action(detail=False, methods=["get"], permission_classes=[permissions.AllowAny])
    def mapa(self, request):
        """Puntos del muro que pueden mostrarse en el mapa (excluye lo sensible)."""
        qs = (
            Story.objects.visible_for(request.user)
            .filter(is_sensitive=False, latitude__isnull=False, longitude__isnull=False)
            .select_related("community")
            .only(
                "id", "title", "kind", "place_name", "latitude", "longitude",
                "community__name", "community__slug",
            )
        )
        return Response(
            [
                {
                    "id": s.id,
                    "title": s.title,
                    "kind": s.kind,
                    "place_name": s.place_name,
                    "latitude": float(s.latitude),
                    "longitude": float(s.longitude),
                    "community": s.community.name if s.community_id else None,
                }
                for s in qs
            ]
        )


class CommentViewSet(viewsets.ModelViewSet):
    serializer_class = CommentSerializer
    permission_classes = [CommentPermission]
    filterset_fields = ["story", "parent"]

    def get_queryset(self):
        visible = Story.objects.visible_for(self.request.user).values("pk")
        return (
            Comment.objects.filter(story__in=visible, is_hidden=False)
            .select_related("author", "story")
            .prefetch_related("replies__author")
        )

    def perform_create(self, serializer):
        story = serializer.validated_data["story"]
        if not story.can_be_seen_by(self.request.user):
            raise PermissionDenied("No puede comentar una historia que no tiene acceso a ver.")
        comment = serializer.save(author=self.request.user)
        comment.story.recount()

    def perform_destroy(self, instance):
        story = instance.story
        super().perform_destroy(instance)
        story.recount()

    @action(detail=True, methods=["post"], permission_classes=[permissions.IsAuthenticated])
    def ocultar(self, request, pk=None):
        comment = self.get_object()
        user = request.user
        if not (
            user.is_staff_role
            or comment.story.community_id in user.authority_community_ids()
        ):
            raise PermissionDenied("Solo la moderación puede ocultar comentarios.")
        comment.is_hidden = True
        comment.hidden_reason = request.data.get("reason", "")
        comment.save(update_fields=["is_hidden", "hidden_reason", "updated_at"])
        comment.story.recount()
        return Response(status=status.HTTP_204_NO_CONTENT)


class TagViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Tag.objects.all()
    serializer_class = TagSerializer
    permission_classes = [permissions.AllowAny]
    search_fields = ["name"]
    pagination_class = None


class ReactionViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = ReactionSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if not user.is_authenticated:
            return Reaction.objects.none()
        return Reaction.objects.filter(user=user).select_related("story")


class ReportViewSet(viewsets.ModelViewSet):
    serializer_class = ReportSerializer
    permission_classes = [permissions.IsAuthenticated]
    http_method_names = ["get", "post", "patch", "head", "options"]

    def get_queryset(self):
        user = self.request.user
        qs = Report.objects.select_related("story", "comment")
        if not user.is_authenticated:
            return qs.none()
        if user.is_staff_role:
            return qs
        community_ids = user.authority_community_ids()
        return qs.filter(reporter=user) | qs.filter(story__community_id__in=community_ids)

    def perform_create(self, serializer):
        serializer.save(reporter=self.request.user)

    def perform_update(self, serializer):
        user = self.request.user
        report = self.get_object()
        if not (
            user.is_staff_role
            or (report.story and report.story.community_id in user.authority_community_ids())
        ):
            raise PermissionDenied("Solo la moderación puede resolver reportes.")
        serializer.save()


class ConsentViewSet(viewsets.ReadOnlyModelViewSet):
    """Consulta de autorizaciones, para autoridades y moderación."""

    serializer_class = ConsentSerializer
    permission_classes = [permissions.IsAuthenticated]
    filterset_fields = ["story", "community", "scope"]

    def get_queryset(self):
        user = self.request.user
        qs = Consent.objects.select_related("story", "community")
        if not user.is_authenticated:
            return qs.none()
        if user.is_staff_role:
            return qs
        return qs.filter(
            story__community_id__in=user.authority_community_ids()
        ) | qs.filter(story__author=user)


class AccessGrantViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = StoryAccessGrantSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if not user.is_authenticated:
            return StoryAccessGrant.objects.none()
        return StoryAccessGrant.objects.filter(user=user).select_related("story")
