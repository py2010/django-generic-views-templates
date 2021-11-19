# coding=utf-8
import logging
# import traceback
from django.db import models

from django.views import generic
# from django.db.models.constants import LOOKUP_SEP

from django.db.models.fields import reverse_related
from django.db.models.fields import related
from django.urls import reverse_lazy

from . import conf

logger = logging.getLogger()


def get_field_from_meta(_meta, field_name):
    '''
    根据字段名, 获取对应的字段
    django正向外键/m2m字段未设置related_name时, 反向字段(x2m)名称会加上"_set"后缀
    '''
    try:
        return _meta.get_field(field_name)
    except Exception as e:
        if field_name.endswith('_set'):
            if field_name[:-4] in _meta.fields_map:
                field = _meta.fields_map[field_name[:-4]]
                if field.get_accessor_name() == field_name:
                    # 正向字段未设置related_name时的反查字段, 名称匹配
                    return field
                else:
                    '反查字段有设置 related_name, 无需加后缀"_set"或其它巧合的情况, 字段返回None'

        # logger.debug(f'字段获取失败: {e}')
        # # raise


class ListView(generic.ListView):
    '''
    列表页视图
    list_fields, 格式示例:
        [
            'pk',
            字段2,
            (外键字段4__字段2, 外键表字段2标识名),
            (外键字段4__外键字段3__字段3, 多层关联表字段3标识名称),  # x2o支持多层__关联
            (<多对多|反向外键>字段5, 字段5标识名), # 碰到x2m (o2m/m2m), 不再支持后续__xxx
        ]
    标识名可以省略, 将自动从Model取 field.verbose_name,
    关联表类型为x2o(正向外键/正反o2o), 关联对应一条obj数据, 支持多层__关联, 层数不限.
    关联表类型为x2m(反向外键/正反m2m), 关联对应多条obj数据, 不支持进一步__指向xx字段, 以免判断处理复杂.
    设置错误的字段将忽略.
    '''
    # template_name = 'generic/_list.html'
    list_fields = []  # 列表页显示的字段

    def get_context_data(self, *args, **kwargs):
        # 根据用户权限，对应显示增删改查的链接/按钮
        action_perm = {
            # action: 对应的action权限码
            'create': 'add',
            'delete': 'delete',
            'update': 'change',
            'detail': 'view',
            # 'list': 'view',
        }
        app_label = self.model_meta.app_label
        model_name = self.model_meta.model_name

        model_perms = {
            # action: 操作权限
            action: self.request.user.has_perm(f'{app_label}.{perm}_{model_name}')
            for action, perm in action_perm.items()
        }

        # list_view_name = self.request.resolver_match.view_name  # app_name可能和meta.app_label不同
        # view_name = list_view_name[:-5]

        # for action, perm in model_perms.items():
        #     if perm:
        #         # 有权限，获取视图url
        #         try:
        #             model_perms[action] = reverse_lazy(f'{view_name}_{action}')
        #         except Exception:
        #             '未配置action路径，忽略'

        # import ipdb; ipdb.set_trace()  # breakpoint f7da10f4 //

        context_data = super().get_context_data(model_perms=model_perms, *args, **kwargs)
        return context_data

    def get_queryset(self):
        model = self.model or self.queryset.model
        self.list_fields = self.init_fields(self.list_fields) or [
            ('', model._meta.verbose_name, '', None)
        ]  # 列表页字段为空时, 只一列显示obj列表, 提供标识名.
        return super().get_queryset()

    def init_fields(self, fields):
        # 处理 list_fields, 转field对象用以模板页显示标识名verbose_name, 去除错误配置的字段
        model = self.model or self.queryset.model
        _fields = []
        for _field in fields:
            if isinstance(_field, str):
                field_path, verbose_name = _field, None
            else:
                field_path, verbose_name = _field

            field_names = field_path.split('__')
            _field_names = []
            _meta = model._meta
            for index, field_name in enumerate(field_names):
                if field_name == 'pk':
                    field_name = _meta.pk.name

                field = get_field_from_meta(_meta, field_name)
                if not field:
                    break

                _field_names.append(field_name)
                if index + 1 < len(field_names):
                    if isinstance(field, (related.ForeignKey, reverse_related.OneToOneRel)):
                        # 其它对应一条数据的关联表字段 (外键/正反o2o), 循环取字段
                        _meta = field.related_model._meta
                    elif isinstance(field, (
                        reverse_related.ManyToOneRel,
                        reverse_related.ManyToManyRel,
                        related.ManyToManyField
                    )):  # 反向外键/正反m2m 对应多条数据, 循环应当结束, 否则认为错误的字段配置
                        logger.warning(f'反向外键/正反m2m 对应多条数据, 因SQL优化处理复杂, 不支持进行后续__{field_names[index + 1]}关联')
                        field = None
                        break

            if field:
                if not verbose_name:
                    if hasattr(field, 'verbose_name'):
                        verbose_name = field.verbose_name
                    else:
                        # 反向关系字段 ForeignObjectRel, 使用对方model标识名称
                        verbose_name = field.related_model._meta.verbose_name
                _field_path = '__'.join(_field_names)
                _fields.append((_field_path, verbose_name, field_name, field))

        return _fields


