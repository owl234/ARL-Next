import os
import json
import ipaddress
from flask_restx import Resource, Namespace, fields
from app.utils import get_logger, auth
from app.utils.dict_utils import file_lock
from . import get_arl_parser
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
                with file_lock(f, exclusive=False):
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
        保存（覆盖）CDN 字典（具备严格格式校验与排他文件锁保护）
        """
        args = save_parser.parse_args()
        data = args.get('data', [])

        if not isinstance(data, list):
            return {'code': 400, 'message': '数据格式错误，必须为列表'}

        # 严格防御性格式校验（阻断非法 CIDR 与 CNAME 破坏全局探测引擎）
        cleaned_data = []
        for item in data:
            if not isinstance(item, dict):
                return {'code': 400, 'message': 'CDN 条目必须为合法 JSON 对象'}
            name = (item.get('name') or '').strip()
            if not name:
                return {'code': 400, 'message': 'CDN 厂商名称不能为空'}

            raw_cnames = item.get('cname_domain', [])
            if not isinstance(raw_cnames, list):
                return {'code': 400, 'message': f'厂商【{name}】的 CNAME 特征必须为列表'}
            cnames = []
            for cn in raw_cnames:
                if not isinstance(cn, str):
                    continue
                cn_clean = cn.strip()
                if not cn_clean:
                    continue
                if any(c in cn_clean for c in [' ', '\t', '/', '\\', '\r', '\n']):
                    return {'code': 400, 'message': f'厂商【{name}】包含非法 CNAME 后缀: {cn_clean}'}
                cnames.append(cn_clean)

            raw_cidrs = item.get('ip_cidr', [])
            if not isinstance(raw_cidrs, list):
                return {'code': 400, 'message': f'厂商【{name}】的 IP/CIDR 特征必须为列表'}
            cidrs = []
            for cidr in raw_cidrs:
                if not isinstance(cidr, str):
                    continue
                cidr_clean = cidr.strip()
                if not cidr_clean:
                    continue
                try:
                    ipaddress.IPv4Network(cidr_clean, strict=False)
                    cidrs.append(cidr_clean)
                except Exception:
                    return {'code': 400, 'message': f'厂商【{name}】包含无效的 IPv4/CIDR 网段: {cidr_clean}'}

            cleaned_data.append({
                'name': name,
                'cname_domain': cnames,
                'ip_cidr': cidrs
            })

        try:
            os.makedirs(os.path.dirname(CDN_FILE_PATH), exist_ok=True)
            with open(CDN_FILE_PATH, 'w', encoding='utf-8') as f:
                with file_lock(f, exclusive=True):
                    json.dump(cleaned_data, f, ensure_ascii=False, indent=4)
                    f.flush()

            # 重载 cdn 的运行时内存缓存
            from app.utils import cdn
            cdn.cdn_info = cleaned_data
            cdn.cdn_cname_list = []
            cdn.cdn_ip_cidr_list = []
            for item in cleaned_data:
                if item.get("cname_domain"):
                    cdn.cdn_cname_list.extend(item["cname_domain"])
                if item.get("ip_cidr"):
                    cdn.cdn_ip_cidr_list.extend(item["ip_cidr"])

            return {'code': 200, 'message': '保存成功'}
        except Exception as e:
            logger.error(f"Error saving CDN dictionary: {e}")
            return {'code': 500, 'message': str(e)}
