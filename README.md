# ARL-PRO (资产侦察灯塔系统进阶版)

![License](https://img.shields.io/badge/license-MIT-blue.svg)
![Vue](https://img.shields.io/badge/Vue.js-3.x-4FC08D.svg)
![Python](https://img.shields.io/badge/Python-3.8+-blue.svg)
![Docker](https://img.shields.io/badge/Docker-Ready-2496ED.svg)
![Build](https://img.shields.io/github/actions/workflow/status/owl234/arl-pro/deploy-laptop.yml?label=CI%2FCD)

ARL-PRO 是对原版 ARL（Asset Reconnaissance Lighthouse）的全面重构与进阶版本，旨在提供更加现代化、高并发和高度自动化的资产侦察与漏洞扫描功能。系统采用前后端完全分离架构，内置丰富的 ARL-NPoC 武器库、GitHub 敏感信息监控模块，并打通了 GitHub Actions 自动化 CI/CD 部署流水线，为安全研究人员提供持续、稳定的 0-day 挖掘与资产监控能力。

---

## 1. 整体功能和架构梳理

系统采用微服务化的容器编排设计，根据 `docker-compose` 的配置，整个系统主要由以下核心服务构成：

* **前端服务 (frontend)**：基于 **Vue 3** 和 **Vite** 构建。提供现代化的单页面应用 (SPA) 界面，运行在 Nginx 容器中。
* **后端 Web API 服务 (backend)**：基于 **Python**、**Flask** 和 **Flask-RESTX** 开发。提供 RESTful API，处理用户请求、数据查询和任务调度，通过 Gunicorn 运行。
* **核心扫描节点 (worker)**：基于 **Celery** 的分布式工作节点，负责执行重量级的资产收集和扫描任务（如域名枚举、端口扫描、漏洞探测等）。
* **GitHub 监控节点 (worker-github)**：专门用于监控 GitHub 源码泄露和敏感信息的独立 Celery 节点。
* **定时调度器 (scheduler)**：处理周期性任务和计划任务的分布式调度模块。
* **消息队列 (rabbitmq)**：作为 Celery 的 Broker，负责后端 API、Scheduler 与各个 Worker 之间的任务消息传递。
* **数据库引擎 (mongodb)**：存储各种扫描结果、资产数据、指纹信息及任务状态等持久化数据。

## 2. 技术栈总结

* **前端生态**：Vue 3, Vite, Ant Design Vue, Vue Router, Axios
* **后端生态**：Python 3, Flask, Flask-RESTX, Gunicorn
* **分布式/高并发**：Celery, RabbitMQ
* **持久化存储**：MongoDB
* **DevOps/部署**：Docker, Docker Compose, GitHub Actions, Shell 自动化

---

## 3. 🚀 部署方式一：生产环境 CI/CD 自动部署 (强烈推荐)

本系统全面打通了 CI/CD 自动化流水线。只需在一台纯净的 Ubuntu 服务器/虚拟机上执行以下三步，后续的所有构建、运行与端口放行均由流水线接管。

> **⚠️ 开发者必看（流水线配置更新）**：
> 生产环境默认使用 `docker-compose.test.yml`，直接映射宿主机 80 端口。请确保 GitHub 流水线中执行的是 `test.yml`。

### Step 1: 节点环境一键初始化
拉取代码后，在你的 Ubuntu 终端执行以下脚本：
```bash
chmod +x init_ubuntu_env.sh
./init_ubuntu_env.sh
```
> **⚙️ 脚本自动完成：** 1. 安装 Docker Engine；2. 配置免 `sudo` 执行；3. 配置自动化流水线免密提权。

### Step 2: 配置并注册 GitHub Runner
1. 打开本项目 GitHub 网页：`Settings` -> `Actions` -> `Runners` -> `New self-hosted runner`。
2. 按照网页提示下载 Runner，并绑定仓库（注意打上如 `laptop` 的标签）。
3. 安装并启动常驻服务：
   ```bash
   sudo ./svc.sh install
   sudo ./svc.sh start
   ```

### Step 3: 刷新权限与触发部署
```bash
# 刷新权限并重启 Runner 服务
newgrp docker
cd actions-runner
sudo ./svc.sh stop && sudo ./svc.sh start
```
**完成！** 向 `main` 分支推送代码，流水线将自动拉起所有分布式容器，并自动放行 **前端 (80)** 和 **后端 API (5003)** 端口。

---

## 4. 💻 部署方式二：测试与手动部署

若不使用 CI/CD，请确保本地已安装 Docker 和 Docker Compose (v2)。

```bash
git clone [https://github.com/owl234/arl-pro.git](https://github.com/owl234/arl-pro.git)
cd arl-pro

# 方式 A: 生产/测试环境运行 (映射宿主机 80 端口，含容灾重启策略)
docker compose -f docker-compose.test.yml up -d

# 方式 B: 本地沙盒/独立部署环境 (映射宿主机 8080 端口)
docker compose -f docker-compose.local.yml up -d --build
```
> **访问地址**：生产模式访问 `http://IP/`；开发模式访问 `http://127.0.0.1:8080/`
> **默认账号密码**：`admin` / `arlpass` (登录后请立即修改)

---

## 5. 🛠️ 进阶开发与编排架构指南

为了兼顾“生产环境的绝对稳定”与“开发环境的极致效率”，本项目严格分离了编排配置：

| 维度 | `local.yml` (本地开发沙盒) | `test.yml` (测试/生产部署靶标) |
| :--- | :--- | :--- |
| **核心定位** | 本地写代码、Debug 调试、热重载 | CI/CD 流水线部署、提供稳定服务 |
| **端口策略** | 暴露调试端口 (如前端 8080，后端 5003) | 仅暴露标准服务端口 (如 Web 80) |
| **代码挂载** | 直通挂载宿主机目录 (`./backend:/code`) | 源码打包进镜像内，环境高度一致且防篡改 |
| **容灾策略** | `restart: no` (报错即停，方便查日志) | `restart: always` (崩溃/重启后自动拉起服务) |

### 👨‍💻 最佳开发实践：前后端混合热加载 (Hot-Reload)

ARL-PRO 支持极其高效的开发体验，建议采用 **“后端跑 Docker，前端跑原生”** 的混合模式：

1. **一键拉起后端底座**（包含数据库、MQ、API 与调度节点）：
   ```bash
   # 不启动前端容器，仅启动后端基建
   docker compose -f docker-compose.local.yml up -d backend worker scheduler mongodb rabbitmq
   ```
   *此时，后端 API (映射于 5003 端口) 已开启 Gunicorn `--reload` 机制，修改任意 `.py` 文件，容器内服务即刻无缝重启生效。*

2. **原生启动 Vue 前端**（享受 Vite 毫秒级 HMR 热更新）：
   ```bash
   cd frontend
   pnpm install
   pnpm run dev
   ```
   *前端将运行于 `localhost:5173`，并通过 Vite Proxy 自动将 API 请求转发至 Docker 承载的 `5003` 端口。前后端热更新互不干扰，开发效率达到极致。*

---

## 6. 完成度评估 (功能清单)

目前项目已经实现了核心功能模块的重构，完成度极高：
* **前端功能模块**：涵盖任务列表与详情、资产监控、指纹信息、资产组详情、策略详情、GitHub 敏感信息监控全套面板。
* **后端 API 支持**：全面支撑高并发任务下发，涵盖资产管理 (`domain`, `ip`, `site`等)、漏洞与安全 (`poc`, `vuln`, `npoc_service`) 及 GitHub 监控体系。

## 7. 近期开发动态

* **DevOps 升级**：全面打通 GitHub Actions 自动化部署流水线，支持 Ubuntu 节点一键环境装配与免密提权。
* **容灾与高可用配置**：为生产环境引入容灾编排策略 (`test.yml`)，确保分布式工作节点及核心数据库在宿主机异常重启后能够自动恢复，实现 24/7 无人值守资产侦察。