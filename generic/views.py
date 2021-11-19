# coding=utf-8
import logging

from django.http import JsonResponse
from django.views.generic import View, DetailView, CreateView, UpdateView
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
# from django.db.models.constants import LOOKUP_SEP
from django.urls import reverse_lazy

import traceback
from django.db.models.fields import reverse_related
from django.db.models.fields import related

from django.contrib.admin import utils
from django.core.exceptions import ObjectDoesNotExist
from django.utils.html import format_html

from . import listview
logger = logging.getLogger()

__all__ = [
    'ModelMixin', 'MyCreateView', 'MyDeleteView', 'MyUpdateView', 'MyListView', 'MyDetailView',
    'lookup_val'

]


class ModelMixin(LoginRequiredMixin, PermissionRequiredMixin):
    '''
    由于不想在MyListView/MyDetailView等视图中分别重写as_view(), 所以统一在当前重写.
    多重继承时注意顺序, python中越往右为越远的基类祖先, 和VUE中继承顺序书写相反.
    '''
    model = None
    queryset = None

    # def __init__(self, **initkwargs):
    #     super().__init__(**initkwargs)

    @classmethod
    def as_view(cls, *a, **k):
        if not cls.model:
            if not cls.queryset:
                raise Exception(f'{cls}: Model View ??')
            else:
                cls.model = cls.queryset.model

        ops = cls.model._meta
        cls.model_meta = ops  # 由于模板中禁止访问"_"开头的属性.

        if hasattr(cls, 'get_template_names'):
            # 自动设置模板页
            def get_template_names(self):
                '''
                django-ListView 是从object_list 中取model, 而不是取view.model
                object_list 如果不是QuerySet, 生成不了model_template, 所以本函数重新处理.
                '''
                try:
                    templates = super().get_template_names()
                except Exception:
                    # traceback.print_exc()  # django 2.*
                    templates = []

                model_template = f'{ops.app_label}/{ops.model_name}{self.template_name_suffix}.html'
                generic_template = f'generic/{self.template_name_suffix}.html'

                logger.debug(f'\r\nmodel_template: {model_template} \r\ngeneric_template: {generic_template}')
                # 优先使用自定义模板 model_template
                if model_template not in templates:
                    templates.append(model_template)

                if generic_template not in templates:
                    templates.append(generic_template)

                return templates
            cls.get_template_names = get_template_names

        if not cls.permission_required:
            # 自动设置权限代码
            if issubclass(cls, CreateView):
                action = 'add'  # 增
            elif issubclass(cls, MyDeleteView):
                action = 'delete'  # 删
            elif issubclass(cls, UpdateView):
                action = 'change'  # 改
            else:
                action = 'view'  # 查

            cls.permission_required = f'{ops.app_label}.{action}_{ops.model_name}'
            # print(cls, cls.permission_required, 77777)
        # if issubclass(cls, (CreateView, UpdateView)) and not cls.success_url:
        #     # 新增/编辑, 完成后跳转URL
        #     cls.success_url = reverse_lazy(f'{ops.app_label}:{ops.model_name}_list')

        view = super().as_view(*a, **k)
        return view


class MyModelFormMixin(ModelMixin):

    # def get_form_class(self):
    #     if self.form_class is None and self.fields is None:
    #         self.fields = '__all__'
    #     return super().get_form_class()

    def get_success_url(self):
        # 保存完成后, 跳转url
        try:
            if self.success_url:
                return str(self.success_url)
        except Exception:
            traceback.print_exc()

        # success_url未配置或错误配置, 跳转到列表页
        view_name = self.request.resolver_match.view_name  # app_name可能和meta.app_label不同
        list_view_name = f'{view_name[:-6]}list'
        return reverse_lazy(list_view_name)


class MyCreateView(MyModelFormMixin, CreateView):
    1


class MyUpdateView(MyModelFormMixin, UpdateView):
    1


class MyDeleteView(ModelMixin, View):
    '''批量删除model表数据'''
    model = None

    def post(self, request, *args, **kwargs):
        error = ''
        if self.model:
            ids = request.POST.getlist('id', [])
            if ids:
                try:
                    self.model.objects.filter(id__in=ids).delete()
                except Exception as e:
                    error = str(e)
            else:
                error = '未提供删除对象id, 操作忽略'
        else:
            error = 'View未配置model, 操作忽略'

        return JsonResponse({
            'status': False if error else True,
            'error': error
        })


# class MyPermissionRequiredMixin(PermissionRequiredMixin):
#     '''
#     django的PermissionRequiredMixin不按request.method请求类型进行区分权限,
#     GET/POST/DELETE之前都是先dispatch判断权限, 所以重写使支持Restful方式的权限
#     '''

