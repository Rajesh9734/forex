from django import template

register = template.Library()


@register.filter
def money(value):
    if value is None:
        return "—"
    return f"{value:,.2f}"


@register.filter
def price(value):
    if value is None:
        return "—"
    text = format(value, "f").rstrip("0").rstrip(".")
    return text if text else "0"


@register.filter
def signed(value):
    if value is None:
        return "—"
    return f"{value:+,.2f}"


@register.filter
def tone(value):
    if value is None:
        return "neutral"
    return "positive" if value > 0 else "negative" if value < 0 else "neutral"


@register.filter
def words(value):
    return str(value).replace("_", " ")


@register.simple_tag(takes_context=True)
def querystring(context, **kwargs):
    query = context["request"].GET.copy()
    query.pop("page", None)
    for key, value in kwargs.items():
        if value is None:
            query.pop(key, None)
        else:
            query[key] = str(value)
    return query.urlencode()
