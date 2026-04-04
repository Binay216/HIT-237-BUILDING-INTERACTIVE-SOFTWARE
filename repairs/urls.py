from django.urls import path
from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('create/', views.create_request, name='create_request'),
    path('my-requests/', views.my_requests, name='my_requests'),
    path('edit/<int:id>/', views.edit_request, name='edit_request'),
    path('delete/<int:id>/', views.delete_request, name='delete_request'),
    path('login/', views.user_login, name='login'),
    path('logout/', views.user_logout, name='logout'),
    path('register/', views.register, name='register'),
]