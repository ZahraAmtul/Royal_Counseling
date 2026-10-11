import hashlib
import json
import os
import uuid
from datetime import timedelta

from django import forms
from django.conf import settings
from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.core.files.storage import default_storage
from django.db import IntegrityError
from django.db.models import Count, Prefetch, Q
from django.http import Http404, HttpResponseRedirect, JsonResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views import View
from django.views.generic import DetailView, ListView

from .forms import CommentForm, make_form_token
from .models import Category, Comment, Post, PostLike, Tag

PAGE_SIZE = 9
COMMENT_LIMIT = 3                         # comments per visitor ...
COMMENT_WINDOW = timedelta(minutes=10)    # ... per this window
DUPLICATE_WINDOW = timedelta(days=1)
VISITOR_SESSION_KEY = "blog_visitor_id"

EDITOR_IMAGE_MAX_BYTES = 5 * 1024 * 1024
EDITOR_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".webp"}


# -----------------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------------

def site_name():
    return getattr(settings, "SITE_NAME", "STU CONSULTANT")


def ip_hash(request):
    # REMOTE_ADDR only. If you deploy behind a proxy (nginx, a load balancer),
    # configure it to set REMOTE_ADDR correctly; never trust X-Forwarded-For blindly.
    ip = request.META.get("REMOTE_ADDR", "")
    return hashlib.sha256(f"{settings.SECRET_KEY}:{ip}".encode()).hexdigest()


def get_visitor_id(request, create=False):
    visitor_id = request.session.get(VISITOR_SESSION_KEY)
    if not visitor_id and create:
        visitor_id = uuid.uuid4().hex
        request.session[VISITOR_SESSION_KEY] = visitor_id
    return visitor_id


def like_lookup(request, create=False):
    """Filter kwargs identifying this visitor's like, or None if they have no identity yet."""
    if request.user.is_authenticated:
        return {"user": request.user}
    visitor_id = get_visitor_id(request, create=create)
    return {"visitor_id": visitor_id} if visitor_id else None


def can_preview(user, post):
    """Staff who can edit a draft in admin can also preview it on the site."""
    if not (user.is_authenticated and user.is_staff):
        return False
    if user.is_superuser:
        return True
    profile = getattr(user, "counselor_profile", None)
    return profile is not None and post.counselor_id == profile.id


def published_posts():
    return (
        Post.objects.published()
        .select_related("category", "counselor__user")
        .prefetch_related("tags")
    )


def json_ld(data):
    """Serialise structured data safely for a <script> tag."""
    return (
        json.dumps(data, ensure_ascii=False)
        .replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")
    )


# -----------------------------------------------------------------------------
# Public pages
# -----------------------------------------------------------------------------

class PostListView(ListView):
    template_name = "blog/post_list.html"
    context_object_name = "posts"
    paginate_by = PAGE_SIZE

    def get_queryset(self):
        qs = published_posts()
        self.category = self.tag = self.featured = None
        self.query = self.request.GET.get("q", "").strip()[:100]

        if "category_slug" in self.kwargs:
            self.category = get_object_or_404(Category, slug=self.kwargs["category_slug"])
            qs = qs.filter(category=self.category)
        if "tag_slug" in self.kwargs:
            self.tag = get_object_or_404(Tag, slug=self.kwargs["tag_slug"])
            qs = qs.filter(tags=self.tag)
        if self.query:
            qs = qs.filter(
                Q(title__icontains=self.query)
                | Q(excerpt__icontains=self.query)
                | Q(content__icontains=self.query)
                | Q(tags__name__icontains=self.query)
                | Q(category__name__icontains=self.query)
            ).distinct()

        # On the unfiltered first page, lift the newest featured post into a banner.
        is_first_page = self.request.GET.get(self.page_kwarg, "1") == "1"
        if not (self.category or self.tag or self.query) and is_first_page:
            self.featured = qs.filter(is_featured=True).first()
            if self.featured:
                qs = qs.exclude(pk=self.featured.pk)
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        now = timezone.now()
        live = Q(posts__status=Post.Status.PUBLISHED, posts__published_at__lte=now)
        ctx.update({
            "categories": Category.objects.annotate(post_total=Count("posts", filter=live)).filter(post_total__gt=0),
            "current_category": self.category,
            "current_tag": self.tag,
            "query": self.query,
            "featured_post": self.featured,
            "site_name": site_name(),
            "canonical_url": self.request.build_absolute_uri(self.request.path),
        })
        return ctx


