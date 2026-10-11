"""
HTML sanitising for blog content.

Post content comes from the rich-text editor, so it is HTML. Counselors are
staff but not superusers, so their HTML is still treated as untrusted: every
save runs it through an allow-list. Anything not listed here (script, iframe,
on* handlers, javascript: links, inline styles other than text-align) is
removed.

Visitor comments never use this: they are stored as plain text and escaped on
output by Django's auto-escaping.
"""
import nh3

ALLOWED_TAGS = {
    "p", "br", "hr", "h2", "h3", "h4", "h5", "h6",
    "strong", "b", "em", "i", "u", "s", "sub", "sup", "mark",
    "blockquote", "q", "cite", "code", "pre",
    "ul", "ol", "li",
    "a", "img", "figure", "figcaption",
    "table", "thead", "tbody", "tfoot", "tr", "th", "td", "caption",
    "span", "div",
}

ALLOWED_ATTRIBUTES = {
    "*": {"style"},  # filtered down to text-align below
    "a": {"href", "title", "target"},
    "img": {"src", "alt", "title", "width", "height"},
    "th": {"colspan", "rowspan", "scope"},
    "td": {"colspan", "rowspan"},
    "ol": {"start"},
}

ALLOWED_STYLE_PROPERTIES = {"text-align"}
ALLOWED_URL_SCHEMES = {"http", "https", "mailto", "tel"}


def clean_post_html(html):
    if not html:
        return ""
    return nh3.clean(
        html,
        tags=ALLOWED_TAGS,
        attributes=ALLOWED_ATTRIBUTES,
        url_schemes=ALLOWED_URL_SCHEMES,
        filter_style_properties=ALLOWED_STYLE_PROPERTIES,
        link_rel="noopener noreferrer",
    )
