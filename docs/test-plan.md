# Test plan and acceptance checklist

Run from the project root: `python -m unittest discover -s tests -v`. Tests use temporary SQLite databases and ephemeral ports; they do not erase the demonstration database.

| Case | Input/action | Expected result |
|---|---|---|
| TC01 | Normal samples | Online, stored values, no threshold alerts |
| TC02 | Stable motion true then false | One detected and one cleared event |
| TC03 | Door open for two samples | One DOOR_OPENED event |
| TC04 | Repeated complete door cycles | Exactly one event per stable transition |
| TC05 | Temp36 x3,34 x5,32 x3 | Activate, remain active in band, then clear |
| TC06 | Gas2600 repeatedly then400 x3 | One active gas alert then clear |
| TC07 | Missing humidity key | Reject; no heartbeat refresh |
| TC08 | Strings, bools or out-of-range numeric values | Reject invalid schema |
| TC09 | Broken JSON, bad encoding, NaN, oversized body | Reject; later valid sample still accepted |
| TC10 | Disconnect real TCP peers and reconnect | Offline then online; resubscription works |
| TC11 | No sample for more than20 seconds | One offline event |
| TC12 | Fresh sample following timeout | Online transition |
| TC13 | Simultaneous temp/gas/motion/door | Both environmental alerts and contact events |
| TC14 | Alternating threshold/contact noise | No confirmed activation |
| TC15 | 10,000 normal samples | Stored without extra events; bounded query response |

Additional checks: invalid sensor values do not clear alarms; gas warmup gate; duplicate/out-of-order packets do not refresh heartbeat; old-boot last will and telemetry cannot replace a newer observed boot; gaps reset candidate counts; acknowledgement survives database reopen; cross-origin acknowledgement rejection; API error handling; fragmented MQTT framing.

## Hardware acceptance (not yet executed)

- Build and flash the full ESP32 sketch for the exact board.
- Measure MQ-2 divider output before connecting GPIO34. Verify sensor pin order and common ground.
- Compare DHT22 against a reference and observe invalid-read rate during Wi-Fi traffic.
- Open/close reed and trigger PIR; compare local and dashboard timing.
- Confirm green/yellow/red behavior, buzzer driver current and supply stability.
- Verify conditioning/baseline process; test alert logic using simulator, without releasing flammable gas.
- Disconnect Wi-Fi and stop broker: local monitoring must continue; dashboard must become stale/offline.
- Restore connection; check latest readings, no duplicate activation and timestamps.
- Restart backend and verify preserved history. Check actual browser at desktop/mobile widths.

## Release acceptance

Do not call the final physical prototype complete until the live MQTT/API tests, full firmware compilation, browser smoke test and hardware checklist pass. Record test date, board model, software versions and evidence. TC15 is an accelerated database/rule test, not a measured 7-hour physical soak test.
