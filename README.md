<div align="center">

  # ARL-Next
  **自动化资产侦察与漏洞监控平台**

  <p>
    <a href="https://github.com/owl234/arl-next/actions"><img src="https://img.shields.io/github/actions/workflow/status/owl234/arl-next/ci.yml?style=flat-square&logo=github&label=Build" alt="build"></a>
    <a href="https://hub.docker.com/"><img src="https://img.shields.io/badge/docker-ready-blue.svg?style=flat-square&logo=docker" alt="Docker"></a>
    <a href="https://github.com/owl234/arl-next/releases"><img src="https://img.shields.io/github/v/release/owl234/arl-next?style=flat-square&color=success" alt="Release"></a>
    <img src="https://img.shields.io/badge/python-3.8%2B-blue?style=flat-square&logo=python" alt="Python">
    <img src="https://img.shields.io/badge/vue-3.x-4fc08d?style=flat-square&logo=vuedotjs" alt="Vue">
  </p>

  [**English**](./README_EN.md) | [**本地开发教程**](./docs/local_dev_guide.md) | [**更新日志**](./CHANGELOG.md) | [**在线文档**](https://your-doc-link.com)
</div>

<br/>

---

## 💡 什么是 ARL-Next？

ARL-Next 旨在为安全团队及红蓝对抗工程师提供一套开箱即用的资产监控与漏洞发现平台。它将资产发现、端口扫描、指纹识别到漏洞探测融为一体，并通过 Vue 3 控制台呈现全局安全态势。

## 🤝 致谢与声明

**ARL-Next** 是基于开源项目 [ARL (Asset Reconnaissance Lighthouse) 资产侦察灯塔](https://github.com/TophantTechnology/ARL) 进行重构与二次开发的增强版本。

我们对原 ARL 开发团队为信息安全开源社区做出的巨大贡献表示最诚挚的感谢！本着开源互助的精神，ARL-Next 将继续遵循开源精神。

### 🌟 为什么要重构 ARL-Next？

随着网络环境的演变，我们对原项目进行了现代化改造，以解决部分历史痛点：

* **前端栈升级**：重构前端，基于 Vue 3 + 现代 UI 框架构建，提供更流畅的交互体验。
* **部署架构解耦**：引入全面的 Docker 化构建流程，支持自动化部署与数据卷解耦持久化。
* **中间件替换**：将消息中间件从 RabbitMQ 迁移至 Redis，彻底解决高并发场景下的连接池异常与版本兼容问题。

---

## ✨ 核心特性

* **前后端分离架构**
  前端基于 Vue 3 + Vite 构建 SPA 面板，后端依托 Python 3.8+ 与 Flask 提供 RESTful API，提高交互体验和二次开发扩展性。
* **高并发异步调度**
  以 **Redis** 为消息中枢并开启 AOF 持久化，配合 Celery 分布式工作节点为执行引擎。在保持极高吞吐量的同时，享受轻量级内存占用。支持将核心扫描 Worker 和专门的 GitHub 敏感信息监控 Worker 分散部署。
* **现代 Web 无头渲染**
  重构底层截图与指纹探测引擎，使用 Chromium 与 Puppeteer 替代 PhantomJS。支持 React、Vue 等 SPA（单页面应用）截图和 Wappalyzer 指纹解析，内置中文字库解决乱码问题。
* **漏洞探测与资产梳理**
  内置不断更新的 PoC 武器库，并对接 FOFA 等第三方资产引擎。结合指纹识别与端口扫描，实现自动化资产收集与探测。

---

## 🏗️ 架构设计

ARL-Next 采用微服务容器编排设计：

1. **安全网关与展示层 (Frontend)**：基于 Vite 构建前端代理与静态资源托管。
2. **业务逻辑层 (Backend)**：基于 Flask，负责接收前端指令、操作 MongoDB 数据库。
3. **消息总线 (Broker)**：**Redis** 承担任务排队、状态分发工作，通过 AOF 保证数据可靠性。
4. **异步执行层 (Workers)**：核心节点 (worker)、GitHub 监控节点 (worker-github) 与定时调度器 (scheduler) 协同处理高耗时扫描任务。
5. **持久化存储 (Database)**：MongoDB 负责海量扫描结果与资产数据的落地。

---

## 🚀 部署指南

我们为开发者提供了两套部署方案，满足从二次开发到生产环境的不同需求。

### 方案 A：纯本地开发流 (推荐开发者使用)

如果你想对 ARL-Next 进行二次开发、调试接口或修改前端 UI，我们极度推荐你使用这套**无 Docker** 的本地运行方案。支持“保存代码，瞬间生效”的热重载体验。

📖 **[点此查看：从零开始的本地开发与调试教程 (macOS/Windows)](./docs/local_dev_guide.md)**

环境准备完毕后，启动开发环境只需在根目录执行：
```bash
bash start_local.sh
```

---

### 方案 B：生产环境部署 (Docker Compose)

如果你只想在服务器上快速跑起来，可以使用 Docker Compose 进行部署。系统通过 Docker Volumes 自动持久化 MongoDB 数据与资产截图，防止容器重启造成数据丢失。

```bash
# 1. 克隆代码并进入目录
git clone https://github.com/owl234/arl-next
cd arl-next

# 2. (首次部署必做) 生成安全的随机密码并写入 .env 文件
chmod +x init_env.sh
./init_env.sh

# 3. 启动所有服务容器
docker-compose -f docker-compose.test.yml build
docker-compose -f docker-compose.test.yml up -d
```
*提示：初始账号密码如果在 `init_env.sh` 中未被覆盖，默认为 `admin` / `arlpass`。*

---

## 🗄️ 数据库直连指引 (可选)

开发期间如需直连数据库查看数据，可使用以下参数（如果是通过 Docker 启动，需确保暴露了相应端口）：

**MongoDB 核心数据库**
* **Host:** `127.0.0.1`
* **Port:** `27017`
* **认证库 (Database):** `admin`
*(业务数据均存储在 `ARLV2` 数据库中)*

**Redis 消息队列**
* **Host:** `127.0.0.1`
* **Port:** `6379`
* **认证:** 无密码，连接 `db: 0` 即可。

---

## ⚠️ 声明与免责

本工具仅面向合法授权的企业安全建设、SRC 漏洞挖掘以及安全研究学术交流。
使用本工具进行资产扫描与漏洞探测时，请务必遵守当地法律法规（如《中华人民共和国网络安全法》）及目标平台的测试范围规定。未经授权对目标进行探测属非法行为。使用者因使用本工具造成的任何直接或间接的法律责任与后果，由使用者自行承担，项目作者及贡献者不负任何连带责任。

---

## 🌟 Star History

<div align="center">

<a href="https://github.com/owl234/arl-next/stargazers">
  <img src="https://img.shields.io/github/stars/owl234/arl-next?style=for-the-badge&logo=github&logoColor=white&label=Stars&color=FFD700&labelColor=1a1a2e" alt="GitHub Stars">
</a>

<br/>

[![Star History Chart](https://api.star-history.com/svg?repos=owl234/arl-next&type=Date)](https://star-history.com/#owl234/arl-next&Date)

</div>
