# Study Monitor
macOS-only Python app (PyObjC, SQLite, Flask). Run: `python main.py`. Settings: `python -m rules.config_editor`. Dashboard: http://127.0.0.1:5050

- Roadmap and phase checklist are in README.md.
- Never commit data/*.db or config.json.
- Work on a new branch per feature and open a PR. Never push to main.
- Keep FocusTracker and classify free of macOS calls so they stay unit-testable with pytest.
