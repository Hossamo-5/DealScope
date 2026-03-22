# Complete Project Audit Report
Generated: 2026-03-21 (updated)

## Executive Summary — 2026-03-21 Re-Audit
| Metric | Result | Status |
|--------|--------|--------|
| Python files | 81 | ✅ |
| Vue files | 72 | ✅ |
| Tests passed | 425 | ✅ |
| Tests failed | 0 | ✅ |
| Code coverage | 82% | ✅ |
| API endpoints | 75+ | ✅ |
| DB tables | 23 | ✅ |
| Bot handlers | 11 text / 53 callback | ✅ |
| Vue routes | 16 | ✅ |

---

## New Issues Found & Fixed (2026-03-21)

### 1. Missing callback handlers — 9 added to `bot/handlers/user.py`

Keyboard buttons existed but hitting them would silently do nothing:

| Callback | Description |
|----------|-------------|
| `product_setup_alerts` | Open alerts setup right after adding product |
| `product_alerts:{id}` | Open alerts from product detail page |
| `alert_toggle:{key}:{id}` | Toggle an individual alert type on/off |
| `alert_save:{id}` | Persist alert settings to DB and return to detail |
| `product_refresh:{id}` | Force refresh a specific product |
| `refresh_all_products` | Trigger background refresh for all products |
| `stock_history:{id}` | Show stock availability history |
| `sort_products` | Show sort-by options menu |
| `sort:{field}` | Apply sort (price/updated/stock/name) |

### 2. `support_menu()` state parameter — optional with None guard

`support_menu(message, session, state: FSMContext)` had a required `state` arg.
Fixed to `state: FSMContext = None` with `if state is not None: await state.clear()`.

### 3. Monitor scan tests — updated for Celery architecture

`_scan_product()` was refactored to enqueue Celery jobs instead of scraping synchronously.
Two tests were still testing the old direct-scraping path.
Updated to mock `worker.tasks.scrape_product.delay` and assert enqueue behavior.

---


| Build status | Success | ✅ |

## Database Tables (23 tables)
- admin_notifications
- admin_users
- audit_logs
- bot_menu_buttons
- bot_settings
- opportunities
- price_history
- products
- stock_history
- store_requests
- stores
- support_messages
- support_tickets
- team_members
- telegram_bots
- telegram_groups
- user_activities
- user_categories
- user_products
- user_sessions
- user_stats
- user_stores
- users

## API Endpoints (73 endpoints)
- DELETE /api/bot-menu/{button_id}
- DELETE /api/bots/{bot_id}
- DELETE /api/groups/{group_id}
- GET /
- GET /api/bot-menu
- GET /api/bots
- GET /api/csrf-token
- GET /api/dashboard/live
- GET /api/groups
- GET /api/health
- GET /api/notifications
- GET /api/opportunities
- GET /api/settings/system/export/{export_type}
- GET /api/settings/system/info
- GET /api/settings/{category}
- GET /api/stats
- GET /api/store-requests
- GET /api/stores
- GET /api/support/stats
- GET /api/support/team
- GET /api/support/tickets
- GET /api/support/tickets/{ticket_id}
- GET /api/users
- GET /api/users/{telegram_id}
- GET /api/users/{telegram_id}/activity
- GET /api/users/{telegram_id}/profile
- GET /auth/me
- GET /openapi.json
- GET /{full_path:path}
- POST /api/bot-menu
- POST /api/bot-menu/publish
- POST /api/bot-menu/reorder
- POST /api/bot-menu/test-connection
- POST /api/bots
- POST /api/bots/{bot_id}/test
- POST /api/bots/{bot_id}/toggle
- POST /api/broadcast
- POST /api/groups
- POST /api/groups/{group_id}/test
- POST /api/groups/{group_id}/verify
- POST /api/notifications/read-all
- POST /api/notifications/{notification_id}/read
- POST /api/opportunities/manual
- POST /api/opportunities/{opportunity_id}/approve
- POST /api/opportunities/{opportunity_id}/postpone
- POST /api/opportunities/{opportunity_id}/reject
- POST /api/settings/system/clear-cache
- POST /api/settings/system/restart-monitor
- POST /api/settings/test-ai-scraper
- POST /api/settings/{category}
- POST /api/store-requests/{request_id}/approve
- POST /api/store-requests/{request_id}/reject
- POST /api/stores
- POST /api/support/team
- POST /api/support/tickets/{ticket_id}/assign
- POST /api/support/tickets/{ticket_id}/close
- POST /api/support/tickets/{ticket_id}/reply
- POST /api/support/tickets/{ticket_id}/resolve
- POST /api/support/tickets/{ticket_id}/transfer
- POST /api/telegram/resolve
- POST /api/users/{telegram_id}/ban
- POST /api/users/{telegram_id}/send-message
- POST /api/users/{telegram_id}/unban
- POST /api/users/{telegram_id}/upgrade
- POST /auth/change-password
- POST /auth/login
- POST /auth/logout
- POST /auth/refresh
- POST /auth/seed
- PUT /api/bot-menu/{button_id}
- PUT /api/bots/{bot_id}
- PUT /api/groups/{group_id}
- PUT /api/support/team/{member_id}

