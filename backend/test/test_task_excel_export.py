# coding: utf-8
"""资产侦查任务批量/单任务多工作表 Excel 导出单元测试与路由验证。"""

from datetime import datetime
from io import BytesIO
import sys
from pathlib import Path
from unittest.mock import patch
from zipfile import ZipFile

from bson import ObjectId
from flask import Flask
from flask_restx import Api
import openpyxl
import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# 先加载 app 以启用 openpyxl/numpy 兼容补丁
import app  # noqa: E402,F401
from app.services import task_excel_export as svc  # noqa: E402


class FakeCursor:
    def __init__(self, docs):
        self._docs = list(docs)

    def limit(self, n):
        return FakeCursor(self._docs[:n])

    def __iter__(self):
        return iter(self._docs)


class FakeCollection:
    def __init__(self, docs=None):
        self._docs = list(docs or [])

    def _matches(self, doc, query):
        for key, cond in (query or {}).items():
            val = doc.get(key)
            if isinstance(cond, dict) and "$in" in cond:
                if val not in cond["$in"]:
                    return False
            else:
                if val != cond:
                    return False
        return True

    def find(self, query=None, projection=None):
        matched = [doc for doc in self._docs if self._matches(doc, query)]
        return FakeCursor(matched)

    def find_one(self, query=None, projection=None):
        for doc in self._docs:
            if self._matches(doc, query):
                return doc
        return None

    def count_documents(self, query=None):
        return sum(1 for doc in self._docs if self._matches(doc, query))


def make_fake_db(collections_map):
    store = {name: FakeCollection(docs) for name, docs in collections_map.items()}

    def _getter(name):
        return store.setdefault(name, FakeCollection([]))

    return _getter


def _load_wb_and_assert_no_formulas(xlsx_bytes):
    with ZipFile(BytesIO(xlsx_bytes)) as archive:
        for name in archive.namelist():
            if name.startswith("xl/worksheets/") and name.endswith(".xml"):
                assert b"<f>" not in archive.read(name), f"Formula tag found in {name}"
    return openpyxl.load_workbook(BytesIO(xlsx_bytes), data_only=False)


def _sheet_rows(ws):
    return [list(row) for row in ws.iter_rows(values_only=True)]