class QueryListView(ListView):
    '''
    搜索过滤, filter_fields 配置格式同 list_fields
    '''
    filter_fields = []  # 使用模糊搜索多字段功能
    filter_orm = conf.LISTVIEW_FILTER_ORM  # 是否开启ORM过滤功能

    def get_queryset(self):
        qs = super().get_queryset()
        if self.filter_orm:
            qs = self.get_queryset_orm(qs, True)
        return self.get_queryset_search(qs)

    def get_queryset_search(self, queryset=None):
        '''
        模糊查询多字段, 各字段逻辑或
        外键使用<field>__关联表<field>,
        django不支持 <field>_id 模糊查询, 使用 <field>__id 代替
        '''
        field_infos = self.init_fields(self.filter_fields)
        self.filter_fields = [f[0] for f in field_infos]
        self.filter_labels = [f[1] for f in field_infos]  # 搜索框提示名称

        if queryset is None:
            queryset = super().get_queryset()
        s = self.request.GET.get('s')
        if s and self.filter_fields:
            Q_kwargs = {f'{field}__icontains': s.strip() for field in self.filter_fields}
            # print(Q_kwargs, 77777777)
            q = models.Q(**Q_kwargs)
            q.connector = 'OR'  # 写法兼容django 1.x
            queryset = queryset.filter(q)
        return queryset

    def get_queryset_orm(self, queryset=None, ignore_error=False):
        '''
        使ListView支持GET参数ORM查询过滤，
        参数ignore_error, 当ORM字段参数错误时, 是否忽略, 不忽略则查询为空.
        本函数不考虑ORM外键过滤/攻击限制之类的需求，如有请根据model实例自定义。

        如果有其它类型的搜索过滤，则为逻辑与叠加操作过滤。

        示例：
        class xxxListView(xxx):
            xxxx
            get_queryset = get_queryset_orm
            或
            def get_queryset(self):return get_queryset_orm(self, True)

        http://xxx列表页/?orm_city__name=深圳&orm_field__icontains=xx
        相当于queryset.filter(city__name='深圳', field__icontains='xx')
        多个参数一律视为"和"，不支持“或”操作，因为URL的&只是间隔符，不含逻辑与或信息
        '''
        if queryset is None:
            queryset = super().get_queryset()
        for k, v in self.request.GET.items():
            if k.startswith('orm_'):
                # print('ORM_参数', k, v)
                try:
                    queryset = queryset.filter(**{k[4:]: v})
                except Exception:
                    if ignore_error:
                        # 忽略错误的orm表达式参数
                        continue
                    return queryset.none()

        return queryset


