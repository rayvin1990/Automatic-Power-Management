# Mi Smart Plug Auto Charger

Use a Mi Home smart plug to keep a Windows laptop battery between two healthy thresholds.

This project watches your laptop battery locally. When the battery is low, it turns on the Mi Home plug. When the battery is high, it turns the plug off. Before shutdown, it also tries to power off the plug so the laptop is not left charging overnight.

Default policy:

- Start charging when battery is at or below `20%`.
- Stop charging when battery is at or above `80%`.
- On shutdown, turn the plug off only if the laptop is currently charging.

## Why

Many laptops spend most of their life plugged in. If you already have a Mi Home smart plug, this script turns it into a simple battery-care controller without needing a full smart-home platform.

## Features

- Battery-aware charging: local battery status decides when to turn the plug on or off.
- Mi Home QR login: scan once with the Mi Home app; credentials are cached locally.
- Shutdown protection: console handler, `atexit`, and optional Windows scheduled task.
- Sleep-safe charging: prevents Windows auto-sleep while charging, so the script keeps running and prevents overcharging.
- Credential auto-recovery: if the Xiaomi token expires, the script stays alive and automatically reloads once you re-scan the QR code.
- Status file: `smart_charger_status.json` is written to your Desktop every 10 minutes so you can instantly verify the script is still running.
- Quiet startup: optional VBS launcher for background startup.
- Local-first safety: device credentials and runtime logs stay on your machine.

## Requirements

- Windows laptop with battery status available through Windows.
- Mi Home / Xiaomi smart plug under the same Xiaomi account.
- Python 3.8 or newer.
- Network access from the laptop to Xiaomi cloud APIs.

Tested primarily with Mi Home Wi-Fi smart plugs on the China server (`cn`).

## Quick Start

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

If you prefer installing manually:

```bash
pip install psutil colorama requests pycryptodome Pillow
```

### 2. Find your plug information

Run the token helper and scan the QR code with the Mi Home app:

```bash
python token_extractor.py
```

After login, find the target plug's `did` and model value.

### 3. Create config

```bat
copy config.example.json config.json
```

Edit `config.json`:

```json
{
  "plug_did": "your-device-did",
  "plug_model": "your-device-model",
  "server": "cn",
  "charge_on_threshold": 20,
  "charge_off_threshold": 80,
  "check_interval": 60
}
```

### 4. Run the charger

```bash
python smart_charger.py
```

The first run may ask you to scan a QR code. After that, the login cache is reused.

### 5. Optional: run silently on login

Double-click:

```text
启动智能充电(静默).vbs
```

To start it automatically after login, put that VBS file in:

```text
%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\
```

### 6. Optional: register shutdown protection

Right-click this file and run it as administrator:

```text
注册关机断电任务.bat
```

It registers:

- `SmartCharger_ShutdownTurnOff`: powers off the plug when Windows reports shutdown/logoff.
- `SmartCharger_AutoStart`: starts the silent VBS launcher on login.

### 7. Optional: enable sleep-mode battery checks

When the laptop sleeps, `smart_charger.py` pauses. The script resumes automatically when the laptop wakes up.

> **Note:** The `注册唤醒检测任务.bat` and `quick_check.py` files are included for reference but are no longer the recommended approach. The main `smart_charger.py` now prevents the system from auto-sleeping while charging, which covers the common case without needing WakeToRun.

## Configuration

| Field | Description | Recommended |
| --- | --- | --- |
| `plug_did` | Target Mi Home plug device ID. Required. | copied from `token_extractor.py` |
| `plug_model` | Target Mi Home plug model. | copied from `token_extractor.py` |
| `server` | Xiaomi cloud region. | `cn` |
| `charge_on_threshold` | Turn plug on when battery is at or below this percent. | `20` |
| `charge_off_threshold` | Turn plug off when battery is at or above this percent. | `80` |
| `check_interval` | Battery check interval in seconds. | `60` to `600` |

