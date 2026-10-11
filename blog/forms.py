import re
import time

from django import forms
from django.core import signing
from django.utils.html import strip_tags

URL_RE = re.compile(r"(https?://|www\.)", re.IGNORECASE)
MAX_LINKS = 2
MIN_SECONDS_TO_SUBMIT = 3          # bots submit instantly
TOKEN_MAX_AGE = 60 * 60 * 6        # form must be submitted within 6 hours
TOKEN_SALT = "blog.comment-form"


def make_form_token(post_id):
    return signing.dumps({"p": post_id, "t": int(time.time())}, salt=TOKEN_SALT)


class CommentForm(forms.Form):
    name = forms.CharField(
        min_length=2, max_length=80,
        widget=forms.TextInput(attrs={"class": "form-control", "autocomplete": "name"}),
    )
    body = forms.CharField(
        label="Comment", min_length=3, max_length=2000,
        widget=forms.Textarea(attrs={"class": "form-control", "rows": 5, "maxlength": 2000}),
    )
    # Honeypot: hidden from people with CSS, but bots fill every field.
    website = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={"autocomplete": "off", "tabindex": "-1"}),
    )
    form_token = forms.CharField(widget=forms.HiddenInput)

    def __init__(self, *args, post=None, **kwargs):
        self.post = post
        super().__init__(*args, **kwargs)
        if not self.is_bound and post is not None:
            self.initial["form_token"] = make_form_token(post.pk)

    @property
    def is_bot(self):
        return bool(self.cleaned_data.get("website"))

    def clean_name(self):
        name = " ".join(strip_tags(self.cleaned_data["name"]).split())
        if len(name) < 2:
            raise forms.ValidationError("Please enter your name.")
        if URL_RE.search(name):
            raise forms.ValidationError("Names can't contain links.")
        return name

    def clean_body(self):
        body = strip_tags(self.cleaned_data["body"]).strip()
        body = re.sub(r"\n{3,}", "\n\n", body)
        if len(body) < 3:
            raise forms.ValidationError("Please write a comment.")
        if len(URL_RE.findall(body)) > MAX_LINKS:
            raise forms.ValidationError(f"Comments can include at most {MAX_LINKS} links.")
        return body

    def clean_form_token(self):
        error = forms.ValidationError("This form has expired. Please reload the page and try again.")
        try:
            data = signing.loads(self.cleaned_data["form_token"], salt=TOKEN_SALT, max_age=TOKEN_MAX_AGE)
        except signing.BadSignature:  # includes SignatureExpired
            raise error
        if self.post is None or data.get("p") != self.post.pk:
            raise error
        if time.time() - data.get("t", 0) < MIN_SECONDS_TO_SUBMIT:
            raise forms.ValidationError("That was quick. Please wait a moment and submit again.")
        return self.cleaned_data["form_token"]
