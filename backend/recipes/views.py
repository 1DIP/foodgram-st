from django.shortcuts import redirect
from django.urls import reverse
from rest_framework.views import APIView

from .models import Recipe


class RecipeShortLinkView(APIView):
    """Обработка коротких ссылок"""

    def get(self, request, pk):
        """Редирект на полную ссылку рецепта"""
        recipe = Recipe.objects.get(pk=pk)
        return redirect(reverse('recipes-detail', args=[pk]))