def _build_fixture_db():
    tid1 = ObjectId("650000000000000000000001")
    tid2 = ObjectId("650000000000000000000002")
    s1, s2 = str(tid1), str(tid2)

    collections = {
        "task": [
            {
                "_id": tid1,
                "name": "主站测绘",
                "target": "alpha.example",
                "status": "done",
                "start_time": "2026-11-20 10:00:00",
                "end_time": "2026-11-20 10:15:00",
                "statistic": {
                    "site_cnt": 2, "domain_cnt": 1, "ip_cnt": 1, "service_cnt": 2,
                    "wih_cnt": 1, "vuln_cnt": 1, "nuclei_result_cnt": 1,
                    "fileleak_cnt": 1, "url_cnt": 1, "cert_cnt": 1, "cip_cnt": 1,
                },
            },
            {
                "_id": tid2,
                "name": "复测任务",
                "target": "beta.example",
                "status": "port_scan",
                "start_time": "2026-11-21 09:00:00",
                "end_time": "",
            },
        ],
        "site": [
            {
                "_id": ObjectId(), "task_id": s1,
                "site": "https://app.alpha.example",
                "title": "=1+1\x00管理后台",
                "status": 200, "http_server": "nginx",
                "finger": [{"name": "Vue"}],
                "favicon": {"hash": 123456},
                "ip": "192.0.2.10", "tag": ["重点"],
                "save_date": datetime(2026, 11, 20, 10, 5, 0),
            },
            {
                "_id": ObjectId(), "task_id": s2,
                "site": "https://app.alpha.example",
                "title": "",
                "status": 200, "http_server": "nginx",
                "finger": [{"name": "ElementUI"}],
                "favicon": {"hash": 123456},
                "ip": "192.0.2.10", "tag": ["复测"],
                "save_date": datetime(2026, 11, 21, 9, 5, 0),
            },
            {
                "_id": ObjectId(), "task_id": s1,
                "site": "http://api.alpha.example",
                "title": "+CMD|' /C calc'!A0",
                "status": 403, "http_server": "openresty",
                "finger": [], "favicon": {},
                "ip": "192.0.2.11", "tag": [],
                "save_date": datetime(2026, 11, 20, 10, 6, 0),
            },
        ],
        "domain": [
            {
                "_id": ObjectId(), "task_id": s1,
                "domain": "app.alpha.example", "type": "A",
                "record": ["192.0.2.10"], "ips": ["192.0.2.10"],
                "source": "brute", "save_date": datetime(2026, 11, 20, 10, 1, 0),
            },
            {
                "_id": ObjectId(), "task_id": s2,
                "domain": "app.alpha.example", "type": "A",
                "record": ["192.0.2.12"], "ips": ["192.0.2.12"],
                "source": "dns_plugin", "save_date": datetime(2026, 11, 21, 9, 1, 0),
            },
        ],
        "ip": [
            {
                "_id": ObjectId(), "task_id": s1,
                "ip": "192.0.2.10", "c_segment": "192.0.2.0/24",
                "port_info": [
                    {"port_id": 80, "service_name": "http", "product": "nginx", "version": "1.24"},
                    {"port_id": 443, "service_name": "https-alt", "product": "nginx", "version": "1.24"},
                ],
                "os_info": {"name": "Linux"},
                "domain": ["app.alpha.example"],
                "geo_city": {"country_name": "中国", "region_name": "上海", "city": "上海"},
                "geo_asn": {"number": 4134, "organization": "CHINANET"},
                "cdn_name": "", "ip_type": "PUBLIC",
                "save_date": datetime(2026, 11, 20, 10, 2, 0),
            },
            {
                "_id": ObjectId(), "task_id": s2,
                "ip": "192.0.2.10", "c_segment": "192.0.2.0/24",
                "port_info": [
                    {"port_id": 443, "service_name": "https", "product": "nginx", "version": "1.24"},
                    {"port_id": 8080, "service_name": "http", "product": "Tomcat", "version": "9.0"},
                ],
                "os_info": {},
                "domain": ["admin.beta.example"],
                "geo_city": {}, "geo_asn": {},
                "cdn_name": "", "ip_type": "PUBLIC",
                "save_date": datetime(2026, 11, 21, 9, 2, 0),
            },
        ],
        # 任务1 有融合 service 记录；任务2 无 service 记录（测试回退到 ip.port_info）
        "service": [
            {
                "_id": ObjectId(), "task_id": s1,
                "ip": "192.0.2.10", "port_id": 443,
                "service_name": "https", "product": "=nginx", "version": "1.24",
                "sources": ["nmap", "npoc"], "target": "https://192.0.2.10:443",
                "save_date": datetime(2026, 11, 20, 10, 3, 0),
            },
        ],
        "vuln": [
            {
                "_id": ObjectId(), "task_id": s1,
                "vul_name": "弱口令", "vul_category": "weak_pass",
                "app_name": "ssh", "target": "192.0.2.10:22",
                "verify_data": "@admin:123456",
                "save_date": datetime(2026, 11, 20, 10, 8, 0),
            },
            {
                "_id": ObjectId(), "task_id": s2,
                "vul_name": "弱口令", "vul_category": "weak_pass",
                "app_name": "ssh", "target": "192.0.2.10:22",
                "verify_data": "@admin:123456",
                "save_date": datetime(2026, 11, 21, 9, 8, 0),
            },
        ],
        "nuclei_result": [
            {
                "_id": ObjectId(), "task_id": s1,
                "template_id": "CVE-2025-0001", "vuln_name": "Demo RCE",
                "vuln_severity": "critical", "target": "https://app.alpha.example",
                "vuln_url": "https://app.alpha.example/vuln",
                "template_source": "custom", "curl_command": "curl -k https://app.alpha.example/vuln",
                "save_date": datetime(2026, 11, 20, 10, 9, 0),
            },
        ],
        "wih": [
            {
                "_id": ObjectId(), "task_id": s1,
                "record_type": "api_endpoint", "content": "GET https://app.alpha.example/api/v1",
                "source": "https://app.alpha.example/app.js", "site": "https://app.alpha.example",
                "save_date": datetime(2026, 11, 20, 10, 10, 0),
            },
        ],
        "fileleak": [
            {
                "_id": ObjectId(), "task_id": s1,
                "url": "https://app.alpha.example/.env", "title": "",
                "status_code": 200, "content_length": 512,
                "save_date": datetime(2026, 11, 20, 10, 11, 0),
            },
        ],
        "cert": [
            {
                "_id": ObjectId(), "task_id": s1,
                "ip": "192.0.2.10", "port": 443,
                "cert": {
                    "subject_dn": "CN=app.alpha.example",
                    "issuer_dn": "CN=Demo CA",
                    "extensions": {"subjectAltName": "DNS:app.alpha.example"},
                    "validity": {"start": "2026-01-01", "end": "2027-01-01"},
                    "fingerprint": {"sha1": "AABBCCDD"},
                },
                "save_date": datetime(2026, 11, 20, 10, 4, 0),
            },
        ],
        "url": [],  # 刻意置空以测试空维度自动跳过
        "cip": [
            {
                "_id": ObjectId(), "task_id": s1,
                "cidr_ip": "192.0.2.0/24",
                "ip_list": ["192.0.2.10"], "domain_list": ["app.alpha.example"],
                "ip_count": 1, "domain_count": 1,
                "save_date": datetime(2026, 11, 20, 10, 12, 0),
            },
            {
                "_id": ObjectId(), "task_id": s2,
                "cidr_ip": "192.0.2.0/24",
                "ip_list": ["192.0.2.10", "192.0.2.12"], "domain_list": ["admin.beta.example"],
                "ip_count": 2, "domain_count": 1,
                "save_date": datetime(2026, 11, 21, 9, 12, 0),
            },
        ],
    }
    return [s1, s2], make_fake_db(collections)


