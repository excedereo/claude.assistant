<p align="center">
  <img src="assets/CCA_banner.png" alt="Claude Code Assistant" width="560"/>
</p>

<p align="center">
  <em>A Windows voice assistant overlay that speaks directly to Claude Code</em>
</p>

<p align="center">
  <img alt="Python" src="https://img.shields.io/badge/Python-3.10+-3776AB?logo=python&logoColor=white"/>
  <img alt="Platform" src="https://img.shields.io/badge/Platform-Windows-0078D4?logo=windows&logoColor=white"/>
  <img alt="Claude Code" src="https://img.shields.io/badge/Claude_Code-required-D97757"/>
  <img alt="License" src="https://img.shields.io/badge/License-AGPL--3.0-purple"/>
  <img alt="Version" src="https://img.shields.io/badge/Version-1.0.0-8B5CF6"/>
</p>

<p align="center">
  <a href="README_RU.md">🇷🇺 Русская версия</a>
</p>

---

## Features

- **Voice input** — hold a hotkey, speak, release; Whisper transcribes locally on your machine
- **Screenshot mode** — second hotkey attaches a screenshot of your screen to the request
- **Overlay UI** — borderless floating panel at the bottom of the screen, mood icon on the left
- **Mood tags** — Claude can express `[happy]` `[sad]` `[angry]` `[shy]` `[flirty]` `[lovely]`; icon and tray update accordingly
- **Manual input** — type directly into the overlay's text field and hit Enter
- **Session resume** — continues a specific Claude Code session via `--resume <session_id>`
- **Live settings** — all config editable from the tray icon without touching any files

---

## Requirements

- **Windows 10/11**
- **Python 3.10+** — only if running from source
- **[Claude Code CLI](https://claude.ai/code)** — installed and authenticated, available in PATH
- A microphone

---

## Installation

```bash
git clone https://github.com/your-username/claude.assistant
cd claude.assistant
pip install -r requirements.txt
python main.py
```

On first launch the Whisper model (`small`, ~460 MB) downloads automatically.

---

## Running the exe

Download `claude_assistant.exe` from [Releases](../../releases) and run it directly — no Python required.  
The Whisper model will still download on first launch.

---

## Configuration

Open **Settings** from the tray icon — changes apply immediately without restart.  
All values are stored in `config.json` next to the executable.

| Field | Default | Description |
|---|---|---|
| `hotkey` | `f9` | Hold to record voice |
| `screenshot_hotkey` | `f10` | Hold to record + attach screenshot |
| `session_id` | `null` | Claude Code session to resume (see below) |
| `claude_path` | `""` | Path to `claude` executable — leave empty for auto-detection |
| `overlay_opacity` | `0.85` | Overlay transparency `0.1 – 1.0` |
| `auto_hide_seconds` | `15` | Seconds before overlay hides automatically (`0` = never) |
| `whisper_model` | `"small"` | Model size: `tiny` `base` `small` `medium` — requires restart |
| `sample_rate` | `16000` | Audio sample rate in Hz — requires restart |

### Finding the session ID

The session ID lets the assistant resume an existing Claude Code conversation.

In `~/.claude/sessions/` find the most recently modified `.json` file and copy the `sessionId` field:

```json
{ "sessionId": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx", ... }
```

Paste it into **Settings → Session ID**. If left empty, the assistant uses `--continue` (most recent session).

---

## Hotkeys

| Key | Action |
|---|---|
| Hold `F9` | Record voice and send |
| Hold `F10` | Record voice + attach screenshot |
| `Escape` while recording | Cancel without sending |

All hotkeys are configurable in Settings.

---

## Mood tags

Start a Claude response with a tag to change the overlay and tray icon:

```
[happy]   [sad]   [angry]   [shy]   [flirty]   [lovely]
```

Responses without a tag default to `happy`.

---

## Building the exe

```bash
pip install pyinstaller
build.bat
```

Output: `dist/claude_assistant.exe`

---

## Custom icons

The `assets/` folder contains PNG icons used by the overlay and tray.  
Replace any of them with your own — recommended size **64×64** or larger.

```
claudeHappy.png   claudeSad.png     claudeAngry.png
claudeShy.png     claudeFlirty.png  claudeLovely.png
claudeListening.png  claudeThinking.png  claudeClose.png
```

---

## License

AGPL-3.0
