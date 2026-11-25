from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

User = get_user_model()


class UserPublicSerializer(serializers.ModelSerializer):
    """Datos mínimos de autoría que se muestran en el muro."""

    class Meta:
        model = User
        fields = ["id", "display_name", "role", "place", "avatar"]
        read_only_fields = fields


class UserSerializer(serializers.ModelSerializer):
    communities = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            "id",
            "email",
            "display_name",
            "role",
            "bio",
            "place",
            "avatar",
            "accepted_care_terms_at",
            "communities",
            "date_joined",
        ]
        read_only_fields = ["id", "email", "role", "date_joined", "accepted_care_terms_at"]

    def get_communities(self, user):
        from communities.serializers import MembershipSerializer

        qs = user.memberships.select_related("community").filter(status="activo")
        return MembershipSerializer(qs, many=True).data


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=8)
    accept_care_terms = serializers.BooleanField(write_only=True)

    class Meta:
        model = User
        fields = [
            "email",
            "display_name",
            "password",
            "place",
            "bio",
            "accept_care_terms",
        ]

    def validate_accept_care_terms(self, value):
        if not value:
            raise serializers.ValidationError(
                "Debe aceptar los criterios de cuidado cultural del archivo."
            )
        return value

    def create(self, validated):
        validated.pop("accept_care_terms")
        password = validated.pop("password")
        user = User.objects.create_user(
            password=password,
            accepted_care_terms_at=timezone.now(),
            **validated,
        )
        return user


class LoginSerializer(TokenObtainPairSerializer):
    """Devuelve también el usuario, para que el front no haga una segunda llamada."""

    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        token["display_name"] = user.display_name
        token["role"] = user.role
        return token

    def validate(self, attrs):
        data = super().validate(attrs)
        data["user"] = UserSerializer(self.user).data
        return data
