"""
URL configuration for config project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.conf import settings
from django.contrib import admin
from django.urls import include, path

from accounts import views as accounts_views
from shortener import views as shortener_views

urlpatterns = [
    path('', accounts_views.root_redirect, name='root'),
    path('admin/', admin.site.urls),
    path('api/auth/', include('accounts.urls', namespace='accounts')),
    path('api/v1/', include('shortener.api_urls')),
    path('dashboard/', include('shortener.urls', namespace='shortener')),
    path('login/', accounts_views.login_page, name='login_page'),
    path('register/', accounts_views.register_page, name='register_page'),
    path('verify-email/', accounts_views.verify_email_page, name='verify_email_page'),
    path('verify-email/<str:token>/', accounts_views.verify_email_link, name='verify_email_link'),
    path('forgot-password/', accounts_views.forgot_password_page, name='forgot_password_page'),
    path('reset-password/<str:token>/', accounts_views.reset_password_page, name='reset_password_page'),
    path('password/<str:code>/', shortener_views.password_gate_view, name='password_gate'),
]

if settings.DEBUG:
    urlpatterns += [
        path('debug/otp/', shortener_views.debug_otp_view, name='debug_otp'),
    ]

urlpatterns += [
    path('<str:code>/', shortener_views.redirect_view, name='redirect'),
]