class PageListView(QueryListView):
    '''
    分页ListView, 支持url请求参数:
        page: 页码
        pagesize: 每页条数 (最大限制100条)
    '''

    paginate_by = conf.LISTVIEW_PAGINATE_BY  # 每页条数
    # paginate_orphans = 3  # 尾页少于数量则合并到前一页

    page_kwarg = conf.LISTVIEW_PAGE_KWARG  # url页码参数名称
    page_size_kwarg = conf.LISTVIEW_PAGE_SIZE_KWARG  # url参数PageSize名称, 类似page_kwarg
    page_size_list = conf.LISTVIEW_PAGE_SIZE_LIST  # 前端PageSize选择列表
    js_table_data = None  # 开启DataTable.js前端表格分页

    def get_context_data(self, *args, **kwargs):

        pagesize = self.request.GET.get(self.page_size_kwarg)  # 每页显示条数
        try:
            self.paginate_by = min(100, int(pagesize))  # 限制最大100条
        except Exception:
            pass

        context_data = super().get_context_data(*args, **kwargs)
        if context_data.get('is_paginated'):
            # 生成url参数，用于各分页链接，不包含page=xx参数本身
            context_data['url_args'] = [
                f'{arg}={val}' for arg, val in self.request.GET.items() if arg != self.page_kwarg
            ]
            context_data['page_range'] = self.get_page_range(context_data['page_obj'])

        elif self.js_table_data is None:
            # 前端js分页，用户未指定True/False，且后端分页/搜索都未开启时, 开启前端js分页/搜索过滤
            self.js_table_data = not self.filter_fields
        return context_data

    def get_page_range(self, page_obj):
        # 大表分页时，优化页码显示
        page_range = page_obj.paginator.page_range
        num_pages = page_obj.paginator.num_pages
        if num_pages > 10:
            # 页数太多时不全显示，只显示当前页附近页码
            PAGES = 3  # 附近页数
            page_range_1 = max(1, page_obj.number - PAGES)  # 显示的起始页码
            page_range_2 = min(num_pages + 1, page_obj.number + 1 + PAGES)  # 显示的结束页码
            page_range = range(page_range_1, page_range_2)
        # print(page_range, 333333333333)
        return page_range


class SqlListView(PageListView):
    '''
    SQL优化
    '''
    optimize_sql = conf.LISTVIEW_OPTIMIZE_SQL  # SQL优化, 根据list_fields配置字段进行处理, 优化SQL性能

    def get_queryset(self):
        qs = super().get_queryset()
        if self.optimize_sql:
            qs = self.optimize_queryset(qs)
        return qs

    def optimize_queryset(self, queryset=None):
        '''
        SQL查询优化, select_related() + prefetch_related() + only()
        django默认SQL是查询所有字段, 且对于外键等关联表, 对每条数据去where查询,
        为提高效率, 一次性查询所需数据供模板页后续使用, 如果是自定义模板页, 需手工优化.

        对于关联字段, 如果未含__指定关联表字段, 数据是用的关联表obj.__str__(), 此时关联表无法限定字段.
        如果要求只查询所需用到的字段, 则关联字段必需带__指定关联表字段, 比如外键字段xxx__外键表xxx字段
        '''
        # logger.debug('ListView开启SQL查询自动优化...')
        if self.template_name and self.template_name != 'generic/_list.html':
            logger.debug(
                f'\r\n自定义模板{self.template_name} 不是通用模板generic/_list.html,'
                f'\r\n若模板中有自定义字段不在list_fields中, 会额外每条where查询sql,'
                f'\r\n可自行配置queryset.only(*)增加自定义字段来防止模板页where查询.'
            )
        # queryset = queryset or super().get_queryset()  # or需库查询qs才能判断真假, 且qs.none()为假
        if queryset is None:
            queryset = super().get_queryset()
        onlys = []  # 限定查询字段
        sr_fields = []  # x2o关联, select_related. 多表左联/内联
        pr_fields = []  # x2m关联, prefetch_related. 关联表独立进行一次性查出
        # logger.debug(self.list_fields)
        for field_info in self.list_fields:
            field_path, verbose_name, last_field_name, field = field_info
            if field_path:
                if isinstance(field, (
                    reverse_related.ManyToOneRel,
                    reverse_related.ManyToManyRel,
                    related.ManyToManyField
                )):  # 反向外键/正反m2m 对应多条数据, prefetch_related优化, 并排除加入限定字段only()
                    pr_fields.append(field_path)
                else:
                    onlys.append(field_path)
                    if isinstance(field, related.ForeignKey) and last_field_name != field.attname:
                        # 外键/o2o字段, 未进一步配置__外表字段, 显示obj.__str__(),
                        # 这种情形无法限定关联表查询字段, SQL将查询关联表所有字段或每条where查询.
                        logger.warning(
                            f'\r\n关联字段"{field_path}"未指明链到关联表Model哪个字段,'
                            f'\r\n如果是取本表字段数据库值({field.attname}), 应当加上_id: "{field_path}_id"'
                            f'\r\n否则取关联obj.__str__(), 无法确定str()使用哪些字段, 关联表SQL查询不进行优化.'
                            f'\r\n只有list_fields配置字段改为: {field_path}__xx外表字段, 才可确定所需查询字段.'
                        )
                        sr_fields.append(field_path)
                    elif '__' in field_path:
                        # 关联字段, 去掉最后一级的外部表字段, 得到"当前表"model中的关联字段
                        field_names = field_path.split('__')
                        lookup_field = '__'.join(field_names[:-1])  # 去掉末尾的__外部关联表字段
                        sr_fields.append(lookup_field)

        sr_fields = [*set(sr_fields)]  # 去重
        pr_fields = [*set(pr_fields)]  # 去重
        logger.debug(f'\r\nx2o关联: {sr_fields} \r\nx2m关联: {pr_fields} \r\n限定查询字段: \r\n{onlys}')
        if sr_fields:
            queryset = queryset.select_related(*sr_fields)
        if pr_fields:
            queryset = queryset.prefetch_related(*pr_fields)
        self.add_only_fields(queryset, onlys)
        return queryset

    def add_only_fields(self, queryset, field_names=[]):
        '''
        进行限定字段, 执行queryset.only(*field_names),
        如果多次执行only(), 按django设计的方案只有最后一次的only()有效,
        所以这里改成only追加字段的方式, 相当于在前一次only()限定字段基础上, 追加新字段.
        使用户ListView若有自定义的only(), 不会被删.
        '''
        if field_names:
            existing, defer = queryset.query.deferred_loading
            field_names = set(field_names)
            if 'pk' in field_names:
                field_names.remove('pk')
                field_names.add(self.model._meta.pk.name)

            if defer:
                # 用户queryset没进行only()自定义限定字段, defer()差集
                # return queryset.only(*field_names)
                field_names = field_names.difference(existing)
            else:
                # 在前一次限定字段基础上, 追加新限定字段, only()并集
                logger.debug(f'保留用户queryset已有的only限定字段: {existing}')
                field_names = existing.union(field_names)
            queryset.query.deferred_loading = field_names, False


