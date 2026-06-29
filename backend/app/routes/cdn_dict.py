import os
import json
from flask_restx import Resource, Namespace, fields
from app.utils import get_logger, auth
from . import ARLResource, get_arl_parser
from app.config import Config

ns = Namespace('cdn_dict', description="CDN字典管理")
logger = get_logger()

# 基础目录配置，使用 Config 中的 basedir
CDN_FILE_PATH = Config.CDN_JSON_PATH if hasattr(Config, 'CDN_JSON_PATH') else os.path.join(Config.basedir, 'dicts', 'cdn_info.json')

# /save 请求参数 (JSON body)
save_fields = {
    'data': fields.List(fields.Raw, required=True, description="完整的CDN数据列表")
}
save_parser = get_arl_parser(save_fields, location='json')


@ns.route('/list')
class CdnDictList(Resource):
    @auth
    def get(self):
        """
        获取 CDN 字典列表
        """
        try:
            if not os.path.exists(CDN_FILE_PATH):
                return {'code': 404, 'message': 'CDN字典文件不存在'}
            
            with open(CDN_FILE_PATH, 'r', encoding='utf-8', errors='ignore') as f:
                data = json.load(f)
                
            return {'code': 200, 'message': 'success', 'data': data}
        except Exception as e:
            logger.error(f"Error reading CDN dictionary: {e}")
            return {'code': 500, 'message': str(e)}


@ns.route('/save')
class CdnDictSave(Resource):
    @auth
    @ns.expect(save_parser)
    def post(self):
        """
        保存（覆盖）CDN 字典
        """
        args = save_parser.parse_args()
        data = args.get('data', [])
        
        # 简单验证数据结构
        if not isinstance(data, list):
            return {'code': 400, 'message': '数据格式错误，必须为列表'}
            
        try:
            with open(CDN_FILE_PATH, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=4)
                
            # 重载 cdn 的缓存 (触发 utils.cdn 里面的重新初始化)
            # 在 ARL 架构里 utils.cdn.cdn_info 是动态的，如果有用到需要让其清空，但是由于
            # python 进程的隔离，最好不直接修改。重新发起探测任务时会生效，
            # 也可以在这里强制更新缓存：
            from app.utils import cdn
            cdn.cdn_info = data
            cdn.cdn_cname_list = []
            cdn.cdn_ip_cidr_list = []
            for item in data:
                if item.get("cname_domain"):
                    cdn.cdn_cname_list.extend(item["cname_domain"])
                if item.get("ip_cidr"):
                    cdn.cdn_ip_cidr_list.extend(item["ip_cidr"])
                    
            return {'code': 200, 'message': '保存成功'}
        except Exception as e:
            logger.error(f"Error saving CDN dictionary: {e}")
            return {'code': 500, 'message': str(e)}
