import time
from datetime import timedelta
from unittest import mock

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from bookings.models import Counselor

from .forms import make_form_token
from .models import Category, Comment, Post, PostLike, Tag


def make_counselor(username):
    user = User.objects.create_user(username, password="pass12345", is_staff=True, first_name=username.title())
    return Counselor.objects.create(user=user, specialization="Anxiety")


class BlogTestBase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = User.objects.create_superuser("admin", "a@x.com", "pass12345")
        cls.sarah = make_counselor("sarah")
        cls.michael = make_counselor("michael")
        cls.cat = Category.objects.create(name="Anxiety")
        cls.tag = Tag.objects.create(name="stress")
        cls.live = Post.objects.create(
            title="How to manage stress", content="<p>Breathe.</p>", category=cls.cat,
            counselor=cls.sarah, status=Post.Status.PUBLISHED,
        )
        cls.live.tags.add(cls.tag)
        cls.draft = Post.objects.create(title="Secret draft", content="<p>wip</p>", counselor=cls.sarah)
        cls.other = Post.objects.create(
            title="Michael on sleep", content="<p>Sleep.</p>", category=cls.cat,
            counselor=cls.michael, status=Post.Status.PUBLISHED,
        )

    def comment_data(self, post, **overrides):
        data = {"name": "Visitor", "body": "Very helpful, thank you.", "website": "", "form_token": make_form_token(post.pk)}
        data.update(overrides)
        return data

    def post_comment(self, post, **overrides):
        data = self.comment_data(post, **overrides)
        # Pretend the visitor spent 10 seconds on the form so the time-trap passes.
        with mock.patch("blog.forms.time.time", return_value=time.time() + 10):
            return self.client.post(post.get_absolute_url(), data)


class PublicPagesTests(BlogTestBase):
    def test_slug_and_excerpt_are_generated(self):
        self.assertEqual(self.live.slug, "how-to-manage-stress")
        self.assertEqual(self.live.excerpt, "Breathe.")
        self.assertEqual(self.live.get_absolute_url(), "/blog/how-to-manage-stress/")

    def test_list_shows_published_only(self):
        res = self.client.get(reverse("blog:list"))
        self.assertContains(res, "How to manage stress")
        self.assertNotContains(res, "Secret draft")

    def test_scheduled_post_hidden(self):
        Post.objects.create(title="Future", content="x", status="published",
                            published_at=timezone.now() + timedelta(days=2))
        self.assertNotContains(self.client.get(reverse("blog:list")), "Future")

    def test_search_category_tag(self):
        self.assertContains(self.client.get(reverse("blog:list"), {"q": "sleep"}), "Michael on sleep")
        self.assertNotContains(self.client.get(reverse("blog:list"), {"q": "sleep"}), "How to manage stress")
        self.assertContains(self.client.get(self.cat.get_absolute_url()), "How to manage stress")
        res = self.client.get(self.tag.get_absolute_url())
        self.assertContains(res, "How to manage stress")
        self.assertNotContains(res, "Michael on sleep")

    def test_draft_detail_404_for_public_but_previewable_by_owner(self):
        self.assertEqual(self.client.get(self.draft.get_absolute_url()).status_code, 404)
        self.client.login(username="michael", password="pass12345")
        self.assertEqual(self.client.get(self.draft.get_absolute_url()).status_code, 404)
        self.client.login(username="sarah", password="pass12345")
        self.assertContains(self.client.get(self.draft.get_absolute_url()), "Preview")

    def test_detail_seo_and_related(self):
        res = self.client.get(self.live.get_absolute_url())
        self.assertContains(res, '<link rel="canonical" href="http://testserver/blog/how-to-manage-stress/">', html=False)
        self.assertContains(res, '"@type": "BlogPosting"')
        self.assertContains(res, 'property="og:title"')
        self.assertEqual(list(res.context["related_posts"]), [self.other])

    def test_homepage_latest_posts_excludes_drafts(self):
        res = self.client.get(reverse("home"))
        self.assertContains(res, "From our blog")
        self.assertContains(res, "How to manage stress")
        self.assertNotContains(res, "Secret draft")

    def test_content_is_sanitised(self):
        p = Post.objects.create(title="x", content='<p onclick="a()">ok</p><script>alert(1)</script>')
        self.assertEqual(p.content, "<p>ok</p>")

    def test_reserved_slug_avoided(self):
        self.assertEqual(Post.objects.create(title="Category", content="x").slug, "category-post")


