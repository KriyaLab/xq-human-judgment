<p align="center">
  <img src="screenshots/banner_xq.png" alt="XQ Banner" width="500"/>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.10-blue.svg" />
  <img src="https://img.shields.io/badge/LLM-Groq%20API-purple" />
  <img src="https://img.shields.io/badge/UI-Streamlit-green" />
</p>

> **Showcase Only**  
> This repo demonstrates the architecture, UI, and outcomes of a working product.  
> The production code and pipelines are proprietary and available **under NDA**.  
> To request a demo: **akar@akar7a.onmicrosoft.com**

# XQ – Human Judgment Layer Over AI Reports

## ⚡ 60-Second Summary

**XQ** is a brutal, honest startup idea evaluator.  
It adds a **human-like judgment layer** over AI outputs to guide founders with data-backed clarity — using a staged flow:  
**VET → SHAPE → SCOPE → LAUNCH**. Each step outputs a downloadable PDF for investors or advisors.

---

## ✅ What’s Inside (and what’s not)
- ✅ Project banner, videos, and architecture
- ✅ Sample input/output reports (PDF)
- ✅ Small, safe code sample + prompt logic
- ❌ No API keys, private prompts, or UI source
- ❌ No setup scripts or deployment guide

---

## 🧠 Architecture

```sora
title: XQ System Architecture

User[User Info Entry] --> IdeaForm[Idea Submission (One-liner, Desc, Context)]
IdeaForm --> VET[🧠 VET: Viability Scoring via Groq LLM]
VET --> SHAPE[🎯 SHAPE: Generate 2 Pivot/Refinement Options]
SHAPE --> SCOPE[📐 SCOPE: MVP Build Plan]
SCOPE --> LAUNCH[🚀 LAUNCH: GTM Strategy + 60-Day Roadmap]
VET --> PDF1[🧾 PDF Generator]
SHAPE --> PDF2[🧾 PDF Generator]
SCOPE --> PDF3[🧾 PDF Generator]
LAUNCH --> PDF4[🧾 PDF Generator]
PDF1 --> Reports[📥 Downloadable Reports]
PDF2 --> Reports
PDF3 --> Reports
PDF4 --> Reports
User --> DB[🗃️ SQLite: Users + Feedback]
Feedback[User Feedback (Rating + Comments)] --> DB
