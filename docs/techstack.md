# Tech Stack — Banking AI Agent

## Backend
| Layer | Technology |
|---|---|
| Language | Python 3.14 |
| Web Framework | FastAPI |
| Database | SQLite |
| ORM | SQLAlchemy 2.1 |
| LLM | OpenAI GPT-4o / DeepSeek |

## AI/ML
| Component | Technology |
|---|---|
| LLM Provider | DeepSeek |
| Intent Parsing | Function Calling |
| Task Planning | DAG (custom) |
| Vector Store | ChromaDB (optional) |

## Security
| Layer | Technology |
|---|---|
| Auth | JWT |
| MFA | pyotp |
| Sandbox | RestrictedPython |
| Audit | SQLAlchemy logs |

## Frontend
| Layer | Technology |
|---|---|
| UI | HTML/CSS/JavaScript/react |
| Chat | Fetch API |
| Deploy | Local / Docker |

## DevOps
| Layer | Technology |
|---|---|
| Version Control | Git + GitHub |
| CI/CD | GitHub Actions (optional) |
| Virtual Env | venv |