def test_batch_export_deduplicate_all_sheets_and_literal_safety():
    task_ids, db_getter = _build_fixture_db()
    result = svc.build_tasks_excel_report(
        task_id_list=task_ids,
        sheets=list(svc.SHEET_ORDER),
        deduplicate=True,
        db_getter=db_getter,
    )

    assert result.task_count == 2
    assert result.deduplicate is True
    assert result.has_active_tasks is True
    assert result.truncated_sheets == []
    assert "url" in result.empty_sheets
    assert "url" not in result.included_sheets
    assert result.included_sheets[0] == "overview"

    wb = _load_wb_and_assert_no_formulas(result.content)
    assert wb.sheetnames[0] == "任务概览"
    assert "URL" not in wb.sheetnames

    # 1. 任务概览：包含实时状态（含阶段状态映射）、快照提示、维度汇总
    overview_rows = _sheet_rows(wb["任务概览"])
    overview_flat = "\n".join(str(cell) for row in overview_rows for cell in row if cell is not None)
    assert "包含进行中或排队中任务" in overview_flat
    assert "已完成" in overview_flat
    assert "进行中 · 端口扫描" in overview_flat
    assert "无数据（已自动跳过）" in overview_flat

    # 2. 站点去重与公式字面安全
    site_ws = wb["站点"]
    site_rows = _sheet_rows(site_ws)
    assert len(site_rows) == 3  # 1 表头 + 2 去重站点
    assert site_rows[1][0] == "https://app.alpha.example"
    assert site_rows[1][1] == "=1+1管理后台"
    assert site_ws["B2"].data_type == "s"
    assert site_ws["C2"].data_type == "n"
    assert site_rows[1][2] == 200
    assert "Vue" in site_rows[1][4] and "ElementUI" in site_rows[1][4]
    assert "重点" in site_rows[1][7] and "复测" in site_rows[1][7]
    assert site_rows[1][9] == "主站测绘, 复测任务"
    assert site_rows[2][1] == "+CMD|' /C calc'!A0"
    assert site_ws["B3"].data_type == "s"

    # 3. IP 去重合并端口与域名并集，geo 去重相邻重复地名
    ip_rows = _sheet_rows(wb["IP"])
    assert len(ip_rows) == 2
    assert ip_rows[1][0] == "192.0.2.10"
    assert ip_rows[1][2] == "80, 443, 8080"
    assert ip_rows[1][3] == 3
    assert "app.alpha.example" in ip_rows[1][5] and "admin.beta.example" in ip_rows[1][5]
    assert ip_rows[1][6] == "中国/上海"
    assert ip_rows[1][7] == "AS4134 CHINANET"
    assert ip_rows[1][11] == "主站测绘, 复测任务"

    # 4. 系统服务：任务1 融合 service 表(443) + 补齐同任务 ip.port_info(80) + 任务2 回退 ip.port_info(443/8080)
    svc_ws = wb["系统服务"]
    svc_rows = _sheet_rows(svc_ws)
    assert len(svc_rows) == 4  # 表头 + 80(task1补齐) + 443(merged) + 8080(task2补齐)
    row_80 = [r for r in svc_rows[1:] if r[1] == 80][0]
    assert row_80[3] == "nginx"
    assert row_80[8] == "主站测绘"
    row_443 = [r for r in svc_rows[1:] if r[1] == 443][0]
    assert row_443[3] == "=nginx"
    assert row_443[8] == "主站测绘, 复测任务"
    row_8080 = [r for r in svc_rows[1:] if r[1] == 8080][0]
    assert row_8080[3] == "Tomcat"
    assert row_8080[8] == "复测任务"

    # 5. 风险漏洞去重 + Nuclei 模板来源映射 + C段集合合并
    vuln_rows = _sheet_rows(wb["风险漏洞"])
    assert len(vuln_rows) == 2
    assert vuln_rows[1][4] == "@admin:123456"
    assert vuln_rows[1][6] == "主站测绘, 复测任务"

    nuclei_rows = _sheet_rows(wb["Nuclei漏洞"])
    assert len(nuclei_rows) == 2
    assert nuclei_rows[1][5] == "自建"

    cip_rows = _sheet_rows(wb["C段"])
    assert len(cip_rows) == 2
    assert cip_rows[1][1] == 2  # 192.0.2.10 + 192.0.2.12
    assert cip_rows[1][2] == 2  # app.alpha.example + admin.beta.example

    # 6. 资产统计显式标注去重口径且端口总数与去重结果一致（80, 443, 8080 = 3）
    stat_rows = _sheet_rows(wb["资产统计"])
    stat_text = "\n".join(str(cell) for row in stat_rows for cell in row if cell is not None)
    assert "跨任务去重统计" in stat_text
    assert "端口开放总数: 3" in stat_text


