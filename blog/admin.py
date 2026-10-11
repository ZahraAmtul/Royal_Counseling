from django import forms
from django.contrib import admin, messages
from django.db.models import Count, Q
from django.urls import reverse
from django.utils import timezone
from django.utils.html import format_html
from django.utils.text import Truncator
from tinymce.widgets import TinyMCE

# Reuse the project's existing isolation rules instead of a parallel system.
from bookings.admin import CounselorFilteredAdmin

from .models import Category, Comment, Post, Tag


def is_counselor(user):
    return hasattr(user, "counselor_profile")


def editor_config():
    upload_url = reverse("blog:editor_upload")
    return {
        "height": 520,
        "menubar": False,
        "plugins": "lists link image autolink table code fullscreen wordcount",
        "toolbar": (
            "undo redo | blocks | bold italic underline | bullist numlist | "
            "blockquote link image table | alignleft aligncenter alignright | removeformat | code fullscreen"
        ),
        "block_formats": "Paragraph=p; Heading 2=h2; Heading 3=h3; Heading 4=h4",
        "relative_urls": False,
        "remove_script_host": True,
        "convert_urls": True,
        "image_caption": True,
        "automatic_uploads": True,
        "images_file_types": "jpg,jpeg,png,gif,webp",
        # django-tinymce evaluates this string into a JS function (see static/blog/js/admin_editor.js).
        "images_upload_handler": f"(blobInfo, progress) => window.blogUploadImage(blobInfo, progress, '{upload_url}')",
        "link_default_protocol": "https",
        "content_style": "body { font-family: Georgia, serif; font-size: 17px; line-height: 1.7; max-width: 720px; margin: 1rem auto; }",
    }


# -----------------------------------------------------------------------------
# Category & Tag — catalog managed by the superadmin (same rule as Service)
# -----------------------------------------------------------------------------

@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ["name", "slug", "published_posts"]
    search_fields = ["name"]
    prepopulated_fields = {"slug": ("name",)}

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(
            _published=Count("posts", filter=Q(posts__status=Post.Status.PUBLISHED))
        )

    @admin.display(description="Published posts", ordering="_published")
    def published_posts(self, obj):
        return obj._published

    def has_module_permission(self, request):
        return request.user.is_superuser

    def has_view_permission(self, request, obj=None):
        return request.user.is_superuser

    def has_add_permission(self, request):
        return request.user.is_superuser

    def has_change_permission(self, request, obj=None):
        return request.user.is_superuser

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser


@admin.register(Tag)
class TagAdmin(admin.ModelAdmin):
    list_display = ["name", "slug", "post_count"]
    search_fields = ["name"]
    prepopulated_fields = {"slug": ("name",)}

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(_posts=Count("posts"))

    @admin.display(description="Posts", ordering="_posts")
    def post_count(self, obj):
        return obj._posts

    # Counselors may create tags (via the "+" next to the tag picker) but only
    # the superadmin can rename or delete them.
    def has_module_permission(self, request):
        return request.user.is_superuser

    def has_view_permission(self, request, obj=None):
        return request.user.is_superuser

    def has_add_permission(self, request):
        return request.user.is_superuser or is_counselor(request.user)

    def has_change_permission(self, request, obj=None):
        return request.user.is_superuser

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser


# -----------------------------------------------------------------------------
# Posts
# -----------------------------------------------------------------------------

class PostAdminForm(forms.ModelForm):
    class Meta:
        model = Post
        fields = "__all__"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["content"].widget = TinyMCE(mce_attrs=editor_config())


