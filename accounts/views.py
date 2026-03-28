from functools import wraps

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.db.models import Count, Q
from django.http import HttpResponse, HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token

from .forms import (
    AccountDeleteForm,
    AnnouncementForm,
    AnnouncementReplyForm,
    BudgetCategoryForm,
    MembershipStatusUpdateForm,
    MessageForm,
    ProfileUpdateForm,
    PurchaseRequestForm,
    PurchaseRequestReviewForm,
    ResourceDocumentForm,
    UserRoleUpdateForm,
)
from .models import (
    Announcement,
    BudgetCategory,
    Conversation,
    Message,
    Profile,
    PurchaseRequest,
    ResourceDocument,
)


def build_unique_username(email: str) -> str:
    base_username = email.split('@')[0].replace('.', '_').replace('+', '_')[:140] or 'user'
    username = base_username
    counter = 1
    while User.objects.filter(username=username).exclude(email=email).exists():
        username = f'{base_username}_{counter}'[:150]
        counter += 1
    return username


def resolve_google_user(email: str, google_sub: str | None):
    if google_sub:
        linked_profile = Profile.objects.select_related('user').filter(google_sub=google_sub).first()
        if linked_profile:
            return linked_profile.user, False, False

    matches = list(User.objects.filter(email__iexact=email).order_by('-is_superuser', '-is_staff', 'date_joined', 'id'))
    if matches:
        return matches[0], False, len(matches) > 1

    user = User.objects.create(
        email=email,
        username=build_unique_username(email),
    )
    return user, True, False


def get_profile(user):
    return Profile.objects.get_or_create(user=user)[0]


def visibility_queryset(queryset, profile):
    if profile.role == Profile.ROLE_TREASURER:
        return queryset
    if profile.role == Profile.ROLE_OFFICER:
        return queryset.exclude(visibility=Profile.ROLE_TREASURER)
    return queryset.filter(visibility=Profile.ROLE_MEMBER)


def bootstrap_profile(profile, user_created: bool):
    changed = False
    if profile.role == Profile.ROLE_USER_ADMIN:
        if profile.status != Profile.STATUS_ACTIVE:
            profile.status = Profile.STATUS_ACTIVE
            changed = True
    elif user_created:
        other_normal_profiles = Profile.objects.exclude(pk=profile.pk).exclude(role=Profile.ROLE_USER_ADMIN)
        if not other_normal_profiles.exists():
            profile.role = Profile.ROLE_TREASURER
            profile.status = Profile.STATUS_ACTIVE
            if not profile.organization_name:
                profile.organization_name = 'Founding Treasurer'
            changed = True
        else:
            if profile.status != Profile.STATUS_PENDING:
                profile.status = Profile.STATUS_PENDING
                changed = True
    if changed:
        profile.save()


def post_login_redirect_for(user):
    profile = get_profile(user)
    if profile.role == Profile.ROLE_USER_ADMIN:
        return 'accounts:role_management'
    if profile.status == Profile.STATUS_BANNED:
        return 'accounts:banned_page'
    if profile.status == Profile.STATUS_PENDING:
        return 'accounts:pending_approval'
    return 'accounts:dashboard'


def user_admin_only(view_func):
    @wraps(view_func)
    @login_required
    def wrapper(request, *args, **kwargs):
        profile = get_profile(request.user)
        if profile.role != Profile.ROLE_USER_ADMIN:
            return HttpResponseForbidden('Only User Administrators can access this page.')
        return view_func(request, *args, **kwargs)

    return wrapper


def non_user_admin_required(view_func):
    @wraps(view_func)
    @login_required
    def wrapper(request, *args, **kwargs):
        profile = get_profile(request.user)
        if profile.role == Profile.ROLE_USER_ADMIN:
            return redirect('accounts:role_management')
        return view_func(request, *args, **kwargs)

    return wrapper


def active_member_required(view_func):
    @wraps(view_func)
    @login_required
    def wrapper(request, *args, **kwargs):
        profile = get_profile(request.user)
        if profile.role == Profile.ROLE_USER_ADMIN:
            return redirect('accounts:role_management')
        if profile.status == Profile.STATUS_BANNED:
            return redirect('accounts:banned_page')
        if profile.status != Profile.STATUS_ACTIVE:
            return redirect('accounts:pending_approval')
        return view_func(request, *args, **kwargs)

    return wrapper


