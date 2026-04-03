# 安全聊天、TLS 与在线状态实施计划

## 1. 目标

在现有 `client_app` / `server_app` 的 JSON 行协议基础上，完成以下能力：

- 私聊消息链路可实际联通并保持兼容现有 UI
- 服务端对外暴露用户在线状态
- 客户端与服务端之间的通信改为 TLS 加密传输
- 保留现有数据库消息存储与编码规则逻辑，不以“可逆编码”替代真正加密

## 2. 当前现状

### 2.1 已具备能力

- `server_app/network/server_controller.py`
  - 已支持 `login/logout/register/search_users/add_friend/list_friends/send_message/pull_messages`
  - 已在内存中维护 `_online_users`
  - 已在连接结束时调用 `_set_online(..., False)` 清理在线状态
- `server_app/db.py`
  - 已具备用户、好友、消息表与查询/写入方法
  - `list_friends()` / `list_sessions()` / `pull_messages()` 已能支撑聊天界面
- `client_app/network/client_controller.py`
  - 已具备统一 `_request()` 通道
  - 已基于持久 socket 发送/接收 JSON 行协议
- `client_app/app.py`
  - 已完成登录后好友/会话加载
  - 已完成发送消息与拉取消息的 UI 接线

### 2.2 缺口

- 在线状态仅保存在 `ServerController._online_users`，未向客户端返回
- 传输层仍是明文 TCP，仓库内暂无 `ssl` 接入
- 仓库内无现成证书文件（无 `.pem/.crt/.key`）
- 服务端 UI 当前无 TLS 配置入口

## 3. 实施范围

### 3.1 在线状态

- 服务端登录成功后登记在线
- 注销与连接断开后移除在线
- 登录返回、好友列表、会话列表中补充 `is_online`
- 客户端聊天界面消费 `is_online`，在好友/会话展示中体现在线状态

### 3.2 TLS 传输加密

- 服务端使用 `ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)` 包装监听 socket
- 客户端使用 `ssl.create_default_context()` 或 `ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)` 包装连接
- 本地开发环境提供证书加载路径
- 默认以本地开发可运行优先，后续再扩展正式证书校验策略

### 3.3 聊天链路补强

- 不推翻现有 `send_message/pull_messages` action
- 保持数据库落库与拉取逻辑
- 仅将在线状态和 TLS 透明接入现有链路

## 4. 预计修改文件

### 服务端

- `server_app/network/server_controller.py`
  - 增加 TLS server 初始化逻辑
  - 在线状态查询/注入逻辑
  - 登录、好友列表、会话列表响应结构增强
- `server_app/ui/main_window.py`
  - 如需要，增加 TLS 启用状态或证书路径配置入口
- `server_app/app.py`
  - 启动时准备证书目录或 TLS 配置注入
- `server_app/db.py`
  - 若仅透传 `is_online`，原则上不改表结构

### 客户端

- `client_app/network/client_controller.py`
  - 增加 SSL context 与 TLS socket 建立逻辑
  - 保持现有请求/响应 API 不变
- `client_app/app.py`
  - 消费新的 `is_online` 字段
- `client_app/ui/chat_window.py`
  - 好友/会话列表显示在线状态

### 配置与资产

- `plans/`：保留本计划文档
- 证书目录（待定，建议放在 `data/certs/` 或项目根下专用目录）

## 5. 分阶段实施

### 阶段一：TLS 接入设计定稿

- 确认 Python 标准库 `ssl` 的最小正确接法
- 确认证书文件位置与加载方式
- 确认本地开发环境是否允许自签名证书

### 阶段二：服务端在线状态透出

- 为 `_online_users` 增加统一读取接口
- 在登录响应中补充当前好友/会话的在线状态
- 在 `list_friends` / `list_sessions` 相关返回中统一注入 `is_online`

### 阶段三：服务端 TLS 化

- 监听 socket 在启动阶段完成 `wrap_socket()`
- 保持 `StreamRequestHandler` 读取方式不变
- 确保 stop/start 生命周期不被 TLS 破坏

### 阶段四：客户端 TLS 化

- 在 `_ensure_connection()` 中建立 TLS 连接
- 保持 `_request()` 与 `_recv_line()` 行为不变
- 针对本地自签名证书处理开发模式校验策略

### 阶段五：UI 在线状态显示

- 在 `ChatWindow` 的好友列表、会话列表中显示在线/离线
- 保持当前布局改动最小，不重构整个界面

### 阶段六：验证

- `py_compile` 检查所有改动 Python 文件
- 运行现有相关单测
- 视环境能力进行服务端/客户端联调
- 若环境缺少证书或 GUI 依赖，明确记录阻塞项

## 6. 风险与注意点

- Python 标准库不能直接生成 X.509 证书，真实 TLS 需要现成证书文件或外部生成流程
- 若采用自签名证书，客户端校验策略需明确区分开发模式与正式模式
- 在线状态当前为内存态，服务端重启后会清空，这是可接受的即时状态设计
- 当前消息仍会按用户编码规则落库；TLS 负责传输加密，二者职责不同

## 7. 验证清单

- 登录后好友列表可见在线/离线状态
- 用户关闭客户端或注销后，在线状态能在服务端清除
- 客户端到服务端连接已通过 TLS 建立
- 消息发送与拉取在 TLS 下仍正常
- 代码通过语法检查，相关测试不回归
