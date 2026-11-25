from rest_framework.routers import DefaultRouter

from .views import (
    AccessGrantViewSet,
    CommentViewSet,
    ConsentViewSet,
    ReactionViewSet,
    ReportViewSet,
    StoryViewSet,
    TagViewSet,
)

router = DefaultRouter()
router.register("historias", StoryViewSet, basename="historia")
router.register("comentarios", CommentViewSet, basename="comentario")
router.register("etiquetas", TagViewSet, basename="etiqueta")
router.register("reacciones", ReactionViewSet, basename="reaccion")
router.register("reportes", ReportViewSet, basename="reporte")
router.register("autorizaciones", ConsentViewSet, basename="autorizacion")
router.register("mis-accesos", AccessGrantViewSet, basename="mi-acceso")

urlpatterns = router.urls
