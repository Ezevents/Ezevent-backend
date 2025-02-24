from django.urls import path
from .auth_views.auth_views import (
    home, login, signup_with_token, logout, send_forgot_password_email,update_password, signup_clients
)
urlpatterns = [
    path('active', home, name='home'),
    path('login', login, name='login'),
    path('token_signup', signup_with_token, name='signup_promoter'),
    path('signup', signup_clients, name='signup_clients'),
    path('logout', logout, name='logout'),
    path("forgotPassword", send_forgot_password_email, name= "forgotpasswordemail"),
    path('updatepassword', update_password, name = "updatepassword"),
    path('home', home, name='auth_home'),
]