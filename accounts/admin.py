from django.contrib import admin, messages
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin
from django.contrib.auth.models import User

from .models import (
    Announcement,
    AnnouncementReply,
    BudgetCategory,
    Conversation,
    Message,
    Profile,
    PurchaseRequest,
    ResourceDocument,
)


class ProfileInline(admin.StackedInline):
    model = Profile
    can_delete = False
    extra = 0
    verbose_name_plural = 'profile and role settings'
    fields = (
        'role',
        'status',
        'organization_name',
        'phone_number',
        'google_picture_url',
        'profile_image',
        'bio',
        'join_date',
        'created_at',
        'updated_at',
    )
    readonly_fields = ('join_date', 'created_at', 'updated_at')


class CustomUserAdmin(DjangoUserAdmin):
    inlines = (ProfileInline,)
    list_display = (
        'username',
        'email',
        'first_name',
        'last_name',
        'is_staff',
        'is_superuser',
        'profile_role',
        'profile_status',
        'date_joined',
    )
    search_fields = ('username', 'email', 'first_name', 'last_name')
    list_select_related = ('profile',)
    actions = (
        'approve_selected_accounts',
        'ban_selected_accounts',
        'make_members',
        'make_officers',
        'make_treasurers',
        'delete_selected_accounts',
    )

    @admin.display(description='Role')
    def profile_role(self, obj):
        profile = getattr(obj, 'profile', None)
        return profile.get_role_display() if profile else '—'

    @admin.display(description='Status')
    def profile_status(self, obj):
        profile = getattr(obj, 'profile', None)
        return profile.get_status_display() if profile else '—'

    def _ensure_profile(self, user):
        profile, _ = Profile.objects.get_or_create(user=user)
        return profile

    @admin.action(description='Approve selected user accounts')
    def approve_selected_accounts(self, request, queryset):
        count = 0
        for user in queryset:
            profile = self._ensure_profile(user)
            if profile.status != Profile.STATUS_ACTIVE:
                profile.status = Profile.STATUS_ACTIVE
                profile.save(update_fields=['status', 'updated_at'])
                count += 1
        self.message_user(request, f'Approved {count} account(s).', messages.SUCCESS)

    @admin.action(description='Ban selected user accounts')
    def ban_selected_accounts(self, request, queryset):
        count = 0
        for user in queryset:
            profile = self._ensure_profile(user)
            if profile.status != Profile.STATUS_BANNED:
                profile.status = Profile.STATUS_BANNED
                profile.save(update_fields=['status', 'updated_at'])
                count += 1
        self.message_user(request, f'Banned {count} account(s).', messages.WARNING)

    def _set_role(self, request, queryset, role_value, role_label):
        count = 0
        for user in queryset:
            if user.is_superuser:
                continue
            profile = self._ensure_profile(user)
            if profile.role != role_value:
                profile.role = role_value
                profile.save(update_fields=['role', 'updated_at'])
                count += 1
        self.message_user(request, f'Updated {count} account(s) to {role_label}.', messages.SUCCESS)

    @admin.action(description='Change selected users to Member')
    def make_members(self, request, queryset):
        self._set_role(request, queryset, Profile.ROLE_MEMBER, 'Member')

    @admin.action(description='Change selected users to Officer')
    def make_officers(self, request, queryset):
        self._set_role(request, queryset, Profile.ROLE_OFFICER, 'Officer')

    @admin.action(description='Change selected users to Treasurer')
    def make_treasurers(self, request, queryset):
        self._set_role(request, queryset, Profile.ROLE_TREASURER, 'Treasurer')

    @admin.action(description='Delete selected user accounts completely')
    def delete_selected_accounts(self, request, queryset):
        protected = queryset.filter(is_superuser=True)
        delete_queryset = queryset.exclude(is_superuser=True)
        deleted_count = delete_queryset.count()
        delete_queryset.delete()
        if protected.exists():
            self.message_user(
                request,
                'Superuser accounts were skipped for safety. Delete them manually if you really want to.',
                messages.WARNING,
            )
        self.message_user(request, f'Deleted {deleted_count} user account(s).', messages.SUCCESS)


try:
    admin.site.unregister(User)
except admin.sites.NotRegistered:
    pass
