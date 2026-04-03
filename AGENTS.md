# AGENTS.md

## Repository scope

- This file applies to the repository root: `SD1`.
- There was no existing `AGENTS.md` in this repository when this file was created.
- No Cursor rules were found in `.cursor/rules/`.
- No `.cursorrules` file was found.
- No Copilot instructions file was found at `.github/copilot-instructions.md`.

## Project overview

- This is a Python desktop chat project with a PyQt5 client and PyQt5 server UI.
- Main areas:
  - `client_app/`: desktop client, UI + network controller
  - `server_app/`: desktop server UI, TCP/TLS server, SQLite database logic
  - `tests/`: `unittest`-based test suite
  - `plans/`: implementation plans and design notes
  - `tls_support.py`: local TLS certificate/context helpers

## Dependency baseline

- The only declared dependency in `requirements.txt` is:
  - `PyQt5==5.15.10`
- Standard library modules are heavily used:
  - `sqlite3`
  - `socket`, `socketserver`, `ssl`
  - `threading`
  - `unittest`

## Primary run commands

Run these from the repository root.

### Install dependencies

```powershell
python -m pip install -r requirements.txt
```

### Start the server UI

```powershell
python -m server_app
```

### Start the client UI

```powershell
python -m client_app
```

## Test commands

This repository currently uses `unittest`, not `pytest`.

### Run the full test suite

```powershell
python -m unittest discover -s tests -p "test_*.py"
```

### Run a single test file

```powershell
python -m unittest tests.test_secure_chat_tls_presence
```

```powershell
python -m unittest tests.test_client_app_message_mapping
```

### Run a single test case class

```powershell
python -m unittest tests.test_secure_chat_tls_presence.SecureChatTLSPresenceTest
```

### Run a single test method

```powershell
python -m unittest tests.test_secure_chat_tls_presence.SecureChatTLSPresenceTest.test_tls_message_roundtrip
```

## Syntax / compile checks

There is no configured linter in the repository today. The most reliable lightweight validation is `py_compile`.

### Check one file

```powershell
python -m py_compile "client_app/app.py"
```

### Check several files

```powershell
python -m py_compile "client_app/app.py" "client_app/network/client_controller.py" "server_app/network/server_controller.py"
```

### Recommended pre-finish validation

```powershell
python -m py_compile "client_app/app.py" "client_app/network/client_controller.py" "client_app/ui/chat_window.py" "server_app/db.py" "server_app/network/server_controller.py" "tls_support.py"
python -m unittest discover -s tests -p "test_*.py"
```

## Files and entry points that matter most

### Client

- `client_app/__main__.py`: client module entry point
- `client_app/app.py`: main application orchestration
- `client_app/network/client_controller.py`: request/response transport layer
- `client_app/protocol.py`: JSON line protocol encode/decode
- `client_app/ui/login_window.py`: login UI
- `client_app/ui/register_dialog.py`: registration UI
- `client_app/ui/chat_window.py`: chat UI and list rendering

### Server

- `server_app/__main__.py`: server module entry point
- `server_app/app.py`: server UI startup and DB bootstrap
- `server_app/db.py`: SQLite schema and query layer
- `server_app/network/server_controller.py`: TCP/TLS server and request dispatch
- `server_app/protocol.py`: request parsing and response encoding
- `server_app/security.py`: password hashing and verification
- `server_app/ui/main_window.py`: server UI shell

### Tests

- `tests/test_client_app_message_mapping.py`: message/error mapping tests with mocked PyQt modules
- `tests/test_secure_chat_tls_presence.py`: TLS, presence, and message roundtrip integration-style tests

## Current repository conventions

These rules are inferred from the existing codebase and should be followed unless the user explicitly asks for a different direction.

### Imports

- Use `from __future__ import annotations` at the top of Python modules.
- Group imports in this order:
  1. standard library
  2. third-party modules
  3. local package imports
- Prefer explicit local imports like `from .network import ClientController` or `from ..db import Database`.
- Remove unused imports when editing files.

### Formatting