def test_batch_export_without_deduplication_preserves_raw_rows():
    task_ids, db_getter = _build_fixture_db()
    result = svc.build_tasks_excel_report(
        task_id_list=task_ids,
        sheets=["overview", "site", "ip", "vuln", "statist"],
        deduplicate=False,
        db_getter=db_getter,
    )

    wb = _load_wb_and_assert_no_formulas(result.content)
    assert len(_sheet_rows(wb["站点"])) == 4  # 1 表头 + 3 原始站点
    assert len(_sheet_rows(wb["IP"])) == 3  # 1 表头 + 2 原始 IP
    assert len(_sheet_rows(wb["风险漏洞"])) == 3  # 1 表头 + 2 原始漏洞

    stat_text = "\n".join(str(c) for row in _sheet_rows(wb["资产统计"]) for c in row if c is not None)
    assert "未去重" in stat_text
    assert "端口开放总数: 4" in stat_text  # task1(2) + task2(2)


def test_all_empty_asset_sheets_falls_back_to_overview():
    tid = ObjectId("650000000000000000000009")
    db_getter = make_fake_db({
        "task": [{"_id": tid, "name": "空任务", "target": "empty.example", "status": "done"}],
    })
    result = svc.build_tasks_excel_report(
        task_id_list=[str(tid)],
        sheets=["vuln", "nuclei_result"],
        deduplicate=True,
        db_getter=db_getter,
    )
    assert result.empty_sheets == ["vuln", "nuclei_result"]
    assert result.included_sheets == ["overview"]
    wb = _load_wb_and_assert_no_formulas(result.content)
    assert wb.sheetnames == ["任务概览"]


