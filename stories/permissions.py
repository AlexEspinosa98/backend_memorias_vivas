from rest_framework import permissions


class StoryPermission(permissions.BasePermission):
    """
    Lectura: abierta (el queryset ya filtra por visibilidad).
    Escritura: solo autenticados.
    Objeto: autoría, autoridad de la comunidad o moderación de plataforma.
    """

    def has_permission(self, request, view):
        if request.method in permissions.SAFE_METHODS:
            return True
        return bool(request.user and request.user.is_authenticated)

    def has_object_permission(self, request, view, obj):
        user = request.user
        if request.method in permissions.SAFE_METHODS:
            return obj.can_be_seen_by(user)
        if not user or not user.is_authenticated:
            return False
        return (
            obj.author_id == user.id
            or user.is_staff_role
            or obj.community_id in user.authority_community_ids()
        )


class CanModerateStory(permissions.BasePermission):
    """Publicar, rechazar o conceder acceso: autoridad de la comunidad o moderación."""

    def has_object_permission(self, request, view, obj):
        user = request.user
        if not user or not user.is_authenticated:
            return False
        return user.is_staff_role or obj.community_id in user.authority_community_ids()


class CommentPermission(permissions.BasePermission):
    def has_permission(self, request, view):
        if request.method in permissions.SAFE_METHODS:
            return True
        return bool(request.user and request.user.is_authenticated)

    def has_object_permission(self, request, view, obj):
        user = request.user
        if request.method in permissions.SAFE_METHODS:
            return obj.story.can_be_seen_by(user)
        if not user or not user.is_authenticated:
            return False
        return (
            obj.author_id == user.id
            or user.is_staff_role
            or obj.story.community_id in user.authority_community_ids()
        )
