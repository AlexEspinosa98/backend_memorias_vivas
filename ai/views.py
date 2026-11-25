from django.utils import timezone
from datetime import timedelta

from rest_framework import permissions, serializers, status
from rest_framework.response import Response
from rest_framework.views import APIView

from .assistant import preguntar
from .models import AssistantQuery

LIMITE_POR_HORA = 30


class PreguntaSerializer(serializers.Serializer):
    pregunta = serializers.CharField(max_length=500, trim_whitespace=True)


class AsistenteView(APIView):
    """
    Consulta al archivo en lenguaje natural.

    Abierta a cualquiera, como el archivo: una persona sin cuenta recibe
    respuestas construidas solo con el contenido de uso abierto, porque el
    contexto sale de `visible_index_for(user)`.
    """

    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = PreguntaSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        if self._excedio_el_limite(request):
            return Response(
                {
                    "estado": "limite",
                    "respuesta": (
                        "Ha hecho muchas consultas seguidas. Espere un momento "
                        "antes de volver a preguntar."
                    ),
                    "fuentes": [],
                },
                status=status.HTTP_429_TOO_MANY_REQUESTS,
            )

        user = request.user if request.user.is_authenticated else None
        return Response(preguntar(serializer.validated_data["pregunta"], user))

    @staticmethod
    def _excedio_el_limite(request) -> bool:
        """Un tope sencillo por persona: el modelo cuesta y la cuota es finita."""
        if not request.user.is_authenticated:
            return False
        desde = timezone.now() - timedelta(hours=1)
        return (
            AssistantQuery.objects.filter(
                asked_by=request.user, created_at__gte=desde
            ).count()
            >= LIMITE_POR_HORA
        )
