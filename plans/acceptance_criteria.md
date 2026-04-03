# Acceptance Criteria (Experiment 1)

This file maps what must work/appear in the deliverable to the screenshots (`主界面.png`, `用户管理.png`).

## A. Main Window (`主界面.png`)
- Window title: `安全网络聊天工具 - 服务器`.
- Top toolbar contains:
  - Action: `用户管理`
  - Label: `监听端口:`
  - Port selector: `QSpinBox` default **8000**
  - Start button (play/stop icon)
- Upper panel:
  - User avatar list shows **all unlocked users** from SQLite (`locked = 0`)
  - Each item shows avatar icon (or placeholder) + username
- Lower panel:
  - A read-only log console appends timestamped logs
- Start button behavior (stub):
  - First click: disables port selector, switches icon to Stop, logs `Server started (stub) on port <port>`
  - Second click: enables port selector, switches icon to Play, logs `Server stopped (stub)`

## B. User Management Dialog (`用户管理.png`)
- Dialog title: `用户管理`
- Layout:
  - Left: table
  - Right: buttons in column: `添加`, `删除`, `退出`
- Table columns in order:
  1. 用户ID (read-only)
  2. 用户名 (inline editable)
  3. 头像 (shows thumbnail; double-click changes)
  4. 密码 (inline editable; display `******` after save)
  5. 编码规则 (inline editable, comma-separated tokens)
  6. 锁定 (checkbox)
  7. 创建时间 (read-only)
- Persistence:
  - Add/Delete persist in SQLite (`data/server.db`)
  - Inline edits persist immediately:
    - 用户名: must remain unique
    - 密码: stored as salted PBKDF2 hash (no plaintext)
    - 编码规则: only allow base64/hex/caesar
    - 锁定: toggling immediately updates DB and affects MainWindow unlocked list after closing dialog

## C. Database (`data/server.db`)
- `users` table exists with fields:
  - `id` autoincrement primary key
  - `username` unique
  - `avatar` blob
  - `password_salt`, `password_hash` blobs
  - `encoding_rule` JSON text
  - `locked` int 0/1
  - `created_at`, `updated_at` text timestamps

## D. Run
- `pip install -r requirements.txt`
- `python -m server_app`
