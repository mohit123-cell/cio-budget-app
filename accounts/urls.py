from django.urls import path

from . import views

app_name = 'accounts'

urlpatterns = [
    path('', views.home_page, name='home'),
    path('sign-in/', views.sign_in, name='sign_in'),
    path('sign-out/', views.sign_out, name='sign_out'),
    path('auth-receiver/', views.auth_receiver, name='auth_receiver'),

    path('pending/', views.pending_approval, name='pending_approval'),
    path('banned/', views.banned_page, name='banned_page'),
    path('dashboard/', views.dashboard, name='dashboard'),

    path('profile/', views.user_profile, name='user_profile'),
    path('profile/edit/', views.edit_profile, name='edit_profile'),
    path('account/delete/', views.delete_account, name='delete_account'),

    path('roles/', views.role_management, name='role_management'),
    path('membership/', views.membership_management, name='membership_management'),

    path('budget/categories/', views.budget_category_list, name='budget_category_list'),
    path('budget/categories/new/', views.budget_category_create, name='budget_category_create'),
    path('budget/requests/', views.purchase_request_list, name='purchase_request_list'),
    path('budget/requests/new/', views.purchase_request_create, name='purchase_request_create'),
    path('budget/requests/<int:request_id>/review/', views.purchase_request_review, name='purchase_request_review'),

    path('announcements/', views.announcement_list, name='announcement_list'),
    path('announcements/new/', views.announcement_create, name='announcement_create'),
    path('announcements/<int:announcement_id>/', views.announcement_detail, name='announcement_detail'),
    path('announcements/<int:announcement_id>/edit/', views.announcement_edit, name='announcement_edit'),

    path('documents/', views.document_list, name='document_list'),
    path('documents/upload/', views.document_upload, name='document_upload'),
    path('documents/<int:document_id>/delete/', views.document_delete, name='document_delete'),

    path('messages/', views.conversation_list, name='conversation_list'),
    path('messages/<int:conversation_id>/', views.conversation_detail, name='conversation_detail'),
    path('messages/start/<int:user_id>/', views.start_conversation, name='start_conversation'),
    path('users/', views.user_list, name='user_list'),
]
