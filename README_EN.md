# Xiaoyuan Tutor 🌸

An AI math tutor that accompanies middle school students through warm, conversational guidance, helping children **build confidence** and develop **mathematical thinking skills**.

[中文版](./README.md)

> Teaching philosophy inherited from [《Math Growth Plan for Middle School》](./初中数学成长方案.md):
> No task-based pressure; let children self-identify and execute proactively.
> Targeted gap-filling in fragmented time; never accumulate thinking blind spots.
> Respect state fluctuations with deep and baseline modes; protect the learning chain from breaking.

---

## ✨ Core Features

| Feature | Description |
|---------|-------------|
| 💬 Conversational Guidance | Xiaoyuan doesn't give answers directly; she guides students to think through questions |
| 🌗 Three Learning Modes | Deep Growth (10-18 min) / Baseline Stability (5 min) / Weekend Repair |
| 📷 Photo Problem Solving | Take a photo of the problem, OCR recognition, then guided problem-solving |
| 🔍 Blind Spot Tracking | Automatically identifies knowledge gaps (conceptual vs. careless errors) |
| ⭐ Knowledge Star Map | Shanghai Education knowledge graph; light up stars as you master topics |
| 🏅 Achievement Badges | Blind Spot Hunter, Derivation Warrior, Error Detective, 7-Day Streak... |
| 📖 Learning Records | Auto-archive each session; view conversation details; delete records |
| 😊 Mood Check-in | Record mood at start; Xiaoyuan responds with empathy |
| 🎤 Emotional Support | Xiaoyuan first empathizes → chats → shows "Start Learning" button |
| 🍅 Pomodoro Timer | Auto-timer after mode selection; 25 min study + 5 min break |
| 📈 Confidence Curve | Compare with yourself, not others |
| 🧭 Error Two-Question Protocol | Fixed questions: ①Where did you get stuck? ②What's the thinking gap? |
| 🎨 Multi-theme Switching | Matcha Green (default) / Sakura Pink / Lavender Purple |
| 🔑 API Key Configuration | Enter your DeepSeek Key in settings panel |
| 🚪 Multi-user Switching | Create/delete profiles; share one computer |
| 📝 Teaching Journal | Auto-extract teaching insights from conversations |

## 🚀 Quick Start

### Option 1: Desktop App (Recommended)

1. Download `Xiaoyuan.zip` from [Releases](../../releases)
2. Extract and double-click `Xiaoyuan.exe`
3. Browser opens automatically

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

Desktop app will be in `dist/Xiaoyuan` folder.

### Optional: Photo Problem Solving

```bash
pip install rapidocr-onnxruntime   # OCR (downloads ~60MB model on first run)
```

## 📁 Project Structure

```
xiaoyuan/
├── backend/
│   ├── main.py              # FastAPI entry + all APIs
│   ├── config.py            # Configuration management
│   ├── agent/
│   │   ├── persona.py       # Xiaoyuan persona: philosophy + personality + red lines
│   │   ├── chat.py          # Dialogue state machine
│   │   └── assessment.py    # Mastery assessment + badge determination
│   ├── models/student.py    # Student data model
│   ├── services/
│   │   ├── llm.py           # DeepSeek API wrapper (streaming)
│   │   ├── storage.py       # JSON atomic read/write
│   │   ├── ocr.py           # Photo OCR (optional)
│   │   └── teaching_journal.py  # Auto teaching insights extraction
│   └── knowledge/syllabus.py # Shanghai Education knowledge graph (78 nodes)
├── frontend/                # Single-page frontend (no build tools)
│   ├── index.html           # Chat / Star Map / Badges views
│   ├── css/style.css        # Multi-theme styles
│   └── js/app.js            # SSE streaming + Canvas + Image upload
├── docs/
│   └── 设计方案.md          # Design document
├── requirements.txt         # Python dependencies
├── run.py                   # Startup script
└── build.py                 # Build desktop app
```

## 🧡 Design Principles (Xiaoyuan's Red Lines)

- ❌ Never say "How can you not understand this?" — blame "loose building blocks," not ability
- ❌ Never assign copying or rote tasks
- ❌ Never recommend brute-force practice
- ❌ Never suggest "go back and relearn the whole chapter"
- ❌ Never push when student says tired — immediately downgrade or wrap up
- ✅ "I don't understand" is always praised for honesty
- ✅ Praise must be specific to thinking actions
- ✅ Fill gaps only until new lesson comprehension isn't affected
- ✅ When receiving photos, confirm content first; never pretend to understand

## 📝 Version History

- **V1 (2026-08-24)**: Conversational guidance + dual modes + star map + badges + mood check-in
- **V1.1 (2026-08-25)**: Matcha theme + multi-theme + mode bar optimization
- **V1.2 (2026-08-25)**: Photo problem solving (RapidOCR)
- **V1.3 (2026-08-25)**: Learning record archiving + history timeline
- **V1.4 (2026-08-25)**: Logout + account deletion + API Key configuration
- **V1.5 (2026-08-26)**: Desktop app + teaching journal + emotional support + Pomodoro timer

## 📄 License

For personal learning use only.
