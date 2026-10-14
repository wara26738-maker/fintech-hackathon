# Tech Stack — Non-Technical Explanation

> A plain-language overview of the technologies we use.
> No technical background needed.

---

## 🎯 What is a "Tech Stack"?

Think of a tech stack as the **ingredients and tools** we use to build our Banking AI Agent.

Just like a restaurant needs:
- Ingredients (vegetables, meat)
- Tools (pots, pans, knives)
- Kitchen (the space to cook)
- Staff (chefs, servers)

Our project needs:
- **Programming languages** (how we talk to computers)
- **Frameworks** (pre-built tools)
- **Services** (external helpers)
- **Infrastructure** (where everything runs)

---

## 🧩 Our Tech Stack — In Plain Words

### 1. 🐍 Programming Language: Python

**What it is:** The language we use to write the code.

**Why we chose it:** Python is the most popular language for AI. It's easy to read and has the most AI tools available.

**Analogy:** Like choosing English as the language to write a book — because everyone speaks it.

---

### 2. 🌐 API Framework: FastAPI

**What it is:** A tool that lets different programs talk to each other.

**Why we need it:** Our AI Agent needs a way to receive messages from users (via the app or website) and send responses back.

**Analogy:** Like a **waiter** in a restaurant — takes your order and brings your food.

**Plain-language:** It's the "messenger" between the user and the AI.

---

### 3. 🗄️ Database: SQLite

**What it is:** A simple way to store information.

**Why we need it:** To remember things like:
- User accounts and balances
- Transactions
- Cards
- Subscriptions

**Analogy:** Like a **filing cabinet** where we keep all the documents.

**Why SQLite:** It's free, simple, and doesn't need a separate server. Perfect for a demo.

---

### 4. 🧠 AI Engine: Large Language Model (LLM)

**What it is:** The "brain" that understands what users say.

**Why we need it:** To understand natural language like:
- "Send 500 to mom"
- "How much did I spend this month?"

**Analogy:** Like a **smart assistant** who understands what you mean, even if you don't say it perfectly.

**Options:** OpenAI GPT-4o, DeepSeek, or other LLMs.

---

### 5. 🔒 Security Tools

**What they are:** Tools that keep users safe.

| Tool | What it does | Plain Words |
|---|---|---|
| **JWT** | Verifies identity | Like an ID card |
| **MFA** | Extra verification | Like a second lock on the door |
| **Sandbox** | Safe execution | Like a playpen for code |
| **Audit Log** | Records everything | Like a security camera |

---

### 6. 💻 Frontend: HTML, CSS, JavaScript, react

**What it is:** The visual part users see.

**Why we need it:** To give users a chat interface.

**Analogy:** Like the **menu and dining area** in a restaurant.

---

### 7. 🛠️ Development Tools

| Tool | What it does | Plain Words |
|---|---|---|
| **Git** | Tracks changes | Like "Track Changes" in Word |
| **GitHub** | Stores code online | Like Google Drive for code |
| **VS Code** | Code editor | Like Microsoft Word for code |
| **venv** | Isolated environment | Like a separate kitchen for each recipe |

---

## 🍽️ Full Analogy: Our Project as a Restaurant

| Restaurant | Our Project |
|---|---|
| **Menu** | API endpoints (what you can ask for) |
| **Kitchen** | FastAPI + Python (where the work happens) |
| **Chef** | AI Agent (makes decisions) |
| **Recipe Book** | LLM (knows how to respond) |
| **Filing Cabinet** | SQLite (stores data) |
| **Waiter** | FastAPI (delivers messages) |
| **Dining Area** | Web Chat (where customers sit) |
| **Security Camera** | Audit Log (records everything) |
| **ID Check at Door** | JWT + MFA (verifies users) |

---

## 📊 Simple Tech Stack Table

| Layer | Technology | What It Does (Plain Words) |
|---|---|---|
| **Language** | Python | How we write the code |
| **API** | FastAPI | Messenger between user and AI |
| **Database** | SQLite | Filing cabinet for data |
| **AI Brain** | LLM (GPT-4o/DeepSeek) | Understands what users say |
| **Auth** | JWT + MFA | Verifies identity |
| **Safety** | Sandbox | Runs code safely |
| **Logging** | Audit Log | Records every action |
| **Frontend** | HTML/CSS/JS | What users see |
| **Version Control** | Git + GitHub | Tracks code changes |
| **Editor** | VS Code | Where we write code |

---

## 🎯 Why This Stack?

### 1. Fast to Build
Everything is pre-built. We don't waste time reinventing.

### 2. AI-Friendly
Python + LLM = the standard combo for AI projects.

### 3. Safe
Multiple layers of security built in.

### 4. Free (Mostly)
- Python: Free
- FastAPI: Free
- SQLite: Free
- GitHub: Free
- LLM: Pay-as-you-go (very cheap for demo)

### 5. Easy to Demo
Anyone can run it with one command:
