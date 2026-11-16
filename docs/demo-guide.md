# Home IoT Monitoring & Alert System demo guide

See [the presentation checklist in Vietnamese](tinh-nang-va-demo.md). Open PowerShell inside `home-iot-monitoring`, stop any previous demo using ports 1883 and 8080, and start:

```powershell
py -3.11 -m tools.run_demo --scenario home_showcase
```

Open http://127.0.0.1:8080/ in Edge and choose **Create an account** on your first visit. After signing in, **Dataset video** lists all 160 included clips. Keep PowerShell open during the demo and press Ctrl+C to stop. The default notification mode requires no account or Internet. To test a real phone with your bot, follow [Telegram setup](telegram.md).
