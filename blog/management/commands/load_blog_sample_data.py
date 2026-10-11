from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from bookings.models import Counselor
from blog.models import Category, Post, Tag

CATEGORIES = [
    "Mental Health", "Anxiety", "Stress Management", "Relationships", "Self-Care",
    "Personal Growth", "Emotional Wellbeing", "Therapy", "Counseling",
]

SAMPLE_POSTS = [
    {
        "title": "Five small ways to manage everyday stress",
        "category": "Stress Management",
        "tags": ["stress", "self-care", "habits"],
        "featured": True,
        "content": (
            "<p>Stress is a normal response to pressure, but when it never switches off it affects sleep, "
            "mood and concentration. These small habits can help.</p>"
            "<h2>1. Notice your early signs</h2><p>Tight shoulders, a shorter temper or racing thoughts are "
            "useful signals. Naming them is the first step to responding.</p>"
            "<h2>2. Breathe slowly for two minutes</h2><p>Breathe in for four counts and out for six. A longer "
            "out-breath tells your body it is safe to slow down.</p>"
            "<h2>3. Protect your sleep</h2><ul><li>Keep a regular wake-up time</li><li>Put screens away an hour "
            "before bed</li></ul>"
            "<blockquote>You don't have to fix everything today. You only have to take the next small step.</blockquote>"
            "<h2>4. Move your body</h2><p>A ten-minute walk is enough to change how you feel.</p>"
            "<h2>5. Talk to someone</h2><p>If stress is affecting your daily life, a counselor can help you "
            "understand it and find a way forward.</p>"
        ),
    },
    {
        "title": "Understanding anxiety: what it is and when to get help",
        "category": "Anxiety",
        "tags": ["anxiety", "mental health"],
        "content": (
            "<p>Everyone feels anxious sometimes. Anxiety becomes a problem when it is intense, lasts a long "
            "time, or stops you doing things that matter to you.</p>"
            "<h2>Common signs</h2><ul><li>Constant worry that is hard to control</li><li>Restlessness or "
            "feeling on edge</li><li>Trouble sleeping</li><li>Avoiding situations</li></ul>"
            "<h2>When to reach out</h2><p>If anxiety has been affecting your work, relationships or sleep for "
            "a few weeks, it is a good time to speak with a professional.</p>"
        ),
    },
    {
        "title": "Healthy communication in relationships",
        "category": "Relationships",
        "tags": ["relationships", "communication"],
        "content": (
            "<p>Most conflict isn't about the topic. It's about feeling unheard. These three habits help.</p>"
            "<h3>Listen to understand</h3><p>Reflect back what you heard before giving your view.</p>"
            "<h3>Use “I” statements</h3><p>“I felt worried when…” lands differently from “You always…”.</p>"
            "<h3>Take a pause</h3><p>If a conversation gets heated, agree to come back to it in 20 minutes.</p>"
        ),
    },
]


class Command(BaseCommand):
    help = "Create blog categories and a few published sample posts (safe to run more than once)."

    def handle(self, *args, **options):
        for name in CATEGORIES:
            Category.objects.get_or_create(name=name)
        self.stdout.write(self.style.SUCCESS(f"{len(CATEGORIES)} categories ready."))

        counselors = list(Counselor.objects.all()[:3])
        created = 0
        for i, data in enumerate(SAMPLE_POSTS):
            if Post.objects.filter(title=data["title"]).exists():
                continue
            post = Post.objects.create(
                title=data["title"],
                content=data["content"],
                category=Category.objects.get(name=data["category"]),
                counselor=counselors[i % len(counselors)] if counselors else None,
                status=Post.Status.PUBLISHED,
                published_at=timezone.now() - timedelta(days=i * 3),
                is_featured=data.get("featured", False),
            )
            for tag_name in data["tags"]:
                tag, _ = Tag.objects.get_or_create(name=tag_name)
                post.tags.add(tag)
            created += 1
        self.stdout.write(self.style.SUCCESS(f"{created} sample post(s) created."))
