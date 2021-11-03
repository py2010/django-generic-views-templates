# coding=utf-8
# from importlib import import_module

import logging
from django import template
from generic.views import lookup_val
register = template.Library()
logger = logging.getLogger()


@register.filter
def debug(mm, nn=None):
    # 自定义过滤器 - 模板调试 {{ mm|debug:nn }}
    print({'mm': mm, 'nn': nn})
    import ipdb; ipdb.set_trace()
    return


@register.simple_tag
def add(*args):
    # 自定义标签 -- 字符串拼接 {% add a b c %} (内置过滤器add一次只能拼接二个变量, 语法长不直观)
    return ''.join([str(i) for i in args])


register.filter(lookup_val)  # 列表页获取 object.field_name


# @register.simple_tag
# def get_attr(obj, *args):
#     # 模板标签 getattr
#     val = None
#     for arg in args:
#         val = getattr(obj, arg, None)
#         if val:
#             obj = val
#         else:
#             return None
#     if callable(val):
#         val = val()
#     return val

