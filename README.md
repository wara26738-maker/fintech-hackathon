# 🏦 Banking AI Agent — Fintech Hackathon

> An AI-powered banking agent integrated into existing banking apps,
> making financial management smarter, more accessible, and personalized.

[![Python](https://img.shields.io/badge/Python-3.11-blue)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.111-green)](https://fastapi.tiangolo.com/)
[![License](https://img.shields.io/badge/License-Hackathon-yellow)]()

---

## 🎮 Live Demo

**🚀 Try it now:** [**fintech-hackathon-production-7c97.up.railway.app**](https://fintech-hackathon-production-7c97.up.railway.app)

### Try These Commands

| Command | What it does |
|---|---|
| `Check balance` | View your balance |
| `Show transactions` | Recent transactions |
| `Transfer 500 to Mom` | Send money (🟡 confirm) |
| `Transfer 5000 to Mom` | Send money (🔴 OTP) |
| `What am I paying for` | View subscriptions |
| `Cancel Netflix` | Cancel subscription |
| `Show cards` | View cards |
| `Block card` | Block card (🟡 confirm) |
| `Report card lost` | Report lost (🔴 OTP) |
| `Show contacts` | View beneficiaries |
| `My profile` | View profile |
| `help` | Show all commands |

**💡 I understand natural language — try typing any way you like!**

---

## ✨ Key Features

- 🗣️ **Natural Language** — Chat with your bank like a human
- 🔒 **3-Tier Permissions** — 🟢 Green / 🟡 Yellow / 🔴 Red
- 🔐 **OTP Verification** — Strong MFA for high-risk actions
- 🤖 **6 Core Scenarios** — Transfers, bills, wealth, cards, subs, cross-scenario
- 📊 **Audit Logs** — Every action tracked and traceable

**[📄 Read the full Project Brief (≤ 200 words) →](docs/brief.md)**

---

## 📄 Documents

- [project structure](docs/project-structure.md)
- [techstack](docs/techstack.md)
- [security](docs/securiy.md)

## 🚀 Quick Start

```bash
# 1. Clone
git clone https://github.com/wara26738-maker/fintech-hackathon.git
cd fintech-hackathon

# 2. Virtual environment
python3.11 -m venv .venv
source .venv/bin/activate        # macOS / Linux
# .venv\Scripts\activate          # Windows

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure environment
cp .env.example .env

# 5. Run the API
python -m src.api.main
# 5. (Optional) Initialize the local database
python scripts/init_db.py

# 6. Run the agent
python main.py
