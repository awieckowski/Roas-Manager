from django import template
from datetime import datetime

register = template.Library()


@register.filter
def subtract(value, arg):
    return value - arg


@register.filter
def multiply(value, arg):
    return value * arg


@register.filter
def days_remaining(from_date, to_date):
    diff = to_date - from_date
    return diff