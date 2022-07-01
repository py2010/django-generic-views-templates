# django-generic-views-templates
django通用视图模板 (low-code)

* 功能:

        我们在开发网站时, 经常碰到要实现对一些数据库表进行增删改查的功能, 模型需配置urls, 配置模板等,
        配置增删改查的Views, 大家平时开发任何新网站或增加新模块功能, 都要做很多这种复制粘贴的重复劳动.
        这时就可利用本APP进行简单配置实现各种常见功能.

        django自带的admin也可简单配置便能实现增删改查, 和后来CBV类视图是二套独立的程序,
        且admin大多十几年以前的代码, 无论前端还是后端py代码, 和我们开发的网站整合麻烦.
        除非是纯用admin功能简单, 如果某些页面要增加复杂功能, 改起来就繁琐一堆体力活. 
        也没有generic通用视图设计的合理便于维护和扩展功能, 二套东西堆积一起感觉比较乱.
        所以通常只适合在小项目中用用, 大项目则都是使用django的Views自定义开发,
        本APP可放入各django项目中, 对于增删改查等常用功能, 减少体力活.

最新代码在示例中

[https://github.com/py2010/example/tree/main/apps/generic](https://github.com/py2010/example/tree/main/apps/generic)

示例

https://github.com/py2010/example/

https://gitee.com/py2010/example/


```

'''
# views使用示例:

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


