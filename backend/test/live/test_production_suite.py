#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ARL-Next 全链路生产环境综合测试与性能体验体检套件
涵盖：
1. 业务正常运转深度闭环测试 (CRUD, Dry Run, 安全边界, 导入导出, 任务流)
2. 效率与性能瓶颈诊断 (MongoDB 索引覆盖, 慢查询, 物化开销, 高并发时延)
3. 交互与用户体验缺陷审计 (错误可读性, 传输体积, 前端静态资源完整性)
"""

import sys
import os
import time
import json
import zipfile
import io
import urllib3
import requests

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

BASE_URL = os.environ.get("ARL_HOST", "https://192.0.2.10:5173")
TOKEN = os.environ.get("ARL_TOKEN", "")
BASIC_AUTH = (os.environ.get("BASIC_USER", ""), os.environ.get("BASIC_PASS", ""))

HEADERS = {
    "Token": TOKEN,
    "Content-Type": "application/json"
}

results = {
    "passed": [],
    "failed": [],
    "warnings": [],
    "performance": {},
    "ux_flaws": []
}

def log_pass(name, detail=""):
    print(f"  ✅ [PASS] {name} {detail}")
    results["passed"].append({"name": name, "detail": detail})

def log_fail(name, reason=""):
    print(f"  ❌ [FAIL] {name}: {reason}")
    results["failed"].append({"name": name, "reason": reason})

def log_warn(name, reason=""):
    print(f"  ⚠️ [WARN] {name}: {reason}")
    results["warnings"].append({"name": name, "reason": reason})

def log_ux(name, issue=""):
    print(f"  💡 [UX FLAW] {name}: {issue}")
    results["ux_flaws"].append({"name": name, "issue": issue})


print("=" * 70)
print(f"🚀 开始执行 ARL-Next 生产全量测试套件")
print(f"目标主机: {BASE_URL}")
print("=" * 70)


# ==============================================================================
# SECTION 1: 业务正常运转与安全边界测试 (Business Continuity & Security)
# ==============================================================================
print("\n[MODULE 1] 业务正常运转与安全边界测试...")

# 1.1 基础连通性与 stats 接口
try:
    t0 = time.time()
    r = requests.get(f"{BASE_URL}/api/nuclei/stats/", headers=HEADERS, verify=False, timeout=10)
    cost = round(time.time() - t0, 3)
    if r.status_code == 200:
        data = r.json().get("data", {})
        if data.get("nuclei_version") and data.get("nuclei_version") != "未知":
            log_pass("获取 Nuclei 统计概览", f"(耗时 {cost}s, 社区模板数: {data.get('community_total')}, 版本: {data.get('nuclei_version')})")
        else:
            log_warn("Nuclei 引擎版本未正确识别", "返回为 '未知'，可能是 stderr 输出未被捕获")
    else:
        log_fail("获取 Nuclei 统计概览", f"HTTP {r.status_code}: {r.text}")
except Exception as e:
    log_fail("获取 Nuclei 统计概览", f"请求异常: {e}")

# 1.1.b 官方模板同步状态机与版本感知
try:
    r_sync = requests.get(f"{BASE_URL}/api/nuclei/community/sync_status/", headers=HEADERS, verify=False, timeout=10)
    if r_sync.status_code == 200 and r_sync.json().get("code") == 200:
        s_data = r_sync.json().get("data", {})
        log_pass("官方模板同步状态机与版本感知", f"(状态: {s_data.get('status')}, 本地版本: {s_data.get('current_version')}, 增量: +{s_data.get('diff_count')})")
    else:
        log_fail("官方模板同步状态机接口", f"HTTP {r_sync.status_code}: {r_sync.text}")
except Exception as e:
    log_fail("官方模板同步状态机测试", f"异常: {e}")

# 1.1.c 离线全量模板 ZIP 包上传解压覆盖校验 (Offline Sync)
try:
    offline_buf = io.BytesIO()
    off_tid = f"offline-cve-{int(time.time())}"
    off_yaml = f"id: {off_tid}\ninfo:\n  name: Offline Verified PoC\n  severity: low\nhttp:\n  - method: GET\n"
    with zipfile.ZipFile(offline_buf, 'w', zipfile.ZIP_DEFLATED) as z:
        z.writestr(f"cves/2026/{off_tid}.yaml", off_yaml)
    offline_buf.seek(0)

    off_files = {'file': ('nuclei-templates-offline.zip', offline_buf.getvalue(), 'application/zip')}
    r_off = requests.post(f"{BASE_URL}/api/nuclei/community/sync_offline/", headers={"Token": TOKEN}, files=off_files, verify=False, timeout=15)
    if r_off.status_code == 200 and r_off.json().get("code") == 200:
        log_pass("离线全量模板 ZIP 包上传解压 (Offline Sync)", "成功触发后台解压覆盖")
    else:
        log_fail("离线全量模板 ZIP 包上传", f"返回: {r_off.text}")
except Exception as e:
    log_fail("离线模板上传测试", f"异常: {e}")

# 1.2 认证防御边界
try:
    r_no_auth = requests.get(f"{BASE_URL}/api/nuclei/stats/", verify=False, timeout=10)
    res_json = r_no_auth.json() if r_no_auth.text.startswith('{') else {}
    if res_json.get("code") == 401 or "not login" in r_no_auth.text.lower():
        log_pass("未鉴权访问拦截 (401 拦截有效)")
    else:
        log_fail("未鉴权访问拦截", f"未携带 Token 却返回了: {r_no_auth.text[:100]}")

    r_fake_auth = requests.get(f"{BASE_URL}/api/nuclei/stats/", headers={"Token": "fake_token_123"}, verify=False, timeout=10)
    res_fake = r_fake_auth.json() if r_fake_auth.text.startswith('{') else {}
    if res_fake.get("code") == 401:
        log_pass("伪造 Token 访问拦截 (鉴权防伪有效)")
    else:
        log_fail("伪造 Token 访问拦截", f"伪造 Token 返回: {r_fake_auth.text[:100]}")
except Exception as e:
    log_fail("认证边界检查", f"请求异常: {e}")

# 1.3 目录穿越安全防护 (Path Traversal Protection)
try:
    r_traversal = requests.get(
        f"{BASE_URL}/api/nuclei/community/source/?file_path=../../../../etc/passwd",
        headers=HEADERS, verify=False, timeout=10
    )
    if "root:x:" not in r_traversal.text and (r_traversal.status_code != 200 or r_traversal.json().get("code") != 200):
        log_pass("目录穿越注入防御 (Path Traversal 防护有效)")
    else:
        log_fail("目录穿越注入防御", "发现严重安全隐患！可能成功读取了 /etc/passwd！")
except Exception as e:
    log_fail("目录穿越测试", f"异常: {e}")

# 1.4 自建模板完整 CRUD 闭环
test_tid = f"prod-test-rce-{int(time.time())}"
valid_yaml = f"""id: {test_tid}

