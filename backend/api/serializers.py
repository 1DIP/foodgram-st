from djoser.serializers import UserSerializer as DjoserUserSerializer
from djoser.serializers import UserCreateSerializer as DjoserUserCreateSerializer
from drf_extra_fields.fields import Base64ImageField
from rest_framework import serializers
import re

from recipes.models import (
    Favorite,
    Ingredient,
    IngredientInRecipe,
    Recipe,
    ShoppingCart,
    Subscription,
)


class UserCreateSerializer(DjoserUserCreateSerializer):
    first_name = serializers.CharField(required=True, max_length=150)
    last_name = serializers.CharField(required=True, max_length=150)
    username = serializers.CharField(required=True, max_length=150)
    email = serializers.EmailField(required=True, max_length=254)

    class Meta(DjoserUserCreateSerializer.Meta):
        fields = (
            'email',
            'id',
            'username',
            'first_name',
            'last_name',
            'password',
        )

    def validate_username(self, value):
        if not re.match(r'^[\w.@+-]+$', value):
            raise serializers.ValidationError(
                'Username может содержать только буквы, цифры и символы: @ . + -'
            )
        return value

    def to_representation(self, instance):
        data = {
            'email': instance.email,
            'id': instance.id,
            'username': instance.username,
            'first_name': instance.first_name,
            'last_name': instance.last_name,
        }
        return data


class UserSerializer(DjoserUserSerializer):
    """Сериализатор пользователя с подпиской"""

    is_subscribed = serializers.SerializerMethodField()
    avatar = Base64ImageField(required=False)

    class Meta(DjoserUserSerializer.Meta):
        fields = (
            *DjoserUserSerializer.Meta.fields,
            'avatar',
            'is_subscribed'
        )

    def get_is_subscribed(self, obj):
        request = self.context.get('request')
        if not request or not hasattr(request, 'user'):
            return False
        user = request.user
        if not user.is_authenticated:
            return False
        return Subscription.objects.filter(
            author=obj,
            user=user
        ).exists()


class AvatarSerializer(serializers.ModelSerializer):
    """Сериализатор для аватара"""
    avatar = Base64ImageField(required=True)

    class Meta:
        model = DjoserUserSerializer.Meta.model
        fields = ('avatar',)


class IngredientSerializer(serializers.ModelSerializer):
    """Сериализатор ингредиентов"""

    class Meta:
        model = Ingredient
        fields = ('id', 'name', 'measurement_unit')


class IngredientInRecipeSerializer(serializers.ModelSerializer):
    """Сериализатор ингредиентов в рецепте"""

    id = serializers.PrimaryKeyRelatedField(
        queryset=Ingredient.objects.all(),
        source='ingredient'
    )
    name = serializers.ReadOnlyField(source='ingredient.name')
    measurement_unit = serializers.ReadOnlyField(
        source='ingredient.measurement_unit'
    )
    amount = serializers.IntegerField(min_value=1)

    class Meta:
        model = IngredientInRecipe
        fields = ('id', 'name', 'measurement_unit', 'amount')


class RecipeSerializer(serializers.ModelSerializer):
    """Сериализатор рецептов"""

    author = UserSerializer(read_only=True)
    ingredients = IngredientInRecipeSerializer(
        source='recipe_ingredients', many=True
    )
    is_favorited = serializers.SerializerMethodField()
    is_in_shopping_cart = serializers.SerializerMethodField()
    image = Base64ImageField(required=True)
    name = serializers.CharField(max_length=256, required=True)
    text = serializers.CharField(required=True)
    cooking_time = serializers.IntegerField(min_value=1, required=True)

    class Meta:
        model = Recipe
        fields = (
            'id',
            'name',
            'text',
            'image',
            'author',
            'cooking_time',
            'ingredients',
            'is_favorited',
            'is_in_shopping_cart',
        )

    def validate_ingredients(self, value):
        if not value:
            raise serializers.ValidationError(
                'Необходимо добавить хотя бы один ингредиент'
            )

        ingredient_ids = [item['ingredient'].id for item in value]
        if len(ingredient_ids) != len(set(ingredient_ids)):
            raise serializers.ValidationError(
                'Ингредиенты не должны повторяться'
            )

        return value

    def validate_image(self, value):
        if not value:
            raise serializers.ValidationError(
                'Необходимо добавить изображение'
            )
        return value

    def validate_name(self, value):
        if not value or not value.strip():
            raise serializers.ValidationError(
                'Название рецепта не может быть пустым'
            )
        return value

    def validate_text(self, value):
        if not value or not value.strip():
            raise serializers.ValidationError(
                'Описание рецепта не может быть пустым'
            )
        return value

    def create(self, validated_data):
        ingredients_data = validated_data.pop('recipe_ingredients')
        recipe = super().create(validated_data)
        self.add_ingredients(recipe, ingredients_data)
        return recipe

    def update(self, instance, validated_data):
        if 'recipe_ingredients' not in validated_data:
            raise serializers.ValidationError({
                'ingredients': 'Необходимо добавить хотя бы один ингредиент'
            })
        ingredients_data = validated_data.pop('recipe_ingredients')
        instance.recipe_ingredients.all().delete()
        self.add_ingredients(instance, ingredients_data)
        return super().update(instance, validated_data)

    def add_ingredients(self, recipe, ingredients_data):
        IngredientInRecipe.objects.bulk_create(
            IngredientInRecipe(
                recipe=recipe,
                ingredient=ingredient['ingredient'],
                amount=ingredient['amount']
            )
            for ingredient in ingredients_data
        )

    def check_recipe_status(self, model, recipe):
        request = self.context.get('request')
        return (
            request and request.user.is_authenticated
            and model.objects.filter(
                user=request.user,
                recipe=recipe
            ).exists()
        )

    def get_is_favorited(self, obj):
        return self.check_recipe_status(Favorite, obj)

    def get_is_in_shopping_cart(self, obj):
        return self.check_recipe_status(ShoppingCart, obj)


class ShortRecipeSerializer(serializers.ModelSerializer):
    """Краткий сериализатор рецепта"""

    class Meta:
        model = Recipe
        fields = ('id', 'name', 'image', 'cooking_time')
        read_only_fields = ('id', 'name', 'image', 'cooking_time')


class UserWithRecipesSerializer(UserSerializer):
    """Сериализатор пользователя с рецептами"""

    recipes = serializers.SerializerMethodField()
    recipes_count = serializers.ReadOnlyField(
        source='recipes.count'
    )

    class Meta(UserSerializer.Meta):
        fields = (
            *UserSerializer.Meta.fields,
            'recipes',
            'recipes_count',
        )

    def get_recipes(self, obj):
        request = self.context.get('request')
        recipes_limit = 10**10
        if request:
            recipes_limit = int(request.GET.get('recipes_limit', 10**10))
        return ShortRecipeSerializer(
            obj.recipes.all()[:recipes_limit],
            many=True
        ).data


class SubscriptionSerializer(serializers.ModelSerializer):
    """Сериализатор подписки"""
    user = serializers.StringRelatedField()
    author = serializers.StringRelatedField()

    class Meta:
        model = Subscription
        fields = ('user', 'author')
