# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**DealScope** is a professional Telegram bot for monitoring product prices, stock availability, and deals from various online stores (Amazon, Shopify, WooCommerce, etc.). It features an integrated affiliate system and a complete web admin dashboard.

### Key Features
- 🛍️ Product, category, and store monitoring
- 🔔 Price drop, stock availability, and target price alerts
- 💡 Automatic opportunity detection with scoring (0-100)
- 🌐 Complete FastAPI admin dashboard
- 📊 User activity tracking and analytics
- 🎧 Integrated support ticket system
- 📱 Custom bot menu system
- 🔒 Security features (rate limiting, JWT auth)

## Architecture

### Core Components
```
dealscope/
├── main.py                    # Entry point - runs bot + dashboard
├── config/settings.py         # All settings (API keys, limits, intervals)
├── db/models.py              # SQLAlchemy database models (28 tables)
├── core/monitor.py           # Monitoring engine + opportunity scorer
├── core/connectors/          # Store connectors (Amazon, generic)
├── bot/handlers/            # Telegram bot handlers (user, admin)
├── admin/dashboard.py       # FastAPI admin dashboard
├── worker/                  # Celery tasks for scraping
└── tests/                   # Comprehensive test suite
```

### Data Flow
1. **Bot receives commands** → Middleware processes → Handler executes
2. **Monitoring engine** → Queues scrape tasks → Celery workers process → DB updated
3. **Opportunity detection** → Score calculated → Admin notified → Approval/Rejection
4. **User alerts** → Redis pub/sub → Telegram notifications

## Common Development Tasks

### Running the Bot
```bash
# Install dependencies
pip install -r requirements.txt
playwright install chromium  # Required for browser automation

# Set up environment
cp .env.example .env
# Edit .env with your API keys

# Run directly
python main.py

# Or using the batch file (Windows)
start_bot.bat
```

### Database Operations
```bash
# Create tables (automatic on first run)
# Manual migration if needed
alembic upgrade head

# Create new migration
alembic revision --autogenerate -m "Description"
```

### Running Tests
```bash
# Run all tests
pytest tests/ -v

# Run specific test file
pytest tests/test_monitor.py -v

# Run with coverage
pytest --cov=dealscope tests/

# Run specific test function
pytest tests/test_crud.py::test_create_user -v
```

### Code Quality
```bash
# Check for import issues
python -m py_compile dealscope/*.py

# Run audit scripts (if available)
python tests/_audit/phase1_import_check.py
```

## Key Files and Their Responsibilities

### Configuration
- `config/settings.py` - **ONLY FILE** that needs modification for API keys and settings
- `.env` - Environment variables (never commit this)
- `requirements.txt` - Python dependencies

### Database (SQLAlchemy Models)
Major tables:
- `User` - Bot users with subscription plans
- `Product` - Monitored products
- `UserProduct` - Many-to-many relationship with alert settings
- `PriceHistory` / `StockHistory` - Historical tracking
- `Opportunity` - Discounted products for admin approval
- `StoreRequest` - User requests to add new stores

### Bot Handlers
- `bot/handlers/user.py` - Basic user commands (add product, list products)
- `bot/handlers/user2.py` - Deals, subscriptions, settings
- `bot/handlers/admin.py` - Admin commands and opportunity management

### Core Logic
- `core/monitor.py` - Main monitoring loop and opportunity scoring
- `core/connectors/amazon.py` - Amazon-specific scraping
- `core/connectors/generic.py` - Generic store connector (Shopify, WooCommerce)
- `core/connectors/ai_scraper.py` - AI-powered fallback scraper

### Admin Dashboard (FastAPI)
- `admin/dashboard.py` - Main FastAPI app
- `admin/routes/` - API endpoints (system, notifications, etc.)

### Worker System
- `worker/tasks.py` - Celery tasks for product scraping
- `worker/celery_app.py` - Celery configuration
- `worker/rate_limit.py` - Rate limiting logic

## Technical Details

### Monitoring Engine
- Runs in infinite loop, checks products every minute
- Respects user's subscription plan scan intervals
- Prevents duplicate URL scanning across users
- Calculates opportunity scores (0-100) based on:
  - Discount percentage (40% weight)
  - Product rating (20% weight)
  - Review count (15% weight)
  - Stock availability (10% weight)
  - Historical low price (15% weight)

### Security Features
- Rate limiting with `slowapi`
- JWT authentication for dashboard
- Redis-based FSM storage for bot state
- Activity tracking middleware
- Admin notification system

### AI Integration
- LongCat AI API for intelligent scraping
- Fallback mode: CSS selectors first, AI if fails
- Primary mode: AI first, CSS as backup

## Testing

### Test Categories
1. **Unit Tests** - Individual components (CRUD, connectors)
2. **Integration Tests** - Bot handlers, dashboard endpoints
3. **E2E Tests** - Complete user flows, API integration
4. **Security Tests** - Dashboard authentication, rate limiting

### Key Test Files
- `tests/test_crud.py` - Database operations
- `tests/test_monitor.py` - Monitoring engine
- `tests/test_amazon_connector.py` - Amazon scraping
- `tests/test_dashboard.py` - Dashboard endpoints
- `tests/e2e/test_bot_flows.py` - End-to-end bot interactions

## Deployment

### Docker (Recommended)
```bash
docker-compose up -d
```

### Manual Production
1. Set up PostgreSQL 14+ and Redis 7+
2. Configure environment variables
3. Run with process manager (systemd, supervisor)
4. Use HTTPS for dashboard in production

## Important Notes

- **Never commit `.env`** - Contains sensitive API keys
- **Change `SECRET_KEY`** in production for dashboard session encryption
- **Run `playwright install chromium`** once after installation
- **Check logs** at `logs/bot.log` for debugging
- **Dashboard URL** - http://localhost:8000 (after bot starts)
- **Conflict handling** - Use `start_bot.bat` to kill old instances

## Troubleshooting

### Common Issues
1. **"Conflict" error** - Another bot instance running, use `start_bot.bat`
2. **Database connection failed** - Check PostgreSQL is running and `DATABASE_URL`
3. **Redis unavailable** - Falls back to memory storage (not recommended for production)
4. **Scraping failures** - Check Playwright installation and site accessibility

### Log Messages to Watch For
- ✅ Database ready
- ✅ All handlers registered
- ✅ Monitoring engine started
- 📊 Dashboard: http://localhost:8000