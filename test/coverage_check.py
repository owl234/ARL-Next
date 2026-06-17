#!/usr/bin/env python3
"""
coverage_check.py
=================
从路由文件中提取所有注册的 @ns.route() 端点，
再扫描测试文件中调用的 URL，输出覆盖差距报告。
"""
import os
import re
from pathlib import Path

ROUTES_DIR = Path("/Users/sienchen/Documents/arl-pro/backend/app/routes")
TEST_DIR   = Path("/Users/sienchen/Documents/arl-pro/test")

# ─────────────────────────────────────────────────────
# 1. 从路由文件提取所有 Namespace + route 组合
# ─────────────────────────────────────────────────────
def extract_routes(routes_dir: Path) -> list[dict]:
    results = []

    for pyfile in sorted(routes_dir.glob("*.py")):
        if pyfile.name.startswith("_"):
            continue

        src = pyfile.read_text(encoding="utf-8", errors="ignore")

        # 提取 Namespace 名称：ns = Namespace('xxx', ...)
        ns_match = re.search(r"Namespace\(['\"](\w+)['\"]", src)
        ns_name = ns_match.group(1) if ns_match else pyfile.stem

        # 提取所有 @ns.route('xxx') 装饰器
        for m in re.finditer(r"@ns\.route\(['\"]([^'\"]+)['\"]", src):
            route_path = m.group(1)
            full_path = f"/api/{ns_name}{route_path}"
            # 提取下方 def get/post/put/delete
            after = src[m.end():]
            methods = re.findall(r"^\s+def (get|post|put|delete|patch)\b", after[:300], re.MULTILINE)
            results.append({
                "file": pyfile.name,
                "namespace": ns_name,
                "route": route_path,
                "full_path": full_path,
                "methods": [m.upper() for m in methods] or ["GET"],
            })

    return results


# ─────────────────────────────────────────────────────
# 2. 从测试文件提取所有调用的 URL 片段
# ─────────────────────────────────────────────────────
def extract_tested_urls(test_dir: Path) -> set[str]:
    tested = set()
    patterns = [
        # api_client.get(f"{BASE_URL}/xxx/yyy/")
        r'api_client\.\w+\(f?["\{].*?BASE_URL[}]?/([^\s"\'\\{]+)',
        # requests.get(f"{BASE_URL}/xxx")
        r'requests\.\w+\(f?["\{].*?BASE_URL[}]?/([^\s"\'\\{]+)',
    ]
    for testfile in sorted(test_dir.glob("test_api_*.py")):
        src = testfile.read_text(encoding="utf-8", errors="ignore")
        for pat in patterns:
            for m in re.finditer(pat, src):
                path_frag = m.group(1).rstrip("/").rstrip('"').rstrip("'")
                # 去掉变量插值部分，只保留静态前缀
                path_frag = re.sub(r'\{[^}]+\}.*', '', path_frag).rstrip("/")
                if path_frag:
                    tested.add("/api/" + path_frag)
    return tested


# ─────────────────────────────────────────────────────
# 3. 对比 & 输出报告
# ─────────────────────────────────────────────────────
def check_coverage():
    all_routes = extract_routes(ROUTES_DIR)
    tested_urls = extract_tested_urls(TEST_DIR)

    print(f"\n{'='*70}")
    print(f"  ARL-PRO API 覆盖度检查报告")
    print(f"{'='*70}")
    print(f"  路由文件总计注册端点数：{len(all_routes)}")
    print(f"  测试文件中识别到的 URL 数：{len(tested_urls)}")
    print(f"{'='*70}\n")

    covered = []
    uncovered = []

    for r in all_routes:
        fp = r["full_path"]
        # 把路径变量（<string:xxx>）替换成通配符后比对
        fp_generic = re.sub(r'<[^>]+>', '*', fp).rstrip("/")
        base_prefix = fp_generic.split('*')[0].rstrip("/")

        hit = False
        for url in tested_urls:
            url_clean = url.rstrip("/")
            if url_clean == fp_generic:
                hit = True
                break
            # 前缀命中（测试中可能含更多路径段）
            if base_prefix and url_clean.startswith(base_prefix):
                hit = True
                break

        if hit:
            covered.append(r)
        else:
            uncovered.append(r)

    # 打印已覆盖
    print(f"✅ 已覆盖端点（{len(covered)} 个）")
    print("-" * 70)
    for r in covered:
        methods_str = "/".join(r["methods"])
        print(f"  [{methods_str:12s}] {r['full_path']:<55} ({r['file']})")

    # 打印未覆盖
    print(f"\n❌ 未覆盖端点（{len(uncovered)} 个）")
    print("-" * 70)
    if uncovered:
        for r in uncovered:
            methods_str = "/".join(r["methods"])
            print(f"  [{methods_str:12s}] {r['full_path']:<55} ({r['file']})")
    else:
        print("  (全部覆盖！)")

    # 统计
    total = len(all_routes)
    cov_count = len(covered)
    pct = cov_count / total * 100 if total else 0
    print(f"\n{'='*70}")
    print(f"  覆盖率：{cov_count}/{total}  ({pct:.1f}%)")
    print(f"{'='*70}\n")

    # 同时打印测试文件识别到的所有 URL（供调试）
    print("📋 测试文件中识别到的所有 URL（去重）：")
    print("-" * 70)
    for u in sorted(tested_urls):
        print(f"  {u}")


if __name__ == "__main__":
    check_coverage()
