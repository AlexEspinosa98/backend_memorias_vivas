from rest_framework import serializers

from accounts.serializers import UserPublicSerializer

from .models import Community, Membership


class CommunitySerializer(serializers.ModelSerializer):
    member_count = serializers.IntegerField(read_only=True)
    my_membership = serializers.SerializerMethodField()

    class Meta:
        model = Community
        fields = [
            "id",
            "name",
            "slug",
            "people",
            "description",
            "territory",
            "municipality",
            "department",
            "latitude",
            "longitude",
            "cover",
            "is_open_to_requests",
            "member_count",
            "my_membership",
            "created_at",
        ]
        read_only_fields = ["id", "slug", "created_at"]

    def get_my_membership(self, community):
        user = self.context.get("request").user if self.context.get("request") else None
        if not user or not user.is_authenticated:
            return None
        membership = next(
            (m for m in community.memberships.all() if m.user_id == user.id), None
        )
        if membership is None:
            return None
        return {"role": membership.role, "status": membership.status}


class MembershipSerializer(serializers.ModelSerializer):
    community_name = serializers.CharField(source="community.name", read_only=True)
    community_slug = serializers.CharField(source="community.slug", read_only=True)
    user = UserPublicSerializer(read_only=True)

    class Meta:
        model = Membership
        fields = [
            "id",
            "community",
            "community_name",
            "community_slug",
            "user",
            "role",
            "status",
            "note",
            "created_at",
        ]
        read_only_fields = ["id", "user", "created_at"]


class JoinRequestSerializer(serializers.Serializer):
    note = serializers.CharField(required=False, allow_blank=True, max_length=300)


class MembershipDecisionSerializer(serializers.Serializer):
    status = serializers.ChoiceField(
        choices=[Membership.Status.ACTIVE, Membership.Status.REJECTED]
    )
    role = serializers.ChoiceField(choices=Membership.Role.choices, required=False)
