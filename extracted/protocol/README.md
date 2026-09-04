# Protocol layer — current single-player surface inventory

Two Point Campus exposes no gameplay client↔server protocol in the acquired
single-player build. The current protocol duty is therefore an inventory and
negative proof, not an opcode/message reconstruction.

## Observed native surfaces

| Surface | Client evidence | Product treatment |
|---|---|---|
| Steamworks | `steam_api64.dll` | achievements, DLC entitlement checks, overlay, cloud-save integration |
| crash telemetry | `BacktraceCrashpadWindows.dll`, `crashpad_handler` | crash transport only; not game-state data |
| NVIDIA Ansel | `AnselPlugin64`, `AnselSDK64` | local capture integration |
| Addressables | local catalog and installed bundles | file protocol only; no remote runtime dependency observed for acquired content |

## Verdict

No gameplay truth has been identified as server-authoritative. The durable
game database is reconstructed from the local client. A future build that adds
online/co-op/live services reopens this inventory and must add endpoints,
schemas, authentication/session flow, cadence, and authority boundaries.

The Steam storefront/news kickoff pulls are first-party acquisition metadata,
not a gameplay protocol.

<!-- END OF extracted/protocol/README.md -->