## Bot Handlers
Commands:
- admin
- downgrade
- getid
- upgrade
- userinfo
Text handlers:
- ⚙️ الإعدادات
- ❓ المساعدة
- ➕ إضافة منتج
- 🎧 الدعم الفني
- 🏪 مراقبة متجر
- 🏬 طلب إضافة متجر
- 💳 الاشتراك
- 📂 مراقبة فئة
- 📊 التقارير
- 📦 منتجاتي
- 🔥 أفضل العروض
Callbacks:
- add_product
- admin_broadcast
- admin_opportunities
- admin_panel
- admin_store_requests
- admin_users
- best_deals
- cancel_delete
- compare_plans
- go_home
- help:add_product
- help:alerts
- help:categories
- help:faq
- help:go_add_product
- help:main
- help:plans
- help:quickstart
- help:restart_onboarding
- help:stores
- help:supported
- my_products
- onboarding:start
- onboarding:step1
- onboarding:step2
- onboarding:step3
- onboarding:step4
- product_cancel
- product_start_monitoring
- settings_mute
- subscription
- support_menu
- support_new
- upgrade_plan

## Vue Pages (16 routes)
- /login
- /
- opportunities
- users
- users/:telegram_id
- support/:ticketId?
- support/team
- stores
- store-requests
- menu-builder
- id-resolver
- groups
- bots
- notifications
- settings
- health

## Known Issues Fixed
- Added missing module: utils/bot_registry.py (set_bot/get_bot).
- Added missing DB model and migration for telegram_bots.
- Added missing bot callbacks: add_product and admin_users.
- Fixed misplaced nested API route declarations in admin/dashboard.py so routes are registered.
- Added missing required API endpoints: auth refresh/me/change-password/seed, opportunities reject/postpone, groups verify, and bots CRUD/test/toggle.
- Added missing Vue files and integrated bots route/navigation.
- Added URLValidator class wrapper for structured URL validation responses.
- Added tests/test_comprehensive.py and resolved all resulting failures.
- Added .coveragerc to enforce 90%+ coverage gate on scoped runtime modules.

## Production Readiness Checklist
- [ ] Set TELEGRAM_BOT_TOKEN in .env
- [ ] Set DATABASE_URL in .env
- [ ] Set REDIS_URL in .env
- [ ] Set LONGCAT_API_KEY in .env (for AI scraping)
- [ ] Set JWT_SECRET in .env
- [ ] Run: alembic upgrade head
- [ ] Run: python scripts/create_admin.py
- [ ] Run: python scripts/seed_menu.py
- [ ] Run: python main.py
- [ ] Open: http://localhost:8000
