from rest_framework.pagination import PageNumberPagination


class CustomPagePagination(PageNumberPagination):
    """Пагинация для API приложения"""

    page_query_param = 'page'
    page_size_query_param = 'limit'
    page_size = 6
