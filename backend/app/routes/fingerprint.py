import json
import time
import yaml
from werkzeug.datastructures import FileStorage
from urllib.parse import quote
from flask import make_response
from flask_restx import Resource, Api, reqparse, fields, Namespace
from bson import ObjectId
from app.utils import get_logger, auth, parse_human_rule, transform_rule_map
from app import utils
from app.modules import ErrorMsg
from app.services import check_expression_with_error, have_human_rule_from_db
from app.services import check_expression
from . import base_query_fields, ARLResource, get_arl_parser

ns = Namespace('fingerprint', description="指纹信息")

logger = get_logger()

base_search_fields = {
    'name': fields.String(required=False, description="名称"),
    "update_date__dgt": fields.String(description="更新时间大于"),
    "update_date__dlt": fields.String(description="更新时间小于")
}

base_search_fields.update(base_query_fields)


add_fingerprint_fields = ns.model('addFingerSite', {
    'name': fields.String(required=True, description="名称"),
    'human_rule': fields.String(required=True, description="规则"),
})


@ns.route('/')
class ARLFingerprint(ARLResource):
    parser = get_arl_parser(base_search_fields, location='args')

    @auth
    @ns.expect(parser)
    def get(self):
        """
        指纹信息查询
        """
        args = self.parser.parse_args()
        data = self.build_data(args=args, collection='fingerprint')

        return data

    @auth
    @ns.expect(add_fingerprint_fields)
    def post(self):
        """
        添加指纹信息
        """
        args = self.parse_args(add_fingerprint_fields)

        human_rule = args.pop('human_rule')
        name = args.pop('name')

        if have_human_rule_from_db(human_rule):
            return utils.build_ret(ErrorMsg.RuleAlreadyExists, {"rule": human_rule})

        flag, err = check_expression_with_error(human_rule)
        if not flag:
            return utils.build_ret(ErrorMsg.RuleInvalid, {"error": str(err)})

        data = {
            "name": name,
            "human_rule": human_rule,
            "update_date": utils.curr_date_obj()
        }

        utils.conn_db('fingerprint').insert_one(data)

        finger_id = str(data.pop('_id'))

        data.pop('update_date')

        return utils.build_ret(ErrorMsg.Success, {"_id": finger_id, "data": data})


delete_finger_fields = ns.model('deleteFingerSite',  {
    '_id': fields.List(fields.String(required=True, description="指纹 _id"))
})


@ns.route('/delete/')
class DeleteARLFinger(ARLResource):
    @auth
    @ns.expect(delete_finger_fields)
    def post(self):
        """
        删除指纹
        """
        args = self.parse_args(delete_finger_fields)
        id_list = args.pop('_id', "")
        for _id in id_list:
            query = {'_id': ObjectId(_id)}
            utils.conn_db('fingerprint').delete_one(query)

        return utils.build_ret(ErrorMsg.Success, {'_id': id_list})


@ns.route('/export/')
class ExportARLFinger(ARLResource):

    @auth
    def get(self):
        """
        指纹导出
        """
        items = []
        results = list(utils.conn_db('fingerprint').find())
        for result in results:
            item = dict()
            item["name"] = result["name"]
            item["rule"] = result["human_rule"]
            items.append(item)

        data = yaml.dump(items, default_flow_style=False, sort_keys=False, allow_unicode=True)
        response = make_response(data)
        filename = "fingerprint_{}_{}.yml".format(len(items), int(time.time()))
        response.headers['Content-Type'] = 'application/octet-stream'
        response.headers["Access-Control-Expose-Headers"] = "Content-Disposition"
        response.headers["Content-Disposition"] = "attachment; filename={}".format(quote(filename))

        return response


file_upload = reqparse.RequestParser()
file_upload.add_argument('file',
                         type=FileStorage,
                         location='files',
                         required=True,
                         help='JSON file')


@ns.route('/sync/')
class SyncARLFinger(ARLResource):

    @auth
    def post(self):
        """
        同步指纹到 webapp.json
        """
        from app.config import Config
        import json
        import os

        webapp_file = Config.web_app_rule
        
        # Load existing webapp.json
        webapp_data = {}
        if os.path.exists(webapp_file):
            try:
                with open(webapp_file, 'r', encoding='utf-8') as f:
                    webapp_data = json.load(f)
            except Exception as e:
                logger.error(f"Failed to load webapp.json: {e}")
                return utils.build_ret(ErrorMsg.Error, {'msg': f"加载 webapp.json 失败: {e}"})

        # Fetch all from DB
        results = list(utils.conn_db('fingerprint').find())
        
        # Keep track of updated or added
        sync_cnt = 0
        for result in results:
            name = result["name"]
            human_rule = result["human_rule"]
            
            if name in webapp_data:
                # Update existing rule
                if webapp_data[name].get("fofa_rule") != human_rule:
                    webapp_data[name]["fofa_rule"] = human_rule
                    sync_cnt += 1
            else:
                # Add new rule
                webapp_data[name] = {
                    "cats": [],
                    "headers": [],
                    "html": [],
                    "title": [],
                    "icon": "default.png",
                    "website": "https://www.riskivy.com/",
                    "fofa_rule": human_rule
                }
                sync_cnt += 1

        # Save back to webapp.json
        try:
            with open(webapp_file, 'w', encoding='utf-8') as f:
                json.dump(webapp_data, f, ensure_ascii=False, indent=4)
            return utils.build_ret(ErrorMsg.Success, {'msg': f"成功同步了 {sync_cnt} 条更新到 webapp.json"})
        except Exception as e:
            logger.error(f"Failed to save webapp.json: {e}")
            return utils.build_ret(ErrorMsg.Error, {'msg': f"保存 webapp.json 失败: {e}"})


@ns.route('/upload/')
class UploadARLFinger(ARLResource):

    @auth
    @ns.expect(file_upload)
    def post(self):
        """
        指纹上传
        """
        args = file_upload.parse_args()
        file_data = args['file'].read()
        try:
            obj = yaml.safe_load(file_data)
            if not isinstance(obj, list):
                return utils.build_ret(ErrorMsg.Error, {'msg': "not list obj"})

            # Pre-fetch existing rules for in-memory deduplication (massively improves speed)
            existing_rules = {doc.get('human_rule') for doc in utils.conn_db('fingerprint').find({}, {"human_rule": 1})}

            error_cnt = 0
            success_cnt = 0
            repeat_cnt = 0
            new_docs = []

            for rule in obj:
                human_rule = rule.get("rule", "")
                rule_name = rule.get('name', "")

                if not human_rule or not rule_name:
                    error_cnt += 1
                    continue

                rule_flag = check_expression(human_rule)
                if not rule_flag:
                    error_cnt += 1
                    continue

                if human_rule in existing_rules:
                    repeat_cnt += 1
                    continue

                new_docs.append({
                    "name": rule_name,
                    "human_rule": human_rule,
                    "update_date": utils.curr_date_obj()
                })
                # Prevent duplicates within the uploaded file itself
                existing_rules.add(human_rule)
                success_cnt += 1

            if new_docs:
                utils.conn_db('fingerprint').insert_many(new_docs)

            return utils.build_ret(ErrorMsg.Success, {'error_cnt': error_cnt,
                                                      'repeat_cnt': repeat_cnt,'success_cnt': success_cnt})
        except Exception as e:
            return utils.build_ret(ErrorMsg.Error, {'msg': str(e)})