- Follow existing formatting style; there is no enforced formatter config in the repo.
- Keep lines and blocks readable rather than over-compressed.
- Use blank lines between top-level functions/classes.
- Prefer concise docstrings; many modules use none unless the explanation is genuinely helpful.

### Naming

- Classes use `PascalCase`.
- Functions, methods, variables, and module-level helpers use `snake_case`.
- Private helpers use a leading underscore, e.g. `_request`, `_with_presence`, `_logout_current_user`.
- Constants use `UPPER_SNAKE_CASE`, e.g. `ERROR_MESSAGE_MAP`, `ALLOWED_ENCODINGS`.
- Qt signal names are descriptive snake_case, e.g. `login_requested`, `messages_loaded`.

### Types

- Use Python 3.10+ type syntax already present in the repo, e.g. `dict[str, Any] | None`.
- Add type hints to new public functions and most internal helpers.
- Preserve concrete container types where they improve readability.
- Prefer precise signatures over untyped `dict` / `list` when practical, but match surrounding file style.

### Data handling

- Network request/response payloads are plain dictionaries encoded as JSON lines.
- Keep protocol payloads explicit and stable.
- Preserve backward-compatible response keys when extending server actions.
- Presence-like derived fields belong in network response assembly, not in the SQLite schema, unless requirements change.

### Error handling

- Do not swallow exceptions silently.
- Existing code often converts failures into structured responses or user-visible messages.
- For request handlers, prefer returning `encode_response_line(ok=False, code=..., message=...)` rather than crashing the handler.
- For client network failures, preserve the current pattern of closing the socket and returning a `network_error` payload.
- If you catch a broad exception, do something concrete with it: log, map to a response, or re-raise.

### UI / Qt patterns

- Keep orchestration in `ClientApplication` rather than pushing business logic deep into UI widgets.
- `ChatWindow`, `LoginWindow`, and dialogs emit signals; the application layer wires them to network actions.
- Prefer signal/slot integration over tightly coupling widgets to transport code.
- When updating list widgets, preserve user context where possible; avoid unnecessary resets that change the current selection.

### Networking patterns

- The current client transport is synchronous request/response over a persistent TLS socket.
- Do not introduce server-push or background read loops casually; that changes the communication model.
- Minimal-churn extensions should reuse existing actions like `list_friends`, `pull_messages`, and JSON line responses.

### Database patterns

- Use short-lived SQLite connections via `with self.connect() as conn:`.
- Keep schema changes minimal and explicit.
- Default DB journal mode is currently configurable via `Database(..., journal_mode=...)`.
- Test-only DB behavior may differ from production behavior when needed for Windows cleanup stability.

## Testing expectations for agents

- Prefer targeted tests first, then broader test runs.
- If you change client message mapping, run:

```powershell
python -m unittest tests.test_client_app_message_mapping
```

- If you change TLS, presence, server networking, or chat transport, run:

```powershell
python -m unittest tests.test_secure_chat_tls_presence
```

- If you touch several cross-cutting files, run the full test discovery command.
- If no test covers your change, at minimum run `py_compile` on all edited files.

## Agent boundaries

### Always

- Use commands that are real for this repository.
- Validate edited Python files with `py_compile`.
- Run targeted `unittest` commands for impacted areas.
- Match the surrounding module style rather than inventing a new architectural pattern.

### Ask first

- Major protocol redesigns
- SQLite schema changes
- New third-party dependencies
- Replacing the synchronous client transport model
- Large UI rewrites rather than incremental changes

### Never

- Do not invent `pytest`, `ruff`, `black`, `mypy`, or `make` commands as if they are configured here.
- Do not assume Cursor or Copilot rules exist when they do not.
- Do not commit secrets, generated private keys, or unrelated local artifacts.
- Do not use type suppression shortcuts or leave broken code behind.

## Definition of done

A change is not done until all applicable items below are true:

- Edited files compile with `python -m py_compile ...`
- Relevant `unittest` targets pass
- No unused imports or obviously dead code were introduced
- The change follows existing module boundaries and naming patterns
- User-visible messages remain clear and consistent with the rest of the app
