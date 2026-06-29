import re
from flask_restx import Resource, reqparse, fields
from bson.objectid import ObjectId
from datetime import datetime
from urllib.parse import quote
from flask import make_response
import time

from app.utils import conn_db as conn

# 定义通用的api契约
base_query_fields = {
    'page': fields.Integer(description="当前页数", example=1),
    'size': fields.Integer(description="页面大小", example=10),
    'order': fields.String(description="排序字段", example='_id'),
}

# 只能用等号进行mongo查询的字段
EQUAL_FIELDS = ["task_id", "task_tag", "ip_type", "scope_id", "type"]


class ARLResource(Resource):
    def get_parser(self, model, location='json'):
        """
        根据传入的模型（model）自动生成一个请求参数解析器（pareser）。

        :param model: 字段的要求清单（字典格式），比如包含了具体要求：name是必填的，age是整数等。
        :param location: 告诉解析器去哪里找和数据。默认是‘json’（从HTTP请求的JSON请求体中找），有时候也会传‘args’（从URL的问号后面的参数中找，如？page=1）
        :return: 配置好的解析器对象
        """

        # 1. 实例化一个解析器对象
        # bundle_errors=True 的意思是：如果前端传错了好几个参数，不要报错一次就停下，
        # 而是把所有的错误打包在一起，一次性返回给前端，告诉他们“这几个地方全错了”。
        parser = reqparse.RequestParser(bundle_errors=True)

        # 2.遍历清单(model)中的每一个字段
        for name in model:
            # 拿到当前字段的具体要求配置
            curr_field = model[name]

            # 3. 把这个字段的要求,添加到解析器的规则本里
            parser.add_argument(name,                               # 字段的名称(比如‘username’)
                                required=curr_field.required,       # 是否必填?( True 或 False)
                                type=curr_field.format,             # 数据的类型?(比如 字符串、整数)
                                help=curr_field.description,        # 如果前端填错了,返回什么提示信息?(比如“用户名不能为空”)
                                location=location)                  # 去哪里找到这个字段的数据?  (json 或 args)
        # 4. 把配置好所有规则的解析器返回,交给后面的业务逻辑去真正执行校验.
        return parser

    def parse_args(self, model, location='json'):
        """
        根据传入的模型(model),自动提取并校验前端传来的参数.

        :param model: 字段的要求清单(比如哪些必填,是什么类型)
        :param location: 去哪里找参数,默认在 HTTP请求的JSON里找
        :return: 校验成功后,返回一个干净、合规的参数字典(args)
        """

        # 1.制造校验员:调用我们刚才讲过的get_parser方法, 根据清单(model)为你量身定制一个“参数解析器”.
        parser = self.get_parser(model, location)

        # 2. 正式开始查验:让解析器去检查前端发来的真实数据.
        #   - 如果符合 model 的要求,它会把数据打包好赋值给args.
        #   - 如果数据不合规(比如漏了必填项),它在这里会直接拦截,自动给前端返回报错信息,代码不会再往下执行.
        args = parser.parse_args()

        # 3. 交接工作:把查验合格的参数返回,交给后续真正的业务代码去使用.
        return args

    def build_db_query(self, args):
        """
        动态构造数据库查询语句:将前端传来的参数转化为 MongoDB 认识的格式.

        :param args: 前端传来的参数字典,比如{'name':'test','age__gt':'18'}
        :return: 转化后的 MongoDB 查询字典,比如{'name':{'#regex':'test'},'age':{'$gt':18}}
        """
        query_args = {} # 准备一个空字典,用来装翻译后的结果

        for key in args: # 遍历前端传来的每一个参数名
            # 1.忽略基础分页字段(page,size,order 不需要放进数据库查询条件里)
            if key in base_query_fields:
                continue

            # 2. 特殊处理 MongoDB 的主键 _id:必须把字符串转换成专属的 ObjectID 类型
            if key == '_id':
                if args[key]:
                    query_args[key] = ObjectId(args[key])

                continue

            # 3. 忽略空值（前端传了字段但没给值的，不管它）
            if args[key] is None:
                continue

            # 4. 核心魔法：识别后缀并翻译成 MongoDB 指令
            # __dgt 代表 datetime greater than (时间大于)
            if key.endswith("__dgt"):
                real_key = key.split('__dgt')[0]
                raw_value = query_args.get(real_key, {})
                raw_value.update({
                    "$gt": datetime.strptime(args[key],
                                             "%Y-%m-%d %H:%M:%S")
                })
                query_args[real_key] = raw_value

            # __dlt 代表 datetime less than (时间小于)
            elif key.endswith("__dlt"):
                real_key = key.split('__dlt')[0]
                raw_value = query_args.get(real_key, {})
                raw_value.update({
                    "$lt": datetime.strptime(args[key],
                                             "%Y-%m-%d %H:%M:%S")
                })
                query_args[real_key] = raw_value

            # __neq 代表 not equal (不等于)
            elif key.endswith("__neq"):
                real_key = key.split('__neq')[0]
                raw_value = {
                    "$ne": args[key]
                }
                query_args[real_key] = raw_value

            # __not 代表正则不匹配
            elif key.endswith("__not"):
                real_key = key.split('__not')[0]
                raw_value = {
                    "$not": re.compile(re.escape(args[key]))
                }
                query_args[real_key] = raw_value

            # __gt 代表数字大于 (greater than)
            elif key.endswith("__gt") and isinstance(args[key], int):
                real_key = key.split('__gt')[0]
                raw_value = {
                    "$gt": args[key]
                }
                query_args[real_key] = raw_value

            # __lt 代表数字小于 (less than)
            elif key.endswith("__lt") and isinstance(args[key], int):
                real_key = key.split('__lt')[0]
                raw_value = {
                    "$lt": args[key]
                }
                query_args[real_key] = raw_value

            # 5. 普通字符串处理（如果没有上面那些花里胡哨的后缀）
            elif isinstance(args[key], str):
                # 如果是设定好的必须绝对相等的字段（比如 task_id），直接赋值
                if key in EQUAL_FIELDS:
                    query_args[key] = args[key]
                else:
                    # 否则，一律默认变成“模糊搜索”（使用正则表达式 $regex，且忽略大小写 $options: "i"）
                    query_args[key] = {
                        "$regex": re.escape(args[key]),
                        '$options': "i"
                    }

            # 6. 其他类型（比如布尔值 True/False，或者普通的整数等），直接照搬
            else:
                query_args[key] = args[key]

        # 返回翻译好的指令书，交给 MongoDB 数据库去执行
        return query_args

    def build_return_items(self, data):
        """
        格式化即将返回给前端的数据列表.
        主要是把 MongoDB 专属的特殊数据类型转化为普通的字符串.

        :param data: 从数据库中查询出来的原始数据列表, 比如[{'_id': ObjectId('...'), 'name': 'test'}]
        :return: 处理好、可以直接转化为 JSON 发给前端的列表
        """
        items = [] # 准备一个空列表，用来装“包装合格”的数据

        # 定义一张“特殊重点关照名单”
        # _id 是 MongoDB 专属的 ObjectId 类型
        # save_date, update_date 可能是 Python 的 datetime 时间对象
        special_keys = ["_id", "save_date", "update_date"]

        # 第一层循环：遍历查出来的每一条数据（每一行记录）
        for item in data:
            # 第二层循环：遍历这一条数据里的每一个字段名（比如 name, _id, status）
            for key in item:
                # 核心操作：把它的值强制转换成普通字符串 (string)
                if key in special_keys:
                    item[key] = str(item[key])

            # 把这行处理干净的数据，放进我们准备好的合格列表里
            items.append(item)

        # 把所有合格的数据一次性发走
        return items

    def build_data(self, args=None, collection=None):

        """
        通用数据查询核心方法:负责翻译条件、去数据库拿数据、分页、包装并返回.

        :param args: 前端传来的请求参数字典
        :param collection:  要查询的 MongoDB 集合（表）名，比如 'task' 或 'site'
        :return: 包含分页信息、总数、数据列表的标准 JSON 字典格式
        """
        # 1. 提取基础控制参数（会自动把 page, size, order 从 args 里拿出来并删掉）
        default_field = self.get_default_field(args)
        page = default_field.get("page", 1)         # 当前第几页（默认第1页）
        size = default_field.get("size", 10)        # 每页多少条数据（默认10条）
        orderby_list = default_field.get('order', [("_id", -1)])    # 按什么排序（默认按 _id 倒序，即最新的排前面）

        # 2. 让“翻译官”把剩下的 args 翻译成 MongoDB 查询语句
        query = self.build_db_query(args)

        # 3. 核心数据库操作（连招）：
        #   find(query): 按照条件查找
        #   sort(): 排序
        #   skip(): 跳过前面不要的数据（比如第2页每页10条，就跳过前10条）
        #   limit(): 限制只拿多少条（每页的数据量）
        result = conn(collection).find(query).sort(orderby_list).skip(size * (page - 1)).limit(size)

        # 4. 计算一共有多少条符合条件的数据（前端要做分页条，必须知道总数）
        count = conn(collection).count(query)

        # 5. 让“打包流水线”把查出来的数据里的特殊字符（活鱼）包装成普通文本
        items = self.build_return_items(result)

        # 6. 【扫尾工作】：把查询条件 query 里的特殊对象也变成普通字符串
        # 为什么要搞这一步？因为 ARL 习惯把查询条件原封不动地返回给前端，方便调试或展示
        special_keys = ["_id", "save_date", "update_date"]
        for key in query:
            if key in special_keys:
                query[key] = str(query[key])

            raw_value = query[key]
            if isinstance(raw_value, dict):
                if "$not" in raw_value:
                    # 把编译好的正则表达式对象，还原成普通字符串
                    if isinstance(raw_value["$not"], type(re.compile(""))):
                        raw_value["$not"] = raw_value["$not"].pattern

        # 7. 组装“最终包裹”，按照统一标准发给前端
        data = {
            "page": page,   # 当前页码
            "size": size,   # 每页大小
            "total": count, # 数据总数
            "items": items, # 真正的核心数据列表
            "query": query, # 刚刚执行的查询条件（原样返回）
            "code": 200     # HTTP 状态码，200代表成功
        }
        return data

    '''
    取默认字段的值，并且删除
    '''

    def get_default_field(self, args):
        """
        提取并清洗分页和排序参数.
        注意:提取后会把这些字段从原始 args 中删除(pop),防止它们被误当成数据库查询条件.

        :param args: 前端传来的原始参数字典，比如 {'name': 'test', 'page': 2, 'size': -5}
        :return: 清洗后的控制参数字典
        """

        # 1. 制定“保底规则”（如果前端啥也没传，就按这个来）
        default_field_map = {
            "page": 1,
            "size": 10,
            "order": "-_id"
        }

        # 复制一份保底规则，准备往里面填入真实数据
        ret = default_field_map.copy()

        # 2. 挨个检查前端有没有传这三个控制参数
        for x in default_field_map:
            if x in args and args[x]:
                # 【核心操作】：pop 会把这个参数从 args 里“拿走”并赋值给 ret
                # 这样 args 里剩下的就全是纯粹的搜索条件了（比如 name='test'）
                ret[x] = args.pop(x)

                # 3. 安全校验：防止前端瞎传数据把数据库撑爆
                if x == "size":
                    if ret[x] <= 0:
                        ret[x] = 10        # 每页条数不能是负数或0，强制变回10
                    if ret[x] >= 100000:
                        ret[x] = 100000     # 每页最多只能查 10万 条，防止内存溢出

                if x == "page":
                    if ret[x] <= 0:
                        ret[x] = 1  # 页码不能是负数或0，强制变回第1页

        # 4. 翻译排序规则
        orderby_list = []
        # 获取排序字符串，如果没有就用默认的 "-_id"
        orderby_field = ret.get("order", "-_id")

        # 支持多个字段组合排序，比如 "-age,+name,status" (年龄倒序，名字正序，状态正序)
        for field in orderby_field.split(","):
            field = field.strip()

            # 以减号 - 开头，代表降序 (MongoDB 里的 -1)
            if field.startswith("-"):
                orderby_list.append((field.split("-")[1], -1))

            # 以加号 + 开头，代表升序 (MongoDB 里的 1)
            elif field.startswith("+"):
                orderby_list.append((field.split("+")[1], 1))

            # 什么都不带，默认就是升序 (MongoDB 里的 1)
            else:
                orderby_list.append((field, 1))

        # 把翻译好的排序列表放回字典
        ret['order'] = orderby_list
        return ret

    def send_export_file(self, args, _type):
        """
        通用数据导出核心逻辑:根据不同的数据类型,提取出关键字段,并打包成文件发给前端.

        :param args: 前端传来的过滤条件(比如只要存活的站点)
        :param _type: 导出的表名/类型，比如 "site"（站点）, "domain"（域名）, "ip"（IP地址）
        :return: 调用发送文件的方法，返回给前端一个文件流
        """

        # 1. 定义一张“提取说明书”（字典映射）
        # 告诉程序：如果要导出 site 表，就提取里面叫做 "site" 的字段；
        # 如果要导出 wih（Web信息收集），就提取 "content" 字段。
        _type_map_field_name = {
            "site": "site",
            "domain": "domain",
            "ip": "ip",
            "asset_site": "site",
            "asset_domain": "domain",
            "asset_ip": "ip",
            "asset_wih": "content",
            "url": "url",
            "cip": "cidr_ip",
            "wih": "content",
        }

        # 2. 复用之前讲过的总调度室 build_data，去数据库里把符合条件的数据全捞出来
        data = self.build_data(args=args, collection=_type)["items"]

        # 3. 准备一个“去重篮子” (Set 集合)
        # 为什么用 set 而不是 list？因为导出的文件里，我们不希望有重复的行（比如两个相同的域名）
        items_set = set()

        # 4. 遍历捞出来的每一条数据
        for item in data:
            # 去说明书里查一下，当前这种数据类型，我该提取哪个字段名？（注意这里原作者拼写错误写成了 filed_name）
            filed_name = _type_map_field_name.get(_type, "")

            # 如果找到了需要提取的字段名，并且这条数据里刚好有这个字段
            if filed_name and filed_name in item:

                # 5. 【特殊处理】如果当前导出的是 ip 类型的数据
                if filed_name == "ip":
                    curr_ip = item[filed_name]  # 先拿到基础 IP (比如 192.168.1.1)

                    # 因为一个 IP 可能开了多个端口，所以要遍历它的 port_info 列表
                    for port_info in item.get("port_info", []):
                        # 把 IP 和 端口 拼起来，格式化成 "IP:Port" (比如 192.168.1.1:80)，扔进篮子
                        items_set.add("{}:{}".format(curr_ip, port_info["port_id"]))

                # 6. 【常规处理】如果是其他类型（比如域名、URL）
                else:
                    # 直接把对应的值扔进篮子即可
                    items_set.add(item[filed_name])

        # 7. 把装满去重数据的篮子，交给专门负责发货的兄弟 (send_file) 去生成真实的文件并下载
        return self.send_file(items_set, _type)

    # 表示从 给定集合中 导出相应的字段来
    def send_export_file_attr(self, args, collection, field):
        """
        万能数据导出逻辑:从任意表里提取任意字段,去重后打包成文件.

        :param args: 前端传来的搜索和过滤条件
        :param collection: 要查询的集合（表）名，比如 "user", "task"
        :param field: 你想导出的具体字段名，比如 "email", "domain"
        :return:返回一个可下载的文件流
        """
        # 1. 调兵遣将：使用我们熟悉的 build_data 去数据库里把符合条件的数据全拿出来
        # 注意这里直接加上 ["items"]，意思是只拿具体的数据列表，不要总数、页码等外层包装了
        data = self.build_data(args=args, collection=collection)["items"]

        # 2. 准备一个空的“去重草稿本”（集合 Set），保证导出的数据没有重复项
        items_set = set()

        # 3. 遍历数据库里捞出来的每一条数据（每一行）
        for item in data:
            # 如果当前这条数据里，确实包含我们要找的那个字段
            if field in item:
                # 把这个字段的值取出来
                value = item[field]

                # 4. 【核心判断】看看取出来的值是个什么东西？
                # isinstance() 用于判断数据类型。这里判断它是不是一个列表 (list)
                if isinstance(value, list):
                    # 如果它是个列表（比如这行记录里存了多个邮箱 ["a@qq.com", "b@qq.com"]）
                    # 那么把这几个邮箱一起倒进我们的草稿本里
                    # |= 是集合特有的“并集”符号，意思是把两个集合合并，遇到重复的自动过滤
                    items_set |= set(value)
                else:
                    # 如果它只是个普通的值（比如就是一个单独的邮箱 "a@qq.com"）
                    # 直接把它写进草稿本里
                    items_set.add(value)

        # 5. 草稿写完后，交给送货员 (send_file) 去打包生成 txt 文件。
        # 文件名的前缀会根据表名和字段名自动生成，比如 f"user_email"
        return self.send_file(items_set, f"{collection}_{field}")

    def send_batch_export_file(self, task_id_list, _type):
        """
        批量导出核心逻辑:根据传入的多个任务ID,把它们的数据合并去重后,打包成文件发给前端.

        :param task_id_list:前端传来的任务 ID 列表，比如 ["id_1", "id_2", "id_3"]
        :param _type:导出的表名/类型，比如 "domain"（域名）
        :return: 调用发送文件的方法，返回给前端一个文件流
        """
        # 1. 依然是那份熟悉的“提取说明书”（字典映射）
        _type_map_field_name = {
            "site": "site",
            "domain": "domain",
            "ip": "ip",
            "url": "url",
            "cip": "cidr_ip",
            "wih": "content",
        }
        # 2. 准备好我们的“去重魔法本” (Set)
        items_set = set()

        # 3. 去说明书里查一下当前要提取哪个字段
        # （原作者在这里拼写错了，把 field 拼成了 filed，不过不影响代码运行，咱们心里清楚就行）
        filed_name = _type_map_field_name.get(_type, "")

        # 4. 遍历前端传过来的每一个任务 ID
        for task_id in task_id_list:
            # 【安全防御】：如果这类型的数据不在说明书里，或者遇到个空的 task_id，直接跳过，看下一个
            if not filed_name:
                continue
            if not task_id:
                continue

            # 5. 组装查询条件：我要查归属于当前这个 task_id 的数据
            query = {"task_id": task_id}

            # 6. 【核心高阶操作】：直接让 MongoDB 数据库帮我们去重提取！
            # conn(_type) 是连接到对应的表
            # .distinct(字段名, 查询条件) 的意思是：去数据库里把符合条件的指定字段全拿出来，并且数据库层面直接去重！
            items = conn(_type).distinct(filed_name, query)

            # 7. 把从数据库拿回来的结果（已经是一个列表了），倒进我们的总草稿本里，合并去重
            items_set |= set(items)

        # 8. 循环结束，所有的任务数据都合并完了，交给发货员去打包下载
        return self.send_file(items_set, _type)

    def send_scope_batch_export_file(self, scope_id_list, _type):
        """
        资产组批量导出逻辑:根据传入的多个资产组(scope)ID,提取合并指定类型的数据,并打包下载.

        :param scope_id_list: 前端传来的资产组 ID 列表，比如 ["scope_1", "scope_2"]
        :param _type: 导出的资产表名，比如 "asset_domain"（已确认的资产域名表）
        :return: 调用发送文件的方法，返回下载文件流
        """

        # 1. 专门针对“资产库(asset)”的提取说明书
        # 和之前的任务导出不同，这里查的都是 asset_ 开头的表
        _type_map_field_name = {
            "asset_site": "site",       # 如果导资产站点，提取 site 字段
            "asset_domain": "domain",   # 如果导资产域名，提取 domain 字段
            "asset_ip": "ip",           # 如果导资产 IP，提取 ip 字段
            "asset_wih": "content"      # 如果导 Web 信息，提取 content 字段
        }

        # 2. 准备全局去重草稿本 (Set)
        items_set = set()

        # 3. 查说明书，拿到要提取的字段名（作者依然保留了 filed_name 的拼写错误）
        filed_name = _type_map_field_name.get(_type, "")

        # 4. 遍历前端选中的每一个资产组 ID
        for scope_id in scope_id_list:
            # 安全拦截：如果没有查到要提取的字段，或者资产组 ID 为空，直接跳过
            if not filed_name:
                continue
            if not scope_id:
                continue

            # 5. 组装查询条件：这次是查归属于当前 scope_id 的数据
            query = {"scope_id": scope_id}

            # 6. 高阶查库：让 MongoDB 数据库直接吐出当前资产组下，去重后的干干净净的数据列表
            items = conn(_type).distinct(filed_name, query)

            # 7. 将当前资产组的数据合并进总草稿本，利用 Set(集合) 自动去除跨资产组的重复数据
            items_set |= set(items)

        # 8. 全部合并完毕，调用发货程序打包成 txt 下载
        return self.send_file(items_set, _type)

    def send_file(self, items_set, _type):
        response = make_response("\r\n".join(items_set))
        filename = "{}_{}_{}.txt".format(_type, len(items_set), int(time.time()))
        response.headers['Content-Type'] = 'application/octet-stream'
        response.headers["Access-Control-Expose-Headers"] = "Content-Disposition"
        response.headers["Content-Disposition"] = "attachment; filename={}".format(quote(filename))
        return response