def role_required(*allowed_roles):
    def decorator(view_func):
        @wraps(view_func)
        @active_member_required
        def wrapper(request, *args, **kwargs):
            profile = get_profile(request.user)
            if profile.role not in allowed_roles:
                return HttpResponseForbidden('You do not have access to this page.')
            return view_func(request, *args, **kwargs)

        return wrapper

    return decorator


def home_page(request):
    if request.user.is_authenticated:
        return redirect(post_login_redirect_for(request.user))
    return render(request, 'accounts/home.html')


def sign_in(request):
    if request.user.is_authenticated:
        return redirect(post_login_redirect_for(request.user))
    return render(request, 'accounts/sign_in.html', {'google_client_id': settings.GOOGLE_OAUTH_CLIENT_ID})


def auth_receiver(request):
    if request.method != 'POST':
        return HttpResponse('Only POST is allowed.', status=405)

    token = request.POST.get('credential')
    if not token:
        return HttpResponse('Missing credential token.', status=400)
    if not settings.GOOGLE_OAUTH_CLIENT_ID:
        return HttpResponse('GOOGLE_OAUTH_CLIENT_ID is not configured.', status=500)

    try:
        user_data = id_token.verify_oauth2_token(token, google_requests.Request(), settings.GOOGLE_OAUTH_CLIENT_ID)
    except ValueError:
        return HttpResponse('Invalid Google token.', status=403)

    email = (user_data.get('email') or '').strip().lower()
    if not email:
        return HttpResponse('Email not provided by Google.', status=400)

    google_sub = user_data.get('sub')
    given_name = user_data.get('given_name', '')
    family_name = user_data.get('family_name', '')
    picture = user_data.get('picture', '')

    user, created, had_duplicates = resolve_google_user(email, google_sub)

    updated = False
    if user.email != email:
        user.email = email
        updated = True
    if given_name and user.first_name != given_name:
        user.first_name = given_name
        updated = True
    if family_name and user.last_name != family_name:
        user.last_name = family_name
        updated = True
    if not user.username:
        user.username = build_unique_username(email)
        updated = True
    if updated:
        user.save()

    profile = get_profile(user)
    profile_updates = []
    if google_sub and profile.google_sub != google_sub:
        profile.google_sub = google_sub
        profile_updates.append('google_sub')
    if picture and profile.google_picture_url != picture:
        profile.google_picture_url = picture
        profile_updates.append('google_picture_url')
    if profile_updates:
        profile_updates.append('updated_at')
        profile.save(update_fields=profile_updates)

    bootstrap_profile(profile, created)
    login(request, user)
    if had_duplicates:
        messages.warning(request, 'We found more than one local account with this email, so you were signed into the primary matching account. You can clean up duplicate test accounts in Django admin.')
    messages.success(request, f'Welcome, {profile.display_name}!')
    return redirect(post_login_redirect_for(user))


@non_user_admin_required
def pending_approval(request):
    profile = get_profile(request.user)
    if profile.status == Profile.STATUS_ACTIVE:
        return redirect('accounts:dashboard')
    if profile.status == Profile.STATUS_BANNED:
        return redirect('accounts:banned_page')
    return render(request, 'accounts/pending_approval.html', {'profile': profile})


@non_user_admin_required
def banned_page(request):
    profile = get_profile(request.user)
    if profile.status != Profile.STATUS_BANNED:
        return redirect(post_login_redirect_for(request.user))
    return render(request, 'accounts/banned.html', {'profile': profile})


@active_member_required
def dashboard(request):
    profile = get_profile(request.user)
    categories = BudgetCategory.objects.all()
    requests_qs = PurchaseRequest.objects.select_related('category', 'requested_by', 'reviewed_by')
    if profile.role == Profile.ROLE_TREASURER:
        visible_requests = requests_qs
    elif profile.role == Profile.ROLE_OFFICER:
        visible_requests = requests_qs.filter(Q(requested_by=request.user) | Q(status=PurchaseRequest.STATUS_APPROVED)).distinct()
    else:
        visible_requests = requests_qs.filter(status=PurchaseRequest.STATUS_APPROVED)

    announcements = visibility_queryset(Announcement.objects.select_related('created_by'), profile)[:5]
    documents = visibility_queryset(ResourceDocument.objects.select_related('uploaded_by'), profile)[:5]
    conversation_count = request.user.conversations.count()

    context = {
        'profile': profile,
        'categories': categories[:5],
        'recent_requests': visible_requests[:5],
        'announcements': announcements,
        'documents': documents,
        'conversation_count': conversation_count,
        'approved_count': requests_qs.filter(status=PurchaseRequest.STATUS_APPROVED).count(),
        'pending_count': requests_qs.filter(status=PurchaseRequest.STATUS_PENDING).count(),
    }
    return render(request, 'accounts/dashboard.html', context)


