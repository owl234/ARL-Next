# 🚀 ARL-PRO (Asset Reconnaissance Lighthouse Professional)

> **专为实战而生：下一代全自动化、分布式的资产侦察与漏洞挖掘工作站。**

![License](https://img.shields.io/badge/license-MIT-blue.svg)
![Vue](https://img.shields.io/badge/Vue.js-3.x-4FC08D.svg)
![Python](https://img.shields.io/badge/Python-3.8+-blue.svg)
![Docker](https://img.shields.io/badge/Docker-Ready-2496ED.svg)
![Build](https://img.shields.io/github/actions/workflow/status/owl234/arl-pro/ci.yml?label=CI%2FCD)

---

## 📖 关于项目 (About)

在竞争激烈的 Bug Bounty 生态（如 HackerOne、Intigriti 及各大企业 SRC）中，时间就是赏金。传统的资产扫描工具往往面临着部署繁琐、架构老旧、难以进行分布式横向扩展等痛点。

**ARL-PRO** 是对原版 ARL 的深度重构与架构革新。它不仅仅是一个扫描器，更是一套**高度自动化的 0-day 挖掘与资产监控流水线**。通过彻底的前后端分离与容器化改造，结合坚如磐石的 CI/CD 集成，ARL-PRO 让你能够将扫描节点静默部署在全球的 VPS 上，轻松绕过网络限制，实现 24/7 全天候的自动化资产侦察。释放双手，让系统为你创造稳定的漏洞挖掘收益。

---

## ✨ 核心特性 (Features)

* **🔥 现代化前后端分离架构**
  彻底告别臃肿。前端基于 Vue 3 + Vite 构建现代化 SPA 面板，后端依托 Python 3.8+ 与 Flask 提供纯粹的 RESTful API。这带来了毫秒级的交互体验和极佳的二次开发扩展性。

* **⚡ 全自动 CI/CD 敏捷交付**
  时间应该花在挖掘逻辑上，而不是运维上。本项目已完全打通 GitHub Actions 自动化流水线。代码一经 Push，系统自动在云端构建不可变的纯净 Docker 镜像，并跨网络全自动部署到你的生产节点，实现基础设施的“丝滑热更”。

* **🌍 生产级分布式调度与高并发**
  以 RabbitMQ 为消息中枢，Celery 分布式工作节点为执行引擎。你可以轻松将核心扫描 Worker 和专门的 GitHub 敏感信息监控 Worker 分散部署，实现真正的高并发多节点协同扫描。

* **⚔️ 硬核武器库无缝集成**
  内置庞大且不断更新的 ARL-NPoC 武器库，并无缝对接 FOFA 等第三方资产引擎。结合资产梳理、指纹识别、端口扫描，实现从“发现资产”到“自动打出 Payload”的完整闭环。

* **🛡️ 7x24 高可用与容灾监控**
  生产环境编排全面引入 `restart: always` 容灾策略。即使遭遇宿主机意外重启或高负载崩溃，数据库与核心节点也能自动拉起恢复，保障无人值守监控的绝对稳定。

---

## 🏗️ 架构设计 (Architecture)

ARL-PRO 采用经典且强健的微服务容器编排设计，数据流转清晰高效：

1.  **网关与展示层 (Frontend)**：Nginx 承载 Vue3 编译后的静态资源，并将 API 请求反向代理穿透至后端。
2.  **业务逻辑层 (Backend)**：Gunicorn 驱动的 Flask 应用，负责接收前端指令、操作 MongoDB 数据库，并将重量级扫描任务分发至消息队列。
3.  **消息总线 (Broker)**：RabbitMQ 承担任务排队与状态分发的高吞吐工作。
4.  **异步执行层 (Workers)**：
   * **核心节点 (worker)**：执行耗时的端口探测、指纹识别、漏洞扫描。
   * **GitHub 监控节点 (worker-github)**：常驻监听，捕捉源码与凭证泄露。
   * **定时调度器 (scheduler)**：精准触发周期性自动化监控计划。
5.  **持久化存储 (Database)**：MongoDB 负责海量扫描结果与配置资产的落地存储。

---

## 🚀 极速部署 (Quick Start)

我们为开发者提供了两套编排方案，以平衡“开发效率”与“生产稳定”。

### 方案 A：本地极速迭代调试流 (Local Development)

适用于二次开发、编写 PoC 与前后端联调。采用热重载机制，代码修改浏览器/接口即刻生效，互不干扰。

```bash
git clone [https://github.com/owl234/arl-pro.git](https://github.com/owl234/arl-pro.git)
cd arl-pro

# 1. 单独构建本地镜像，一键拉起后端底座（挂载本地源码，暴露 5003 端口供 Vite 代理）
docker-compose -f docker-compose.local.yml build backend
docker-compose -f docker-compose.local.yml up -d backend worker worker-github scheduler mongodb rabbitmq


# 2. 另起终端，原生启动前端开发服务器（享受 Vite 极速 HMR）
cd frontend
npm install -g pnpm
pnpm install
pnpm add -D vite@5 @vitejs/plugin-vue@5
pnpm run dev
```
### 方案 B：生产环境全自动 CI/CD 流 (Production)

适用于部署到 VPS 监控节点的正式环境，实现纯净镜像运行和无人值守的 24/7 监控。

**1. 配置生产节点环境：**

在干净的 Ubuntu 生产节点执行初始化脚本：

```bash
chmod +x init_ubuntu_env.sh
./init_ubuntu_env.sh
```
**2. 注册 GitHub Runner：**

在仓库 Settings -> Actions -> Runners 中绑定该节点，并为其打上专属标签（如 laptop）。

**3. 享受全自动部署：**

在本地修改代码后，只需执行 git push 到 main 分支。GitHub Actions 流水线 (ci.yml) 将自动构建纯净的 Docker 镜像，下发至 VPS，并使用 docker-compose.test.yml 自动重启服务（请确保 VPS 已放行 80 端口）。

**初始账号密码：** admin / arlpass （登录后请立即修改）


## 📸 界面预览 (Screenshots)
精美的现代化控制台，让复杂的数据一目了然。


## ⚠️ 声明与免责 (Disclaimer)
本工具（ARL-PRO）仅面向合法授权的企业安全建设、SRC 漏洞挖掘以及安全研究学术交流。

使用本工具进行资产扫描与漏洞探测时，请务必遵守当地法律法规（如《中华人民共和国网络安全法》）及目标平台的测试范围规定。

未经授权对目标进行探测属非法行为。使用者因使用本工具造成的任何直接或间接的法律责任与后果，由使用者自行承担，项目作者及贡献者不负任何连带责任。