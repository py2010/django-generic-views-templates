
import sys
import logging
from importlib import import_module
from django.conf.urls import url

from . import views
from . import conf

logger = logging.getLogger()


class MyRouter:
    """根据Model, 自动生成对应的Views和urls"""
    INDEXS = {
        5: 'create',
        4: 'delete',
        3: 'update',
        2: 'detail',
        1: 'list',
    }

    def __init__(self, model, args=0b11111, **kwargs):
        '''
        model 用户提供的模型对象, 用于自动生成对应的ModelView
        args 和 kwargs, conf.ROUTER_ACTIONS 都是用来确定生成哪些view,
        配置冲突时, 配置优先级:
        kwargs 自定义配置 > 宏观配置(conf.ROUTER_ACTIONS ) > args

        kwargs: action字典, 比如(create=True, list=False)表示生成CreateView, 不生成ListView,
            action字典会合并宏观配置 conf.ROUTER_ACTIONS, 当某项action为None时, 则由args参数确定.
            True: 生成
            False: 不生成
            None: 由args确定

        args: 只对action字典中未配置的action才生效,
            五位二进制数字, 1为开启, 0为禁用
            分别代表是否开启生成 "增/删/改/查单/查列" 对应的View和url,
            5: create
            4: delete
            3: update
            2: detail
            1: list
            默认0b11111表示所有action都自动生成,
            比如 0b00011, 表示增删改的视图和url由人工定义,
            只自动生成 DetailView ListView 视图及对应url

        '''
        self.model = model
        self.args = args
        self.kwargs = kwargs
        self.set_actions()  # 合并args配置

        self.urls = []
        self.set_urls()

    def __getitem__(self, i):
        return self.urls[i]

    def set_actions(self):
        self.actions = conf.ROUTER_ACTIONS.copy()  # 默认actions配置
        self.actions.update(self.kwargs)  # 加载urls.py提供的actions
        for index in range(1, 6):
            self.set_action(index)
        logger.debug(f'{self.actions} - ({self.model._meta.app_label}.{self.model.__name__})')

    def set_action(self, index):
        if index in self.INDEXS:
            action = self.INDEXS[index]
            if self.actions.get(action) is None:
                # actions中未配置时, 根据args来确定是否生成action对应的视图和url
                enable = self.args & (1 << (index - 1)) > 0
                self.actions[action] = enable

    def set_urls(self):
        for action, enable in self.actions.items():
            if enable:
                self.urls.append(self.get_url(action))

    def get_url(self, action):
        # 自动创建url路由
        model_name = self.model._meta.model_name
        url_path = self.get_url_path(action)
        return url(
            rf'^{model_name}/{url_path}',
            self.get_view(action).as_view(),
            name=f"{model_name}_{action}"
        )

    def get_url_path(self, action):
        # url路由对应的路径
        return conf.ROUTER_URL_RULES.get(action, f'{action}/')

    def get_view(self, action):
        # 自动创建MyModelView视图, 用于urls.py调用
        kwargs = {
            '__module__': f'{__name__}.{self.model._meta.app_label}',
            'model': self.model,
        }
        if action in ['create', 'update']:
            kwargs['fields'] = '__all__'

        view_name = f'{action.capitalize()}View'
        view = type(
            f'{self.model.__name__}{view_name}',
            (getattr(views, f'My{view_name}'), ),
            kwargs
        )
        return view


def add_router_for_all_models(models=None, urlpatterns=None, args=0b11111, **kwargs):
    # 自动为models模块中所有的模型创建urls/views.
    f_locals = sys._getframe().f_back.f_locals
    if hasattr(models, '_meta'):
        models = [models]
    else:
        models = models or f_locals.get('models') or get_models(f_locals)
    urlpatterns = urlpatterns or f_locals['urlpatterns']  # 未提供则自动从urls.loacls()中取

    logger.debug(f"{f_locals.get('__name__')} 自动路由...")
    for attr in dir(models):
        if attr.startswith('_'):
            continue
        model = getattr(models, attr)
        if hasattr(model, '_meta') and not model._meta.abstract:
            # 自动生成model的url和视图
            urlpatterns.extend(MyRouter(model, args, **kwargs))


def get_models(f_locals):
    # 未提供models时, 自动从urls模块所在基目录加载
    module = f_locals['__name__'].split('.')[:-1]
    module.append('models')
    models = import_module('.'.join(module))
    return models


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
