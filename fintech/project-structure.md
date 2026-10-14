# Project Structure — Pre-Code Setup

> This document describes the planned structure of the repository
> **before any actual code has been written**.
>
> The goal is to set up the "skeleton" of the project on GitHub first,
> then fill in the code later.

---

## 🏗️ Planned Structure (Before Code)

---

## 📋 What Can Be Set Up Now (Without Code)

| # | Item | Status |
|---|---|---|
| 1 | `README.md` | ✅ Done |
| 2 | `docs/` folder + documents | ✅ Done |
| 3 | `.gitignore` | ✅ Done |
| 4 | `.env.example` | ✅ Done |
| 5 | `requirements.txt` (can be empty or with names) | ⬅️ To create |
| 6 | Folder structure `src/` (empty files) | ⬅️ To create |
| 7 | Folder structure `tests/` (empty files) | ⬅️ To create |
| 8 | `main.py` (empty with comments) | ⬅️ To create |
| 9 | `LICENSE` (if needed) | ⬅️ Optional |
| 10 | GitHub Actions (`.github/workflows/`) | ⬅️ Optional |
| 11 | Issues + Projects as task checklist | ⬅️ Recommended |
| 12 | Invite team members | ⬅️ Recommended |

---

## ⏳ What Must Wait Until Code Exists

| # | Item |
|---|---|
| 1 | Real code in `src/` |
| 2 | Real tests in `tests/` |
| 3 | Demo video |
| 4 | Defence deck |

---

## 🎯 Recommended Order of Setup

### 🔴 Round 1 — Safety Files (Highest Priority)
1. `.gitignore`
2. `.env.example`
3. `requirements.txt`

### 🟡 Round 2 — Folder Structure
4. `src/__init__.py`
5. `tests/__init__.py`
6. `main.py` (empty with comments)

### 🟢 Round 3 — Missing Documentation
7. `docs/brief.md`
8. `docs/technical.md`
9. `docs/architecture-nontech.md`

### 🔵 Round 4 — Team Preparation
10. Invite team members
11. Create branches: `develop`, `feature/*`
12. Create Issues as task checklist

---

## 💡 Tip: Creating Empty Folders on GitHub

Git does not track empty folders, so you need at least one file inside.

**How to create a folder on GitHub:**
1. Click **Add file** → **Create new file**
2. Type the path with a filename, e.g.:
