# Home IoT Windows verification

- Windows 11 and Python 3.11.9: 34 Python tests passed, plus the portable C++ rules.
- Microsoft Edge: 10 synthetic cases passed, covering single and multiple actors, three fall locations, partial views, quick recovery and an empty room. Interrupted replay reset and 390 px layout were verified separately.
- Notification preview: one gas activation and one sensor-offline notice from the one-pass home showcase, followed by online recovery. Both rows survived backend restart.
- Telegram response handling was exercised with mocked acceptance, rejection and timeout. Live bot delivery still needs verification with the user's linked account.
- ESP32 build, physical wiring and camera video analysis remain outside this software demonstration.

See `tests/results.txt` and the external Windows evidence ZIP for logs and captures.