class VirtualRelation:
    '''
    表model obj虚拟关联
    示例场景: 表关系业务上为"外键"关系, 但数据库结构上不是外键, 只是普通字段, 也无约束.
    比如跨数据库的两表, SQL无法左联, 为提高SQL查询效率, 使用CPU进行虚拟"左联".
    类似实现django关联表 select_related / prefetch_related 的功能.

    原理:
        两表关联时, SQL只查出二个表数据, 然后面象对象开发进行"连接", 后续处理只消耗CPU, 不再有二表数据库IO操作.

    注意:
        列表页展示虚拟关联表数据, 暂不支持list_fields自动处理虚拟字段, 需自定义模板页扩展新列.
        如果提供的qs有.only()限定字段, 模板也需只使用这些字段, 否则超出字段会产生大量where查询SQL.
        如果模板中使用的最终字段数据, 是多层虚拟"外键"关系, 需进行多次两两虚拟关联, 类似三表m2m需关联二次.
    '''

    def virtual_join(self, qs1, qs2, attr=None, rel_field=None, to_field='pk', reverse=False):
        '''
        表数据在业务上是o2o/m2o或m2o关系, 而DB表/Model字段为普通字段, 对两表进行虚拟左联.
        两个Model如果有实际的关联关系, 也可当虚拟关联来处理, attr和外键字段同名时, 注意obj1.save()
        o2o o2m m2o 虚拟关联处理一次即可, m2m的关系, 对应三个表, 虚拟关联需处理二次.

        rel_field: 在业务上有关联关系的字段名, 为空表示主键, 这种情形为o2o扩展表,
                   两表都是通过主键数据进行关联, 表结构上无正反方向.
        to_field: 相当于 model.ForeignKey 配置的 "to_field"  (obj1.rel_field_id 数据值等于 obj2.to_field)
        attr: 虚拟关系联接名, 尽量不能与obj1本身的方法/属性重名.
        reverse: 业务关联正反方向
            False 业务关联字段rel_field在obj1表
            True  业务关联字段rel_field在obj2表

        返回obj1列表, 不允许后续再进行叠加过滤等qs操作, 以免obj2关联关系丢失
        '''

        obj_list1 = [obj1 for obj1 in qs1]  # qs._fetch_all()

        o2m = True if rel_field and reverse else False  # 一对多
        field1 = field2 = to_field
        if o2m:
            field2 = rel_field
        else:
            field1 = rel_field or to_field

        qs2 = self.optimize_qs2(obj_list1, qs2, field1, field2)
        obj_list2 = [obj2 for obj2 in qs2]  # qs._fetch_all()

        if obj_list1 and obj_list2:

            if o2m:
                '''
                反向关联, 业务关系当成o2m关联来处理, 也就是一obj1对多obj2
                如果实际业务是每个obj1对应一个obj2, 也就是反向o2o,
                业务上类似反向外键, 只是对应的反向数据只有一条, 兼容
                不管对应一条还是多条数据, 模板中都需for迭代取.
                '''
                # field1 = to_field
                # field2 = rel_field
                dict2 = {}
                for obj2 in obj_list2:
                    key2 = getattr(obj2, field2)
                    if key2 in dict2:
                        dict2[key2].append(obj2)
                    else:
                        dict2[key2] = [obj2]
            else:
                # field1 = rel_field or to_field
                # field2 = to_field

                # obj1与obj2 为x2o关联
                dict2 = {getattr(obj2, field2): obj2 for obj2 in obj_list2}

            # 检查attr是否为model1的 x2o 或 o2x 字段
            attr, IsForeignKeyField = self.check_attr(attr, obj_list1[0]._meta, obj_list2[0]._meta)

            for obj1 in obj_list1:
                key2 = getattr(obj1, field1)
                obj2 = dict2.get(key2)
                # if obj2:
                if 1:  # 为空也应setattr, 防止AttributeError (虽然模板不会raise)
                    self.set_attr(obj1, attr, obj2, IsForeignKeyField)

        return obj_list1

    def optimize_qs2(self, qs1, qs2, field1, field2):
        '''
        优化查询， qs2过滤数据， 减少查询量
        比如提供关联表qs2为所有数据 model2.objects.all()，而本表qs1不是全部数据(分页/查询等)，
        qs2实际只有一小部分数据和qs1本表产生关联，则qs2没必要查出所有。
        '''

        if isinstance(qs2, models.query.QuerySet) and getattr(self, 'optimize_sql', None):
            ids = [getattr(o, field1) for o in qs1]
            qs2 = qs2.filter(**{f'{field2}__in': ids})
        return qs2

    def virtual_m2m(self,
                    qs_1, qs_m, qs_2,
                    m_rel_field_1, m_rel_field_2,
                    attr_m=None, attr_2=None,
                    to_field_1='pk', to_field_2='pk',
                    ):
        '''
        表数据在业务上是m2m关系, 比如表跨库, DB关联字段不是外键, Model 无m2m关系. 进行虚拟m2m关联.
        (实际上Model字段为m2m时也可使用, 注意attr重名及是否影响obj.save())

        qs_1, 当前表model_1 - QuerySet
        qs_m, 中间表model_m - QuerySet
        qs_2, 关联表model_2 - QuerySet

        m_rel_field_1: model1在中间表model_m的业务关联字段
        m_rel_field_2: model2在中间表model_m的业务关联字段

        to_field_1: 中间表的业务关联字段m_rel_field_1的数据库存储值, 是model_1哪个字段, 一般为pk
        to_field_2: 中间表的业务关联字段m_rel_field_2的数据库存储值, 是model_2哪个字段, 一般为pk

        attr_m/attr_2: 虚拟关系联接名, 注意不能与obj本身的方法/属性重名.
                        obj_1.attr_m = obj_m 列表
                        obj_m.attr_2 = obj_2

        '''
        qs_m = self.optimize_qs2(qs_1, qs_m, field1=to_field_1, field2=m_rel_field_1 or 'pk')  # 过滤数据减少查询量

        m_objs = self.virtual_join(qs_m, qs_2, attr=attr_2, rel_field=m_rel_field_2, to_field=to_field_2)
        return self.virtual_join(qs_1, m_objs, attr=attr_m, rel_field=m_rel_field_1, to_field=to_field_1, reverse=True)

    def set_attr(self, obj1, attr, obj2, IsForeignKeyField=False):
        '''
        当提供的attr与obj1的外键或o2o字段名同名时, 设置obj1.attr值可能影响obj1.save()
        导致外键值可能变化, 所以不可直接setattr, 而应放到 obj1._state.fields_cache
        '''
        if IsForeignKeyField:
            logger.debug(f'obj1已含有名称为"{attr}"的关联字段, 不直接settattr')
            if hasattr(obj1._state, 'fields_cache'):
                obj1._state.fields_cache[attr] = obj2  # django 2.*
            else:
                setattr(obj1, f'_{attr}_cache', obj2)  # django 1.*
        else:
            setattr(obj1, attr, obj2)

    def check_attr(self, attr, meta1, meta2):
        '''
        检查attr是否与obj1的外键或o2o字段名同名, 以免设置obj1.attr值在obj1.save()时可能会更新值.
        比如两个model有真实外键关系, 进行虚拟关联且attr与关联字段同名.
        '''
        if not attr:
            attr = meta2.model_name

        IsForeignKeyField = False
        field = get_field_from_meta(meta1, attr)
        if field:
            logger.warning(f'虚拟字段名"{attr}"与{meta1.model}字段{field}同名!')

            if isinstance(field, related.ForeignKey):
                # 正向 m2o o2o
                IsForeignKeyField = True
            elif isinstance(field, reverse_related.OneToOneRel):
                # 反向 o2o
                if field.get_accessor_name() == attr:
                    IsForeignKeyField = True

            '''
            反查多条数据的(x2m)字段
            如果正向字段未设置related_name, 反查名会增加"_set", 不会同名.
            如果有设置related_name, attr与反查字段同名会覆盖功能, 但save不影响数据
            '''

        return attr, IsForeignKeyField


