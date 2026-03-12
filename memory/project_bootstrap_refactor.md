---
name: Bootstrap Refactor
description: Consolidated all setup logic (venv, pip, creds) into src/bootstrap.py; removed duplicated code from shell scripts and run_autograder.py
type: project
---

Unified cross-platform bootstrap completed 2026-03-11. All setup logic (Python check, venv creation, pip install, credential management) moved to `src/bootstrap.py`. Shell wrappers (`run.bat`, `run.sh`) are now ~15 lines each. Removed `run_autograder.bat`, `run_autograder.sh`, `scripts/windows/run.bat`, `scripts/windows/credentials.bat`. Renamed `run_autograder_v1-3.py` → `run_autograder.py`.

**Why:** Duplicated ~150 lines of setup logic across .bat and .sh files led to platform-specific bugs and maintenance burden.

**How to apply:** Any future setup changes (new deps, new credential sources, venv config) go in `src/bootstrap.py` only. Shell wrappers should stay minimal.