@non_user_admin_required
def user_profile(request):
    profile = get_profile(request.user)
    return render(request, 'accounts/profile.html', {'profile': profile})


@non_user_admin_required
def edit_profile(request):
    profile = get_profile(request.user)
    if request.method == 'POST':
        form = ProfileUpdateForm(request.POST, request.FILES, instance=profile)
        if form.is_valid():
            form.save()
            messages.success(request, 'Your profile was updated.')
            return redirect('accounts:user_profile')
    else:
        form = ProfileUpdateForm(instance=profile)
    return render(request, 'accounts/profile_edit.html', {'form': form, 'profile': profile})


@login_required
def delete_account(request):
    if request.method == 'POST':
        form = AccountDeleteForm(request.POST)
        if form.is_valid():
            if form.cleaned_data['confirm_email'].lower() != (request.user.email or '').lower():
                form.add_error('confirm_email', 'The email does not match your account email.')
            else:
                user_email = request.user.email
                user = request.user
                logout(request)
                user.delete()
                messages.success(request, f'Account {user_email} was deleted.')
                return redirect('accounts:home')
    else:
        form = AccountDeleteForm(initial={'confirm_email': request.user.email})
    return render(request, 'accounts/account_delete.html', {'form': form})


def sign_out(request):
    logout(request)
    return redirect('accounts:sign_in')


@active_member_required
def conversation_list(request):
    conversations = request.user.conversations.all().prefetch_related('participants')
    return render(request, 'messaging/conversation_list.html', {'conversations': conversations})


@active_member_required
def conversation_detail(request, conversation_id):
    conversation = get_object_or_404(
        Conversation.objects.prefetch_related('participants', 'messages__sender'),
        id=conversation_id,
    )
    if request.user not in conversation.participants.all():
        return HttpResponseForbidden('You are not allowed to view this conversation.')

    if request.method == 'POST':
        form = MessageForm(request.POST)
        if form.is_valid():
            message = form.save(commit=False)
            message.conversation = conversation
            message.sender = request.user
            message.save()
            return redirect('accounts:conversation_detail', conversation_id=conversation.id)
    else:
        form = MessageForm()

    conversation.messages.exclude(sender=request.user).filter(is_read=False).update(is_read=True)
    return render(
        request,
        'messaging/conversation_detail.html',
        {'conversation': conversation, 'messages': conversation.messages.all(), 'form': form},
    )


@active_member_required
def start_conversation(request, user_id):
    other_user = get_object_or_404(User, id=user_id)
    other_profile = get_profile(other_user)
    if other_user == request.user:
        return HttpResponseForbidden('You cannot message yourself.')
    if other_profile.role == Profile.ROLE_USER_ADMIN or other_profile.status != Profile.STATUS_ACTIVE:
        return HttpResponseForbidden('That user is not available for messaging.')

    existing = Conversation.objects.filter(participants=request.user).filter(participants=other_user).distinct()
    if existing.exists():
        return redirect('accounts:conversation_detail', conversation_id=existing.first().id)

    conversation = Conversation.objects.create()
    conversation.participants.add(request.user, other_user)
    return redirect('accounts:conversation_detail', conversation_id=conversation.id)


@active_member_required
def user_list(request):
    users = User.objects.exclude(id=request.user.id).select_related('profile')
    users = [
        user for user in users
        if hasattr(user, 'profile')
        and user.profile.role != Profile.ROLE_USER_ADMIN
        and user.profile.status == Profile.STATUS_ACTIVE
    ]
    return render(request, 'messaging/user_list.html', {'users': users})


@active_member_required
def budget_category_list(request):
    categories = BudgetCategory.objects.all()
    return render(request, 'budgeting/budget_category_list.html', {'categories': categories, 'profile': get_profile(request.user)})