admin.site.register(User, CustomUserAdmin)


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = (
        'user',
        'role',
        'status',
        'organization_name',
        'phone_number',
        'updated_at',
    )
    list_filter = ('role', 'status')
    search_fields = ('user__username', 'user__email', 'organization_name', 'phone_number')
    list_editable = ('role', 'status', 'organization_name', 'phone_number')
    actions = (
        'approve_profiles',
        'ban_profiles',
        'make_members',
        'make_officers',
        'make_treasurers',
        'delete_selected_user_accounts',
    )
    readonly_fields = ('created_at', 'updated_at', 'join_date')
    fieldsets = (
        ('User link', {'fields': ('user',)}),
        ('Role and account status', {'fields': ('role', 'status')}),
        ('Profile details', {'fields': ('organization_name', 'phone_number', 'bio')}),
        ('Images', {'fields': ('google_picture_url', 'profile_image')}),
        ('Timestamps', {'fields': ('join_date', 'created_at', 'updated_at')}),
    )

    @admin.action(description='Approve selected profiles')
    def approve_profiles(self, request, queryset):
        updated = queryset.update(status=Profile.STATUS_ACTIVE)
        self.message_user(request, f'Approved {updated} profile(s).', messages.SUCCESS)

    @admin.action(description='Ban selected profiles')
    def ban_profiles(self, request, queryset):
        updated = queryset.update(status=Profile.STATUS_BANNED)
        self.message_user(request, f'Banned {updated} profile(s).', messages.WARNING)

    @admin.action(description='Change selected profiles to Member')
    def make_members(self, request, queryset):
        updated = queryset.exclude(user__is_superuser=True).update(role=Profile.ROLE_MEMBER)
        self.message_user(request, f'Updated {updated} profile(s) to Member.', messages.SUCCESS)

    @admin.action(description='Change selected profiles to Officer')
    def make_officers(self, request, queryset):
        updated = queryset.exclude(user__is_superuser=True).update(role=Profile.ROLE_OFFICER)
        self.message_user(request, f'Updated {updated} profile(s) to Officer.', messages.SUCCESS)

    @admin.action(description='Change selected profiles to Treasurer')
    def make_treasurers(self, request, queryset):
        updated = queryset.exclude(user__is_superuser=True).update(role=Profile.ROLE_TREASURER)
        self.message_user(request, f'Updated {updated} profile(s) to Treasurer.', messages.SUCCESS)

    @admin.action(description='Delete selected user accounts completely')
    def delete_selected_user_accounts(self, request, queryset):
        users = User.objects.filter(profile__in=queryset).exclude(is_superuser=True)
        deleted_count = users.count()
        users.delete()
        self.message_user(request, f'Deleted {deleted_count} user account(s).', messages.SUCCESS)


@admin.register(BudgetCategory)
class BudgetCategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'allocated_amount', 'created_by', 'created_at')
    search_fields = ('name',)


@admin.register(PurchaseRequest)
class PurchaseRequestAdmin(admin.ModelAdmin):
    list_display = ('title', 'category', 'estimated_cost', 'requested_by', 'status', 'reviewed_by', 'created_at')
    list_filter = ('status', 'category')
    search_fields = ('title', 'requested_by__username', 'requested_by__email')


@admin.register(Conversation)
class ConversationAdmin(admin.ModelAdmin):
    list_display = ('id', 'created_at')
    filter_horizontal = ('participants',)


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ('conversation', 'sender', 'sent_at', 'is_read')
    list_filter = ('is_read',)
    search_fields = ('sender__username', 'body')


class AnnouncementReplyInline(admin.TabularInline):
    model = AnnouncementReply
    extra = 0


@admin.register(Announcement)
class AnnouncementAdmin(admin.ModelAdmin):
    list_display = ('title', 'created_by', 'visibility', 'is_pinned', 'is_locked', 'created_at')
    list_filter = ('visibility', 'is_pinned', 'is_locked')
    search_fields = ('title', 'body')
    inlines = [AnnouncementReplyInline]


@admin.register(ResourceDocument)
class ResourceDocumentAdmin(admin.ModelAdmin):
    list_display = ('title', 'visibility', 'uploaded_by', 'uploaded_at')
    list_filter = ('visibility',)
    search_fields = ('title', 'description')
