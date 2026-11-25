from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers

from accounts.serializers import UserPublicSerializer

from .models import (
    Comment,
    Consent,
    MediaItem,
    Promotion,
    Reaction,
    Report,
    Story,
    StoryAccessGrant,
    StoryStatus,
    Tag,
    Visibility,
    Visit,
)


class TagSerializer(serializers.ModelSerializer):
    class Meta:
        model = Tag
        fields = ["id", "name", "slug"]
        read_only_fields = ["id", "slug"]


class MediaItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = MediaItem
        fields = [
            "id",
            "kind",
            "file",
            "external_url",
            "caption",
            "credit",
            "transcript",
            "order",
        ]
        read_only_fields = ["id"]


class ConsentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Consent
        fields = [
            "id",
            "story",
            "granted_by_name",
            "granted_by_role",
            "community",
            "scope",
            "granted_on",
            "conditions",
            "evidence",
            "created_at",
        ]
        read_only_fields = ["id", "created_at"]


class VisitSerializer(serializers.ModelSerializer):
    class Meta:
        model = Visit
        exclude = ["story"]


class PromotionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Promotion
        exclude = ["story"]


class CommentSerializer(serializers.ModelSerializer):
    author = UserPublicSerializer(read_only=True)
    replies = serializers.SerializerMethodField()

    class Meta:
        model = Comment
        fields = [
            "id",
            "story",
            "author",
            "parent",
            "body",
            "is_hidden",
            "replies",
            "created_at",
        ]
        read_only_fields = ["id", "author", "is_hidden", "created_at"]

    def get_replies(self, comment):
        if comment.parent_id is not None:
            return []
        qs = comment.replies.filter(is_hidden=False).select_related("author")
        return CommentSerializer(qs, many=True, context=self.context).data

    def validate(self, attrs):
        story = attrs.get("story") or getattr(self.instance, "story", None)
        if story and not story.allow_comments:
            raise serializers.ValidationError(
                {"story": "Esta historia no admite comentarios."}
            )
        parent = attrs.get("parent")
        if parent and parent.story_id != (story.id if story else None):
            raise serializers.ValidationError(
                {"parent": "El comentario padre pertenece a otra historia."}
            )
        if parent and parent.parent_id is not None:
            raise serializers.ValidationError(
                {"parent": "Solo se admite un nivel de respuestas."}
            )
        return attrs


class StoryListSerializer(serializers.ModelSerializer):
    """Versión ligera para el muro."""

    author = UserPublicSerializer(read_only=True)
    community_name = serializers.CharField(source="community.name", default=None, read_only=True)
    community_slug = serializers.CharField(source="community.slug", default=None, read_only=True)
    tags = TagSerializer(many=True, read_only=True)
    location = serializers.SerializerMethodField()
    cover = serializers.SerializerMethodField()
    my_reaction = serializers.SerializerMethodField()

    class Meta:
        model = Story
        fields = [
            "id",
            "title",
            "summary",
            "kind",
            "language",
            "visibility",
            "status",
            "author",
            "community",
            "community_name",
            "community_slug",
            "tags",
            "location",
            "cover",
            "is_sensitive",
            "is_featured",
            "allow_comments",
            "like_count",
            "comment_count",
            "view_count",
            "my_reaction",
            "published_at",
            "created_at",
        ]
        read_only_fields = fields

    def get_location(self, story):
        return story.public_location

    def get_cover(self, story):
        item = next(
            (m for m in story.media.all() if m.kind == MediaItem.Kind.IMAGE), None
        )
        if item is None:
            return None
        request = self.context.get("request")
        if item.file:
            url = item.file.url
            return request.build_absolute_uri(url) if request else url
        return item.external_url or None

    def get_my_reaction(self, story):
        request = self.context.get("request")
        user = getattr(request, "user", None)
        if not user or not user.is_authenticated:
            return None
        reaction = next((r for r in story.reactions.all() if r.user_id == user.id), None)
        return reaction.kind if reaction else None


