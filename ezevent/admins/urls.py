from django.urls import path
from django.views.decorators.csrf import csrf_exempt
from .views import (
    GenerateSignupTokenView,ListPromotersView, ListUsersView, DeleteUserView, SuspendUserView
)

# from .views.create_roles import CreateRoleView


urlpatterns = [
    path('generate_signup_token', GenerateSignupTokenView.as_view(), name='generate_signup_token'),

    # path('create_role', CreateRoleView.as_view(), name='create_role'),
    path('list_promoters', ListPromotersView.as_view(), name='list_users'),
    path('list_users', ListUsersView.as_view(), name='list_users'),

    path('delete_user/<int:user_id>/', DeleteUserView.as_view(), name='delete_user'),
    path('users/<int:user_id>/suspend/', SuspendUserView.as_view(), name='suspend-user'),


]