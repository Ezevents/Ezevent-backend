from django.urls import path
from .auth_views.auth_views import (
    home, login, signup_with_token, logout, send_forgot_password_email,update_password, signup_clients, GenerateSignupTokenView,
    UserProfileUpdateView
)

from .auth_views.admin_views import (
    ListPromotersView, ListUsersView, DeleteUserView, SuspendUserView
)

urlpatterns = [
    path('active', home, name='home'),
    path('login', login, name='login'),
    path('token_signup', signup_with_token, name='signup_promoter'),
    path('signup', signup_clients, name='signup_clients'),
    path('logout', logout, name='logout'),
    path('update_profile', UserProfileUpdateView.as_view(), name='update-profile'),
    path("forgotPassword", send_forgot_password_email, name= "forgotpasswordemail"),
    path('updatepassword', update_password, name = "updatepassword"),
    path('home', home, name='auth_home'),

    # path('create_role', CreateRoleView.as_view(), name='create_role'),
    path("admin/generate_sigup_token", GenerateSignupTokenView.as_view(), name = 'auth_signup'),
    path('admin/list_promoters', ListPromotersView.as_view(), name='list_users'),
    path('admin/list_users', ListUsersView.as_view(), name='list_users'),

    path('admin/delete_user/<int:user_id>/', DeleteUserView.as_view(), name='delete_user'),
    path('admin/users/<int:user_id>/suspend/', SuspendUserView.as_view(), name='suspend-user'),

]