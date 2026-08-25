# Two Point Campus — Extraction Log

Seeded by pipeline piece 1 (`run_all.py`). Per doctrine this log is
the source of truth for tool paths and versions: the
`stage-defaults` block below is read by every run, and tooling
changes land in it in the same commit that changes the entrypoint.

## Header pins

- **appid:** 1649080
- **buildId:** 20226581
- **metadataVersion:** 27
- **targetBuildId:** 20226581
- **unityVersion:** 2020.3.47f1
- **versionString:** 10.3.169253+2024-12-06.1241

<!-- stage-defaults-begin -->
```json
{
  "il2cppdumper": {
    "candidates": [
      "../zero-parades/work/_tooling/il2cppdumper/Il2CppDumper.exe",
      "../disco-elysium/zero-parades/work/_tooling/il2cppdumper/Il2CppDumper.exe",
      "../disco-elysium/tools/Il2CppDumper/Il2CppDumper.exe",
      "D:\\unpacked_game_data\\albion-online\\_tooling\\il2cppdumper\\Il2CppDumper.exe"
    ]
  },
  "unitypyVersion": "1.25.3"
}
```
<!-- stage-defaults-end -->

## Run sections

(appended per executed stage below)
### 2026-08-24T16:58:39Z — verify-client
- exitCode: 0
- buildId: 20226581 (TargetBuildID 20226581)
- metadataVersion: 27; dumper: il2cppdumper
- unityVersion: 2020.3.47f1; versionString: `10.3.169253+2024-12-06.1241`
- addressablesVersion: 1.21.10; settingsHash: ff59c4d7914829f354d3efeefc3819f0
- rosterRows: 176 (by class: [('base', 158), ('dlc-ghost', 8), ('dlc-space', 10)]); localeFlagged: 14
- sceneCounts: {'strictUnityBase': 21, 'seasonalSceneCarryingBase': 22, 'strictUnityInstall': 25, 'sceneCarryingInstall': 26}
- extractionLogSeeded: True
### 2026-08-24T16:59:15Z — verify-client
- exitCode: 0
- buildId: 20226581 (TargetBuildID 20226581)
- metadataVersion: 27; dumper: il2cppdumper
- unityVersion: 2020.3.47f1; versionString: `10.3.169253+2024-12-06.1241`
- addressablesVersion: 1.21.10; settingsHash: ff59c4d7914829f354d3efeefc3819f0
- rosterRows: 176 (by class: [('base', 158), ('dlc-ghost', 8), ('dlc-space', 10)]); localeFlagged: 14
- sceneCounts: {'strictUnityBase': 21, 'seasonalSceneCarryingBase': 22, 'strictUnityInstall': 25, 'sceneCarryingInstall': 26}
- extractionLogSeeded: False
### 2026-08-24T16:59:16Z — verify-client
- exitCode: 0
- buildId: 20226581 (TargetBuildID 20226581)
- metadataVersion: 27; dumper: il2cppdumper
- unityVersion: 2020.3.47f1; versionString: `10.3.169253+2024-12-06.1241`
- addressablesVersion: 1.21.10; settingsHash: ff59c4d7914829f354d3efeefc3819f0
- rosterRows: 176 (by class: [('base', 158), ('dlc-ghost', 8), ('dlc-space', 10)]); localeFlagged: 14
- sceneCounts: {'strictUnityBase': 21, 'seasonalSceneCarryingBase': 22, 'strictUnityInstall': 25, 'sceneCarryingInstall': 26}
- extractionLogSeeded: False
### 2026-08-24T17:26:36Z — verify-client
- exitCode: 0
- buildId: 20226581 (TargetBuildID 20226581)
- metadataVersion: 27; dumper: il2cppdumper
- unityVersion: 2020.3.47f1; versionString: `10.3.169253+2024-12-06.1241`
- addressablesVersion: 1.21.10; settingsHash: ff59c4d7914829f354d3efeefc3819f0
- rosterRows: 176 (by class: [('base', 158), ('dlc-ghost', 8), ('dlc-space', 10)]); localeFlagged: 14
- sceneCounts: {'strictUnityBase': 21, 'seasonalSceneCarryingBase': 22, 'strictUnityInstall': 25, 'sceneCarryingInstall': 26}
- extractionLogSeeded: False
### 2026-08-24T19:13:43Z — verify-client
- exitCode: 0
- buildId: 20226581 (TargetBuildID 20226581)
- metadataVersion: 27; dumper: il2cppdumper
- unityVersion: 2020.3.47f1; versionString: `10.3.169253+2024-12-06.1241`
- addressablesVersion: 1.21.10; settingsHash: ff59c4d7914829f354d3efeefc3819f0
- rosterRows: 176 (by class: [('base', 158), ('dlc-ghost', 8), ('dlc-space', 10)]); localeFlagged: 14
- sceneCounts: {'strictUnityBase': 21, 'seasonalSceneCarryingBase': 22, 'strictUnityInstall': 25, 'sceneCarryingInstall': 26}
- extractionLogSeeded: False
### 2026-08-24T19:13:56Z — decompile
- exitCode: 1 (DummyDll/Assembly-CSharp.dll missing)
- tool: Il2CppDumper vunknown at D:\unpacked_game_data\albion-online\_tooling\il2cppdumper\Il2CppDumper.exe
- inputs: GameAssembly.dll 311226368 B, global-metadata.dat 14284260 B
- escalationTrigger: metadata version >= 38 exceeds the staged dumper's supported range (KB does-not-work/il2cppdumper-new-metadata.md). Escalation is a declared manual step: `dotnet publish` on tools/Cpp2IL per toolchain.md section 'Primary dumper decision', version selected against the measured metadata version, result pinned in EXTRACTION-LOG.md. This pipeline never auto-builds Cpp2IL.
### 2026-08-24T19:20:50Z — harvest-bundles
- exitCode: 2 (completed-with-ledger)
- unitypySource: venv-pip
- bundlesAttempted: 176; unreadableBundles: 176
- censusObjectsTotal: 0; exports: 0; catalogueRows: 0; objectErrors: 0; censusOnlyResidual: 0
- carvedClassCensus: {}
### 2026-08-24T20:43:26Z — verify-client
- exitCode: 0
- buildId: 20226581 (TargetBuildID 20226581)
- metadataVersion: 27; dumper: il2cppdumper
- unityVersion: 2020.3.47f1; versionString: `10.3.169253+2024-12-06.1241`
- addressablesVersion: 1.21.10; settingsHash: ff59c4d7914829f354d3efeefc3819f0
- rosterRows: 176 (by class: [('base', 158), ('dlc-ghost', 8), ('dlc-space', 10)]); localeFlagged: 14
- sceneCounts: {'strictUnityBase': 21, 'seasonalSceneCarryingBase': 22, 'strictUnityInstall': 25, 'sceneCarryingInstall': 26}
- extractionLogSeeded: False
### 2026-08-24T20:43:37Z — decompile
- exitCode: 0
- tool: Il2CppDumper vunknown at D:\unpacked_game_data\albion-online\_tooling\il2cppdumper\Il2CppDumper.exe
- inputs: GameAssembly.dll 311226368 B, global-metadata.dat 14284260 B
- measuredMetadataVersion: 27
- dummyDllImages: 101 (gate: non-empty set; Assembly-CSharp.dll not required)
- assemblyIndexPresent: 88
- assemblyIndexTotal: 148
- dllParseErrors: 0
- hierarchyRowCount: 20037
- hierarchySource: dummydll-typedef-enumeration
- registryCount: 1900
### 2026-08-24T20:43:40Z — harvest-catalog
- exitCode: 1 (failed)
- PROBLEM: catalog.bundle decoded via NEITHER route: the primary TextAsset "catalog" is absent or malformed AND no decodable ContentCatalogData MonoBehaviour exists — the secondary typetree route needs stage-1 dump.cs (decompiled/il2cppdumper/dump.cs)
