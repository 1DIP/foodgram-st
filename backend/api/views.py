from django.db.models import Sum
from django.http import FileResponse
from django.utils import timezone
from djoser.views import UserViewSet as DjoserUserViewSet
from recipes.models import (
    Favorite,
    Ingredient,
    Recipe,
    ShoppingCart,
    Subscription,
    User
)
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.generics import get_object_or_404
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import (
    BasePermission,
    IsAuthenticated,
    IsAuthenticatedOrReadOnly
)
from rest_framework.response import Response
from rest_framework.reverse import reverse

from .pagination import CustomPagePagination
from .serializers import (
    AvatarSerializer,
    IngredientSerializer,
    RecipeSerializer,
    ShortRecipeSerializer,
    UserWithRecipesSerializer,
    UserSerializer
)


class IsAuthorOrReadOnly(BasePermission):
    """Права доступа для автора или только чтение"""

    def has_permission(self, request, view):
        """Базовая проверка прав доступа"""
        # Разрешаем чтение всем
        if request.method in ['GET', 'HEAD', 'OPTIONS']:
            return True

        # Для записи требуется аутентификация
        return request.user and request.user.is_authenticated

    def has_object_permission(self, request, view, obj):
        """Проверка прав доступа к конкретному объекту"""
        # Разрешаем чтение всем
        if request.method in ['GET', 'HEAD', 'OPTIONS']:
            return True

        # Для записи проверяем, что пользователь является автором
        return obj.author == request.user


