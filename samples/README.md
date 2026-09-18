# Samples

`demo_case.json` is a local smoke-test request for the completed API.

The supplied planning documents mention ten official public sample cases, but their actual JSON bodies were not included in the provided source files. They are intentionally not fabricated here.

When the official case files are available, copy them into this directory and run:

```powershell
python scripts/run_samples.py --base-url http://127.0.0.1:8000 --samples samples
```

The runner automatically executes every `*.json` file in this directory and replay-checks each returned schedule.
