# Change log — 15 November 2026

- Renamed the existing CC02 Group 8 prototype to **Smart Lab Room Monitor** and updated the device and presentation context to a university electronics storage room.
- Added launcher checks for conflicting ports and made its local HTTP health request bypass configured proxies. Documented PowerShell startup, shutdown, fault injection and troubleshooting.
- Fixed periodic MQTT disconnects during continuous publishing. Added a regression test for a publish-only client.
- Retained the architecture, data schema, thresholds, nine simulator scenarios and original test cases. The `home` MQTT prefix and `home.db` filename preserve compatibility. Updated the dashboard title assertion for the renamed UI.
- Revised the original 13-slide implementation deck in place and retained its Vietnamese speaker notes. Updated the verification section with Windows evidence and kept full ESP32 validation pending.

- Redesigned the dashboard for projection and narrow screens. Slide 8 embeds an actual Windows demo capture and opens the local dashboard when clicked. Published the final implementation report.

- Added a projection-focused Present toggle and recent-reading CSV export. Added sensor icons and redesigned all 13 slides with editable diagrams and charts or real Edge captures.

- Added Incident Review for a recent alert, including its trigger reading, lifecycle timestamps and nearby events. Reduced the dashboard scale and resequenced the presentation around the lab operator’s problem, solution, demo and results.

- Added alert queue filters and persistent shift handover notes. Added an integration test for validation, note ordering and duplicate-safe retry. Updated slides 6, 9 and 11 with the expanded workflow and test results.

## Home IoT release

- Restored the home context and added a browser camera replay for entry and possible fall.
- Added a persistent notification queue with Telegram preview and opt-in live delivery for high gas and device offline.
- Added the one-pass home_showcase scenario and organized the README, camera, and notification components.
- Added ten Edge-verified camera scenarios for multiple actors, three fall locations, partial views, quick recovery and an empty room.
- Added local dataset video playback with the webcam fall detector. Replaced pose overlays with green and red whole-frame borders, and made the rule tolerate brief gaps while requiring observed evidence for an alert. Documented the GMDCSA-24 sample results and clips for the demo.
- Replaced whole-frame camera borders with person-level boxes for standing, walking, sitting and a possible fall. Used the existing pose landmarks for box geometry and retained the fall rule.
- Updated live and dataset fall detection to check the movement of shoulders and hips, including falls from a seated start. Replayed all 160 annotated clips against both rules and recorded a separate Subject 4 result.
- Stream GMDCSA-24 clips from a configured data folder. The camera panel now has two sources, My camera and Dataset video.
- Included two credited GMDCSA-24 sample videos so a fresh Git checkout or ZIP can run the camera demo immediately. A configured external library takes precedence for the full test set.
- Included all 160 original GMDCSA-24 v2.1 clips and enabled dashboard sign-in and account creation by default in the demo launcher.
