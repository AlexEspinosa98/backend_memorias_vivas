from rest_framework.routers import DefaultRouter

from .views import ArchiveSectionViewSet, SourceViewSet

router = DefaultRouter()
router.register("archivo", ArchiveSectionViewSet, basename="archivo")
router.register("fuentes", SourceViewSet, basename="fuente")

urlpatterns = router.urls
