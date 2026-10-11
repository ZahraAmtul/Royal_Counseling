import math
import re

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q
from django.urls import reverse
from django.utils import timezone
from django.utils.html import strip_tags
from django.utils.text import Truncator, slugify

from bookings.models import Counselor

from .sanitizer import clean_post_html

# Slugs that would collide with fixed blog URLs (e.g. /blog/category/like/).
RESERVED_SLUGS = {"category", "tag", "editor"}

_BLOCK_END = re.compile(r"</(p|h[1-6]|li|blockquote|figcaption|td|th|pre)>|<br\s*/?>", re.IGNORECASE)


def html_to_text(html):
    """Plain text from HTML, keeping a space between paragraphs, headings and list items."""
    return " ".join(strip_tags(_BLOCK_END.sub(" ", html or "")).split())


def unique_slug(instance, source, max_length=200):
    """Slugify `source` and add -2, -3 ... until no other row of this model uses it."""
    base = slugify(source)[:max_length].strip("-") or "item"
    if base in RESERVED_SLUGS:
        base = f"{base}-post"
    slug, n = base, 2
    qs = type(instance)._default_manager.exclude(pk=instance.pk)
    while qs.filter(slug=slug).exists():
        suffix = f"-{n}"
        slug = f"{base[:max_length - len(suffix)]}{suffix}"
        n += 1
    return slug


# -----------------------------------------------------------------------------
# Taxonomy
# -----------------------------------------------------------------------------

class Category(models.Model):
    name = models.CharField(max_length=80, unique=True)
    slug = models.SlugField(max_length=90, unique=True, blank=True)
    description = models.TextField(blank=True, help_text="Optional. Shown on the category page.")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]
        verbose_name_plural = "Categories"

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = unique_slug(self, self.name, 90)
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse("blog:category", kwargs={"category_slug": self.slug})


class Tag(models.Model):
    name = models.CharField(max_length=50, unique=True)
    slug = models.SlugField(max_length=60, unique=True, blank=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = unique_slug(self, self.name, 60)
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse("blog:tag", kwargs={"tag_slug": self.slug})


# -----------------------------------------------------------------------------
# Posts
# -----------------------------------------------------------------------------

class PostQuerySet(models.QuerySet):
    def published(self):
        """Live posts only. Drafts and posts scheduled for the future are excluded."""
        return self.filter(status=Post.Status.PUBLISHED, published_at__lte=timezone.now())


class Post(models.Model):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        PUBLISHED = "published", "Published"

    title = models.CharField(max_length=200)
    slug = models.SlugField(
        max_length=200, unique=True, blank=True,
        help_text="Used in the URL: /blog/<slug>/. Filled from the title; you can edit it.",
    )
    excerpt = models.TextField(
        "short description", max_length=300, blank=True,
        help_text="Shown on blog cards. Leave empty to use the first words of the content.",
    )
    featured_image = models.ImageField(
        upload_to="blog/featured/%Y/%m/", blank=True, null=True,
        help_text="Recommended: 1200×630px (also used when the post is shared).",
    )
    featured_image_alt = models.CharField(
        "image description", max_length=150, blank=True,
        help_text="Describe the image for screen readers and search engines.",
    )
    content = models.TextField()

    # Named `counselor` (not `author`) so the existing CounselorFilteredAdmin
    # isolation works on posts without any changes to bookings/admin.py.
    counselor = models.ForeignKey(
        Counselor, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="blog_posts", verbose_name="author",
        help_text="Leave empty to publish as the site team.",
    )
    category = models.ForeignKey(
        Category, on_delete=models.SET_NULL, null=True, blank=True, related_name="posts",
    )
    tags = models.ManyToManyField(Tag, blank=True, related_name="posts")

    status = models.CharField(max_length=10, choices=Status.choices, default=Status.DRAFT, db_index=True)
    published_at = models.DateTimeField(
        "publication date", null=True, blank=True, db_index=True,
        help_text="Set automatically when first published. A future date schedules the post.",
    )
    is_featured = models.BooleanField(
        "featured", default=False, help_text="Featured posts are highlighted at the top of the blog page.",
    )
    allow_comments = models.BooleanField(default=True)

    seo_title = models.CharField(
        "SEO title", max_length=70, blank=True,
        help_text="Max 70 characters. Leave empty to use the post title.",
    )
    meta_description = models.CharField(
        max_length=160, blank=True,
        help_text="Max 160 characters. Leave empty to use the short description.",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = PostQuerySet.as_manager()

    class Meta:
        ordering = ["-published_at", "-created_at"]

    def __str__(self):
        return self.title

    def clean(self):
        if self.slug and self.slug in RESERVED_SLUGS:
            raise ValidationError({"slug": f'"{self.slug}" is reserved. Please choose another slug.'})

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = unique_slug(self, self.title)
        self.content = clean_post_html(self.content)
        if not self.excerpt.strip():
            self.excerpt = Truncator(html_to_text(self.content)).words(35)[:300]
        if self.status == self.Status.PUBLISHED and not self.published_at:
            self.published_at = timezone.now()
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse("blog:detail", kwargs={"slug": self.slug})

    @property
    def is_live(self):
        return (
            self.status == self.Status.PUBLISHED
            and self.published_at is not None
            and self.published_at <= timezone.now()
        )

    @property
    def author_name(self):
        return self.counselor.full_name if self.counselor_id else getattr(settings, "SITE_NAME", "Our team")

    @property
    def page_title(self):
        return self.seo_title or self.title

    @property
    def page_description(self):
        return self.meta_description or Truncator(self.excerpt).chars(160)

    @property
    def reading_time(self):
        words = len(html_to_text(self.content).split())
        return max(1, math.ceil(words / 200))


class PostLike(models.Model):
    """One like per post per visitor: a logged-in user, or an anonymous session."""
    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name="likes")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, null=True, blank=True)
    visitor_id = models.CharField(max_length=64, blank=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["post", "user"], condition=Q(user__isnull=False), name="blog_unique_like_per_user",
            ),
            models.UniqueConstraint(
                fields=["post", "visitor_id"], condition=~Q(visitor_id=""), name="blog_unique_like_per_visitor",
            ),
        ]

    def __str__(self):
        return f"Like on {self.post}"


class Comment(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending approval"
        APPROVED = "approved", "Approved"
        REJECTED = "rejected", "Rejected"

    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name="comments")
    parent = models.ForeignKey(
        "self", on_delete=models.CASCADE, null=True, blank=True, related_name="replies",
        help_text="Set for replies written by staff.",
    )
    name = models.CharField(max_length=80)
    body = models.TextField("comment", max_length=2000)  # plain text, escaped on output
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING, db_index=True)

    is_staff_reply = models.BooleanField(default=False, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, editable=False,
    )
    # Salted hash of the visitor's IP: used for rate limiting and duplicate checks.
    # The raw IP is never stored.
    ip_hash = models.CharField(max_length=64, blank=True, editable=False, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]
        indexes = [models.Index(fields=["post", "status"])]

    def __str__(self):
        return f"{self.name} on {self.post}"
