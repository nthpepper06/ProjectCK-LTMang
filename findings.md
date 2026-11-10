# Findings & Design Decisions

## System Context
- Python 3.14 on Windows.
- SQLite is the standard embedded SQL engine for Python (`sqlite3`), ideal for standalone server deployment without requiring external database daemon setup, while PostgreSQL schema syntax can be kept compatible.
- In multi-threaded environments, SQLite default configuration (`journal_mode=DELETE`) locks the whole database during writes (`SQLITE_BUSY` error).
- Best practice for multi-threaded SQLite:
  1. `PRAGMA journal_mode=WAL;` (Write-Ahead Logging enables concurrent readers with 1 writer).
  2. `PRAGMA busy_timeout=5000;` (Wait up to 5 seconds for lock release).
  3. `PRAGMA foreign_keys=ON;` (Enforce relational constraints).
  4. Thread-local storage (`threading.local`) so each worker thread gets its own `sqlite3.Connection` handle, preventing SQLite cross-thread connection sharing errors.
  5. Dedicated write mutex lock in `DatabaseConnectionManager` to serialize write transactions safely and prevent database lock contention.
