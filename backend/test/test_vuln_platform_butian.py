# backend/tests/test_butian.py
"""
补天平台适配器单元测试
运行：
    cd backend && pytest tests/test_butian.py -v -s
"""

import os
import sys
import json

import pytest

# 添加项目路径
BACKEND_DIR = os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BACKEND_DIR)


# ═══════════════════════════════════════════════════════════
# 解析逻辑测试（不需要网络）
# ═══════════════════════════════════════════════════════════

class TestBuTianParse:
    """解析逻辑测试（纯函数，无网络请求）"""

    @pytest.fixture
    def adapter(self):
        from app.adapters.vuln_platform.butian import BuTianAdapter
        return BuTianAdapter()

    def test_collect_projects_normal(self, adapter):
        """正常数据解析"""
        items = [
            {
                "company_id": "65526",
                "company_name": "全讯汇聚网络科技(北京)有限公司",
                "avatar": "https://example.com/1.jpg"
            },
            {
                "company_id": "65461",
                "company_name": "北京中教互联教育科技有限公司",
                "avatar": "https://example.com/2.jpg"
            },
        ]
        projects = []
        seen_ids = set()

        adapter._collect_projects(items, projects, seen_ids)

        assert len(projects) == 2
        assert projects[0]["project_id"] == "65526"
        assert projects[0]["project_name"] == "全讯汇聚网络科技(北京)有限公司"
        assert projects[0]["platform"] == "butian"
        assert projects[0]["avatar"] == "https://example.com/1.jpg"

    def test_collect_projects_dedup(self, adapter):
        """去重测试"""
        items = [
            {"company_id": "65526", "company_name": "公司A"},
            {"company_id": "65526", "company_name": "公司A重复"},
            {"company_id": "65461", "company_name": "公司B"},
        ]
        projects = []
        seen_ids = set()

        adapter._collect_projects(items, projects, seen_ids)

        # 应该只保留 2 个（去重后）
        assert len(projects) == 2
        assert projects[0]["project_id"] == "65526"
        assert projects[1]["project_id"] == "65461"

    def test_collect_projects_empty_id(self, adapter):
        """空 ID 跳过"""
        items = [
            {"company_id": "", "company_name": "空ID"},
            {"company_id": "65526", "company_name": "正常"},
        ]
        projects = []
        seen_ids = set()

        adapter._collect_projects(items, projects, seen_ids)

        assert len(projects) == 1
        assert projects[0]["project_id"] == "65526"

    def test_collect_projects_missing_name(self, adapter):
        """缺少名称时用默认值"""
        items = [
            {"company_id": "65526"},   # 无 name
        ]
        projects = []
        seen_ids = set()

        adapter._collect_projects(items, projects, seen_ids)

        assert len(projects) == 1
        assert projects[0]["project_id"] == "65526"
        assert "补天项目" in projects[0]["project_name"]

    def test_extract_scope_domains(self, adapter):
        """域名提取"""
        html = """
        <div>域名：example.com, test.example.com</div>
        <div>目标：*.demo.com</div>
        """
        scope = adapter._extract_scope(html)

        assert "example.com" in scope
        assert "test.example.com" in scope
        assert "*.demo.com" in scope

    def test_extract_scope_ips(self, adapter):
        """IP 提取"""
        html = """
        <div>IP：1.2.3.4</div>
        <div>服务器：192.168.1.1</div>
        """
        scope = adapter._extract_scope(html)

        assert "1.2.3.4" in scope
        assert "192.168.1.1" in scope

    def test_extract_scope_empty(self, adapter):
        """无范围时返回空列表"""
        html = "<div>没有范围信息</div>"
        scope = adapter._extract_scope(html)
        assert scope == []


# ═══════════════════════════════════════════════════════════
# 配置测试
# ═══════════════════════════════════════════════════════════

