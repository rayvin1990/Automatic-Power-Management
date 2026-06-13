# Contributing

Thanks for improving Mi Smart Plug Auto Charger.

## Local Setup

```bash
pip install -r requirements.txt
copy config.example.json config.json
python token_extractor.py
python smart_charger.py
```

Do not commit `config.json`, `.mi_credentials.json`, `devices_tokens.json`, or logs.

## Pull Request Scope

Useful PRs include:

- device compatibility notes for specific Mi Home plug models;
- safer Windows startup and shutdown task scripts;
- platform adapters for macOS or Linux battery status;
- clearer setup, troubleshooting, and screenshots;
- bug fixes with a short reproduction note.

## Before Opening a PR

- Keep credentials and device IDs out of commits.
- Run the changed Python files through syntax checks:

```bash
python -m py_compile smart_charger.py shutdown_turn_off_plug.py token_extractor.py
```

- Mention your Windows version, Python version, Mi Home region, and plug model when the change affects device control.
