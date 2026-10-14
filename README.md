# Banking AI Agent — Fintech Hackathon

An intelligent banking assistant that understands natural-language financial intent,
plans multi-step task chains, and executes banking operations within a strict
security and permission framework.

---

## 🎯 Concept

Mobile banking today is fragmented across many entry points and long user journeys.
This project explores a **"just say it and get it done"** experience using multimodal
LLMs and agent technology.

The agent:
- Understands vague, implicit, or incomplete financial requests in natural language
- Decomposes complex goals into an ordered DAG of executable tasks
- Executes banking operations under a strict risk-tiered permission model
- Supports interruption, rollback, and human takeover during execution

**Industry reference:** Revolut AIR

---

## 🧠 AI Technologies

| Technology | Purpose |
|---|---|
| LLM (Function Calling / Tool Use) | Parse user intent and invoke banking tools |
| Retrieval-Augmented Generation (RAG) | Ground responses in real account, transaction, and product data |
| DAG-based Task Planner | Decompose multi-step goals into ordered, dependency-aware tasks |
| Prompt Injection Defense | Detect and block malicious or manipulated inputs |
| Sandboxed Code Execution | Run generated code in a restricted, monitored environment |
| Multi-Factor Authentication (MFA) | Enforce strong verification for high-risk actions |

---

## 🏗️ Architecture

### High-Level Flow


### Core Components

- **Intent Layer** — LLM parses natural language, handles ambiguity and implicit intent
- **Planner Layer** — Builds a DAG of tasks with dependencies and rollback points
- **Security Layer** — Enforces permission tiers, MFA, prompt-injection defense, safety lock
- **Execution Layer** — Invokes banking tools inside a restricted sandbox
- **Audit Layer** — Stores complete decision and execution logs for traceability

> 📌 *Insert architecture diagram image here (e.g., `docs/architecture.png`)*

---

## 🔐 Permission Tiers

| Tier | Policy | Examples |
|---|---|---|
| 🟢 Green | Automatic | Balance, transaction and bill queries; investment-return queries |
| 🟡 Yellow | User confirmation | Transfers up to RMB 1,000/day; subscription cancellation; virtual-card application |
| 🔴 Red | Strong verification (MFA) | Transfers above RMB 1,000/day; password changes; card loss; investment subscription |

---

## 📄 Documentation

- [Non-Technical Summary](docs/non-technical-summary.md)
- [Technical Documentation](docs/technical.md)
- [Security Self-Assessment](docs/security.md)
- [Deployment Guide](docs/deployment.md)
- [Test Cases](docs/testcases.md)
- [Project Brief](docs/brief.md)
- [Project Structure](docs/project-structure.md)
- [Tech stack](docs/techstack.md)
- [Tech stack (non-technical)](docs/nontechnical-techstack.md)

## 📦 Supported Scenarios

1. **Smart Transfers** — Transfer by name, phone, or note; scheduled transfers; split-bill collection
2. **Bill Analysis** — Spending categories; unusual-transaction detection; monthly/annual reports
3. **Wealth Operations** — Product recommendation, comparison, risk assessment, subscribe/redeem
4. **Card Management** — Card application, limit adjustment, unlocking, loss reporting
5. **Subscriptions & Direct Debit** — Detect recurring charges, renewal reminders, one-click cancellation
6. **Cross-Scenario Orchestration** — e.g., detect a spouse's birthday, reserve RMB 1,000, order flowers and cake two days in advance

---

## ⚙️ Installation

### Prerequisites
- Python 3.10+
- pip / virtualenv
- Git
- (Optional) Docker for sandboxed execution

### Steps

```bash
# 1. Clone the repository
git clone https://github.com/wara26738-maker/fintech-hackathon.git
cd fintech-hackathon

# 2. Create and activate a virtual environment
python -m venv venv
source venv/bin/activate        # macOS / Linux
venv\Scripts\activate           # Windows

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure environment variables
cp .env.example .env
# Then edit .env and fill in your API keys and configuration

# 5. (Optional) Initialize the local database
python scripts/init_db.py

# 6. Run the agent
python main.py