class UserViewSet(DjoserUserViewSet):
    """Управление пользователями и подписками"""

    queryset = User.objects.all()
    serializer_class = UserSerializer
    pagination_class = CustomPagePagination
    permission_classes = [IsAuthenticatedOrReadOnly]

    def get_permissions(self):
        """Настройка прав доступа"""
        if self.action in ['me', 'manage_avatar']:
            return [IsAuthenticated()]
        return super().get_permissions()

    @action(
        detail=False,
        methods=['get'],
        url_path='me',
        permission_classes=[IsAuthenticated]
    )
    def get_me(self, request):
        """Получение данных текущего пользователя"""
        return Response(self.get_serializer(request.user).data)

    @action(
        detail=False,
        methods=['put', 'delete'],
        url_path='me/avatar',
        permission_classes=[IsAuthenticated]
    )
    def manage_avatar(self, request):
        """Добавление или удаление аватара"""

        user = request.user
        if request.method == 'PUT':
            if 'avatar' not in request.data:
                return Response(
                    {'avatar': 'Это поле обязательно.'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            serializer = AvatarSerializer(
                user, data=request.data,
                partial=True
            )
            serializer.is_valid(raise_exception=True)
            serializer.save()
            return Response(
                {'avatar': serializer.data['avatar']},
                status=status.HTTP_200_OK
            )

        if user.avatar:
            user.avatar.delete()
        user.avatar = None
        user.save()
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(
        detail=True,
        methods=['post', 'delete'],
        url_path='subscribe',
        permission_classes=[IsAuthenticated]
    )
    def manage_subscription(self, request, id=None):
        """Подписка и отписка от автора"""

        author = get_object_or_404(User, pk=id)
        if author == request.user:
            raise ValidationError(
                {'error': 'Нельзя подписаться на себя'}
            )

        if request.method == 'POST':
            _, created = Subscription.objects.get_or_create(
                user=request.user,
                author=author
            )

            if not created:
                raise ValidationError({'errors': 'Подписка уже оформлена'})

            return Response(
                UserWithRecipesSerializer(
                    author, context={'request': request}
                ).data,
                status=status.HTTP_201_CREATED
            )

        subscription = request.user.subscriptions.filter(author=author).first()

        if not subscription:
            raise ValidationError({'errors': 'Подписка не найдена'})

        subscription.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(
        detail=False,
        methods=['get'],
        url_path='subscriptions',
        permission_classes=[IsAuthenticated]
    )
    def get_subscriptions(self, request):
        """Список подписок пользователя"""

        user = request.user
        # Исправлено: используем правильный related_name
        subscriptions = (
            user.subscriptions.all()
            .select_related('author')
        )

        paginator = PageNumberPagination()
        paginator.page_size = int(request.query_params.get('limit', 6))
        paginated_subscriptions = paginator.paginate_queryset(
            subscriptions,
            request
        )

        authors = [
            subscription.author for subscription in paginated_subscriptions
        ]

        return paginator.get_paginated_response(
            UserWithRecipesSerializer(
                authors,
                many=True,
                context={'request': request}
            ).data
        )


class IngredientViewSet(viewsets.ReadOnlyModelViewSet):
    """Просмотр ингредиентов"""

    queryset = Ingredient.objects.all()
    serializer_class = IngredientSerializer
    pagination_class = None

    def get_queryset(self):
        """Поиск ингредиентов по названию"""
        name = self.request.query_params.get('name')
        if name:
            return self.queryset.filter(name__istartswith=name.lower())
        return self.queryset


class RecipeViewSet(viewsets.ModelViewSet):
    """Управление рецептами"""

    queryset = Recipe.objects.all()
    serializer_class = RecipeSerializer
    permission_classes = [IsAuthenticatedOrReadOnly, IsAuthorOrReadOnly]
    pagination_class = CustomPagePagination

    def get_queryset(self):
        """Фильтрация рецептов"""

        queryset = super().get_queryset()
        author_id = self.request.query_params.get('author')
        is_favorited = self.request.query_params.get('is_favorited')
        is_in_shopping_cart = self.request.query_params.get(
            'is_in_shopping_cart'
        )
        if author_id:
            queryset = queryset.filter(author__id=author_id)
        if is_favorited == '1' and self.request.user.is_authenticated:
            queryset = queryset.filter(favorites__user=self.request.user)
        if is_in_shopping_cart == '1' and self.request.user.is_authenticated:
            return queryset.filter(
                shoppingcarts__user=self.request.user
            )
        return queryset

    def perform_create(self, serializer):
        """Установка автора рецепта"""
        serializer.save(author=self.request.user)

    @staticmethod
    def handle_recipe_action(request, recipe, model):
        """Добавление/удаление рецепта в избранное или корзину"""
        if request.method == 'POST':
            _, created = model.objects.get_or_create(
                user=request.user,
                recipe=recipe
            )
            if not created:
                raise ValidationError({'errors': 'Рецепт уже добавлен'})

            return Response(
                ShortRecipeSerializer(recipe).data,
                status=status.HTTP_201_CREATED
            )

        obj = model.objects.filter(
            user=request.user,
            recipe=recipe
        ).first()

        if not obj:
            raise ValidationError({'errors': 'Рецепт не найден'})

        obj.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(
        detail=True,
        methods=['post', 'delete'],
        url_path='favorite',
        permission_classes=[IsAuthenticated]
    )
    def manage_favorites(self, request, pk=None):
        """Добавление/удаление рецепта в избранное"""
        return self.handle_recipe_action(
            request,
            get_object_or_404(Recipe, pk=pk),
            Favorite
        )

    @action(
        detail=True,
        methods=['post', 'delete'],
        url_path='shopping_cart',
        permission_classes=[IsAuthenticated]
    )
    def manage_shopping_cart(self, request, pk=None):
        """Добавление/удаление рецепта в корзину"""
        return self.handle_recipe_action(
            request,
            get_object_or_404(Recipe, pk=pk),
            ShoppingCart
        )

    @action(
        detail=False,
        methods=['get'],
        url_path='download_shopping_cart',
        permission_classes=[IsAuthenticated]
    )
    def download_shopping_list(self, request):
        """Скачивание списка покупок"""

        # Получаем агрегированные данные одним запросом
        ingredients_data = (
            request.user.shoppingcarts
            .select_related('recipe__author')
            .prefetch_related('recipe__recipe_ingredients__ingredient')
            .values(
                'recipe__recipe_ingredients__ingredient__name',
                'recipe__recipe_ingredients__ingredient__measurement_unit'
            )
            .annotate(
                total_amount=Sum('recipe__recipe_ingredients__amount')
            )
            .order_by('recipe__recipe_ingredients__ingredient__name')
        )

        # Получаем рецепты одним запросом
        recipes_data = (
            request.user.shoppingcarts
            .select_related('recipe__author')
            .values('recipe__name', 'recipe__author__username')
            .distinct()
            .order_by('recipe__name')
        )

        report_text = self.create_shopping_report(
            ingredients_data,
            recipes_data,
            timezone.now().strftime('%d.%m.%Y')
        )

        return FileResponse(
            report_text,
            content_type='text/plain',
            filename='shopping_list.txt'
        )

    def create_shopping_report(self, ingredients_data, recipes_data, date):
        """Формирование отчета списка покупок"""
        report_lines = [
            f'Список покупок от {date}:',
            'Ингредиенты:',
        ]

        for num, ingredient in enumerate(ingredients_data, start=1):
            name = ingredient['recipe__recipe_ingredients__ingredient__name']
            unit = ingredient[
                'recipe__recipe_ingredients__ingredient__measurement_unit'
            ]
            amount = ingredient['total_amount']
            report_lines.append(
                f'{num}. '
                f'{name.capitalize()} ({unit}) - {amount}'
            )

        report_lines.append('\nРецепты:')
        for num, recipe in enumerate(recipes_data, start=1):
            recipe_name = recipe['recipe__name']
            author = recipe['recipe__author__username']
            report_lines.append(
                f'{num}. {recipe_name} (от: {author})'
            )

        return '\n'.join(report_lines)

    @action(detail=True, methods=['get'], url_path='get-link')
    def get_short_link(self, request, pk=None):
        """Получение короткой ссылки на рецепт"""
        get_object_or_404(Recipe, pk=pk)
        short_link = request.build_absolute_uri(
            reverse('recipes:recipe-short-link', args=[pk])
        )
        return Response({'short-link': short_link}, status=status.HTTP_200_OK)