@admin.register(Post)
class PostAdmin(CounselorFilteredAdmin):
    """
    Inherits CounselorFilteredAdmin, so exactly like Appointment/Availability:
    superadmin sees and edits every post; a counselor sees, edits and deletes
    only posts whose author (`counselor`) is themselves, and new posts are
    assigned to them automatically.
    """
    form = PostAdminForm
    change_form_template = "admin/blog/post/change_form.html"

    list_display = ["title", "author", "category", "status_badge", "is_featured",
                    "published_at", "like_count", "comment_summary"]
    list_select_related = ["category", "counselor__user"]
    search_fields = ["title", "excerpt", "content"]
    prepopulated_fields = {"slug": ("title",)}
    filter_horizontal = ["tags"]
    radio_fields = {"status": admin.HORIZONTAL}
    date_hierarchy = "published_at"
    ordering = ["-created_at"]
    actions = ["publish_selected", "unpublish_selected"]

    fieldsets = (
        ("Content", {"fields": ("title", "slug", "excerpt", "content")}),
        ("Featured image", {"fields": ("featured_image", "image_preview", "featured_image_alt")}),
        ("Author & organisation", {"fields": ("counselor", "category", "tags")}),
        ("Publishing", {"fields": ("status", "published_at", "is_featured", "allow_comments", "view_link")}),
        ("SEO", {
            "fields": ("seo_title", "meta_description"),
            "classes": ("collapse",),
            "description": "Optional. Search engines and social sites use these. Empty fields fall back to the title and short description.",
        }),
        ("Metadata", {"fields": ("created_at", "updated_at"), "classes": ("collapse",)}),
    )

    def get_list_filter(self, request):
        if request.user.is_superuser:
            return ["status", "category", "counselor", "is_featured", "published_at"]
        return ["status", "category", "is_featured", "published_at"]

    def get_readonly_fields(self, request, obj=None):
        fields = ["created_at", "updated_at", "image_preview", "view_link"]
        if not request.user.is_superuser:
            fields.append("is_featured")  # the featured banner is site-wide
        return fields

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(
            _likes=Count("likes", distinct=True),
            _approved=Count("comments", filter=Q(comments__status=Comment.Status.APPROVED), distinct=True),
            _pending=Count("comments", filter=Q(comments__status=Comment.Status.PENDING), distinct=True),
        )

    # Publish / save-as-draft buttons (see the change_form template) ------------

    def save_model(self, request, obj, form, change):
        if "_publish" in request.POST:
            obj.status = Post.Status.PUBLISHED
            if not obj.published_at:
                obj.published_at = timezone.now()
        elif "_save_draft" in request.POST or "_unpublish" in request.POST:
            obj.status = Post.Status.DRAFT
        super().save_model(request, obj, form, change)

        if "_publish" in request.POST:
            if obj.is_live:
                self.message_user(request, f'"{obj}" is published and live on the blog.', messages.SUCCESS)
            else:
                self.message_user(
                    request, f'"{obj}" is scheduled for {obj.published_at:%d %b %Y, %H:%M}.', messages.INFO
                )
        elif "_unpublish" in request.POST:
            self.message_user(request, f'"{obj}" was unpublished and is now a draft.', messages.WARNING)
        elif "_save_draft" in request.POST:
            self.message_user(request, f'"{obj}" was saved as a draft. It is not visible on the site.')

    @admin.action(description="Publish selected posts")
    def publish_selected(self, request, queryset):
        now = timezone.now()
        count = 0
        for post in queryset:
            post.status = Post.Status.PUBLISHED
            post.published_at = post.published_at or now
            post.save()
            count += 1
        self.message_user(request, f"{count} post(s) published.", messages.SUCCESS)

    @admin.action(description="Unpublish selected posts (move to draft)")
    def unpublish_selected(self, request, queryset):
        count = queryset.update(status=Post.Status.DRAFT)
        self.message_user(request, f"{count} post(s) moved to draft.", messages.WARNING)

    # Display helpers ----------------------------------------------------------------

    @admin.display(description="Author", ordering="counselor__user__first_name")
    def author(self, obj):
        return obj.author_name

    @admin.display(description="Status", ordering="status")
    def status_badge(self, obj):
        if obj.status == Post.Status.DRAFT:
            return format_html('<span style="color:#6c757d;font-weight:600;">Draft</span>')
        if not obj.is_live:
            return format_html('<span style="color:#b26a00;font-weight:600;">Scheduled</span>')
        return format_html('<span style="color:#2e7d32;font-weight:600;">Published</span>')

    @admin.display(description="Likes", ordering="_likes")
    def like_count(self, obj):
        return obj._likes

    @admin.display(description="Comments")
    def comment_summary(self, obj):
        if obj._pending:
            url = reverse("admin:blog_comment_changelist") + f"?post__id__exact={obj.pk}&status__exact=pending"
            return format_html('{} <a href="{}" style="color:#b26a00;">({} pending)</a>', obj._approved, url, obj._pending)
        return obj._approved

    @admin.display(description="Preview")
    def image_preview(self, obj):
        if obj and obj.featured_image:
            return format_html('<img src="{}" style="max-height:160px;border-radius:6px;">', obj.featured_image.url)
        return "No image uploaded yet."

    @admin.display(description="On the site")
    def view_link(self, obj):
        if not obj or not obj.pk:
            return "Save the post first."
        label = "View live post" if obj.is_live else "Preview draft (only you and the superadmin can see it)"
        return format_html('<a href="{}" target="_blank" rel="noopener">{}</a>', obj.get_absolute_url(), label)

    class Media:
        js = ("blog/js/admin_editor.js",)


