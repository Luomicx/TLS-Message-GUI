# 客户端与服务端对齐实施计划

## 1. 目标

将现有 `client_app` 的 QFluentWidgets 界面与 `server_app` 的网络和数据库能力对齐，实现以下功能的完整闭环：

- 登录与注销
- 用户注册
- 搜索与添加好友
- 私聊消息发送与拉取
- 通信内容编码

## 2. 现状评估

### 2.1 已实现的后端能力

经过代码审查，以下功能已在服务端实现：

**协议层 (`server_app/network/server_controller.py`)**

| 功能 | 实现方式 | 代码位置 |
|------|----------|----------|
| 登录 | Legacy 文本协议 `LOGIN <username> <password>` | 第 87-99 行 |
| 注销 | Legacy 文本协议 `LOGOUT <username>` | 第 101-109 行 |
| 登录 | JSON 请求 `{"action":"login",...}` | 第 116-137 行 |
| 注销 | JSON 请求 `{"action":"logout",...}` | 第 139-151 行 |
| 注册 | JSON 请求 `{"action":"register",...}` | 第 153-181 行 |
| 搜索用户 | JSON 请求 `{"action":"search_users",...}` | 第 183-200 行 |
| 添加好友 | JSON 请求 `{"action":"add_friend",...}` | 第 202-228 行 |
| 好友列表 | JSON 请求 `{"action":"list_friends",...}` | 第 230-237 行 |
| 发送消息 | JSON 请求 `{"action":"send_message",...}` | 第 239-268 行 |
| 拉取消息 | JSON 请求 `{"action":"pull_messages",...}` | 第 270-291 行 |

**数据库层 (`server_app/db.py`)**

| 方法 | 功能 | 代码位置 |
|------|------|----------|
| `verify_login_detail()` | 验证用户名密码，返回详细结果 | 第 218-251 行 |
| `register_user()` | 注册新用户 | 第 269-296 行 |
| `search_users_fuzzy()` | 模糊搜索用户 | 第 298-316 行 |
| `search_user_by_id()` | 按 ID 精确搜索 | 第 318-336 行 |
| `add_friend()` | 添加好友关系 | 第 338-365 行 |
| `list_friends()` | 获取好友列表 | 第 367-379 行 |
| `save_message()` | 保存聊天消息 | 第 381-416 行 |
| `pull_messages()` | 拉取消息历史 | 第 418-437 行 |
| `list_sessions()` | 获取会话列表 | 第 439-470 行 |

**数据表结构**

已创建的表：
- `users`：用户账户，含密码盐值与哈希、头像、编码规则、锁定状态
- `friends`：好友关系，双向存储
- `messages`：聊天消息，含发送者、接收者、编码规则、时间戳

**安全层 (`server_app/security.py`)**

| 函数 | 算法 | 参数 |
|------|------|------|
| `hash_password()` | PBKDF2-HMAC-SHA256 | 120000 次迭代，16 字节盐，32 字节输出 |
| `verify_password()` | 常数时间对比 | 防止时序攻击 |

**协议工具 (`server_app/protocol.py`)**

| 函数 | 功能 |
|------|------|
| `decode_request_line()` | 解析 JSON 请求行 |
| `encode_response_line()` | 构造 JSON 响应行 |
| `encode_sensitive_text()` | 内容编码（base64/hex/caesar 链） |
| `decode_sensitive_text()` | 内容解码（逆序） |

### 2.2 已实现的客户端能力

**网络层 (`client_app/network/client_controller.py`)**

| 方法 | 对应服务端 action |
|------|-------------------|
| `login()` | `login` |
| `logout()` | `logout` |
| `register()` | `register` |
| `search_users()` | `search_users` |
| `add_friend()` | `add_friend` |
| `list_friends()` | `list_friends` |
| `send_message()` | `send_message` |
| `pull_messages()` | `pull_messages` |

**协议工具 (`client_app/protocol.py`)**

