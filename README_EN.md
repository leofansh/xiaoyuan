# Xiaoyuan Tutor 🌸

An AI math tutor that accompanies middle school students through warm, conversational guidance, helping children **build confidence** and develop **mathematical thinking skills**.

[中文版](./README.md) ｜ [Full Design Doc](./docs/设计方案.md)

> Teaching philosophy: no task-based pressure — let children self-identify and execute proactively; targeted gap-filling in fragmented time, never accumulate thinking blind spots; respect state fluctuations with deep and baseline modes, protect the learning chain from breaking.

---

## ✨ Core Features

### Teaching Core

| Feature | Description |
|---------|-------------|
| 💬 Conversational Guidance | Xiaoyuan doesn't give answers directly; she guides students to think through questions |
| 🌗 Three Learning Modes | Deep Growth (10–18 min) / Baseline (5 min) / Weekend Repair; pick via quick bar or type |
| 🔍 Blind Spot Tracking | 22 fine-grained gap categories (concept/calc/reading/thinking/careless) with root cause + repair strategy |
| 🧠 Thinking Models | 10 math thinking models, dynamically injected and made explicit (🧩 tag) |
| 📈 Mastery Assessment | Bayesian mastery model + confidence + forgetting decay |
| 🧭 Error Two-Question Protocol | Fixed questions: ①Where did you get stuck? ②What's the thinking gap? |
| ⭐ Knowledge Map | Shanghai Education (五四制) knowledge graph, 78 nodes, prerequisite chains + cognitive gates |

### Cognition & Psychology

| Feature | Description |
|---------|-------------|
| 🔬 Cognitive Profile | 6 diagnostic questions → 5-dimension cognitive profile; continuously updated via Bayesian inference |
| 🎤 Emotional Support | Xiaoyuan first empathizes → chats → shows "Start Learning"; pace is set by the child |
| 😊 Mood Check-in | Records mood at start; Xiaoyuan responds with empathy |
| 🛡 Crisis & Safety | 4-tier crisis detection + content filter + anti-addiction (time limits / night reminders / cognitive-load alerts) |
| 🏅 Achievement Badges | 17 badges (7 base + 10 thinking-model), all tied to thinking-growth events |

### Learning Loop

| Feature | Description |
|---------|-------------|
| 🔁 Spaced Repetition | Schedule reviews by mastery (1/2/5/10/20 days), 70+ retrieval questions |
| 📰 Weekly Report | This week vs last week stats + insights + ≤3 actionable suggestions |
| 🗺 Weekly Learning Plan | Gap-first / ZPD / variant priority, ≤5 items per week |
| 📖 Learning Records | Auto-archive each session; view details; delete |
| 📝 Teaching Journal | Auto-extract teaching insights; Xiaoyuan learns how to teach this child better |

### Experience

| Feature | Description |
|---------|-------------|
| 🍅 Pomodoro Timer | 25 min study + 5 min rest, floating icon with ring countdown |
| 🎤 Voice Input | Web Speech API, Chrome only, auto-hidden when unsupported |
| 📷 Photo Problem Solving | Photo → OCR (text/formula/vision) → confirm → guide |
| 🧮 Calculation Correctness | SymPy symbolic engine + verification layer, no LLM mental-math errors |
| 🎨 Multi-theme | Matcha Green (default) / Sakura Pink / Lavender Purple |
| 🌐 Bilingual | Switch between 中文 / English in settings |
| 🔑 API Key Config | Enter your DeepSeek Key in the settings panel |
| 🚪 Multi-user Switching | Create/delete profiles; share one computer |

## 🚀 Quick Start

### Option 1: Desktop App (Recommended)

1. Download `Xiaoyuan.zip` from [Releases](../../releases)
2. Unzip and double-click `Xiaoyuan.exe`
3. Browser opens automatically; tray icon appears (right-click to quit)

### Option 2: Run from Source (For Developers)

