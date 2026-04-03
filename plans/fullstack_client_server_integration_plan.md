# Secure IM 全栈联调执行计划

## 1. 目标
在现有仓库基础上，将 `client_app` 的 QFluentWidgets 界面与 `server_app` 的网络与数据库能力真正打通，覆盖以下功能：
- 登录
- 注销
- 注册
- 搜索用户（昵称模糊 / Id 精确）
- 添加好友
- 好友列表
- 私聊消息发送与拉取
- 基础安全保护（密码哈希 + 通信内容编码链）

## 2. 当前现状

### 已存在能力
- `server_app/network/server_controller.py`
  - 支持 `LOGIN <username> <password>`
  - 支持 `LOGOUT <username>`
- `server_app/db.py`
  - `users` 表已存在
  - 已支持用户新增、删除、改名、改密码、锁定、头像、编码规则
  - 登录密码使用 PBKDF2-HMAC-SHA256 校验
- `server_app/security.py`
  - 已有密码哈希与校验能力
- `client_app/ui/*.py`
  - 登录、注册、聊天、搜索、注销界面均已完成 QFluentWidgets 改造

### 缺失能力
- 客户端网络控制器不存在
- 客户端协议封装不存在
- 服务端未支持注册协议
- 服务端未支持搜索/添加好友协议
- 服务端未支持聊天消息协议
- 服务端未维护在线用户会话
- 数据库无好友关系表与消息表

## 3. 修改文件清单

### 服务端
- 修改 `server_app/db.py`
- 修改 `server_app/network/server_controller.py`
- 新增 `server_app/protocol.py`

### 客户端
- 新增 `client_app/network/__init__.py`
- 新增 `client_app/network/client_controller.py`
- 新增 `client_app/protocol.py`
- 修改 `client_app/app.py`
- 修改 `client_app/ui/login_window.py`
- 修改 `client_app/ui/register_dialog.py`
- 修改 `client_app/ui/chat_window.py`

## 4. 协议设计

### 4.1 传输形式
- 使用 JSON 行协议
- 每条请求与响应一行 JSON，以 `\n` 结尾

### 4.2 请求结构
```json
{"action":"login","username":"besti","password":"123456"}
{"action":"logout","username":"besti"}
{"action":"register","username":"新用户","password":"123456"}
{"action":"search_users","mode":"fuzzy","query":"zh","username":"besti"}
{"action":"search_users","mode":"id","query":"12","username":"besti"}
{"action":"add_friend","username":"besti","friend_id":2}
{"action":"list_friends","username":"besti"}
{"action":"send_message","from":"besti","to":"zhjw","content":"hello"}
{"action":"pull_messages","username":"besti","since_id":0}
```

### 4.3 响应结构
```json
{"ok":true,"code":"ok","message":"登录成功","data":{}}
{"ok":false,"code":"invalid_credentials","message":"用户名或密码错误"}
```

### 4.4 错误码
- `ok`
- `invalid_request`
- `invalid_credentials`
- `user_locked`
- `user_exists`
- `user_not_found`
- `already_friend`
- `not_friend`
- `send_failed`
- `server_error`

## 5. 数据库扩展

### 5.1 friends 表
- `id INTEGER PRIMARY KEY AUTOINCREMENT`
- `username TEXT NOT NULL`
- `friend_id INTEGER NOT NULL`
- `created_at TEXT NOT NULL`
- `UNIQUE(username, friend_id)`
- `FOREIGN KEY(friend_id) REFERENCES users(id) ON DELETE CASCADE`

### 5.2 messages 表
- `id INTEGER PRIMARY KEY AUTOINCREMENT`
- `sender TEXT NOT NULL`
- `receiver TEXT NOT NULL`
- `content TEXT NOT NULL`
- `encoding_rule TEXT NOT NULL DEFAULT '[]'`
- `created_at TEXT NOT NULL`

## 6. 服务端实现步骤

### 阶段一：数据库与查询能力
- 在 `db.py` 中创建 `friends` / `messages` 表
- 增加以下方法：
  - `register_user()`
  - `verify_login_detail()`
  - `search_users_fuzzy()`
  - `search_user_by_id()`
  - `add_friend()`
  - `list_friends()`
  - `save_message()`
  - `pull_messages()`

### 阶段二：协议封装
- 新增 `server_app/protocol.py`
  - `decode_request_line()`
  - `encode_response_line()`
  - 基础结构校验

### 阶段三：网络控制器
- `server_controller.py` 改为解析 JSON 行协议
- 为不同 action 路由到 DB 方法
- 维护在线用户表：`username -> handler/session`
- 登录成功后登记在线，断开或注销时移除

## 7. 客户端实现步骤

### 阶段一：客户端网络控制器
- 新增 `client_app/network/client_controller.py`
- 负责：
  - 建立 TCP 连接
  - 发送 JSON 行请求
  - 读取 JSON 行响应
  - 对 UI 发信号

### 阶段二：客户端协议封装
- 新增 `client_app/protocol.py`
- 统一构造请求与解析响应

### 阶段三：UI 接线
- `login_window.py`
  - 提交登录请求
  - 根据错误码提示失败原因
- `register_dialog.py`
  - 提交注册请求
- `chat_window.py`
  - 搜索用户
  - 添加好友
  - 加载好友列表
  - 发送消息
  - 拉取消息
  - 注销
- `app.py`
  - 注入 `ClientController`
  - 登录成功后切主界面
  - 应用退出前注销

## 8. 安全策略

### 已有安全能力
- 服务端密码存储：PBKDF2-HMAC-SHA256

### 本次实现范围
- 客户端不保存明文密码
- “记住账号”只保存账号 Id / 用户名
- 通信中消息内容按 `encoding_rule` 进行编码链处理
- 后续如需更强安全性，再升级 TLS / 会话密钥

## 9. 验证方案

### 9.1 语法与启动
- `python -m py_compile ...`
- `python -m server_app`
- `python -m client_app`

### 9.2 联调场景
1. 正确登录成功
2. 错误密码失败
3. 锁定账号失败
4. 注册成功 / 重名失败
5. 昵称模糊搜索
6. Id 精确搜索
7. 添加好友成功 / 重复添加失败
8. 加载好友列表
9. 发送消息并能拉取显示
10. 注销成功

## 10. 风险点
- 当前项目从简单文本协议升级到 JSON 行协议，前后端需同步修改
- `verify_login()` 当前仅返回布尔值，需要升级为可区分失败原因
- 好友与消息功能需要真实表结构支持，不能只靠 UI 占位
- 编码链实现需保证前后端一致，避免消息不可逆

## 11. 实施顺序
1. 服务端数据库扩展
2. 服务端协议升级
3. 客户端网络控制器
4. 登录/注销接线
5. 注册接线
6. 搜索/添加好友接线
7. 聊天接线
8. 安全编码链接线
9. 联调验证
