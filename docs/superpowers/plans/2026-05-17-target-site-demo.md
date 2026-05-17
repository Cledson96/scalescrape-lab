# Target Site Demo Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a polished target-site demo with scalable fake data while preserving scraper compatibility.

**Architecture:** Keep data generation and external normalization in `fake_data.py`, presentation in `views.py`, and route orchestration in `main.py`. Tests exercise pure functions first, then route-rendering selectors indirectly.

**Tech Stack:** Python 3.12, FastAPI, stdlib `urllib`, `unittest`, Docker Compose.

---

### Task 1: Fake Data Source

**Files:**
- Create: `apps/target_site/app/fake_data.py`
- Modify: `tests/test_core_behaviors.py`

- [ ] Add failing tests for deterministic local records, page slicing and RandomUser payload normalization.
- [ ] Run `python -m unittest discover -s tests -v` and confirm the new tests fail because `fake_data.py` is missing.
- [ ] Implement `PublicRecord`, `get_local_records`, `paginate_records`, `normalize_randomuser_payload` and `get_external_records`.
- [ ] Run the same test command and confirm the tests pass.
- [ ] Commit with `feat: adicionar massa fake ao target site`.

### Task 2: Visual Views

**Files:**
- Create: `apps/target_site/app/views.py`
- Modify: `tests/test_core_behaviors.py`

- [ ] Add failing tests confirming rendered list HTML contains `.item-card`, `.item-title`, `.detail-link` and `.next-page`.
- [ ] Run tests and confirm failure because `views.py` is missing.
- [ ] Implement shared layout, home view, list view, detail view and scenario cards.
- [ ] Run tests and confirm pass.
- [ ] Commit with `feat: melhorar interface visual do target site`.

### Task 3: Route Integration

**Files:**
- Modify: `apps/target_site/app/main.py`
- Modify: `README.md`

- [ ] Wire `/`, `/items`, `/external/items`, `/items/{item_id}`, `/protected/items` and scenario routes to the new data/views.
- [ ] Keep existing anti-bot, captcha, rate-limit and layout-changed behavior intact.
- [ ] Update README with the visual demo URLs and the external fake data behavior.
- [ ] Run unit tests and a Docker smoke test.
- [ ] Verify the target visually in the in-app browser.
- [ ] Commit route and docs changes with small conventional commits.