- `encode_request()`：构造 JSON 请求
- `decode_response()`：解析 JSON 响应

**业务接线 (`client_app/app.py`)**

| 方法 | 职责 |
|------|------|
| `open_chat()` | 登录成功后切换到聊天窗口，加载好友和会话 |
| `back_to_login()` | 注销并返回登录页 |
| `register_user()` | 调用注册接口 |
| `search_users()` | 搜索用户并展示结果 |
| `add_friend()` | 添加好友并刷新列表 |
| `send_message()` | 发送消息并刷新会话 |
| `load_messages()` | 拉取消息历史并展示 |

**UI 层**

- `login_window.py`：emit `login_requested(str, str)`
- `register_dialog.py`：通过 `register_submitter` 回调提交注册
- `chat_window.py`：emit `search_requested(str, str)`、`add_friend_requested(int)`、`send_message_requested(str, str)`、`session_selected(str)`

### 2.3 已验证可工作的流程

基于代码静态分析，以下链路已完整实现：

1. **登录链路**：login_window → app.open_chat → client_controller.login → server login → DB verify → 响应返回 → 界面切换
2. **注册链路**：register_dialog → app.register_user → client_controller.register → server register → DB insert → 响应返回
3. **搜索/添加好友链路**：chat_window → app.search_users → client_controller.search_users → server → 响应返回 → 界面展示
4. **消息收发链路**：chat_window → app.send_message → client_controller.send_message → server → DB save → 响应返回

## 3. 缺口与风险分析

### 3.1 身份标识不一致

**问题**：`login_window.py` 第 114 行显示标签为"账号 Id"，但后端 `verify_login_detail()` 实际按 `username` 字段认证。

**影响**：用户可能误以为应输入数字 ID，实际应输入注册时设定的用户名（昵称）。

**建议**：明确产品定义——是使用数字 ID 还是字符串用户名作为登录凭证，并统一 UI 标签文字。

### 3.2 通信安全边界

**现状**：`server_app/protocol.py` 中的 `encode_sensitive_text()` 支持 base64、hex、caesar 三种编码，但这仅是**内容混淆**，非加密。

**风险**：在网络传输层上，数据仍为明文 TCP 可被窃听。攻击者可直接看到 JSON 负载中的 username、password、message content。

**当前安全能力**：
- 密码存储：PBKDF2-HMAC-SHA256（强）
- 通信内容：可逆编码（弱）

**建议**：区分基线安全与强化安全两个阶段，详见第 5 节。

### 3.3 客户端生命周期管理

**问题**：当前注销仅通过"注销并返回登录"按钮触发。如果用户直接关闭聊天窗口，未显式调用 `logout`。

**代码位置**：`chat_window.py` 第 107 行 `btn_logout` 连接了 `back_to_login`，但窗口关闭事件（`closeEvent`）未处理。

**建议**：在 `ChatWindow` 中重写 `closeEvent`，在退出前显式调用注销逻辑。

### 3.4 注册字段映射

**问题**：`register_dialog.py` 第 43 行输入字段标记为"昵称"，但提交后作为 `username` 存入数据库。

**代码位置**：`client_controller.py` 第 54-63 行注册请求使用 `username` 字段。

**产品模糊点**：如果系统后续支持数字 ID 作为唯一标识，当前注册逻辑需要调整。

### 3.5 错误处理覆盖

**现状**：服务端对各 action 已有错误码返回（user_not_found、user_locked、invalid_credentials 等），但客户端 UI 仅通过 `InfoBar` 展示通用错误。

**建议**：在 `client_app/app.py` 中根据 `response.code` 映射为用户可理解的提示。

## 4. 分阶段实施任务

### 阶段一：基础联调验证（优先）

此阶段目标：确保现有代码链路可跑通，无需新增功能。

