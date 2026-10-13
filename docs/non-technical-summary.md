# Banking AI Agent — Non-Technical Summary

> A plain-language explanation for readers who are not developers.

## What It Is

A smart assistant inside your banking app that you can talk to like a real person —
for example, *"Send 500 baht to my mom"* or *"How much did I spend last month?"* —
and it gets things done automatically.

## How It Works (Like a Human Assistant)

1. **Listens** — Understands what you actually mean, even if you say it vaguely
2. **Plans** — Figures out the steps needed, in the right order
3. **Checks safety** — Decides if the action needs your permission first
4. **Acts** — Completes the banking task for you
5. **Records** — Keeps a log of everything for transparency

## Safety Comes First — Three Levels

| Level | Meaning | Example |
|---|---|---|
| 🟢 Green | Do it automatically | Check balance, view history |
| 🟡 Yellow | Ask the user first | Transfer up to 1,000 baht, cancel subscription |
| 🔴 Red | Require strong verification | Transfer over 1,000 baht, change password, report lost card |

In short: **small things happen instantly, big things require confirmation.**

## Key Technologies (In Plain Words)

| Technology | What It Does |
|---|---|
| LLM | The AI brain that understands human language |
| RAG | Lets the AI look up real account data instead of guessing |
| DAG Planner | Organizes tasks in the correct order |
| Prompt Injection Defense | Blocks attempts to trick the AI |
| Sandbox | Runs AI-generated code in a safe, locked environment |

## What It Can Do

1. Smart transfers (by name, phone, note; scheduled; split bills)
2. Bill analysis (spending categories, unusual transactions, reports)
3. Wealth operations (recommendations, risk assessment, buy/sell)
4. Card management (apply, adjust limits, report loss)
5. Subscription detection & cancellation
6. Cross-scenario tasks (e.g., remember a birthday and order gifts in advance)

## Bottom Line

This project builds an AI banking assistant that **listens, thinks, plans, and acts** —
making mobile banking **simpler and safer** through a clear security framework.