@role_required(Profile.ROLE_TREASURER)
def budget_category_create(request):
    if request.method == 'POST':
        form = BudgetCategoryForm(request.POST)
        if form.is_valid():
            category = form.save(commit=False)
            category.created_by = request.user
            category.save()
            messages.success(request, 'Budget category created successfully.')
            return redirect('accounts:budget_category_list')
    else:
        form = BudgetCategoryForm()
    return render(request, 'budgeting/budget_category_form.html', {'form': form, 'mode': 'Create'})


@active_member_required
def purchase_request_list(request):
    profile = get_profile(request.user)
    requests_qs = PurchaseRequest.objects.select_related('category', 'requested_by', 'reviewed_by')
    if profile.role == Profile.ROLE_TREASURER:
        purchase_requests = requests_qs
    elif profile.role == Profile.ROLE_OFFICER:
        purchase_requests = requests_qs.filter(Q(requested_by=request.user) | Q(status=PurchaseRequest.STATUS_APPROVED)).distinct()
    else:
        purchase_requests = requests_qs.filter(status=PurchaseRequest.STATUS_APPROVED)
    return render(request, 'budgeting/purchase_request_list.html', {'purchase_requests': purchase_requests, 'profile': profile})


@role_required(Profile.ROLE_OFFICER, Profile.ROLE_TREASURER)
def purchase_request_create(request):
    if not BudgetCategory.objects.exists():
        messages.error(request, 'A treasurer needs to create at least one budget category first.')
        return redirect('accounts:budget_category_list')
    if request.method == 'POST':
        form = PurchaseRequestForm(request.POST, request.FILES)
        if form.is_valid():
            purchase_request = form.save(commit=False)
            purchase_request.requested_by = request.user
            purchase_request.save()
            messages.success(request, 'Purchase request submitted.')
            return redirect('accounts:purchase_request_list')
    else:
        form = PurchaseRequestForm()
    return render(request, 'budgeting/purchase_request_form.html', {'form': form})


@role_required(Profile.ROLE_TREASURER)
def purchase_request_review(request, request_id):
    purchase_request = get_object_or_404(PurchaseRequest, id=request_id)
    if request.method == 'POST':
        form = PurchaseRequestReviewForm(request.POST, instance=purchase_request)
        if form.is_valid():
            reviewed_request = form.save(commit=False)
            reviewed_request.reviewed_by = request.user
            reviewed_request.reviewed_at = timezone.now()
            reviewed_request.save()
            messages.success(request, 'Purchase request reviewed successfully.')
            return redirect('accounts:purchase_request_list')
    else:
        form = PurchaseRequestReviewForm(instance=purchase_request)
    return render(request, 'budgeting/purchase_request_review.html', {'purchase_request': purchase_request, 'form': form})


@active_member_required
def announcement_list(request):
    profile = get_profile(request.user)
    announcements = visibility_queryset(Announcement.objects.select_related('created_by').annotate(reply_count=Count('replies')), profile)
    return render(request, 'announcements/announcement_list.html', {'announcements': announcements, 'profile': profile})


@active_member_required
def announcement_detail(request, announcement_id):
    profile = get_profile(request.user)
    announcement = get_object_or_404(visibility_queryset(Announcement.objects.select_related('created_by'), profile), id=announcement_id)
    if request.method == 'POST':
        if announcement.is_locked:
            messages.error(request, 'This announcement thread is locked.')
            return redirect('accounts:announcement_detail', announcement_id=announcement.id)
        reply_form = AnnouncementReplyForm(request.POST)
        if reply_form.is_valid():
            reply = reply_form.save(commit=False)
            reply.announcement = announcement
            reply.author = request.user
            reply.save()
            messages.success(request, 'Reply posted.')
            return redirect('accounts:announcement_detail', announcement_id=announcement.id)
    else:
        reply_form = AnnouncementReplyForm()
    return render(request, 'announcements/announcement_detail.html', {'announcement': announcement, 'reply_form': reply_form, 'profile': profile})


@role_required(Profile.ROLE_OFFICER, Profile.ROLE_TREASURER)
def announcement_create(request):
    if request.method == 'POST':
        form = AnnouncementForm(request.POST, request.FILES)
        if form.is_valid():
            announcement = form.save(commit=False)
            announcement.created_by = request.user
            announcement.save()
            messages.success(request, 'Announcement posted.')
            return redirect('accounts:announcement_list')
    else:
        form = AnnouncementForm()
    return render(request, 'announcements/announcement_form.html', {'form': form, 'mode': 'Create'})