# class VirtualRelationListView(VirtualRelation, SqlListView):
#     '''
#     比如跨库虚拟关联, self.model 与 rel_model 通过数据库字段rel_field建立虚拟关联

#     virtual_relations = {
#         # 虚拟关联
#         'attr': {
#             'rel_model': 'model2',
#             'rel_field': 'db_field_name',
#             'rel_type': 'ForeignKey',  # ForeignKey, OneToOneField, ManyToManyField
#             'to_field': 'pk',
#             'reverse': False,  # True:反向关联, False:正向关联
#         }
#     }

#     使虚拟关联无需自定义模板扩展新列, 方便按需展示各字段前后顺序.
#     list_fields 中使用attr虚拟字段,  f'{attr}__关联表(model2)xx字段'
#     '''

#     virtual_relations = {}

#     def init_fields(self, fields):
#         # self.model._meta 加入虚拟字段attr, 仅用于列表页自动模板展示虚拟关联表数据.
#         meta = self.model._meta
#         for attr, info in virtual_relations.items():
#             1

#         return super().init_fields(fields)


'''
# 使用示例:

class XxxList(views.ModelMixin, views.MyListView):
    model = models.Xxx
    list_fields = ['pk', 'm2o__o2o__pk', 'x2o__x2m']
    filter_fields = ['field1', 'x2o__field3']
    optimize_sql = True


# 模板 (虚拟关联)

{% extends "generic/_list.html" %}
    {% block add_table_th %}
                                    <th>两表 x2o 虚拟关联xx字段名称</th> <!-- 正向, 对应一条 -->
                                    <th>两表 o2x 虚拟关联xx字段名称</th> <!-- 反向, 对应多条 -->
                                    <th>三表 m2m 虚拟关联xx字段名称</th> <!-- 正反 多对多 -->
    {% endblock %}

    {% block add_table_td %}
                                    <td>{{ object.attr.xx_field }}</td>
                                    <td>
                                        {% for o in object.attr %}{{ o.xx_field }}</br>{% endfor %}
                                    </td>
                                    <td>
                                        {% for o in object.attr_m %}{{ o.attr_2.xx_field }}</br>{% endfor %}
                                    </td>
    {% endblock %}

'''