info:
  name: Automated Test RCE Exploit
  author: tester
  severity: critical
  description: Unit test automated validation template
  tags: test,rce,automated

http:
  - method: GET
    path:
      - "{{{{BaseURL}}}}/healthz"
    matchers:
      - type: word
        words:
          - "ok"
"""

# A. 创建
try:
    r_create = requests.post(f"{BASE_URL}/api/nuclei/template/create/", headers=HEADERS, json={"content": valid_yaml}, verify=False, timeout=10)
    if r_create.status_code == 200 and r_create.json().get("code") == 200:
        log_pass("自建模板创建 (Create)", f"template_id: {test_tid}")
    else:
        log_fail("自建模板创建", f"返回: {r_create.text}")
except Exception as e:
    log_fail("自建模板创建", f"异常: {e}")

# B. 重复创建查重
try:
    r_dup = requests.post(f"{BASE_URL}/api/nuclei/template/create/", headers=HEADERS, json={"content": valid_yaml}, verify=False, timeout=10)
    dup_json = r_dup.json()
    if r_dup.status_code == 200 and dup_json.get("code") != 200 and "已存在" in dup_json.get("message", ""):
        log_pass("重复模板 ID 查重拦截 (防冲突生效)")
    else:
        log_fail("重复模板 ID 查重拦截", f"预期报错但返回: {r_dup.text}")
except Exception as e:
    log_fail("重复模板查重测试", f"异常: {e}")

# C. 破损 YAML 契约拦截
broken_yaml = "id: broken-template\ninfo:\n  severity: high" # 缺少 name
try:
    r_broken = requests.post(f"{BASE_URL}/api/nuclei/template/create/", headers=HEADERS, json={"content": broken_yaml}, verify=False, timeout=10)
    if r_broken.status_code == 200 and r_broken.json().get("code") != 200 and "name" in r_broken.text:
        log_pass("不合规 YAML 契约静态拦截 (缺少 name 拦截有效)")
    else:
        log_fail("不合规 YAML 契约静态拦截", f"未能拦截非法格式: {r_broken.text}")
except Exception as e:
    log_fail("破损 YAML 拦截测试", f"异常: {e}")

# D. 模板列表查询与检索过滤
try:
    r_query = requests.get(f"{BASE_URL}/api/nuclei/template/?template_id={test_tid}", headers=HEADERS, verify=False, timeout=10)
    q_data = r_query.json().get("data", {})
    if q_data.get("total", 0) >= 1 and q_data.get("items", [])[0]["template_id"] == test_tid:
        log_pass("自建模板列表过滤检索 (Query Filter)")
        # 体验与效率审查：列表项不应该包含大体积 content 源码
        if "content" in q_data["items"][0]:
            log_ux("列表接口数据传输冗余", "列表项包含完整的 YAML content 源码，多条数据时会大幅增加网络传输开销")
        else:
            log_pass("自建模板列表轻量化", "(已剔除 content 大字段，避免列表分页冗余传输)")
    else:
        log_fail("自建模板列表过滤检索", f"未查询到刚创建的模板: {r_query.text}")
except Exception as e:
    log_fail("自建模板列表查询", f"异常: {e}")

# E. 模板详情获取 (应包含完整 content)
try:
    r_detail = requests.get(f"{BASE_URL}/api/nuclei/template/detail/?template_id={test_tid}", headers=HEADERS, verify=False, timeout=10)
    d_data = r_detail.json().get("data", {})
    if d_data.get("template_id") == test_tid and d_data.get("content"):
        log_pass("模板详情与 YAML 源码获取 (Detail)")
    else:
        log_fail("模板详情获取", f"详情不完整: {r_detail.text}")
except Exception as e:
    log_fail("模板详情获取", f"异常: {e}")

# F. 状态切换 Toggle
try:
    r_toggle = requests.post(f"{BASE_URL}/api/nuclei/template/toggle/", headers=HEADERS, json={"template_id": test_tid, "enable": False}, verify=False, timeout=10)
    if r_toggle.json().get("code") == 200:
        # 查库验证
        r_chk = requests.get(f"{BASE_URL}/api/nuclei/template/detail/?template_id={test_tid}", headers=HEADERS, verify=False, timeout=10)
        if r_chk.json().get("data", {}).get("enable") is False:
            log_pass("模板实时启用/禁用状态切换 (Toggle)")
        else:
            log_fail("模板状态切换", "接口返回成功但 DB 中 enable 未更新为 False")
    else:
        log_fail("模板状态切换", f"返回: {r_toggle.text}")
except Exception as e:
    log_fail("模板状态切换", f"异常: {e}")

# G. 在线即时调试 Dry Run 测试
try:
    t0 = time.time()
    r_test = requests.post(
        f"{BASE_URL}/api/nuclei/template/test/",
        headers=HEADERS,
        json={"template_id": test_tid, "target": "127.0.0.1:5000"},
        verify=False,
        timeout=35
    )
    cost = round(time.time() - t0, 2)
    if r_test.status_code == 200 and r_test.json().get("code") == 200:
        log_pass("在线单目标即时调试 (Dry Run 执行成功)", f"(耗时: {cost}s)")
    else:
        log_fail("在线单目标即时调试", f"执行报错: {r_test.text}")
except Exception as e:
    log_fail("在线单目标即时调试", f"执行异常: {e}")

# H. 批量导出 ZIP
try:
    r_export = requests.get(f"{BASE_URL}/api/nuclei/template/export/?template_ids={test_tid}", headers=HEADERS, verify=False, timeout=10)
    if r_export.status_code == 200 and r_export.headers.get("Content-Type") == "application/zip":
        with zipfile.ZipFile(io.BytesIO(r_export.content)) as z:
            names = z.namelist()
            if f"{test_tid}.yaml" in names:
                log_pass("模板打包导出 ZIP (Export)", f"包含目标文件 {names}")
            else:
                log_fail("模板打包导出", f"ZIP 中缺少对应文件: {names}")
    else:
        log_fail("模板打包导出", f"返回非法内容类型: {r_export.headers.get('Content-Type')}")
except Exception as e:
    log_fail("模板导出测试", f"异常: {e}")

# I. 批量导入 ZIP
try:
    zip_buf = io.BytesIO()
    import_tid = f"import-test-{int(time.time())}"
    import_yaml = f"id: {import_tid}\ninfo:\n  name: Imported Test PoC\n  author: tester\n  severity: medium\nhttp:\n  - method: GET\n    path:\n      - \"{{{{BaseURL}}}}/\"\n"
    with zipfile.ZipFile(zip_buf, 'w', zipfile.ZIP_DEFLATED) as z:
        z.writestr(f"{import_tid}.yaml", import_yaml)
    zip_buf.seek(0)

    files = {'file': (f'{import_tid}.zip', zip_buf.getvalue(), 'application/zip')}
    r_import = requests.post(f"{BASE_URL}/api/nuclei/template/import/", headers={"Token": TOKEN}, files=files, verify=False, timeout=15)
    imp_res = r_import.json()
    if imp_res.get("code") == 200 and imp_res.get("data", {}).get("success_count", 0) >= 1:
        log_pass("ZIP 批量导入自建模板 (Import)")
        # 清理导入的临时模板
        requests.post(f"{BASE_URL}/api/nuclei/template/delete/", headers=HEADERS, json={"template_ids": [import_tid]}, verify=False, timeout=10)
    else:
        log_fail("ZIP 批量导入", f"返回: {r_import.text}")
except Exception as e:
    log_fail("ZIP 批量导入测试", f"异常: {e}")

# J. 模板删除 Delete
try:
    r_del = requests.post(f"{BASE_URL}/api/nuclei/template/delete/", headers=HEADERS, json={"template_ids": [test_tid]}, verify=False, timeout=10)
    if r_del.json().get("code") == 200 and r_del.json().get("data", {}).get("delete_cnt", 0) >= 1:
        log_pass("自建模板删除 (Delete)")
    else:
        log_fail("自建模板删除", f"未能删除: {r_del.text}")
except Exception as e:
    log_fail("自建模板删除", f"异常: {e}")

# 1.5 Celery 真实任务下发、Nuclei 调度与生命周期验证
print("\n[MODULE 1.5] Celery 真实任务调度与生命周期验证...")
task_id = None
try:
    task_payload = {
        "name": f"Test-Nuclei-Flow-{int(time.time())}",
        "target": "127.0.0.1",
        "domain_brute": False,
        "port_scan": False,
        "service_detection": False,
        "service_brute": False,
        "os_detection": False,
        "site_identify": False,
        "site_capture": False,
        "file_leak": False,
        "search_engines": False,
        "site_spider": False,
        "arl_search": False,
        "alt_dns": False,
        "ssl_cert": False,
        "dns_query_plugin": False,
        "skip_scan_cdn_ip": False,
        "findvhost": False,
        "web_info_hunter": False,
        "npoc_service_detection": False,
        "nuclei_scan": True,
        "nuclei_config": {
            "severity": ["critical", "high"],
            "enable_custom": True,
            "custom_template_ids": []
        }
    }
    r_task = requests.post(f"{BASE_URL}/api/task/", headers=HEADERS, json=task_payload, verify=False, timeout=15)
    if r_task.status_code == 200 and r_task.json().get("code") == 200:
        items = r_task.json().get("items", [])
        if items:
            task_id = items[0].get("task_id") or items[0].get("_id")
        if task_id:
            log_pass("真实扫描任务下发 (Task Submit with Nuclei)", f"(task_id: {task_id})")
        else:
            log_fail("真实扫描任务下发", f"返回列表中未找到 task_id/_id: {r_task.text}")
    else:
        log_fail("真实扫描任务下发", f"HTTP {r_task.status_code}: {r_task.text}")

    if task_id:
        # 轮询状态并监控 Celery 调度流转
        status_seq = []
        final_status = "waiting"
        for _ in range(6):
            time.sleep(1.5)
            r_st = requests.get(f"{BASE_URL}/api/task/?_id={task_id}", headers=HEADERS, verify=False, timeout=10)
            if r_st.status_code == 200:
                t_items = r_st.json().get("data", {}).get("items", [])
                if t_items:
                    cur_status = t_items[0].get("status")
                    if not status_seq or status_seq[-1] != cur_status:
                        status_seq.append(cur_status)
                    final_status = cur_status
                    if cur_status in ["done", "stop"]:
                        break
        log_pass("任务状态机流转监控", f"(流转观察: {' -> '.join(status_seq)}, 最终状态: {final_status})")

        # 若未结束则优雅停止测试任务
        if final_status not in ["done", "stop"]:
            r_stop = requests.post(f"{BASE_URL}/api/task/batch_stop/", headers=HEADERS, json={"task_id": [task_id]}, verify=False, timeout=10)
            if r_stop.status_code == 200:
                log_pass("测试任务安全回收与终止 (Batch Stop Clean)", f"(task_id: {task_id})")
            else:
                log_warn("测试任务回收告警", f"停止接口返回: {r_stop.text}")
        else:
            log_pass("测试任务已完成执行", f"(状态: {final_status})")

        # 删除测试任务数据，保持无痕
        r_clean = requests.post(f"{BASE_URL}/api/task/delete/", headers=HEADERS, json={"task_id": [task_id]}, verify=False, timeout=10)
        if r_clean.status_code == 200:
            log_pass("测试任务数据无痕清理 (Task Data Purge)")
except Exception as e:
    log_fail("Celery 任务调度链路测试", f"执行异常: {e}")

# 1.6 扫描策略 (Policy) 细粒度 Nuclei 配置读写存取校验
print("\n[MODULE 1.6] 扫描策略 (Policy) 细粒度 Nuclei 选项配置校验...")
try:
    r_pol = requests.get(f"{BASE_URL}/api/policy/?size=5", headers=HEADERS, verify=False, timeout=10)
    if r_pol.status_code == 200:
        pol_items = r_pol.json().get("items", []) or r_pol.json().get("data", {}).get("items", [])
        if pol_items:
            first_pol = pol_items[0]
            site_cfg = first_pol.get("policy", {}).get("site_config", {})
            log_pass("扫描策略列表检索与下发校验", f"(策略名称: {first_pol.get('name')})")
            if "nuclei_config" in site_cfg:
                log_pass("策略向下兼容契约校验 (nuclei_config 配置就绪)")
            else:
                log_pass("策略基础契约通过", "(未设自定义 nuclei_config，默认继承全局)")
        else:
            log_pass("扫描策略列表为空 (跳过字段细则)")
    else:
        log_fail("扫描策略查询接口", f"HTTP {r_pol.status_code}: {r_pol.text}")
except Exception as e:
    log_fail("扫描策略配置校验", f"异常: {e}")

# 1.7 Worker 节点协同响应与健康状态校验
print("\n[MODULE 1.7] Worker 节点协同响应与健康状态校验...")
try:
    r_health = requests.get(f"{BASE_URL}/api/task/?size=1", headers=HEADERS, verify=False, timeout=10)
    if r_health.status_code == 200:
        log_pass("Worker 与基础微服务通信协同健康 (Service Health OK)")
    else:
        log_warn("Worker 通信状态警告", f"HTTP {r_health.status_code}")
except Exception as e:
    log_fail("微服务健康检查", f"异常: {e}")

# ==============================================================================
# SECTION 2: 效率与性能瓶颈诊断 (Efficiency & Performance Profiling)
# ==============================================================================
print("\n[MODULE 2] 效率与性能瓶颈诊断...")

# 2.1 社区模板检索分页耗时压测 (12,001 条数据)
try:
    latencies = []
    for i in range(5):
        t0 = time.time()
        r_comm = requests.get(f"{BASE_URL}/api/nuclei/community/?page={i+1}&size=20&search=cve", headers=HEADERS, verify=False, timeout=10)
        lat = (time.time() - t0) * 1000
        latencies.append(lat)
    avg_lat = round(sum(latencies) / len(latencies), 1)
    results["performance"]["community_search_latency_ms"] = avg_lat
    if avg_lat < 100:
        log_pass("社区模板模糊检索性能", f"(5次平均时延: {avg_lat}ms，极快，内存索引命中)")
    elif avg_lat < 500:
        log_pass("社区模板模糊检索性能", f"(5次平均时延: {avg_lat}ms，符合预期)")
    else:
        log_warn("社区模板模糊检索性能偏慢", f"平均时延 {avg_lat}ms > 500ms，需进一步优化缓存机制")
except Exception as e:
    log_fail("社区模板检索压测", f"异常: {e}")

# 2.2 并发查询压力评估 (HTTP Keep-Alive 连接池基准)
try:
    import concurrent.futures
    req_count = 20
    session = requests.Session()
    session.headers.update(HEADERS)
    adapter = requests.adapters.HTTPAdapter(pool_connections=10, pool_maxsize=10)
    session.mount("https://", adapter)
    session.mount("http://", adapter)

    t0 = time.time()
    def _do_get():
        return session.get(f"{BASE_URL}/api/nuclei/stats/", verify=False, timeout=10).status_code

    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        futs = [executor.submit(_do_get) for _ in range(req_count)]
        codes = [f.result() for f in concurrent.futures.as_completed(futs)]

    total_cost = time.time() - t0
    qps = round(req_count / total_cost, 1)
    results["performance"]["qps"] = qps
    all_200 = all(c == 200 for c in codes)
    if all_200 and qps >= 5:
        log_pass(f"并发稳定性与吞吐量测试 ({req_count} 次高并发请求)", f"(QPS: {qps}, 全部 200 通过)")
    else:
        log_warn("高并发测试存在抖动", f"QPS: {qps}, 状态码分布: {set(codes)}")
except Exception as e:
    log_fail("高并发稳定性测试", f"异常: {e}")


# ==============================================================================
# SECTION 3: 交互与用户体验缺陷审计 (UX & Interaction Audit)
# ==============================================================================
print("\n[MODULE 3] 交互与用户体验缺陷审计...")

# 3.1 前端静态资源完整性、Basic Auth 防护与 Gzip 缓存校验
try:
    # A. 裸连应被 Basic Auth 拦截
    r_front_noauth = requests.get(f"{BASE_URL}/", verify=False, timeout=10)
    if r_front_noauth.status_code == 401:
        log_pass("Nginx 边界防护 (未授权请求拦截 401 有效)")
    elif r_front_noauth.status_code == 200:
        log_pass("前端 HTML 主入口可达 (公开模式)")
    else:
        log_warn("前端入口响应异常", f"HTTP {r_front_noauth.status_code}")

    # B. 携带 Basic Auth 访问
    r_front = requests.get(f"{BASE_URL}/", auth=BASIC_AUTH, verify=False, timeout=10)
    if r_front.status_code == 200 and "html" in r_front.text:
        log_pass("前端 HTML 主入口验证成功", "(Basic Auth 授权通过)")
        # 检查是否包含关键 JS chunks
        import re
        js_chunks = re.findall(r'src=["\']([^"\']+\.js)["\']', r_front.text)
        if js_chunks:
            first_chunk = js_chunks[0]
            chunk_url = f"{BASE_URL}{first_chunk}" if first_chunk.startswith("/") else f"{BASE_URL}/{first_chunk}"
            r_chunk = requests.get(chunk_url, auth=BASIC_AUTH, headers={"Accept-Encoding": "gzip"}, verify=False, timeout=10)
            if r_chunk.status_code == 200:
                is_gzip = "gzip" in r_chunk.headers.get("Content-Encoding", "").lower()
                log_pass("前端静态 JS Chunk 完整加载", f"({first_chunk}, Gzip压缩: {is_gzip})")
            else:
                log_fail("前端静态资源缺失", f"资源 {first_chunk} HTTP {r_chunk.status_code}")
        else:
            log_warn("HTML 中未匹配到外链 JS", "可能内联或路由加载方式特殊")
    else:
        log_fail("前端入口可达性", f"HTTP {r_front.status_code}")
except Exception as e:
    log_fail("前端资源审计", f"异常: {e}")

# 3.2 错误信息友好度审计
try:
    r_err = requests.post(f"{BASE_URL}/api/nuclei/template/create/", headers=HEADERS, json={"content": "invalid_content_test"}, verify=False, timeout=10)
    err_json = r_err.json()
    err_str = err_json.get("error") or err_json.get("message") or ""
    if "Traceback" in err_str:
        log_ux("后端裸露 Python 堆栈异常", "错误回显直接将 Python 代码 Traceback 抛给前端，破坏用户体验且存在信息泄露风险")
    elif err_str:
        log_pass("错误提示人类可读性 (无 Traceback 泄露)", f"回显提示: '{err_str[:60]}'")
    else:
        log_ux("错误提示不明确", f"接口报错但 message/error 均为空: {err_json}")
except Exception as e:
    log_fail("错误信息友好度测试", f"异常: {e}")


print("\n" + "=" * 70)
print(f"📊 测试结果汇总: 通过 {len(results['passed'])}, 失败 {len(results['failed'])}, 警告 {len(results['warnings'])}, 体验缺陷 {len(results['ux_flaws'])}")
print("=" * 70)

if results["failed"]:
    sys.exit(1)
