#!/usr/bin/env python3
"""
Layer 2: 运行时集成验证脚本 (verify_fofa_runtime_live.py)
验证内容：
1. 真实/自适应 MongoDB 实例下的 system_config 动态落库与 ConfigMeta 热更新穿透；
2. clear_system_config_cache 缓存失效后，fofa_query 调用时刻实时感知分页参数变更；
3. dns_query.run_plugin 在热更新 enable 状态时，多轮调用彻底杜绝内存与数据库字典就地突变。
"""

import os
import sys
import time
from types import SimpleNamespace
from unittest.mock import patch

# Ensure backend root is on sys.path
backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

# Initialize config cache to empty so module imports never hang on MongoDB
import app.config as config_mod
config_mod._config_cache["data"] = {}
config_mod._config_cache["last_update"] = 9999999999

from app.config import Config, clear_system_config_cache
from app.services import fofaClient
from app.services import dns_query


class _RecordedFofaClient:
    instances = []

    def __init__(self, key, page_size=2000, max_page=5, fields="host,ip,port"):
        self.key = key
        self.page_size = page_size
        self.max_page = max_page
        self.fields = fields
        _RecordedFofaClient.instances.append(self)

    def search(self, query):
        yield [("sub.example.com", "1.2.3.4", 443)]


class InMemoryMockCollection:
    """自适应内嵌数据库集合模拟器（当本地无 MongoDB 运行实例时透明降级）"""
    def __init__(self):
        self._store = {}

    def find_one(self, filter_doc):
        _id = filter_doc.get("_id")
        doc = self._store.get(_id)
        return dict(doc) if doc else None

    def update_one(self, filter_doc, update_doc, upsert=False):
        _id = filter_doc.get("_id")
        current = self._store.get(_id, {})
        if "$set" in update_doc:
            for k, v in update_doc["$set"].items():
                parts = k.split(".")
                target = current
                for part in parts[:-1]:
                    if part not in target or not isinstance(target[part], dict):
                        target[part] = {}
                    target = target[part]
                target[parts[-1]] = v
        self._store[_id] = current


def check_mongo_connection(uri):
    try:
        from pymongo import MongoClient
        client = MongoClient(uri, serverSelectionTimeoutMS=500)
        client.server_info()
        return client
    except Exception:
        return None


