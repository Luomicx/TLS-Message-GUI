# 项目上下文

## 项目概览
- 项目名称：Secure IM Tool（实验一：服务端界面）
- 技术栈：Python、PyQt5、SQLite
- 运行方式：`python -m server_app`
- 依赖：`PyQt5==5.15.10`
- 数据库文件：`data/server.db`

## 目录结构
- `server_app/__main__.py`：模块启动入口
- `server_app/app.py`：应用启动与初始化
- `server_app/db.py`：数据库连接、建表、种子数据、用户增删改查与登录校验
- `server_app/security.py`：密码哈希与校验
- `server_app/network/server_controller.py`：服务端控制器，处理简单的登录/注销协议
- `server_app/ui/main_window.py`：主窗口
- `server_app/ui/user_management_dialog.py`：用户管理弹窗
- `server_app/ui/add_user_dialog.py`：新增用户弹窗
- `server_app/ui/avatar.py`：头像生成与渲染
- `data/server.db`：SQLite 数据库
- `plans/*.md`：实验计划与验收标准

## 启动流程
1. `server_app/__main__.py` 调用 `app.main()`。
2. `server_app/app.py` 创建 `QApplication`。
3. 初始化 `data` 目录与 `data/server.db`。
4. 构造 `Database`，执行 `init_schema()` 建表。
5. 执行 `ensure_seed_users()` 初始化演示用户。
6. 创建 `MainWindow` 并显示界面。

## 核心模块职责

### 1. 应用入口
`server_app/app.py`
- 负责 Qt 应用初始化
- 负责数据库文件路径准备
- 负责数据库 schema 初始化和演示数据注入
- 负责创建主窗口

### 2. 数据层
`server_app/db.py`
- 使用 SQLite 作为本地持久化存储
- `connect()` 中启用了 `row_factory`、`foreign_keys`、`WAL`
- `init_schema()` 创建 `users` 表和索引
- `ensure_seed_users()` 在空库时插入演示账号
- 提供以下核心能力：
  - `insert_user()`：新增用户
  - `list_users()`：查询全部用户
  - `list_unlocked_users()`：查询未锁定用户
  - `verify_login()`：校验登录
  - `delete_user()`：删除用户
  - `update_username()`：修改用户名
  - `update_locked()`：修改锁定状态
  - `update_encoding_rule()`：修改编码规则
  - `update_password()`：修改密码
  - `update_avatar()`：修改头像

### 3. 安全层
`server_app/security.py`
- 使用 `PBKDF2-HMAC-SHA256` 处理密码
- 参数：
  - 迭代次数：`120000`
  - 盐长度：`16` 字节
  - 摘要长度：`32` 字节
- `hash_password()`：生成盐和摘要
- `verify_password()`：使用恒定时间比较校验密码

### 4. 网络层
`server_app/network/server_controller.py`
- 基于 `socketserver.ThreadingTCPServer`
- `ServerController` 负责服务启动、停止、状态维护
- 协议为按行读取的简单文本命令：
  - `LOGIN <username> <password>`
  - `LOGOUT <username>`
- 登录时调用 `Database.verify_login()` 判断是否成功
- 通过 `log_signal` 将日志发送到 UI

### 5. 界面层

#### 主窗口
`server_app/ui/main_window.py`
- 窗口标题：`安全网络聊天工具 - 服务器`
- 包含工具栏、端口选择、启动/停止按钮
- 展示未锁定用户头像列表
- 展示日志面板
- 与 `ServerController` 连接，负责启动/停止服务
- 可打开用户管理弹窗

#### 用户管理
`server_app/ui/user_management_dialog.py`
- 展示用户表格
- 支持添加、删除、编辑用户
- 支持双击头像单元格修改头像
- 支持直接修改：
  - 用户名
  - 密码
  - 编码规则
  - 锁定状态
- 修改后立即写入数据库

#### 新增用户
`server_app/ui/add_user_dialog.py`
- 用于录入用户名、密码、头像、编码规则、锁定状态
- 保存后插入数据库

#### 头像处理
`server_app/ui/avatar.py`
- 提供默认头像生成
- 支持从数据库 BLOB 渲染头像

## 数据模型
数据库表：`users`
- `id`：主键，自增
- `username`：用户名，唯一，非空
- `avatar`：头像二进制数据，可空
- `password_salt`：密码盐，非空
- `password_hash`：密码摘要，非空
- `encoding_rule`：编码规则，JSON 文本
- `locked`：锁定状态，0/1
- `created_at`：创建时间
- `updated_at`：更新时间

## 业务规则
- 锁定用户不会出现在主界面用户列表中
- 登录时若用户不存在或已锁定，则登录失败
- 密码不以明文保存，只保存盐和哈希摘要
- 编码规则只允许以下值：
  - `base64`
  - `hex`
  - `caesar`
- 编码规则支持逗号分隔文本或 JSON 数组输入，并会去重、转小写

## 当前项目特点
- 这是一个以界面为主的实验项目，不是完整的即时通信服务端
- 具备最小可运行的 TCP 登录/注销控制逻辑
- 界面、数据库和简单网络控制器已经串联完成
- 项目中已包含实验计划文档与验收标准，适合作为课程作业交付基础

## 适合后续扩展的方向
- 增加更完整的消息协议
- 增加服务端日志落盘
- 增加真实在线用户状态管理
- 增加更严格的输入校验与异常处理
- 增加自动化测试