@role_required(Profile.ROLE_OFFICER, Profile.ROLE_TREASURER)
def announcement_edit(request, announcement_id):
    announcement = get_object_or_404(Announcement, id=announcement_id)
    request_profile = get_profile(request.user)
    if request.user != announcement.created_by and request_profile.role != Profile.ROLE_TREASURER:
        return HttpResponseForbidden('Only the original poster or a treasurer can edit this announcement.')
    if request.method == 'POST':
        form = AnnouncementForm(request.POST, request.FILES, instance=announcement)
        if form.is_valid():
            form.save()
            messages.success(request, 'Announcement updated.')
            return redirect('accounts:announcement_detail', announcement_id=announcement.id)
    else:
        form = AnnouncementForm(instance=announcement)
    return render(request, 'announcements/announcement_form.html', {'form': form, 'mode': 'Edit', 'announcement': announcement})


@active_member_required
def document_list(request):
    profile = get_profile(request.user)
    documents = visibility_queryset(ResourceDocument.objects.select_related('uploaded_by'), profile)
    return render(request, 'documents/document_list.html', {'documents': documents, 'profile': profile})


@role_required(Profile.ROLE_OFFICER, Profile.ROLE_TREASURER)
def document_upload(request):
    if request.method == 'POST':
        form = ResourceDocumentForm(request.POST, request.FILES)
        if form.is_valid():
            document = form.save(commit=False)
            document.uploaded_by = request.user
            document.save()
            messages.success(request, 'Document uploaded successfully.')
            return redirect('accounts:document_list')
    else:
        form = ResourceDocumentForm()
    return render(request, 'documents/document_form.html', {'form': form, 'mode': 'Upload'})


@role_required(Profile.ROLE_OFFICER, Profile.ROLE_TREASURER)
def document_delete(request, document_id):
    document = get_object_or_404(ResourceDocument, id=document_id)
    profile = get_profile(request.user)
    if request.user != document.uploaded_by and profile.role != Profile.ROLE_TREASURER:
        return HttpResponseForbidden('Only the uploader or a treasurer can delete this document.')
    if request.method == 'POST':
        document.delete()
        messages.success(request, 'Document deleted.')
        return redirect('accounts:document_list')
    return render(request, 'documents/document_delete.html', {'document': document})


@role_required(Profile.ROLE_TREASURER)
def membership_management(request):
    profiles = Profile.objects.select_related('user').exclude(role=Profile.ROLE_USER_ADMIN).order_by('user__email')
    if request.method == 'POST':
        target_profile = get_object_or_404(Profile, id=request.POST.get('profile_id'))
        if target_profile.role == Profile.ROLE_USER_ADMIN or target_profile.user == request.user:
            return HttpResponseForbidden('That account cannot be changed here.')
        form = MembershipStatusUpdateForm(request.POST, instance=target_profile)
        if form.is_valid():
            form.save()
            messages.success(request, f'Membership status updated for {target_profile.user.email}.')
            return redirect('accounts:membership_management')
    forms_by_profile_id = {
        profile.id: MembershipStatusUpdateForm(instance=profile)
        for profile in profiles if profile.user != request.user
    }
    return render(request, 'accounts/membership_management.html', {'profiles': profiles, 'forms_by_profile_id': forms_by_profile_id})


@user_admin_only
def role_management(request):
    for user in User.objects.all():
        get_profile(user)
    profiles = Profile.objects.select_related('user').order_by('user__email')

    if request.method == 'POST':
        target_profile = get_object_or_404(Profile, id=request.POST.get('profile_id'))
        if target_profile.role == Profile.ROLE_USER_ADMIN or target_profile.user.is_superuser:
            return HttpResponseForbidden('User Administrator accounts cannot be changed here.')
        form = UserRoleUpdateForm(request.POST, instance=target_profile)
        if form.is_valid():
            form.save()
            messages.success(request, f'Updated role for {target_profile.user.email}.')
            return redirect('accounts:role_management')

    forms_by_profile_id = {
        profile.id: UserRoleUpdateForm(instance=profile)
        for profile in profiles
        if profile.role != Profile.ROLE_USER_ADMIN and not profile.user.is_superuser
    }
    return render(request, 'accounts/user_role_management.html', {'profiles': profiles, 'forms_by_profile_id': forms_by_profile_id})
