from django.contrib.auth.models import AbstractUser
from django.core.validators import (RegexValidator,
                                    MinValueValidator,
                                    MaxValueValidator)
from django.db import models

# Константы
NAME_MAX_LENGTH = 150
EMAIL_MAX_LENGTH = 254
INGREDIENT_NAME_MAX_LENGTH = 128
MEASUREMENT_UNIT_MAX_LENGTH = 64
RECIPE_NAME_MAX_LENGTH = 256
MIN_VALUE = 1
MAX_VALUE = 32000


class User(AbstractUser):
    """Кастомная модель пользователя"""

    email = models.EmailField(
        unique=True,
        max_length=EMAIL_MAX_LENGTH
    )

    username = models.CharField(
        max_length=NAME_MAX_LENGTH,
        unique=True,
        validators=[RegexValidator(
            regex=r'^[\w.@+-]+$',
            message='Username может содержать только буквы, '
                    'цифры и символы: @ . + -'
        )]
    )

    first_name = models.CharField(
        max_length=NAME_MAX_LENGTH,
        blank=False,
    )

    last_name = models.CharField(
        max_length=NAME_MAX_LENGTH,
        blank=False,
    )

    avatar = models.ImageField(upload_to='avatars/', blank=True, null=True)

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = [
        'username',
        'first_name',
        'last_name',
    ]

    class Meta:
        verbose_name = 'Пользователь'
        verbose_name_plural = 'Пользователи'
        ordering = ('email',)

    def __str__(self):
        return self.email


class Subscription(models.Model):
    """Подписки пользователей"""

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='subscriptions',
        verbose_name='Подписчик'
    )
    author = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='subscribers',
        verbose_name='Автор'
    )

    class Meta:
        verbose_name = 'Подписка'
        verbose_name_plural = 'Подписки'
        ordering = ('user',)
        constraints = [
            models.UniqueConstraint(
                fields=['user', 'author'],
                name='unique_user_author'
            )
        ]

    def __str__(self):
        return f'{self.user} подписан на {self.author}'


class Ingredient(models.Model):
    """Ингредиенты для рецептов"""
    name = models.CharField(
        verbose_name='Название',
        max_length=INGREDIENT_NAME_MAX_LENGTH
    )

    measurement_unit = models.CharField(
        verbose_name='Единица измерения',
        max_length=MEASUREMENT_UNIT_MAX_LENGTH
    )

    class Meta:
        verbose_name = 'Ингредиент'
        verbose_name_plural = 'Ингредиенты'
        ordering = ('name',)
        constraints = [
            models.UniqueConstraint(
                fields=['name', 'measurement_unit'],
                name='unique_ingredient_unit'
            )
        ]

    def __str__(self):
        return f'{self.name} ({self.measurement_unit})'


class Recipe(models.Model):
    """Рецепты пользователей"""

    name = models.CharField(
        verbose_name='Название',
        max_length=RECIPE_NAME_MAX_LENGTH
    )

    text = models.TextField(
        verbose_name='Описание'
    )

    ingredients = models.ManyToManyField(
        Ingredient,
        through='IngredientInRecipe',
    )

    image = models.ImageField(
        verbose_name='Изображение',
        upload_to='recipes/images/'
    )

    author = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        verbose_name='Автор'
    )

    cooking_time = models.PositiveSmallIntegerField(
        verbose_name='Время приготовления (мин)',
        validators=[
            MinValueValidator(
                MIN_VALUE, 'Время приготовления должно быть больше 0'
            ),
            MaxValueValidator(
                MAX_VALUE, 'Время приготовления не должно превышать 32000'
            )
        ]
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Дата создания'
    )

    class Meta:
        verbose_name = 'Рецепт'
        verbose_name_plural = 'Рецепты'
        ordering = ('-created_at',)
        default_related_name = 'recipes'

    def __str__(self):
        return f'{self.name} (ID: {self.id})'


class IngredientInRecipe(models.Model):
    """Ингредиенты в рецепте с количеством"""

    recipe = models.ForeignKey(
        Recipe,
        on_delete=models.CASCADE,
        verbose_name='Рецепт'
    )

    ingredient = models.ForeignKey(
        Ingredient,
        on_delete=models.CASCADE,
        verbose_name='Ингредиент'
    )

    amount = models.PositiveSmallIntegerField(
        verbose_name='Количество',
        validators=[
            MinValueValidator(
                MIN_VALUE,
                'Количество должно быть больше 0'
            ),
            MaxValueValidator(
                MAX_VALUE,
                'Количество не должно превышать 32000'
            )
        ]
    )

    class Meta:
        verbose_name = 'Ингредиент в рецепте'
        verbose_name_plural = 'Ингредиенты в рецептах'
        ordering = ('recipe',)
        default_related_name = 'recipe_ingredients'
        constraints = [
            models.UniqueConstraint(
                fields=['recipe', 'ingredient'],
                name='unique_recipe_ingredient_pair'
            )
        ]

    def __str__(self):
        return (f'{self.ingredient.name} - {self.amount} '
                f'{self.ingredient.measurement_unit} '
                f'для {self.recipe.name}')


class RecipeUserBase(models.Model):
    """Базовая модель для связи пользователя и рецепта"""
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        verbose_name='Пользователь',
        related_name='%(class)ss'
    )
    recipe = models.ForeignKey(
        Recipe,
        on_delete=models.CASCADE,
        verbose_name='Рецепт',
        related_name='%(class)ss'
    )

    class Meta:
        abstract = True
        ordering = ('user',)
        constraints = [
            models.UniqueConstraint(
                fields=['user', 'recipe'],
                name='unique_user_recipe_%(class)s'
            )
        ]

    def __str__(self):
        return f'{self.user.username} -> {self.recipe.name}'


class Favorite(RecipeUserBase):
    """Избранные рецепты"""

    class Meta(RecipeUserBase.Meta):
        verbose_name = 'Избранный рецепт'
        verbose_name_plural = 'Избранные рецепты'


class ShoppingCart(RecipeUserBase):
    """Список покупок"""

    class Meta(RecipeUserBase.Meta):
        verbose_name = 'Рецепт в корзине'
        verbose_name_plural = 'Рецепты в корзине'