class LikeTests(BlogTestBase):
    def like(self):
        return self.client.post(reverse("blog:like", args=[self.live.slug]), HTTP_X_REQUESTED_WITH="XMLHttpRequest")

    def test_toggle_like_anonymous(self):
        self.assertEqual(self.like().json(), {"liked": True, "count": 1})
        self.assertEqual(self.like().json(), {"liked": False, "count": 0})
        self.assertEqual(self.like().json(), {"liked": True, "count": 1})
        self.assertEqual(PostLike.objects.count(), 1)

    def test_separate_visitors_count_separately(self):
        self.like()
        self.client.cookies.clear()
        self.assertEqual(self.like().json()["count"], 2)

    def test_logged_in_like_uses_user(self):
        self.client.login(username="michael", password="pass12345")
        self.like()
        self.assertEqual(PostLike.objects.get().user.username, "michael")

    def test_cannot_like_draft_or_use_get(self):
        self.assertEqual(self.client.post(reverse("blog:like", args=[self.draft.slug])).status_code, 404)
        self.assertEqual(self.client.get(reverse("blog:like", args=[self.live.slug])).status_code, 405)

    def test_csrf_enforced(self):
        from django.test import Client
        c = Client(enforce_csrf_checks=True)
        self.assertEqual(c.post(reverse("blog:like", args=[self.live.slug])).status_code, 403)


class CommentTests(BlogTestBase):
    def test_comment_is_pending_until_approved(self):
        res = self.post_comment(self.live)
        self.assertEqual(res.status_code, 302)
        c = Comment.objects.get()
        self.assertEqual(c.status, Comment.Status.PENDING)
        self.assertNotContains(self.client.get(self.live.get_absolute_url()), "Very helpful")
        c.status = Comment.Status.APPROVED
        c.save()
        self.assertContains(self.client.get(self.live.get_absolute_url()), "Very helpful")

    def test_html_is_stripped_and_escaped(self):
        self.post_comment(self.live, body="<script>alert(1)</script>Nice <b>post</b>")
        c = Comment.objects.get()
        self.assertEqual(c.body, "alert(1)Nice post")
        Comment.objects.create(post=self.live, name="<img src=x onerror=alert(1)>", body="hi", status="approved")
        self.assertContains(self.client.get(self.live.get_absolute_url()), "&lt;img src=x onerror=alert(1)&gt;")

    def test_honeypot_silently_drops(self):
        res = self.post_comment(self.live, website="http://spam.example")
        self.assertEqual(res.status_code, 302)
        self.assertEqual(Comment.objects.count(), 0)

    def test_too_fast_rejected(self):
        res = self.client.post(self.live.get_absolute_url(), self.comment_data(self.live))
        self.assertEqual(res.status_code, 400)
        self.assertEqual(Comment.objects.count(), 0)

    def test_token_from_other_post_rejected(self):
        res = self.post_comment(self.live, form_token=make_form_token(self.other.pk))
        self.assertEqual(res.status_code, 400)

    def test_validation_empty_long_and_links(self):
        self.assertEqual(self.post_comment(self.live, body="   ").status_code, 400)
        self.assertEqual(self.post_comment(self.live, body="x" * 2001).status_code, 400)
        self.assertEqual(self.post_comment(self.live, body="http://a http://b http://c").status_code, 400)
        self.assertEqual(Comment.objects.count(), 0)

    def test_duplicate_and_rate_limit(self):
        self.post_comment(self.live)
        self.assertEqual(self.post_comment(self.live).status_code, 400)  # duplicate
        self.post_comment(self.live, body="Second thought")
        self.post_comment(self.live, body="Third thought")
        self.assertEqual(self.post_comment(self.live, body="Fourth thought").status_code, 400)  # rate limit
        self.assertEqual(Comment.objects.count(), 3)

    def test_no_comments_on_drafts(self):
        self.client.login(username="sarah", password="pass12345")
        self.assertEqual(self.post_comment(self.draft).status_code, 404)


