<p align="center">
  <img src="assets/CCA_banner.png" alt="Claude Code Assistant" width="560"/>
</p>

<p align="center">
  <em>Windows ассистент на голосовом вводе, прямое общение с Claude Code</em>
</p>

<p align="center">
  <img alt="Python" src="https://img.shields.io/badge/Python-3.10+-3776AB?logo=python&logoColor=white"/>
  <img alt="Платформа" src="https://img.shields.io/badge/Платформа-Windows-0078D4?logo=windows&logoColor=white"/>
  <img alt="Claude Code" src="https://img.shields.io/badge/Claude_Code-обязателен-D97757"/>
  <img alt="Лицензия" src="https://img.shields.io/badge/Лицензия-AGPL--3.0-purple"/>
  <img alt="Версия" src="https://img.shields.io/badge/Версия-1.0.0-8B5CF6"/>
</p>

<p align="center">
  <a href="README.md">🇬🇧 English version</a>
</p>

---

## Возможности

- **Голосовой ввод** — удерживай клавишу, говори, отпусти; Whisper транскрибирует локально на твоём компьютере
- **Режим со скриншотом** — вторая клавиша прикрепляет скриншот экрана к запросу
- **Оверлей UI** — безрамочная плавающая панель в низу экрана, иконка настроения слева
- **Теги настроения** — Claude может выразить `[happy]` `[sad]` `[angry]` `[shy]` `[flirty]` `[lovely]`; иконка в оверлее и трее обновляются
- **Ручной ввод** — пиши прямо в поле оверлея и жми Enter
- **Возобновление сессии** — продолжает конкретную сессию Claude Code через `--resume <session_id>`
- **Живые настройки** — весь конфиг редактируется из иконки трея без касания файлов

---

## Требования

- **Windows 10/11**
- **Python 3.10+** — только если запускаешь из исходников
- **[Claude Code CLI](https://claude.ai/code)** — установлен и авторизован, доступен в PATH
- Микрофон

---

## Установка

```bash
git clone https://github.com/excedereo/claude.assistant
cd claude.assistant
pip install -r requirements.txt
python main.py
```

При первом запуске модель Whisper (`small`, ~460 МБ) загружается автоматически.

---

## Запуск из exe

Скачай `claude_assistant.exe` из [Releases](../../releases) и запусти — Python не требуется.  
Модель Whisper загружается при первом запуске как обычно.

---

## Настройка

Открой **Настройки** из иконки в трее — изменения применяются сразу без перезапуска.  
Все значения сохраняются в `config.json` рядом с исполняемым файлом.

| Поле | По умолчанию | Описание |
|---|---|---|
| `hotkey` | `f9` | Удерживай для записи голоса |
| `screenshot_hotkey` | `f10` | Удерживай для записи + прикрепление скриншота |
| `session_id` | `null` | ID сессии Claude Code для возобновления (см. ниже) |
| `claude_path` | `""` | Путь к исполняемому файлу `claude` — оставь пусто для авто-определения |
| `overlay_opacity` | `0.85` | Прозрачность оверлея `0.1 – 1.0` |
| `auto_hide_seconds` | `15` | Секунды до автоматического скрытия оверлея (`0` = никогда) |
| `whisper_model` | `"small"` | Размер модели: `tiny` `base` `small` `medium` — требует перезапуска |
| `sample_rate` | `16000` | Частота дискретизации аудио в Гц — требует перезапуска |

### Поиск session ID

Session ID позволяет ассистенту продолжить существующую сессию Claude Code.

В `~/.claude/sessions/` найди самый свежий `.json` файл и скопируй поле `sessionId`:

```json
{ "sessionId": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx", ... }
```

Вставь в **Настройки → Session ID**. Если оставить пусто, ассистент использует `--continue` (самая недавняя сессия).

---

## Горячие клавиши

| Клавиша | Действие |
|---|---|
| Удерживай `F9` | Запись голоса и отправка |
| Удерживай `F10` | Запись голоса + прикрепление скриншота |
| `Escape` во время записи | Отмена без отправки |

Все горячие клавиши настраиваются в Настройках (нажимаешь на поле — программа ждёт твоего нажатия).

---

## Теги настроения

Начни ответ Claude с тега чтобы изменить иконку оверлея и трея:

```
[happy]   [sad]   [angry]   [shy]   [flirty]   [lovely]
```

Ответы без тега по умолчанию показывают `happy`.

---

## Сборка exe самостоятельно

```bash
pip install pyinstaller
build.bat
```

Выход: `dist/claude_assistant.exe`

---

## Кастомные иконки

Папка `assets/` содержит PNG иконки, используемые в оверлее и трее.  
Заменяй любые на свои — рекомендуемый размер **64×64** или больше.

```
claudeHappy.png   claudeSad.png     claudeAngry.png
claudeShy.png     claudeFlirty.png  claudeLovely.png
claudeListening.png  claudeThinking.png  claudeClose.png
```

---

## Лицензия

AGPL-3.0