class StoryDetailSerializer(StoryListSerializer):
    media = MediaItemSerializer(many=True, read_only=True)
    visit = VisitSerializer(read_only=True)
    promotion = PromotionSerializer(read_only=True)
    consents = serializers.SerializerMethodField()

    class Meta(StoryListSerializer.Meta):
        fields = StoryListSerializer.Meta.fields + [
            "body",
            "media",
            "visit",
            "promotion",
            "consents",
            "review_note",
            "updated_at",
        ]
        read_only_fields = fields

    def get_consents(self, story):
        """El detalle de la autorización solo lo ven autoría, autoridades y moderación."""
        request = self.context.get("request")
        user = getattr(request, "user", None)
        if not user or not user.is_authenticated:
            return []
        if (
            user.id == story.author_id
            or user.is_staff_role
            or story.community_id in user.authority_community_ids()
        ):
            return ConsentSerializer(story.consents.all(), many=True).data
        # Para el resto: solo que existe autorización y con qué alcance.
        return [
            {"scope": c.scope, "granted_on": c.granted_on}
            for c in story.consents.all()
        ]


class StoryWriteSerializer(serializers.ModelSerializer):
    tags = serializers.ListField(
        child=serializers.CharField(max_length=60), required=False, write_only=True
    )
    visit = VisitSerializer(required=False)
    promotion = PromotionSerializer(required=False)

    class Meta:
        model = Story
        fields = [
            "id",
            "title",
            "summary",
            "body",
            "kind",
            "language",
            "visibility",
            "status",
            "community",
            "place_name",
            "latitude",
            "longitude",
            "is_sensitive",
            "allow_comments",
            "tags",
            "visit",
            "promotion",
        ]
        read_only_fields = ["id"]

    def validate_status(self, value):
        if value == StoryStatus.PUBLISHED:
            raise serializers.ValidationError(
                "La publicación se hace con la acción `publicar/`, que verifica "
                "el registro de autorización de la comunidad."
            )
        return value

    def validate_community(self, community):
        user = self.context["request"].user
        if community is None:
            return community
        if user.is_staff_role:
            return community
        if community.id not in user.community_ids():
            raise serializers.ValidationError(
                "Solo puede publicar en comunidades donde es miembro activo."
            )
        return community

    def _sync_tags(self, story, names):
        tags = []
        for name in names:
            tag, _ = Tag.objects.get_or_create(
                name=name.strip(), defaults={"name": name.strip()}
            )
            tags.append(tag)
        story.tags.set(tags)

    def create(self, validated):
        tag_names = validated.pop("tags", [])
        visit_data = validated.pop("visit", None)
        promo_data = validated.pop("promotion", None)
        story = Story(author=self.context["request"].user, **validated)
        try:
            story.full_clean(exclude=["author"])
        except DjangoValidationError as exc:
            raise serializers.ValidationError(exc.message_dict)
        story.save()
        self._sync_tags(story, tag_names)
        if visit_data:
            Visit.objects.create(story=story, **visit_data)
        if promo_data:
            Promotion.objects.create(story=story, **promo_data)
        return story

    def update(self, instance, validated):
        tag_names = validated.pop("tags", None)
        visit_data = validated.pop("visit", None)
        promo_data = validated.pop("promotion", None)
        for field, value in validated.items():
            setattr(instance, field, value)
        try:
            instance.full_clean(exclude=["author"])
        except DjangoValidationError as exc:
            raise serializers.ValidationError(exc.message_dict)
        instance.save()
        if tag_names is not None:
            self._sync_tags(instance, tag_names)
        if visit_data is not None:
            Visit.objects.update_or_create(story=instance, defaults=visit_data)
        if promo_data is not None:
            Promotion.objects.update_or_create(story=instance, defaults=promo_data)
        return instance


class ReactionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Reaction
        fields = ["id", "story", "kind", "created_at"]
        read_only_fields = ["id", "created_at"]


class StoryAccessGrantSerializer(serializers.ModelSerializer):
    user_detail = UserPublicSerializer(source="user", read_only=True)

    class Meta:
        model = StoryAccessGrant
        fields = ["id", "story", "user", "user_detail", "reason", "created_at"]
        read_only_fields = ["id", "created_at"]


class ReportSerializer(serializers.ModelSerializer):
    class Meta:
        model = Report
        fields = [
            "id",
            "story",
            "comment",
            "reason",
            "detail",
            "status",
            "resolution",
            "created_at",
        ]
        read_only_fields = ["id", "status", "resolution", "created_at"]

    def validate(self, attrs):
        if not attrs.get("story") and not attrs.get("comment"):
            raise serializers.ValidationError(
                "Indique la historia o el comentario reportado."
            )
        return attrs


class PublishSerializer(serializers.Serializer):
    note = serializers.CharField(required=False, allow_blank=True)