| 任务 | 文件 | 说明 |
|------|------|------|
| T1.1 启动服务端 | `server_app/__main__.py` 或 `server_app/__init__.py` | 确认监听端口 8000 |
| T1.2 启动客户端 | `client_app/__main__.py` | 验证登录窗口正常显示 |
| T1.3 手动测试注册 | 使用 DB 工具或服务端 UI 插入测试用户 | 确认 users 表可写入 |
| T1.4 客户端登录 | 输入已存在的用户和密码 | 验证完整链路 |
| T1.5 客户端注册 | 在注册弹窗中填写信息 | 验证注册链路 |
| T1.6 添加好友 | 搜索用户并添加 | 验证添加链路 |
| T1.7 发送消息 | 在聊天窗口发送消息 | 验证消息存储与拉取 |

**验证要点**：
- `server_controller.py` 第 311 行 `serve_forever` 正常监听
- `client_controller.py` 第 128 行 `create_connection` 可连接成功
- `app.py` 第 30-46 行登录成功后 UI 切换

### 阶段二：UI 标签与文案修正

| 任务 | 文件 | 修改内容 |
|------|------|----------|
| T2.1 统一登录标签 | `client_app/ui/login_window.py` 第 114 行 | 将"账号 Id"改为更准确的描述，如"用户名" |
| T2.2 错误码映射 | `client_app/app.py` | 根据 `response.code` 返回中文错误提示 |
| T2.3 注册字段说明 | `client_app/ui/register_dialog.py` 第 44 行 | 明确此字段即为登录用户名 |

### 阶段三：窗口生命周期完善

| 任务 | 文件 | 修改内容 |
|------|------|----------|
| T3.1 添加 closeEvent | `client_app/ui/chat_window.py` | 重写关闭事件，自动调用注销 |
| T3.2 退出时关闭连接 | `client_app/app.py` | 应用退出前确保 socket 关闭 |

### 阶段四：安全强化（可选）

**基线安全（已有）**：
- 密码 PBKDF2 存储 ✓
- 通信内容编码链 ✓

**强化安全（可选）**：

| 任务 | 说明 |
|------|------|
| T4.1 TLS 加密 | 使用 Python `ssl.SSLContext` 包装 socket，服务端创建 `SSLContext(PROTOCOL_TLS_SERVER)` 并调用 `wrap_socket()` |
| T4.2 客户端 TLS | `client_controller.py` 使用 `ssl.create_default_context()` 或 `SSLContext(PROTOCOL_TLS_CLIENT)` 并调用 `wrap_socket()` 连接 |
| T4.3 证书管理 | 生成自签名证书或使用内置 CA 验证 |

## 5. 安全建议

### 5.1 当前安全能力

| 层面 | 方案 | 强度 | 说明 |
|------|------|------|------|
| 密码存储 | PBKDF2-HMAC-SHA256 + 随机盐 | 强 | 120000 次迭代，常规硬件无法暴力破解 |
| 通信内容 | base64/hex/caesar 链式编码 | 弱 | 仅防小白，非真正加密 |
| 传输层 | 明文 TCP | 无 | 任何中间人均可窃听 |

### 5.2 分层建议

**基线交付（本次计划内）**：
- 保持现有密码哈希方案
- 保持现有内容编码链
- 不要求 TLS

**可选强化（后续迭代）**：
- 使用 Python 标准库 `ssl` 将 socket 包装为 SSLSocket
- 服务端创建 `ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)`，加载证书后调用 `wrap_socket()` 包装底层 socket
- 客户端创建 `ssl.create_default_context()`（或 `ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)`），调用 `wrap_socket()` 包装连接 socket
- 建议使用 TLS 1.3，通过 `context.minimum_version = ssl.TLSVersion.TLSv1_3` 强制最低版本

**为什么当前不强制 TLS**：
- 增加实现复杂度，需要证书管理
- 本项目定位为教学实验，核心目标是网络编程理解
- 可将 TLS 作为进阶任务独立处理

### 5.3 密码安全要点