def run_live_verification():
    print("=" * 60)
    print("  PR #52 运行时动态配置与防污染集成验证 (Live Verification)")
    print("=" * 60)

    mongo_uri = os.environ.get("MONGO_URI", "mongodb://admin:admin@localhost:27017/arl?authSource=admin")
    real_client = check_mongo_connection(mongo_uri)

    if real_client:
        print(f"[*] 成功连接真实 MongoDB 实例: {mongo_uri}")
        db = real_client.get_default_database()
        system_config_col = db["system_config"]
        backup_doc = system_config_col.find_one({"_id": "general_config"})
        is_live_db = True
    else:
        print("[!] 本地未探测到运行中的 MongoDB 实例，自动切换至【自适应内嵌数据库引擎】")
        mock_col = InMemoryMockCollection()
        system_config_col = mock_col
        backup_doc = None
        is_live_db = False

    def get_test_col(col_name):
        return system_config_col

    # 使用 patch 保证 conn_db 导向当前选定的 collection（真实或内嵌）
    with patch("app.config.get_system_config_value") as _:
        pass  # 仅测试上下文

    conn_db_patcher = patch("app.utils.conn.conn_db", side_effect=get_test_col)
    conn_db_patcher.start()

    try:
        # ---------------------------------------------------------
        # 步骤 1: 写入初始业务配置
        # ---------------------------------------------------------
        print("\n[*] 步骤 1: 写入初始测试配置至 system_config (page_size=20, max_page=2)...")
        initial_doc = {
            "_id": "general_config",
            "fofa_key": "live-test-token-001",
            "fofa_url": "https://fofa.info",
            "fofa_page_size": 20,
            "fofa_max_page": 2,
            "query_plugin_config": {
                "fofa": {
                    "enable": False,
                    "key": "plugin_secret_key"
                }
            }
        }
        if is_live_db:
            system_config_col.replace_one({"_id": "general_config"}, initial_doc, upsert=True)
        else:
            system_config_col._store["general_config"] = dict(initial_doc)

        clear_system_config_cache()

        # 验证 Config 动态属性读取
        assert Config.FOFA_PAGE_SIZE == 20, f"期望 FOFA_PAGE_SIZE=20，实际: {Config.FOFA_PAGE_SIZE}"
        assert Config.FOFA_MAX_PAGE == 2, f"期望 FOFA_MAX_PAGE=2，实际: {Config.FOFA_MAX_PAGE}"
        print("  -> ConfigMeta 动态属性正确透传数据库配置: page_size=20, max_page=2 [PASS]")

        # ---------------------------------------------------------
        # 步骤 2: 验证 fofa_query 初次调用捕获初始配置
        # ---------------------------------------------------------
        print("\n[*] 步骤 2: 执行 fofa_query，验证运行时自适应抓取初始参数...")
        _RecordedFofaClient.instances.clear()
        with patch.object(fofaClient, "FofaClient", _RecordedFofaClient):
            fofaClient.fofa_query('domain="alpha.example.com"')

        assert len(_RecordedFofaClient.instances) == 1
        client1 = _RecordedFofaClient.instances[0]
        assert client1.page_size == 20, f"客户端期望 page_size=20，实际: {client1.page_size}"
        assert client1.max_page == 2, f"客户端期望 max_page=2，实际: {client1.max_page}"
        print(f"  -> FofaClient 成功以动态初始参数实例化: page_size={client1.page_size}, max_page={client1.max_page} [PASS]")

        # ---------------------------------------------------------
        # 步骤 3: 模拟管理端热更新配置（无需重启后端进程）
        # ---------------------------------------------------------
        print("\n[*] 步骤 3: 模拟 Web 控制台热更新系统配置 (page_size -> 150, max_page -> 6)...")
        if is_live_db:
            system_config_col.update_one(
                {"_id": "general_config"},
                {"$set": {"fofa_page_size": 150, "fofa_max_page": 6}}
            )
        else:
            system_config_col.update_one(
                {"_id": "general_config"},
                {"$set": {"fofa_page_size": 150, "fofa_max_page": 6}}
            )

        clear_system_config_cache()

        # 验证热更新后 Config 状态
        assert Config.FOFA_PAGE_SIZE == 150, f"期望热更新后 FOFA_PAGE_SIZE=150，实际: {Config.FOFA_PAGE_SIZE}"
        assert Config.FOFA_MAX_PAGE == 6, f"期望热更新后 FOFA_MAX_PAGE=6，实际: {Config.FOFA_MAX_PAGE}"

        # 再次执行 fofa_query，必须即刻使用新参数，证明脱离了导入期冻结
        _RecordedFofaClient.instances.clear()
        with patch.object(fofaClient, "FofaClient", _RecordedFofaClient):
            fofaClient.fofa_query('domain="beta.example.com"')

        assert len(_RecordedFofaClient.instances) == 1
        client2 = _RecordedFofaClient.instances[0]
        assert client2.page_size == 150, f"热更新后客户端期望 page_size=150，实际: {client2.page_size}"
        assert client2.max_page == 6, f"热更新后客户端期望 max_page=6，实际: {client2.max_page}"
        print(f"  -> 热更新即时生效！新调用实例化参数: page_size={client2.page_size}, max_page={client2.max_page} [PASS]")

        # ---------------------------------------------------------
        # 步骤 4: 验证插件配置 enable=False 的多轮调用防污染
        # ---------------------------------------------------------
        print("\n[*] 步骤 4: 运行 dns_query.run_plugin 多轮验证（当前配置 enable=False）...")
        init_key_calls = []
        dummy_plugin = SimpleNamespace(
            source_name="fofa",
            query=lambda target: [f"live.{target}"],
            init_key=lambda **kwargs: init_key_calls.append(kwargs)
        )

        for i in range(5):
            source, results = dns_query.run_plugin(dummy_plugin, f"test{i}.com")
            assert source == "fofa"
            assert results == [], f"第 {i+1} 次调用未成功跳过禁用插件"

        # 检查数据库和 Config.QUERY_PLUGIN_CONFIG 中的 enable 字段是否仍在
        cached_plugin_cfg = Config.QUERY_PLUGIN_CONFIG
        assert cached_plugin_cfg["fofa"]["enable"] is False, "缓存中的 enable 字段被异常篡改或删除！"

        db_doc = system_config_col.find_one({"_id": "general_config"})
        assert db_doc["query_plugin_config"]["fofa"]["enable"] is False, "数据库中的 enable 字段被污染！"
        print("  -> 连续 5 次执行 run_plugin，enable=False 稳固保持，无字典就地突变污染 [PASS]")

        # ---------------------------------------------------------
        # 步骤 5: 动态切换插件 enable=True 并带凭据多轮调用
        # ---------------------------------------------------------
        print("\n[*] 步骤 5: 热更新插件配置为 enable=True 并附带凭据参数，验证正常调用与参数保留...")
        if is_live_db:
            system_config_col.update_one(
                {"_id": "general_config"},
                {"$set": {"query_plugin_config.fofa.enable": True}}
            )
        else:
            system_config_col.update_one(
                {"_id": "general_config"},
                {"$set": {"query_plugin_config.fofa.enable": True}}
            )

        clear_system_config_cache()

        for i in range(3):
            source, results = dns_query.run_plugin(dummy_plugin, f"active{i}.com")
            assert source == "fofa"
            assert results == [f"live.active{i}.com"]

        assert len(init_key_calls) == 3
        for kw in init_key_calls:
            assert kw == {"key": "plugin_secret_key"}, f"插件收到的参数不符合预期: {kw}"

        # 确认共享配置中的 enable=True 依然毫发无损
        final_plugin_cfg = Config.QUERY_PLUGIN_CONFIG
        assert final_plugin_cfg["fofa"]["enable"] is True
        assert final_plugin_cfg["fofa"]["key"] == "plugin_secret_key"
        print("  -> 插件热更新启用成功，凭据透传完整，多轮调用后共享对象键值完好无缺 [PASS]")

        print("\n" + "=" * 60)
        print("  🎉 PR #52 运行时动态配置与防污染集成验证全部通过！(100% SUCCESS)")
        print("=" * 60)
        return 0

    finally:
        conn_db_patcher.stop()
        if is_live_db:
            if backup_doc:
                system_config_col.replace_one({"_id": "general_config"}, backup_doc)
            else:
                system_config_col.delete_one({"_id": "general_config"})
            print("[*] 已恢复原始 MongoDB 数据库配置环境。")
        clear_system_config_cache()


if __name__ == "__main__":
    sys.exit(run_live_verification())