@pytest.mark.parametrize("deduplicate", [True, False])
def test_row_cap_truncation_marks_headers_and_overview(deduplicate):
    tid = ObjectId("650000000000000000000010")
    urls = [
        {"_id": ObjectId(), "task_id": str(tid), "url": f"https://a.example/{i}", "status_code": 200}
        for i in range(5)
    ]
    db_getter = make_fake_db({
        "task": [{"_id": tid, "name": "大任务", "target": "a.example", "status": "done"}],
        "url": urls,
    })
    result = svc.build_tasks_excel_report(
        task_id_list=[str(tid)],
        sheets=["overview", "url"],
        deduplicate=deduplicate,
        db_getter=db_getter,
        max_rows_per_sheet=3,
    )
    assert result.truncated_sheets == ["url"]
    assert result.sheet_row_counts["url"] == 3
    wb = _load_wb_and_assert_no_formulas(result.content)
    assert len(_sheet_rows(wb["URL"])) == 4  # 1 表头 + 3 数据行
    overview_text = "\n".join(str(c) for row in _sheet_rows(wb["任务概览"]) for c in row if c is not None)
    assert "截断" in overview_text


def test_validation_rejects_invalid_inputs_and_over_limit():
    with pytest.raises(svc.TaskExcelExportError) as exc1:
        svc.validate_export_params([])
    assert exc1.value.status_code == 400

    with pytest.raises(svc.TaskExcelExportError) as exc2:
        svc.validate_export_params(["not-an-oid"])
    assert exc2.value.status_code == 400

    over_ids = [str(ObjectId()) for _ in range(svc.MAX_EXPORT_TASKS + 1)]
    with pytest.raises(svc.TaskExcelExportError) as exc3:
        svc.validate_export_params(over_ids)
    assert exc3.value.status_code == 400

    with pytest.raises(svc.TaskExcelExportError) as exc4:
        svc.validate_export_params([str(ObjectId())], sheets=["unknown_dim"])
    assert exc4.value.status_code == 400

    with pytest.raises(svc.TaskExcelExportError) as exc5:
        svc.validate_export_params([str(ObjectId())], sheets=[])
    assert exc5.value.status_code == 400

    empty_db = make_fake_db({"task": []})
    with pytest.raises(svc.TaskExcelExportError) as exc6:
        svc.build_tasks_excel_report([str(ObjectId())], db_getter=empty_db)
    assert exc6.value.status_code == 404


def test_batch_export_route_http_response_and_error_handling():
    from app.routes import export as export_route

    flask_app = Flask(__name__)
    api = Api(flask_app, prefix="/api")
    api.add_namespace(export_route.ns)

    task_ids, db_getter = _build_fixture_db()
    client = flask_app.test_client()

    with patch("app.utils.user.user_login_header", return_value=True), \
         patch("app.services.task_excel_export.utils.conn_db", side_effect=db_getter), \
         patch("app.routes.export.utils.conn_db", side_effect=db_getter):
        # 正常批量导出
        resp = client.post(
            "/api/export/batch/",
            json={"task_id": task_ids, "sheets": ["overview", "site", "url"], "deduplicate": True},
            headers={"Token": "fixture-token"},
        )
        assert resp.status_code == 200
        assert "spreadsheetml.sheet" in resp.headers["Content-Type"]
        assert "filename*=UTF-8''" in resp.headers["Content-Disposition"]
        assert resp.headers["X-Export-Truncated"] == "0"
        assert resp.headers["X-Export-Empty-Sheets"] == "url"
        assert "X-Export-Truncated-Sheets" in resp.headers["Access-Control-Expose-Headers"]
        wb = _load_wb_and_assert_no_formulas(resp.data)
        assert wb.sheetnames == ["任务概览", "站点"]

        # 兼容保留旧版单任务导出接口 GET /api/export/<task_id>
        legacy_resp = client.get(f"/api/export/{task_ids[0]}", headers={"Token": "fixture-token"})
        assert legacy_resp.status_code == 200
        legacy_wb = _load_wb_and_assert_no_formulas(legacy_resp.data)
        assert "站点" in legacy_wb.sheetnames

        # 非布尔 deduplicate 返回 400 JSON
        bad_resp = client.post(
            "/api/export/batch/",
            json={"task_id": task_ids, "deduplicate": "false"},
            headers={"Token": "fixture-token"},
        )
        assert bad_resp.status_code == 400
        assert bad_resp.get_json()["code"] == 400

        # 不存在的任务返回 404 JSON
        not_found = client.post(
            "/api/export/batch/",
            json={"task_id": [str(ObjectId())]},
            headers={"Token": "fixture-token"},
        )
        assert not_found.status_code == 404
        assert not_found.get_json()["code"] == 404
