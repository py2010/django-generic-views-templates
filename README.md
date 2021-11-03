# django-generic-views-templates
django通用视图模板 (low-code)

示例
https://github.com/py2010/example/
https://gitee.com/py2010/example/


```
'''
自动生成url及视图, 使用方法:


# urls.py

from generic.routers import MyRouter
from . import models  # 用于自动views
from . import views  # 用于人工views

urlpatterns = [

    # 所有urls及视图都自动创建 (默认配置conf.ROUTER_ACTIONS={})
    *MyRouter(models.Xxx),


    # 如果需使用自定义配置的人工ListView, 除此之外其它自动生成, 则:
    *MyRouter(models.Xxx, list=False),
    url(r'^xxx/$', views.XxxList.as_view(), name='xxx_list'),


    # 如果 增删改 人工生成, 其它自动生成, 则:
    url(r'^xxx/create/$', views.XxxAdd.as_view(), name='xxx_create'),
    url(r'^xxx/delete/$', views.XxxDelete.as_view(), name='xxx_delete'),

    url(r'^xxx/(?P<pk>\d+)/update/$', views.XxxUpdate.as_view(), name='xxx_update'),

    *MyRouter(models.Xxx, 0b11),


    # 自动生成Detail, 其它人工
    *MyRouter(models.Xxx, 0, detail=True),
    ...  # 其它人工处理


]


注意!!
如果自动和人工url都存在, url重复了, 则按django原理, 前面的url优先匹配路由, 使在前面的生效,

model各页面的人工URL路径规则, 如果和当前通用视图模板URL路径规则一致时(conf.ROUTER_URL_RULES),
可以将自动MyRouter()放后面, 前面有人工自定义url则优先生效, 没有则匹配自动url


# 示例:

urlpatterns = [
    ...
]
add_router_for_all_models()

'''


'''
# 使用示例:

class XxxMixin(views.ModelMixin):
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

```

