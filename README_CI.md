CI for Sea Level Dashboard
==========================

This file describes the CI workflow added to the repository.

- Workflow: `.github/workflows/ci.yml` — runs on `push` and `pull_request` for `main`.
- Matrix: Python 3.10 and 3.11.
- Steps: checkout, setup python, install `requirements.txt` (root and `backend/requirements.txt` if present), run `pytest -q`.

Quick notes
-----------

- If you want the workflow to run only on certain paths, edit the `on:` section.
- If tests require additional services (Postgres, Redis), add `services:` or use `docker-compose` in the workflow.

How to run locally
-------------------

1. Create a virtualenv: `python -m venv .venv`
2. Activate: `.\.venv\Scripts\Activate.ps1` (PowerShell)
3. Install deps: `pip install -r requirements.txt` and `pip install -r backend/requirements.txt`
4. Run tests: `pytest -q`
