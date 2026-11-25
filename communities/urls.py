from rest_framework.routers import DefaultRouter

from .views import CommunityViewSet, MyMembershipViewSet

router = DefaultRouter()
router.register("comunidades", CommunityViewSet, basename="comunidad")
router.register("mis-comunidades", MyMembershipViewSet, basename="mi-comunidad")

urlpatterns = router.urls