```bash
# 1. Create virtual environment
python -m venv venv
venv\Scripts\activate        # Windows
# source venv/bin/activate   # macOS/Linux

# 2. Install dependencies
pip install -r requirements.txt

# 3. Start
python run.py
```

Open <http://localhost:8000> in your browser.

Enter your DeepSeek API Key in the settings panel (🎨) on first use.

### Build Desktop App

```bash
pip install pyinstaller
python build.py
```

Output is in `dist/Xiaoyuan` (distribute together with `_internal`).

### Optional Enhancements

```bash
pip install rapidocr-onnxruntime   # OCR for photo problems (~60MB)
pip install pix2tex                # formula recognition (~500MB)
```

### Usage Flow

1. Create a student profile on first entry
2. Mood check-in → Xiaoyuan empathizes → choose a learning mode
3. Chat with Xiaoyuan to learn math, guided step by step
4. Take a photo of a problem (📷) when stuck
5. View history in 🏅 Growth Wall → 📖 Learning Records
6. Use 🚪 to logout / switch profiles

## 📁 Project Structure

```
xiaoyuan/
├── backend/
│   ├── main.py                # FastAPI entry + all APIs
│   ├── config.py              # Config (runtime API Key)
│   ├── agent/
│   │   ├── persona.py         # Persona + system prompt builder
│   │   ├── chat.py            # Session orchestration
│   │   ├── assessment.py      # Eval application + badges
│   │   ├── state_engine.py    # Deterministic state machine
│   │   ├── strategy_engine.py # Teaching strategy selection
│   │   ├── thinking_models.py # Thinking model library
│   │   ├── cognitive_assessment.py # Cognitive diagnostics
│   │   └── metacognition.py   # Metacognitive strategies
│   ├── knowledge/
│   │   ├── syllabus.py        # Knowledge graph (78 nodes)
│   │   └── error_patterns.py  # Gap classification + error patterns
│   ├── models/student.py      # Student data model
│   └── services/              # LLM, storage, calc, safety, etc.
├── frontend/                  # Single-page frontend (no build tools)
│   ├── index.html             # 4 views + settings + pomodoro
│   ├── css/style.css          # Multi-theme styles
│   ├── js/                    # app.js, i18n.js, math.js
│   └── i18n/translations.json # zh/en translations
├── docs/                      # Design / Architecture / Test / Review docs
├── tests/                     # Math test set
├── requirements.txt
├── run.py                     # Startup (with tray icon)
├── build.py                   # Desktop build
└── xiaoyuan.spec              # PyInstaller spec
```

## 🧡 Design Principles (Xiaoyuan's Red Lines)

- ❌ Never say "How can you not understand this?" — blame "loose building blocks," not ability
- ❌ Never assign copying or rote tasks
- ❌ Never recommend brute-force practice
- ❌ Never suggest "go back and relearn the whole chapter"
- ❌ Never push when student says tired — downgrade or wrap up immediately
- ❌ Never do mental math — must be verified by SymPy
- ✅ "I don't understand" is always praised for honesty
- ✅ Praise must be specific to thinking actions
- ✅ Fill gaps only until new lesson comprehension isn't affected
- ✅ When receiving photos, confirm content first; never pretend to understand

## 📝 Version History

- **V1.0 (2026-08-24)**: Conversational guidance + dual modes + star map + badges + mood
- **V1.1–1.4 (2026-08-25)**: Themes / photo OCR / learning records / account & API Key
- **V1.5 (2026-08-26)**: Desktop app + tray + teaching journal + emotional care + pomodoro + i18n
- **V1.6 (2026-08-27)**: Educational psychology (cognitive load/self-efficacy/anxiety) + cognitive profile + thinking models
- **V2.0 (2026-08-27)**: Architecture optimization P0/P1/P2 (state engine/Bayesian mastery/gap classification/strategy engine/learning path/parent notification/anti-addiction)
- **V2.1 (2026-08-28)**: Polished desktop packaging + bilingual UI

## 📄 License

For personal learning use only.
