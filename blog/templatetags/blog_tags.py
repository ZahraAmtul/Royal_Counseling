from django import template

from ..models import Post

register = template.Library()


@register.inclusion_tag("blog/includes/latest_posts.html")
def latest_blog_posts(count=3):
    """Usage: {% load blog_tags %}{% latest_blog_posts 3 %} — published posts only."""
    posts = (
        Post.objects.published()
        .select_related("category", "counselor__user")
        .order_by("-published_at")[:count]
    )
    return {"posts": posts}
