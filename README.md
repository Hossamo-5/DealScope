# 🚀 DealScope

**DealScope** is an open-source product monitoring and deal intelligence platform designed to track prices, stock availability, and discount opportunities across multiple e-commerce stores.

It helps developers, marketers, and affiliate businesses automatically discover profitable deals and act on them in real-time.

---

## 🔥 Features

* 🛒 **Product Monitoring**

  * Track product prices across multiple stores
  * Detect price drops and discounts
  * Monitor stock availability (in-stock / out-of-stock)

* ⚡ **Real-Time Alerts**

  * Telegram notifications for important events
  * Customizable alert rules

* 📊 **Admin Dashboard**

  * Built with FastAPI
  * View products, alerts, and system insights
  * Manage monitoring settings

* 🤖 **Automation Engine**

  * Background workers for scraping and monitoring
  * Scalable architecture using async tasks

* 💰 **Affiliate Ready**

  * Discover high-potential deals
  * Use results for content, Telegram channels, or affiliate marketing

---

## 🏗️ Architecture

DealScope is built with a modular and scalable architecture:

- **Frontend:** Vue.js (Admin Dashboard)
- **Backend:** FastAPI (REST APIs)
- **Bot:** Telegram Bot
- **Workers:** Background monitoring & scraping
- **Database:** PostgreSQL / SQLite (configurable)
- **Queue (optional):** Celery / Redis
- **Scraping:** Playwright / Requests

---

## 📦 Project Structure

```
## 📦 Project Structure

dealscope/
│
├── frontend/           # Vue.js admin dashboard
├── admin/              # FastAPI backend (APIs)
├── bot/                # Telegram bot logic
├── monitor/            # Monitoring engine
├── scraper/            # Scraping logic
├── workers/            # Background jobs
├── models/             # Database models
├── core/               # Config & utilities
├── tests/              # Unit tests
│
└── main.py             # Entry point
```

---

## ⚙️ Installation

## ▶️ Running Frontend

```bash
cd frontend
npm install
npm run dev
### 1. Clone the repository

```bash
git clone https://github.com/your-username/dealscope.git
cd dealscope
```

### 2. Create virtual environment

```bash
python -m venv venv
source venv/bin/activate   # Linux / Mac
venv\Scripts\activate      # Windows
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Setup environment variables

Create a `.env` file:

```
TELEGRAM_BOT_TOKEN=your_token
DATABASE_URL=your_database_url
```

---

## ▶️ Running the Project

### Run FastAPI Dashboard

```bash
uvicorn admin.dashboard:app --reload
```

### Run Telegram Bot

```bash
python -m bot.main
```

### Run Workers (optional)

```bash
python -m workers.main
```

---

## 🧠 How It Works

1. Products are added to the system
2. The monitoring engine checks prices & stock periodically
3. Changes are detected (price drop, restock, etc.)
4. Alerts are triggered (Telegram / dashboard)
5. Data is stored for analytics and tracking

---

## 🔐 Security Notes

* Never commit `.env` files
* Keep API keys and tokens private
* Use environment variables in production

---

## 🌍 Use Cases

* Affiliate marketing automation
* Telegram deal channels
* E-commerce analytics
* Price tracking tools
* Personal deal alerts

---

## 🤝 Contributing

Contributions are welcome!

1. Fork the repo
2. Create a new branch
3. Make your changes
4. Submit a pull request

---

## 📄 License

This project is licensed under the MIT License.

---

## 👨‍💻 Author

Built by a passionate Software Engineer focused on:

* Mobile Development (Flutter)
* Automation & AI
* IoT Systems
* Security & Pentesting

---

## ⭐ Support

If you like this project:

* Star the repo ⭐
* Share it with others
* Contribute 🚀

---

## 💡 Future Plans

* AI-powered deal ranking
* Multi-store integrations
* Advanced analytics dashboard
* SaaS version

---

> DealScope — Monitor smarter. Catch deals faster.
