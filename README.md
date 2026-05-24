# ARL-Rebuild 项目介绍与进度一览

本文档旨在为未接触过本项目的人员提供一个快速了解项目的整体情况，包括整体功能、架构梳理、近期开发动态以及目前的完成度评估。

## 1. 整体功能和架构梳理

本项目是 **ARL（Asset Reconnaissance Lighthouse，资产侦察灯塔系统）** 的重构版本，旨在提供更加现代化和高效的资产侦察和漏洞扫描功能。系统采用前后端分离的架构，并通过 Docker Compose 进行容器化部署。

### 1.1 系统架构组件
根据 `docker-compose.local.yml` 的配置，整个系统主要由以下核心服务构成：

*   **前端服务 (frontend)**：
    *   基于 **Vue 3** 和 **Vite** 构建。
    *   提供现代化的单页面应用 (SPA) 界面，运行在 Nginx 容器中。
*   **后端 Web API 服务 (backend)**：
    *   基于 **Python**、**Flask** 和 **Flask-RESTX** 开发。
    *   提供 RESTful API，处理用户请求、数据查询和任务调度。通过 Gunicorn 运行。
*   **核心扫描节点 (worker)**：
    *   基于 **Celery** 的工作节点，负责执行各种重量级的资产收集和扫描任务（如域名枚举、端口扫描、漏洞探测等）。
*   **GitHub 监控节点 (worker-github)**：
    *   专门用于监控 GitHub 源码泄露和敏感信息的 Celery 工作节点。
*   **定时调度器 (scheduler)**：
    *   处理周期性任务和计划任务的调度模块。
*   **消息队列 (rabbitmq)**：
    *   作为 Celery 的 Broker，负责后端 API、Scheduler 与各个 Worker 之间的任务消息传递。
*   **数据库 (mongodb)**：
    *   存储各种扫描结果、资产数据、任务状态等持久化信息。

## 2. 完成度评估 (功能清单)

目前项目已经实现了 ARL 的核心功能模块，从代码结构来看，完成度非常高。

### 2.1 前端功能模块
前端 (`frontend/src/views`) 已经完成了大量页面的重构，主要包括：
*   **系统与基础界面**：登录 (Login)、布局 (Layout)。
*   **任务管理**：任务列表 (TaskList)、任务详情 (TaskDetail)、计划任务 (PlanningTasks)。
*   **资产管理**：
    *   资产搜索 (AssetSearch)
    *   资产监控 (AssetMonitor)
    *   资产范围 (AssetScope)
    *   指纹信息 (Fingerprint)
    *   资产组详情 (GroupAssetsDetail)
*   **漏洞与策略管理**：
    *   PoC 管理 (PocList)
    *   策略管理 (Policy)
    *   策略详情 (PolicyDetail)
*   **GitHub 监控**：
    *   GitHub 任务列表 (GithubTasksList)
    *   GitHub 任务信息 (GitHubTasksInfo)
    *   GitHub 监控列表 (GithubMonitorList)
    *   GitHub 监控信息 (GitHubMonitorInfo)

### 2.2 后端 API 支持
后端 (`backend/app/routes`) 提供了丰富的 API 接口，全面支撑前端和扫描引擎的工作：
*   **资产类**：`domain`, `ip`, `site`, `url`, `image`, `cert`, `service`, `fileleak`, `wih`, `cip` 等。
*   **任务与调度类**：`task`, `scheduler`, `task_schedule`, `task_fofa` 等。
*   **管理类**：`user`, `asset_scope`, `asset_domain`, `asset_ip`, `asset_site`, `asset_wih` 等。
*   **漏洞与安全类**：`poc`, `vuln`, `policy`, `npoc_service`, `fingerprint`, `stat_finger`, `nuclei_result` 等。
*   **GitHub 监控类**：`github_task`, `github_result`, `github_scheduler`, `github_monitor_result` 等。
*   **工具类**：`export`, `batch_export`, `console` 等。

**结论**：大部分核心业务逻辑（任务下发、资产展示、漏洞扫描、GitHub监控等）的前后端代码均已就绪。

## 3. 近期开发动态

从最近的代码提交通知来看，项目正在进行部署调优和稳定性提升。

*   **最新提交**：`fix: 为所有核心组件开启开机自启 (restart: always)`
    *   **更新说明**：修复了 Docker 部署配置，确保前端、后端、各个工作节点 (worker/github/scheduler)、数据库和消息队列在异常退出或宿主机重启后能够自动恢复，提升了系统的可靠性和无人值守能力。

## 4. 技术栈总结

*   **前端**：Vue 3, Vite, Ant Design Vue, Vue Router, Axios
*   **后端**：Python 3, Flask, Flask-RESTX, Gunicorn
*   **任务分发**：Celery, RabbitMQ
*   **数据库**：MongoDB
*   **部署**：Docker, Docker Compose
