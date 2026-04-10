# 安全网络聊天工具（TLS-Message-GUI）

[![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![PyQt5](https://img.shields.io/badge/PyQt5-5.15.10-41CD52?logo=qt&logoColor=white)](https://pypi.org/project/PyQt5/)
[![SQLite](https://img.shields.io/badge/SQLite-Built--in-003B57?logo=sqlite&logoColor=white)](https://www.sqlite.org/)
[![TLS](https://img.shields.io/badge/Security-TLS-0A66C2?logo=letsencrypt&logoColor=white)](#)
[![Tests](https://img.shields.io/badge/Tests-unittest-8A2BE2)](#测试与校验)
[![Platform](https://img.shields.io/badge/Platform-Windows%2010%2F11-0078D6?logo=windows&logoColor=white)](#快速开始)

基于 Python + PyQt5 + SQLite 的桌面聊天系统，包含客户端、服务端管理界面与 TLS 安全通信。项目适合课程实验、功能演示和小规模本地联调。

## 项目概览

- 客户端：登录、注册、好友管理、私聊/群聊、文件发送与下载、个人资料编辑
- 服务端：图形化启动/停止服务、用户管理、在线状态维护、消息与文件存储
- 协议层：JSON 行协议（保留少量旧版文本协议兼容）
- 安全能力：密码哈希存储、TLS 传输、单账号单终端会话控制、找回问题重置密码

## 项目演示

![image-20260410170114330](https://imgbed.sut.qzz.io/img/20260410170115119.webp)

![image-20260410170156925](https://imgbed.sut.qzz.io/img/20260410170157258.webp)

## 技术栈

- Python 3.10+
- PyQt5 5.15.10
- SQLite3（标准库）
- socket / socketserver / ssl（标准库）
- unittest（标准库）

依赖文件：requirements.txt

## 架构说明

```text
PyQt5 Client (client_app)
        |
        |  TLS + JSON Line Protocol
        v
PyQt5 Server UI (server_app/ui + server_app/app.py)
        |
        v
Server Controller (server_app/network/server_controller.py)
        |
        v
SQLite Database (server_app/db.py -> data/server.db)
```

核心特点：客户端是“同步请求-响应”模型，服务端按 action 分发业务并写入 SQLite。

## 快速开始

### 1. 环境准备

- Windows 10/11（推荐）
- Python 3.10 或更高版本

检查 Python 版本：

```powershell
python --version
```

### 2. 安装依赖

```powershell
python -m pip install -r requirements.txt
```

### 3. 启动服务端

```powershell
python -m server_app
```

### 4. 启动客户端

```powershell
python -m client_app
```

## 项目结构

```text
SD1/
├─ client_app/              # 客户端应用（UI + 应用编排 + 网络控制）
├─ server_app/              # 服务端应用（UI + 网络服务 + 数据层）
├─ tests/                   # unittest 测试
├─ plans/                   # 实施计划与对齐文档
├─ doc/ / docs/             # 项目说明、答辩与技术文档
├─ data/                    # SQLite 数据文件目录
├─ tls_support.py           # TLS 证书与上下文辅助
└─ requirements.txt
```

## 关键功能

- 账号体系：登录、注册、锁定控制、找回问题重置密码
- 社交能力：搜索用户、添加好友、会话列表
- 聊天能力：私聊消息拉取、群聊创建与群消息拉取
- 文件能力：文件发送、文件拉取、客户端下载目录管理
- 在线状态：登录在线、离线时间、会话状态刷新
- 安全能力：PBKDF2 + Salt 密码存储、TLS 通信、单端登录挤下线

## 开发流程（建议）

1. 在 plans/ 下先补一份需求或变更计划
2. 在 client_app 或 server_app 完成功能实现
3. 先做语法校验，再跑对应测试
4. 自查文案与错误码映射，确保客户端提示可读

## 编码约定（摘要）

- 新模块默认包含 `from __future__ import annotations`（延迟注解）
- 导入顺序：标准库 -> 第三方 -> 本地模块
- 命名规则：类用 PascalCase，函数/变量用 snake_case
- 网络错误优先返回结构化响应，不直接让处理线程崩溃
- 保持现有同步通信模型，不随意改成服务端主动推送

## 测试与校验

运行全量测试：

```powershell
python -m unittest discover -s tests -p "test_*.py"
```

按影响范围运行重点测试：

```powershell
python -m unittest tests.test_secure_chat_tls_presence
python -m unittest tests.test_client_app_message_mapping
```

语法校验示例：

```powershell
python -m py_compile "client_app/app.py" "client_app/network/client_controller.py" "client_app/ui/chat_window.py" "server_app/db.py" "server_app/network/server_controller.py" "tls_support.py"
```

## 贡献说明

- 先阅读 AGENTS.md，遵守仓库约定
- 尽量做“小步可验证”提交，避免一次性大改协议或数据库结构
- 涉及网络协议、数据库表结构、通信模型的重大调整，请先达成共识
- 严禁提交密钥、令牌、`.env`（环境变量文件）等敏感信息

## 许可证

当前仓库未提供明确 License 文件。如需开源分发，请先补充 LICENSE。