- 永不将明文密码存入数据库 ✓（已实现）
- 使用足够长的盐值和迭代次数 ✓（16 字节盐，120000 次迭代）
- 使用常数时间比较防止时序攻击 ✓（已使用 `hmac.compare_digest`）

## 6. 验证检查清单

### 6.1 功能验证

| # | 场景 | 预期结果 |
|---|------|----------|
| V1 | 正确用户名 + 正确密码 | 登录成功，切换到聊天窗口 |
| V2 | 正确用户名 + 错误密码 | 登录失败，提示用户名或密码错误 |
| V3 | 不存在的用户名 | 登录失败，提示用户不存在 |
| V4 | 已锁定账户 | 登录失败，提示账号被锁定 |
| V5 | 新用户注册 | 注册成功，返回用户信息 |
| V6 | 注册重复用户名 | 注册失败，提示用户名已存在 |
| V7 | 搜索存在的用户名 | 返回匹配用户列表 |
| V8 | 按 ID 搜索 | 返回精确匹配用户 |
| V9 | 添加陌生人为好友 | 添加成功，好友列表更新 |
| V10 | 添加已好友用户 | 添加失败，提示已是好友 |
| V11 | 发送消息给好友 | 发送成功，消息存入数据库 |
| V12 | 切换会话并拉取消息 | 显示对应聊天历史 |
| V13 | 点击注销按钮 | 返回登录界面 |
| V14 | 关闭聊天窗口 | 自动注销并返回登录界面 |

### 6.2 异常情况

| # | 场景 | 预期结果 |
|---|------|----------|
| E1 | 服务端未启动时点击登录 | 显示连接失败提示 |
| E2 | 网络中断后发送消息 | 显示网络错误提示 |
| E3 | 发送空消息 | 客户端校验拦截，提示不能为空 |

### 6.3 代码质量

- 所有 Python 文件通过 `python -m py_compile` 语法检查
- 无未使用的 import
- 无明显缩进或语法错误
- 中文注释或文档无乱码

## 7. 相关文件索引

### 服务端

| 文件路径 | 核心功能 |
|----------|----------|
| `server_app/network/server_controller.py` | TCP 服务器，请求分发，在线用户管理 |
| `server_app/db.py` | SQLite 数据库操作，用户/好友/消息表管理 |
| `server_app/protocol.py` | JSON 协议编解码，内容编码/解码工具 |
| `server_app/security.py` | 密码哈希与校验 |

### 客户端

| 文件路径 | 核心功能 |
|----------|----------|
| `client_app/network/client_controller.py` | TCP 客户端，网络请求发送与响应接收 |
| `client_app/protocol.py` | JSON 协议编解码 |
| `client_app/app.py` | 业务逻辑接线，UI 与网络控制器桥接 |
| `client_app/ui/login_window.py` | 登录窗口，emit login_requested |
| `client_app/ui/register_dialog.py` | 注册弹窗，submit via register_submitter |
| `client_app/ui/chat_window.py` | 聊天窗口，emit search/add/send/session 信号 |

### 配置与数据

| 路径 | 说明 |
|------|------|
| `data/server.db` | SQLite 数据库文件 |
| `plans/` | 本计划文档所在目录 |

## 8. 总结

本次计划基于代码实际实现情况编制。当前服务端已完整支持登录、注销、注册、搜索、添加好友、消息收发等核心功能，客户端网络层与 UI 接线亦已就位。主要工作为：

1. **验证现有链路可跑通**（阶段一）
2. **修正 UI 标签与错误提示**（阶段二）
3. **完善窗口生命周期管理**（阶段三）
4. **可选的 TLS 安全强化**（阶段四）

密码存储使用 PBKDF2-HMAC-SHA256 已达生产级安全，通信层编码为可逆混淆，非真正加密，建议后续升级 TLS。

---

**编制说明**：本计划基于代码审查编制，列出的函数名和方法均来自实际源码。实施时请以本计划为指南，结合实际测试结果调整任务优先级。
