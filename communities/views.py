from django.db.models import Count, Prefetch, Q
from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response

from .models import Community, Membership
from .serializers import (
    CommunitySerializer,
    JoinRequestSerializer,
    MembershipDecisionSerializer,
    MembershipSerializer,
)


class IsPlatformStaffOrReadOnly(permissions.BasePermission):
    """Las comunidades las crea y edita la administración de la plataforma."""

    def has_permission(self, request, view):
        if request.method in permissions.SAFE_METHODS:
            return True
        return bool(request.user and request.user.is_authenticated and request.user.is_staff_role)


class CommunityViewSet(viewsets.ModelViewSet):
    serializer_class = CommunitySerializer
    permission_classes = [permissions.AllowAny, IsPlatformStaffOrReadOnly]
    lookup_field = "slug"
    search_fields = ["name", "territory", "municipality", "department", "description"]
    filterset_fields = ["people", "department", "municipality"]

    def get_queryset(self):
        # La anotación NO puede llamarse `member_count`: `Community` ya expone
        # una propiedad con ese nombre y Django no puede escribirla sobre la
        # instancia (AttributeError: property has no setter).
        return (
            Community.objects.annotate(
                active_members=Count(
                    "memberships",
                    filter=Q(memberships__status=Membership.Status.ACTIVE),
                    distinct=True,
                )
            )
            .prefetch_related(Prefetch("memberships", queryset=Membership.objects.all()))
            .order_by("name")
        )

    # --- Solicitar ingreso ---------------------------------------------
    @action(detail=True, methods=["post"], permission_classes=[permissions.IsAuthenticated])
    def solicitar(self, request, slug=None):
        community = self.get_object()
        if not community.is_open_to_requests:
            return Response(
                {"detail": "Esta comunidad no está recibiendo solicitudes."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        serializer = JoinRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        membership, created = Membership.objects.get_or_create(
            community=community,
            user=request.user,
            defaults={"note": serializer.validated_data.get("note", "")},
        )
        if not created and membership.status == Membership.Status.LEFT:
            membership.status = Membership.Status.PENDING
            membership.note = serializer.validated_data.get("note", membership.note)
            membership.save(update_fields=["status", "note", "updated_at"])
        return Response(
            MembershipSerializer(membership).data,
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )

    @action(detail=True, methods=["get"], permission_classes=[permissions.IsAuthenticated])
    def miembros(self, request, slug=None):
        community = self.get_object()
        if not self._can_administer(request.user, community):
            qs = community.memberships.filter(status=Membership.Status.ACTIVE)
        else:
            qs = community.memberships.all()
        qs = qs.select_related("user")
        return Response(MembershipSerializer(qs, many=True).data)

    @action(
        detail=True,
        methods=["post"],
        url_path="miembros/(?P<membership_id>[^/.]+)/decidir",
        permission_classes=[permissions.IsAuthenticated],
    )
    def decidir(self, request, slug=None, membership_id=None):
        community = self.get_object()
        if not self._can_administer(request.user, community):
            raise PermissionDenied(
                "Solo las autoridades de la comunidad o la moderación pueden decidir."
            )
        membership = community.memberships.filter(pk=membership_id).first()
        if membership is None:
            return Response(status=status.HTTP_404_NOT_FOUND)
        serializer = MembershipDecisionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        membership.status = serializer.validated_data["status"]
        if "role" in serializer.validated_data:
            membership.role = serializer.validated_data["role"]
        membership.decided_by = request.user
        membership.save()
        return Response(MembershipSerializer(membership).data)

    @staticmethod
    def _can_administer(user, community) -> bool:
        if not user or not user.is_authenticated:
            return False
        if user.is_staff_role:
            return True
        return community.id in user.authority_community_ids()


class MyMembershipViewSet(viewsets.ReadOnlyModelViewSet):
    """Vínculos de la persona autenticada."""

    serializer_class = MembershipSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return self.request.user.memberships.select_related("community", "user")