#     def get_permission_required(self):
#         method = self.request.method  # 根据method返回相应权限


class MyListView(ModelMixin, listview.VirtualRelation, listview.SqlListView):
    1


def lookup_val(obj, field_info):
    '''
    ListView 获取 object.field_name 值, 支持多层关联表路径字段 xx__xxx__xx
    field_info: field_path, verbose_name, field
    '''
    field_path, verbose_name, last_field_name, field = field_info
    if not field_path:
        # ListView.list_fields 为空或无任何有效字段, 返回obj本身
        return obj

    try:
        field_names = field_path.split('__')
        for field_name in field_names[:-1]:
            # 循环取关联表数据
            obj = getattr(obj, field_name)
            if not obj:
                return
        return obj_get_val(obj, field, last_field_name)

    except Exception:
        traceback.print_exc()


def obj_get_val(obj, field, source_field_name=None):
    '''
    从obj 获取 obj.field_name 值.
    source_field_name, 外键/o2o字段不管是field_name还是field_name_id, field对象都一样,
    所以用于list_fields区分返回obj.关联对象, 还是返回数据库值obj.field_name_id
    '''
    # return field.value_from_object(obj)
    try:
        value = ''
        # if isinstance(field, fields.mixins.FieldCacheMixin):  # django 1.x不支持
        if isinstance(field, related.RelatedField):
            # 正向关系字段

            if isinstance(field, related.ManyToManyField):
                # 多对多字段
                qs = getattr(obj, field.name).all()
                return display_qs(qs)
            else:
                # (N对一) 外键/一对一, 注意区分 field.name 与带"_id"的 field.attname
                # 如果是field.attname, 不使用关联表数据, 而是当前表关联字段值
                try:
                    value = getattr(obj, source_field_name or field.name)
                except ObjectDoesNotExist:
                    value = getattr(obj, {field.attname})  # 取数据库字段值

        elif isinstance(field, reverse_related.ForeignObjectRel):
                # 反向关系字段

            related_name = field.get_accessor_name()
            rel_obj = getattr(obj, related_name, None)
            if rel_obj is None:
                return
            if isinstance(field, reverse_related.OneToOneRel):
                    # 反向OneToOne字段
                value = rel_obj
            elif isinstance(field, (
                reverse_related.ManyToOneRel,
                reverse_related.ManyToManyRel,
            )):
                # (N对多) 反向外键/反向m2m字段, 对应多条obj数据.
                qs = rel_obj.all()
                return display_qs(qs)
        if not value:
            # 普通字段, 或外键字段/正反一对一字段
            value = getattr(obj, field.name)

        display_value = utils.display_for_field(value, field, value or '')

        return display_value

    except Exception:
        traceback.print_exc()


def display_qs(qs):
    return format_html('<br/>'.join([str(obj) for obj in qs]))


class MyDetailView(ModelMixin, DetailView):
    # template_name = "generic/_detail.html"

    def get_context_data(self, **kwargs):
        """生成各字段key/val，以便在模板中直接使用"""
        context = super().get_context_data(**kwargs)
        self.object.fields_list = []
        for field in self.object._meta.fields:
            val = obj_get_val(self.object, field)
            self.object.fields_list.append((field.verbose_name or field.attname, val))
        return context


'''
# 使用示例:

class XxxMixin:
    model = models.Xxx


class XxxList(XxxMixin, views.MyListView):
    list_fields = ['pk', 'm2o__o2o__pk', 'x2o__x2m', '反向外键/正反m2m']
    filter_fields = ['field1', 'x2o__field3']


class XxxDetail(XxxMixin, views.MyDetailView):
    1


class XxxForm(XxxMixin):
    fields = '__all__'
    # form_class = forms.XxxForm


class XxxCreate(XxxForm, CreateView):
    # template_name_suffix = '_add'
    1


class XxxUpdate(XxxForm, UpdateView):
    1


class XxxDelete(XxxMixin, views.MyDeleteView):
    1


# URL人工配置示例

from django.conf.urls import url
from xxx_app_label import views

urlpatterns = [

    url(r'^xxx/create/$', views.XxxAdd.as_view(), name='xxx_create'),
    url(r'^xxx/delete/$', views.XxxDelete.as_view(), name='xxx_delete'),

    url(r'^xxx/(?P<pk>\d+)/update/$', views.XxxUpdate.as_view(), name='xxx_update'),

    url(r'^xxx/(?P<pk>\d+)/$', views.XxxDetail.as_view(), name='xxx_detail'),
    url(r'^xxx/$', views.XxxList.as_view(), name='xxx_list'),

]

# 自动生成URL配置及视图示例, 参考 generic.routers.MyRouter

'''
