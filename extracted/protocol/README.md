# Protocol layer — observed surface (single-player inventory)

No gameplay client↔server plane exists. The owed protocol section inventories what the shipped plugins expose:

- `steam_api64` — Steamworks achievements / DLC checks / overlay / cloud-saves
- `BacktraceCrashpad` (`BacktraceCrashpadWindows.dll` + `crashpad_handler`) — crash telemetry
- NVIDIA Ansel capture (`AnselPlugin64` / `AnselSDK64`)

Inventory + no-surface proof land here in a later piece; piece 1 fixes the directory contract only.
