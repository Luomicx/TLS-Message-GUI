# 当前项目功能盘点

## 1. 项目当前定位

当前仓库已经不是只有“服务端界面”的半成品，而是一个基于 Python、PyQt5、SQLite 和 TLS 的桌面安全聊天原型项目，包含：

- 桌面客户端
- 桌面服务端管理界面
- SQLite 数据库
- TLS 安全通信
- 基于 JSON 行协议的客户端/服务端交互

---

## 2. 已实现的核心功能

### 2.1 客户端与服务端双入口

项目已经具备独立启动入口：

- 客户端：`python -m client_app`
- 服务端：`python -m server_app`

服务端启动时会自动：

- 创建 `data/` 目录
- 初始化 `data/server.db`
- 初始化数据库表结构
- 在数据库为空时写入种子用户

相关文件：

- `client_app/__main__.py`
- `server_app/__main__.py`
- `server_app/app.py`

### 2.2 服务端网络与协议能力

服务端已经具备真实网络处理能力，不只是界面展示。

已实现能力：

- 启动/停止 TCP 服务
- 基于 TLS 建立安全连接
- 接收客户端请求
- 解析 JSON 行协议
- 分发不同业务动作
- 维护在线用户状态

当前已支持的请求动作：

- `login`
- `logout`
- `register`
- `search_users`
- `add_friend`
- `list_friends`
- `send_message`
- `pull_messages`

另外还保留了旧版文本协议兼容逻辑：

- `LOGIN <username> <password>`
- `LOGOUT <username>`

相关文件：

- `server_app/network/server_controller.py`
- `server_app/protocol.py`

### 2.3 数据库与业务数据能力

数据库层已经实现了聊天系统核心数据模型。

当前表结构包括：

- `users`：用户信息
- `friends`：好友关系
- `messages`：消息记录

当前数据库层已实现：

- 用户注册
- 登录校验
- 用户查询
- 模糊搜索用户
- 按用户 ID 精确搜索
- 添加好友
- 双向好友关系维护
- 好友列表查询
- 消息保存
- 消息拉取
- 最近会话列表整理
- 用户名、密码、头像、编码规则、锁定状态维护

相关文件：

- `server_app/db.py`

### 2.4 安全能力

当前项目已经具备基础安全能力：

- 密码使用带盐 PBKDF2 哈希存储
- 客户端与服务端之间通过 TLS 通信
- 消息内容支持编码规则处理
- 避免密码明文落库

当前支持的消息编码规则：

- `base64`
- `hex`
- `caesar`

相关文件：

- `server_app/security.py`
- `server_app/protocol.py`
- `tls_support.py`

### 2.5 服务端图形管理界面

服务端 UI 已经可以完成日常演示和基础管理操作。

主窗口支持：

- 启动服务
- 停止服务
- 设置监听端口
- 查看运行日志
- 查看未锁定用户头像列表
- 打开用户管理窗口

用户管理窗口支持：

- 添加用户
- 删除用户
- 修改用户名
- 修改密码
- 修改编码规则
- 锁定/解锁用户
- 上传或更换头像

相关文件：

- `server_app/ui/main_window.py`
- `server_app/ui/user_management_dialog.py`
- `server_app/ui/add_user_dialog.py`
- `server_app/ui/avatar.py`

### 2.6 客户端网络能力

客户端网络控制器已经实现了和服务端对接的真实接口调用，不是纯占位代码。

当前支持：

- 登录
- 注销
- 注册
- 搜索用户
- 添加好友
- 获取好友列表
- 发送消息
- 拉取消息

同时具备：

- TLS 连接建立
- JSON 请求发送
- JSON 响应解析
- 单连接串行请求控制
- 网络错误映射

相关文件：

- `client_app/network/client_controller.py`
- `client_app/protocol.py`

### 2.7 客户端应用编排逻辑

客户端应用层已经写出了完整的业务编排思路。

当前编排逻辑包括：

- 登录成功后切换到聊天界面
- 保存当前登录用户
- 拉取好友列表和会话列表
- 根据当前会话加载消息
- 发送消息后刷新当前会话
- 定时刷新消息
- 定时刷新好友在线状态
- 注销后返回登录页
- 对错误码映射为用户可读提示
- 在请求失败时执行退避重试节奏控制

相关文件：

- `client_app/app.py`

### 2.8 测试已覆盖并证明的功能

当前自动化测试已经直接证明以下链路可用：

- TLS 登录成功
- 登录后返回用户信息
- 登录后返回好友列表
- 在线状态刷新
- 通过 TLS 发送消息
- 对端成功拉取并解码消息

相关文件：

- `tests/test_secure_chat_tls_presence.py`
- `tests/test_client_app_message_mapping.py`

---

## 3. 当前更接近“已打通”的部分

从代码现状看，以下部分相对更完整：

- 服务端数据库与业务逻辑
- 服务端网络协议处理
- TLS 通信链路
- 基础测试链路
- 服务端管理界面
- 客户端网络控制器

换句话说，项目后端主链路已经比较完整，具备课程实验级别的真实可运行能力。

---

## 4. 当前存在的不一致与待打通点

虽然项目功能已经不少，但前端界面层仍然存在明显阶段性痕迹。

### 4.1 客户端 UI 文案仍保留占位阶段描述

以下界面文件中仍可看到“后续接入”“占位”等描述：

- `client_app/ui/login_window.py`
- `client_app/ui/register_dialog.py`
- `client_app/ui/chat_window.py`

这说明客户端界面曾按“先做静态 UI，再接业务”的方式推进过。

### 4.2 `client_app/app.py` 与 `client_app/ui/chat_window.py` 当前快照不一致

`client_app/app.py` 里调用了多个聊天窗口方法，例如：

- `reset_view_state()`
- `set_current_user()`
- `populate_friends()`
- `populate_sessions()`
- `populate_messages()`
- `populate_search_results()`
- `show_notice()`
- `upsert_session()`
- `current_peer`

但当前仓库中的 `client_app/ui/chat_window.py` 仍然是偏静态展示版，未见这些方法定义。

这表示当前仓库至少存在下面两种可能之一：

- 客户端 UI 改造尚未完成
- 业务编排层与界面层代码没有同步到同一版本

### 4.3 注册对话框当前仍以本地校验为主

`client_app/ui/register_dialog.py` 当前行为是：

- 做昵称、密码、确认密码校验
- 勾选同意项校验
- 校验通过后关闭弹窗

但它本身没有直接发起注册网络请求。

因此，虽然网络层有 `register()` 能力，但当前 PyQt 注册交互链路未完全闭环。

---

## 5. 当前项目状态判断

如果从“系统能力”角度判断，项目已经实现了：

- 用户认证
- 好友管理
- 私聊消息收发
- 消息持久化
- 在线状态
- 服务端用户管理
- TLS 安全通信

如果从“桌面客户端完整可交互产品”角度判断，当前状态更准确地说是：

- 后端和通信主链路已经落地
- 部分客户端 UI 仍需继续和应用编排层打通

---

## 6. 结论

当前项目已经实现的是一个具备真实后端能力的桌面安全聊天原型，而不是只有演示界面。

已完成的重点在于：

- 服务端 UI
- 服务端网络
- SQLite 数据层
- 登录/注册/搜索/加好友/发消息/拉消息接口
- TLS 安全通信
- 在线状态维护
- 自动化测试验证

当前最明显的后续工作重点在于：

- 统一客户端 UI 与 `client_app/app.py` 的接口
- 把注册、搜索、会话、消息展示彻底打通到现有 PyQt 客户端界面
- 消除界面中的占位文案，使其和当前真实实现状态一致