## How It Works

```text
Windows battery API
        |
        v
smart_charger.py (always-on monitor)
        |
        | local rule:
        | battery <= 20% and unplugged  -> plug on
        | battery >= 80% and charging   -> plug off
        v
Xiaomi cloud API
        |
        v
Mi Home smart plug

--- while sleeping ---

Windows scheduled task (every 10 min, WakeToRun)
        |
        v
quick_check.py (one-shot check, ~3 sec)
        |
        | same rule as above
        v
Xiaomi cloud API -> Mi Home smart plug
        |
        v
PC goes back to sleep
```

Shutdown protection:

```text
Windows shutdown/logoff
        |
        v
shutdown_turn_off_plug.py
        |
        | if laptop is charging:
        v
turn Mi Home plug off
```

## Files

| File | Purpose |
| --- | --- |
| `smart_charger.py` | Main battery monitor and plug controller. |
| `quick_check.py` | Lightweight one-shot battery check for wake-from-sleep. |
| `shutdown_turn_off_plug.py` | Standalone shutdown protection script. |
| `token_extractor.py` | Xiaomi cloud login and device discovery helper. |
| `config.example.json` | Template for local config. |
| `config.json` | Your local config. Ignored by Git. |
| `.mi_credentials.json` | Local Xiaomi login cache. Ignored by Git. |
| `启动智能充电.bat` | Console launcher. |
| `启动智能充电(静默).vbs` | Silent background launcher. |
| `注册关机断电任务.bat` | Windows scheduled task installer. |
| `注册唤醒检测任务.bat` | Windows wake-from-sleep task installer. |

## Safety Notes

- `config.json`, `.mi_credentials.json`, and `devices_tokens.json` are ignored by Git.
- Credentials are stored locally and are not uploaded by this project.
- Start with the default `20%` / `80%` thresholds before experimenting.
- If Xiaomi cloud control fails, the script logs the error and waits for the next check instead of repeatedly toggling the plug.
- The shutdown script skips plug control when Windows reports the laptop is not charging.
- Keep a manual way to turn the plug on/off in the Mi Home app while testing.

## Troubleshooting

### `psutil.sensors_battery()` returns no battery

This usually means Windows is not exposing a laptop battery to Python. The project currently targets Windows laptops, not desktops.

### The scheduled task does not register

Run `注册关机断电任务.bat` as administrator. The script tries `py`, then `python`, and stops with a clear message if Python is not available.

### The plug does not switch

Check:

- `plug_did` matches the target plug.
- `server` matches your Mi Home account region.
- `.mi_credentials.json` exists after QR login.
- `charger_log.txt` for API errors.

## Roadmap

- [ ] macOS and Linux battery adapters.
- [ ] Tray icon and desktop notifications.
- [ ] Multi-plug configuration.
- [ ] Home Assistant integration.
- [ ] Battery health and charging history dashboard.
- [ ] Safer first-run diagnostics for device model/API compatibility.

## Contributing

PRs are welcome. Good first issues include docs, device compatibility notes, startup scripts, and support for more platforms.

See [CONTRIBUTING.md](CONTRIBUTING.md) for local setup and PR expectations.

## Credits

- [PiotrMachowski/Xiaomi-cloud-tokens-extractor](https://github.com/PiotrMachowski/Xiaomi-cloud-tokens-extractor) for Xiaomi cloud token extraction patterns.

## Disclaimer

**This project is NOT affiliated with, authorized by, or endorsed by Xiaomi Inc.**

This software uses a reverse-engineered, unofficial Xiaomi cloud API. It is provided
for **personal, educational, and research purposes only**. **Commercial use is strictly
prohibited.** The author assumes no responsibility for any consequences arising from
the use of this software, including but not limited to account suspension, device
malfunction, or data loss. Use at your own risk.

## License

Personal & Educational Use only. Commercial use is strictly prohibited. See [LICENSE](LICENSE).