class AdminIsolationTests(BlogTestBase):
    def test_existing_admin_pages_still_work(self):
        self.client.login(username="sarah", password="pass12345")
        for name in ["admin:bookings_appointment_changelist", "admin:bookings_availability_changelist"]:
            self.assertEqual(self.client.get(reverse(name)).status_code, 200)

    def test_counselor_sees_only_own_posts(self):
        self.client.login(username="sarah", password="pass12345")
        res = self.client.get(reverse("admin:blog_post_changelist"))
        self.assertContains(res, "How to manage stress")
        self.assertNotContains(res, "Michael on sleep")
        url = reverse("admin:blog_post_change", args=[self.other.pk])
        self.assertNotEqual(self.client.get(url).status_code, 200)
        self.assertNotEqual(self.client.post(reverse("admin:blog_post_delete", args=[self.other.pk]), {"post": "yes"}).status_code, 200)
        self.assertTrue(Post.objects.filter(pk=self.other.pk).exists())

    def test_superadmin_sees_all(self):
        self.client.login(username="admin", password="pass12345")
        res = self.client.get(reverse("admin:blog_post_changelist"))
        self.assertContains(res, "Michael on sleep")
        self.assertContains(res, "Secret draft")

    def _add_form(self, **extra):
        data = {
            "title": "New anxiety tips", "slug": "", "excerpt": "", "content": "<p>Hello</p>",
            "featured_image_alt": "", "category": self.cat.pk, "status": "draft", "published_at_0": "",
            "published_at_1": "", "allow_comments": "on", "seo_title": "", "meta_description": "",
        }
        data.update(extra)
        return data

    def test_counselor_publish_button_assigns_self(self):
        self.client.login(username="sarah", password="pass12345")
        res = self.client.post(reverse("admin:blog_post_add"), self._add_form(counselor=self.michael.pk, _publish="Publish"))
        # Tampering with the hidden author field is rejected...
        self.assertEqual(res.status_code, 200)
        self.assertFalse(Post.objects.filter(title="New anxiety tips").exists())
        # ...and a normal submit assigns the post to the logged-in counselor.
        res = self.client.post(reverse("admin:blog_post_add"), self._add_form(_publish="Publish"))
        self.assertEqual(res.status_code, 302)
        post = Post.objects.get(title="New anxiety tips")
        self.assertEqual(post.counselor, self.sarah)
        self.assertTrue(post.is_live)
        self.assertEqual(post.slug, "new-anxiety-tips")

    def test_save_draft_and_unpublish_buttons(self):
        self.client.login(username="admin", password="pass12345")
        self.client.post(reverse("admin:blog_post_add"), self._add_form(status="published", _save_draft="1"))
        post = Post.objects.get(title="New anxiety tips")
        self.assertEqual(post.status, "draft")

    def test_counselor_cannot_manage_categories(self):
        self.client.login(username="sarah", password="pass12345")
        self.assertEqual(self.client.get(reverse("admin:blog_category_changelist")).status_code, 403)

    def test_comment_moderation_isolated(self):
        mine = Comment.objects.create(post=self.live, name="A", body="on sarah's post")
        theirs = Comment.objects.create(post=self.other, name="B", body="on michael's post")
        self.client.login(username="sarah", password="pass12345")
        res = self.client.get(reverse("admin:blog_comment_changelist"))
        self.assertContains(res, "on sarah&#x27;s post")
        self.assertNotContains(res, "michael&#x27;s post")
        self.assertNotEqual(self.client.get(reverse("admin:blog_comment_change", args=[theirs.pk])).status_code, 200)

        # Approve via bulk action
        self.client.post(reverse("admin:blog_comment_changelist"),
                         {"action": "approve_selected", "_selected_action": [mine.pk, theirs.pk]})
        mine.refresh_from_db(); theirs.refresh_from_db()
        self.assertEqual(mine.status, "approved")
        self.assertEqual(theirs.status, "pending")

    def test_counselor_reply_inline(self):
        c = Comment.objects.create(post=self.live, name="A", body="Question?", status="approved")
        self.client.login(username="sarah", password="pass12345")
        url = reverse("admin:blog_comment_change", args=[c.pk])
        data = {
            "status": "approved",
            "replies-TOTAL_FORMS": "1", "replies-INITIAL_FORMS": "0",
            "replies-MIN_NUM_FORMS": "0", "replies-MAX_NUM_FORMS": "1000",
            "replies-0-body": "Thanks for asking!", "replies-0-id": "", "replies-0-parent": c.pk,
        }
        res = self.client.post(url, data)
        self.assertEqual(res.status_code, 302, getattr(res, "context", None) and res.context.get("errors"))
        reply = Comment.objects.get(parent=c)
        self.assertTrue(reply.is_staff_reply)
        self.assertEqual(reply.name, "Sarah")
        page = self.client.get(self.live.get_absolute_url())
        self.assertContains(page, "Thanks for asking!")
        self.assertContains(page, "Counselor reply")

    def test_editor_image_upload_requires_staff(self):
        from django.core.files.uploadedfile import SimpleUploadedFile
        url = reverse("blog:editor_upload")
        self.assertEqual(self.client.post(url).status_code, 302)  # redirected to login
        self.client.login(username="sarah", password="pass12345")
        bad = SimpleUploadedFile("x.png", b"not an image", content_type="image/png")
        self.assertEqual(self.client.post(url, {"file": bad}).status_code, 400)