def get_arl_parser(model, location='args'):
    """
    这是一个全局的快捷函数.
    其他文件想要校验参数时,不需要每次都繁琐地实例化 ARLResource类,
    直接调用这个函数,它会在内部帮你实例化并返回一个解析器.

    :param model: 字段要求清单
    :param location:  去哪里找参数,这里默认改成了'args'(URL问号后面的参数)
    :return: 返回一个解析器
    """

    r = ARLResource()                   # 实例化刚才我们讲了半天的大基类
    return r.get_parser(model, location) # 调用它的 get_parser 方法并返回

# ==========================================
# 下面是一大排“模块导入与重命名 (Alias)”
# ==========================================
# 从当前目录(.)的 task.py 文件中，导入名为 ns 的变量，并把它重命名为 task_ns
from .task import ns as task_ns
from .domain import ns as domain_ns
from .site import ns as site_ns
from .ip import ns as ip_ns
from .url import ns as url_ns
from .user import ns as user_ns
from .image import ns as image_ns
from .cert import ns as cert_ns
from .service import ns as service_ns
from .fileleak import ns as fileleak_ns
from .export import ns as export_ns
from .assetScope import ns as asset_scope_ns
from .assetDomain import ns as asset_domain_ns
from .assetIP import ns as asset_ip_ns
from .assetSite import ns as asset_site_ns
from .scheduler import ns as scheduler_ns
from .poc import ns as poc_ns
from .vuln import ns as vuln_ns
from .batchExport import ns as batch_export_ns
from .policy import ns as policy_ns
from .npoc_service import ns as npoc_service_ns
from .taskFofa import ns as task_fofa_ns
from .console import ns as console_ns
from .cip import ns as cip_ns
from .fingerprint import ns as fingerprint_ns
from .stat_finger import ns as stat_finger_ns
from .github_task import ns as github_task_ns
from .github_result import ns as github_result_ns
from .github_monitor_result import ns as github_monitor_result_ns
from .github_scheduler import ns as github_scheduler_ns
from .task_schedule import ns as task_schedule_ns
from .nuclei_result import ns as nuclei_result_ns
from .wih import ns as wih_ns
from .assetWih import ns as asset_wih_ns
from .dashboard import ns as dashboard_ns
from .syslog import ns as syslog_ns
from .dictionary import ns as dictionary_ns
from .cdn_dict import ns as cdn_dict_ns