class PostDetailView(DetailView):
    template_name = "blog/post_detail.html"
    context_object_name = "post"

    def get_queryset(self):
        return Post.objects.select_related("category", "counselor__user").prefetch_related("tags")

    def get_object(self, queryset=None):
        post = super().get_object(queryset)
        if not post.is_live and not can_preview(self.request.user, post):
            raise Http404("No post found")
        return post

    # Comment submission ----------------------------------------------------

    def post(self, request, *args, **kwargs):
        self.object = post = self.get_object()
        if not post.is_live or not post.allow_comments:
            raise Http404("Comments are closed")

        form = CommentForm(request.POST, post=post)
        if form.is_valid():
            if form.is_bot:
                # Pretend it worked so bots don't learn anything.
                messages.success(request, "Thanks! Your comment will appear after it's reviewed.")
                return HttpResponseRedirect(f"{post.get_absolute_url()}#comments")

            visitor = ip_hash(request)
            now = timezone.now()
            recent = Comment.objects.filter(ip_hash=visitor, created_at__gte=now - COMMENT_WINDOW)
            if recent.count() >= COMMENT_LIMIT:
                form.add_error(None, "You've posted several comments in a short time. Please try again in a few minutes.")
            elif Comment.objects.filter(
                post=post, ip_hash=visitor, body__iexact=form.cleaned_data["body"],
                created_at__gte=now - DUPLICATE_WINDOW,
            ).exists():
                form.add_error(None, "You've already sent this comment. It will appear once it's reviewed.")
            else:
                Comment.objects.create(
                    post=post,
                    name=form.cleaned_data["name"],
                    body=form.cleaned_data["body"],
                    ip_hash=visitor,
                )
                messages.success(request, "Thanks! Your comment will appear after it's reviewed.")
                return HttpResponseRedirect(f"{post.get_absolute_url()}#comments")

        context = self.get_context_data(object=post, comment_form=form)
        return self.render_to_response(context, status=400)

    # Page context ------------------------------------------------------------

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        post = self.object
        request = self.request

        approved_replies = Comment.objects.filter(status=Comment.Status.APPROVED).select_related("user")
        comments = (
            post.comments.filter(status=Comment.Status.APPROVED, parent__isnull=True)
            .prefetch_related(Prefetch("replies", queryset=approved_replies))
        )

        tag_ids = list(post.tags.values_list("id", flat=True))
        related = Post.objects.none()
        if post.category_id or tag_ids:
            related = (
                published_posts()
                .filter(Q(category_id=post.category_id) | Q(tags__in=tag_ids))
                .exclude(pk=post.pk)
                .distinct()[:3]
            )

        lookup = like_lookup(request)
        ctx.update({
            "comments": comments,
            "comment_total": post.comments.filter(status=Comment.Status.APPROVED).count(),
            "comment_form": kwargs.get("comment_form") or CommentForm(post=post),
            "form_token": make_form_token(post.pk),
            "related_posts": related,
            "like_total": post.likes.count(),
            "user_liked": bool(lookup) and post.likes.filter(**lookup).exists(),
            "is_preview": not post.is_live,
            "site_name": site_name(),
        })
        ctx.update(self.seo_context(post))
        return ctx

    def seo_context(self, post):
        request = self.request
        url = request.build_absolute_uri(post.get_absolute_url())
        image = request.build_absolute_uri(post.featured_image.url) if post.featured_image else ""
        data = {
            "@context": "https://schema.org",
            "@type": "BlogPosting",
            "mainEntityOfPage": {"@type": "WebPage", "@id": url},
            "headline": post.title[:110],
            "description": post.page_description,
            "datePublished": (post.published_at or post.created_at).isoformat(),
            "dateModified": post.updated_at.isoformat(),
            "author": {"@type": "Person" if post.counselor_id else "Organization", "name": post.author_name},
            "publisher": {"@type": "Organization", "name": site_name()},
            "url": url,
        }
        if image:
            data["image"] = [image]
        if post.category_id:
            data["articleSection"] = post.category.name
        tags = [t.name for t in post.tags.all()]
        if tags:
            data["keywords"] = ", ".join(tags)
        return {"canonical_url": url, "og_image": image, "structured_data": json_ld(data)}


# -----------------------------------------------------------------------------
# Likes
# -----------------------------------------------------------------------------

class LikeToggleView(View):
    http_method_names = ["post"]

    def post(self, request, slug):
        post = get_object_or_404(Post.objects.published(), slug=slug)
        lookup = like_lookup(request, create=True)

        existing = post.likes.filter(**lookup).first()
        if existing:
            existing.delete()
            liked = False
        else:
            try:
                PostLike.objects.create(post=post, **lookup)
            except IntegrityError:  # double-click race: the like already exists
                pass
            liked = True

        count = post.likes.count()
        if request.headers.get("x-requested-with") == "XMLHttpRequest":
            return JsonResponse({"liked": liked, "count": count})
        return HttpResponseRedirect(f"{post.get_absolute_url()}#engagement")


# -----------------------------------------------------------------------------
# Image upload for the admin rich-text editor
# -----------------------------------------------------------------------------

class EditorImageForm(forms.Form):
    file = forms.ImageField()  # Pillow verifies it is a real image


@method_decorator(staff_member_required, name="dispatch")
class EditorImageUploadView(View):
    http_method_names = ["post"]

    def post(self, request):
        user = request.user
        if not (user.is_superuser or hasattr(user, "counselor_profile")):
            return JsonResponse({"error": "You don't have permission to upload images."}, status=403)

        form = EditorImageForm(files=request.FILES)
        if not form.is_valid():
            return JsonResponse({"error": "Upload a valid image (JPG, PNG, GIF or WebP)."}, status=400)

        upload = form.cleaned_data["file"]
        ext = os.path.splitext(upload.name)[1].lower()
        if ext not in EDITOR_IMAGE_EXTENSIONS:
            return JsonResponse({"error": "Only JPG, PNG, GIF and WebP images are allowed."}, status=400)
        if upload.size > EDITOR_IMAGE_MAX_BYTES:
            return JsonResponse({"error": "Images must be 5 MB or smaller."}, status=400)

        path = default_storage.save(
            f"blog/content/{timezone.now():%Y/%m}/{uuid.uuid4().hex}{ext}", upload
        )
        return JsonResponse({"location": default_storage.url(path)})