# -----------------------------------------------------------------------------
# Comments
# -----------------------------------------------------------------------------

class CommentOwnershipMixin:
    """
    Same rules as CounselorFilteredAdmin, but ownership runs through the post:
    a counselor moderates comments on their own posts only.
    """

    def _owns(self, request, obj):
        if request.user.is_superuser:
            return True
        if not is_counselor(request.user):
            return False
        if obj is None:
            return True
        post = obj.post if isinstance(obj, Comment) else obj
        return post.counselor_id == request.user.counselor_profile.id

    def has_module_permission(self, request):
        return request.user.is_superuser or is_counselor(request.user)

    def has_view_permission(self, request, obj=None):
        return self._owns(request, obj)

    def has_change_permission(self, request, obj=None):
        return self._owns(request, obj)

    def has_delete_permission(self, request, obj=None):
        return self._owns(request, obj)


class ReplyInline(CommentOwnershipMixin, admin.StackedInline):
    model = Comment
    fk_name = "parent"
    extra = 1
    fields = ["body", "name", "created_at"]
    readonly_fields = ["name", "created_at"]
    verbose_name = "Reply"
    verbose_name_plural = "Replies (shown publicly under the comment)"

    def has_add_permission(self, request, obj=None):
        return self._owns(request, obj)


@admin.register(Comment)
class CommentAdmin(CommentOwnershipMixin, admin.ModelAdmin):
    list_display = ["name", "short_body", "post_link", "status", "reply_count", "created_at"]
    list_display_links = ["name", "short_body"]
    list_editable = ["status"]
    search_fields = ["name", "body", "post__title"]
    date_hierarchy = "created_at"
    readonly_fields = ["post", "name", "body", "created_at"]
    fields = ["post", "name", "body", "status", "created_at"]
    inlines = [ReplyInline]
    actions = ["approve_selected", "reject_selected"]

    def get_queryset(self, request):
        # Visitor comments only; staff replies are managed inline under each comment.
        qs = (
            super().get_queryset(request)
            .filter(parent__isnull=True)
            .select_related("post")
            .annotate(_replies=Count("replies"))
        )
        if request.user.is_superuser:
            return qs
        if is_counselor(request.user):
            return qs.filter(post__counselor=request.user.counselor_profile)
        return qs.none()

    def get_list_filter(self, request):
        if request.user.is_superuser:
            return ["status", "post__counselor", "post__category", "created_at"]
        return ["status", "created_at"]

    def has_add_permission(self, request):
        return False  # comments come from the website; replies are added inline

    def save_formset(self, request, form, formset, change):
        replies = formset.save(commit=False)
        profile = getattr(request.user, "counselor_profile", None)
        for reply in replies:
            if not reply.pk:
                reply.post = form.instance.post
                reply.name = profile.full_name if profile else (request.user.get_full_name() or "Site team")
                reply.user = request.user
                reply.is_staff_reply = True
                reply.status = Comment.Status.APPROVED
            reply.save()
        for obj in formset.deleted_objects:
            obj.delete()
        if replies and form.instance.status != Comment.Status.APPROVED:
            self.message_user(
                request, "Reply saved. Approve the original comment so both appear on the site.", messages.WARNING
            )

    @admin.action(description="Approve selected comments")
    def approve_selected(self, request, queryset):
        count = queryset.update(status=Comment.Status.APPROVED)
        self.message_user(request, f"{count} comment(s) approved.", messages.SUCCESS)

    @admin.action(description="Reject selected comments")
    def reject_selected(self, request, queryset):
        count = queryset.update(status=Comment.Status.REJECTED)
        self.message_user(request, f"{count} comment(s) rejected.", messages.WARNING)

    @admin.display(description="Comment")
    def short_body(self, obj):
        return Truncator(obj.body).chars(80)

    @admin.display(description="Post", ordering="post__title")
    def post_link(self, obj):
        return format_html('<a href="{}" target="_blank" rel="noopener">{}</a>',
                           obj.post.get_absolute_url(), Truncator(obj.post.title).chars(50))

    @admin.display(description="Replies", ordering="_replies")
    def reply_count(self, obj):
        return obj._replies