class TestBuTianConfig:
    """配置测试"""

    def test_config_loaded(self):
        from app.adapters.vuln_platform.config import (
            PLATFORM_CONFIG, get_platform_config,
        )
        cfg = get_platform_config("butian")

        assert cfg["name"] == "补天平台"
        assert cfg["base_url"] == "https://www.butian.net"
        assert cfg["requires_login"] is True
        assert cfg["rate_limit"] == "6/m"
        assert cfg["default_delay"] == 5.0

    def test_adapter_init(self):
        from app.adapters.vuln_platform.butian import BuTianAdapter
        adapter = BuTianAdapter()

        assert adapter.platform_name == "butian"
        assert adapter.config["name"] == "补天平台"
        # Cookie 管理器应该存在（requires_login=True）
        assert adapter.cookie_mgr is not None
        # 合规检查器应该存在
        assert adapter.compliance is not None

    def test_cookie_loaded(self):
        from app.adapters.vuln_platform.butian import BuTianAdapter
        adapter = BuTianAdapter()

        cookie = adapter.cookie_mgr.cookie_string
        print("\nCookie 长度: {}".format(len(cookie) if cookie else 0))

        if not cookie:
            pytest.skip("未配置补天 Cookie")
        assert "PHPSESSID" in cookie or "session" in cookie.lower()


# ═══════════════════════════════════════════════════════════
# 网络请求测试（需要真实 Cookie 和代理）
# ═══════════════════════════════════════════════════════════

class TestBuTianNetwork:
    """网络请求测试（默认跳过，需 --run-network 启用）"""

    @pytest.fixture
    def adapter(self):
        from app.adapters.vuln_platform.butian import BuTianAdapter
        adapter = BuTianAdapter()

        if not adapter.cookie_mgr or not adapter.cookie_mgr.cookie_string:
            pytest.skip("未配置 Cookie，跳过网络测试")
        return adapter

    def test_fetch_first_page(self, adapter):
        """测试抓取第 1 页"""
        data = adapter._fetch_page_json(1)

        assert data is not None, "第 1 页请求失败"
        assert data.get("status") == 1, "响应状态异常"
        assert "data" in data

        inner = data["data"]
        assert "count" in inner, "缺少 count（总页数）"
        assert "list" in inner, "缺少 list（数据列表）"
        assert len(inner["list"]) > 0, "列表为空"

        print("\n✓ 总页数: {}".format(inner["count"]))
        print("✓ 第 1 页条数: {}".format(len(inner["list"])))
        print("✓ 前 3 条:")
        for item in inner["list"][:3]:
            print("  - {} {}".format(
                item.get("company_id"), item.get("company_name")))

    def test_fetch_projects_limited(self, adapter):
        """测试抓取少量页"""
        projects = adapter.fetch_projects(max_pages=2, concurrency=2)

        assert len(projects) > 0, "未获取到项目"
        assert all(p["platform"] == "butian" for p in projects)
        assert all(p["project_id"] for p in projects)

        print("\n✓ 共抓取 {} 个项目".format(len(projects)))

    def test_fetch_scope(self, adapter):
        """测试获取项目范围"""
        # 先拿一个项目 ID
        projects = adapter.fetch_projects(max_pages=1, concurrency=1)
        if not projects:
            pytest.skip("未获取到项目")

        project_id = projects[0]["project_id"]
        scope = adapter.fetch_scope(project_id)

        print("\n✓ 项目 {} 范围: {} 个".format(project_id, len(scope)))
        for s in scope[:5]:
            print("  - {}".format(s))


# ═══════════════════════════════════════════════════════════
# 代理测试
# ═══════════════════════════════════════════════════════════

class TestBuTianProxy:
    """代理相关测试"""

    def test_proxy_warmup(self):
        """测试代理预热"""
        from app.utils.proxy_cache import proxy_cache
        from app.utils.proxy_client import proxy_client

        status = proxy_client.get_status()
        if not status["online"]:
            pytest.skip("代理池未启动")
        if status["count"] == 0:
            pytest.skip("代理池为空")

        target_url = "https://www.butian.net/Reward/pub"
        count = proxy_cache.warmup(target_url=target_url, size=5)

        print("\n✓ 预热完成: {} 个代理".format(count))
        print("✓ 代理列表: {}".format(
            proxy_cache.get_proxies(target_url)))

        assert count >= 0


# ═══════════════════════════════════════════════════════════
# pytest 命令行选项
# ═══════════════════════════════════════════════════════════

def pytest_addoption(parser):
    parser.addoption(
        "--run-network", action="store_true", default=False,
        help="运行需要网络请求的测试")


def pytest_configure(config):
    config.addinivalue_line("markers", "network: 需要网络的测试")


def pytest_collection_modifyitems(config, items):
    if not config.getoption("--run-network"):
        skip_network = pytest.mark.skip(
            reason="需要 --run-network 启用")
        for item in items:
            if "TestBuTianNetwork" in item.nodeid:
                item.add_marker(skip_network)