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
### 2026-08-25T01:35:11Z — harvest-catalog
- exitCode: 1 (failed)
- PROBLEM: 205 catalog reference(s) outside the roster (match key = case-folded basename after prefix stripping); first few: -1064046067, -1072382081, -109843169, -1123468635, -1127838829, -1150871071, -1167714783, -118462433
### 2026-08-25T01:44:20Z — localisation
- exitCode: 1 (failed)
- PROBLEM: locale 'en' decoded to zero rows — refusing to emit an empty table
### 2026-08-25T03:01:16Z — harvest-catalog
- exitCode: 0
- unitypySource: venv-pip
- decodeRoute: textasset-json(primary) (textasset-json primary (TextAsset 'catalog', 11689576 B, m_LocatorId='AddressablesMainContentCatalog'))
- keysTotal: 56660; distinctBundlesReferenced: 176 of 176 roster rows; bundlesUnreferenced: 0
- keySpaceResolutions: 53658 (dependencyKey strings resolved through the key-name index); hashSuffixMatches: 15478 (file-form references resolved after stripping `_<32-hex>`)
- danglingDependencyKeys: 0 (warning ledger, sample: [])
- outOfRosterFileReferences: 19 (warning ledger — references to bundles absent from this install; never fatal)
- decodeStats: keySlots=56660; buckets=56660; entries=66129; bucketMemberships=81146 (multi-key entries put memberships above entries); distinctEntriesReferenced=66129; unreferencedEntries=0
- OUT-OF-ROSTER-REFERENCE: {TPS.Core.Addressables.AddressablesManager.RuntimeDLCPathHospital}/dlc-hospital-art-patch_assets_all.bundle
- OUT-OF-ROSTER-REFERENCE: {TPS.Core.Addressables.AddressablesManager.RuntimeDLCPathHospital}/dlc-hospital-art_assets_all.bundle
- OUT-OF-ROSTER-REFERENCE: {TPS.Core.Addressables.AddressablesManager.RuntimeDLCPathHospital}/dlc-hospital-audio_assets_all.bundle
- OUT-OF-ROSTER-REFERENCE: dlc-hospital-audio_assets_all_198c0699d9933d2be12a3f00c93f12c5.bundle
- OUT-OF-ROSTER-REFERENCE: {TPS.Core.Addressables.AddressablesManager.RuntimeDLCPathHospital}/dlc-hospital-config-patch_assets_all.bundle
- OUT-OF-ROSTER-REFERENCE: {TPS.Core.Addressables.AddressablesManager.RuntimeDLCPathHospital}/dlc-hospital-config_assets_all.bundle
- OUT-OF-ROSTER-REFERENCE: {TPS.Core.Addressables.AddressablesManager.RuntimeDLCPathHospital}/dlc-hospital-environment-debug_assets_all.bundle
- OUT-OF-ROSTER-REFERENCE: {TPS.Core.Addressables.AddressablesManager.RuntimeDLCPathHospital}/dlc-hospital-loadingscreen_assets_all.bundle
- OUT-OF-ROSTER-REFERENCE: dlc-hospital-loadingscreen_assets_all_09f03ceb7e01502eb999d8c11538e81d.bundle
- OUT-OF-ROSTER-REFERENCE: {TPS.Core.Addressables.AddressablesManager.RuntimeDLCPathHospital}/dlc-hospital-scenes_scenes_scene_dlc3_rurallevel_optimised.unity.bundle
- OUT-OF-ROSTER-REFERENCE: {TPS.Core.Addressables.AddressablesManager.RuntimeDLCPathHospital}/dlc-hospital-scenes_scenes_scene_dlc3_snowylevel_optimised.unity.bundle
- OUT-OF-ROSTER-REFERENCE: {TPS.Core.Addressables.AddressablesManager.RuntimeDLCPathHospital}/dlc-hospital-scenes_scenes_scene_dlc3_tropicallevel_optimised.unity.bundle
- OUT-OF-ROSTER-REFERENCE: {TPS.Core.Addressables.AddressablesManager.RuntimeDLCPathHospital}/dlc-hospital-ui-patch_assets_all.bundle
- OUT-OF-ROSTER-REFERENCE: {TPS.Core.Addressables.AddressablesManager.RuntimeDLCPathHospital}/dlc-hospital-ui-spriteatlas_assets_all.bundle
- OUT-OF-ROSTER-REFERENCE: {TPS.Core.Addressables.AddressablesManager.RuntimeDLCPathHospital}/dlc-hospital-ui_assets_all.bundle
- OUT-OF-ROSTER-REFERENCE: {TPS.Core.Addressables.AddressablesManager.RuntimeDLCPathPreOrder}/dlc-preorder-configs_assets_all.bundle
- OUT-OF-ROSTER-REFERENCE: {TPS.Core.Addressables.AddressablesManager.RuntimeDLCPathPreOrder}/dlc-preorder-items_assets_all.bundle
- OUT-OF-ROSTER-REFERENCE: {TPS.Core.Addressables.AddressablesManager.RuntimeDLCPathPreOrder}/dlc-preorder-ui_assets_all.bundle
- OUT-OF-ROSTER-REFERENCE: dlc-preorder-ui_assets_all_9f85177de2431cd0824a7462406341e6.bundle
### 2026-08-25T03:06:10Z — localisation
- exitCode: 0
- emittedLocales: ['en', 'pt-BR', 'zh-Hans', 'zh-Hant', 'fr', 'de', 'it', 'ja', 'ko', 'pl', 'ru', 'es', 'tr']
- baseOverlayRows: 15672 (registry sources: 26, terms walked: 15677); englishRows: 15665
- compositionPolicy: mixed (evidence: {'baseRowCount': 15672, 'englishRowCount': 15665, 'sharedKeys': 15665, 'identicalTextSharedKeys': 0, 'differingTextSharedKeys': 15665, 'baseOnlyKeys': 7, 'englishOnlyKeys': 0, 'registrySources': 26, 'registryTerms': 15677, 'termStatusForTranslation': 15402, 'termStatusNotForTranslation': 275, 'baseCellsSkippedEmpty': 15677, 'baseCellsSkippedAbsent': 0, 'localeRowsEmittedTotal': 200977, 'localeCellsSkippedEmptyTotal': 2824})
- matrixKeys: 15672
- fallbackVersionUsedBundles: 14/14 (FALLBACK_UNITY_VERSION source: identity.json unityVersion 2020.3.47f1)
- relinksWrittenHere: false (stage 5 is sole owner)
- BASE-OVERLAY: rows=15677 skippedEmpty=15677 skippedAbsent=0 categories=0 sources=26 malformed=0
- de: rows=15450 skippedEmpty=227 skippedAbsent=0 categories=25 sources=0 malformed=0 termStatus={'forTranslation': 15367, 'notForTranslation': 78, 'unregistered': 0}
- en: rows=15670 skippedEmpty=7 skippedAbsent=0 categories=25 sources=0 malformed=0 termStatus={'forTranslation': 15394, 'notForTranslation': 271, 'unregistered': 0}
- es: rows=15445 skippedEmpty=232 skippedAbsent=0 categories=25 sources=0 malformed=0 termStatus={'forTranslation': 15367, 'notForTranslation': 73, 'unregistered': 0}
- fr: rows=15450 skippedEmpty=227 skippedAbsent=0 categories=25 sources=0 malformed=0 termStatus={'forTranslation': 15367, 'notForTranslation': 78, 'unregistered': 0}
- it: rows=15450 skippedEmpty=227 skippedAbsent=0 categories=25 sources=0 malformed=0 termStatus={'forTranslation': 15367, 'notForTranslation': 78, 'unregistered': 0}
- ja: rows=15376 skippedEmpty=301 skippedAbsent=0 categories=25 sources=0 malformed=0 termStatus={'forTranslation': 15346, 'notForTranslation': 25, 'unregistered': 0}
- ko: rows=15462 skippedEmpty=215 skippedAbsent=0 categories=25 sources=0 malformed=0 termStatus={'forTranslation': 15366, 'notForTranslation': 91, 'unregistered': 0}
- pl: rows=15450 skippedEmpty=227 skippedAbsent=0 categories=25 sources=0 malformed=0 termStatus={'forTranslation': 15367, 'notForTranslation': 78, 'unregistered': 0}
- pt-BR: rows=15448 skippedEmpty=229 skippedAbsent=0 categories=25 sources=0 malformed=0 termStatus={'forTranslation': 15367, 'notForTranslation': 76, 'unregistered': 0}
- ru: rows=15427 skippedEmpty=250 skippedAbsent=0 categories=25 sources=0 malformed=0 termStatus={'forTranslation': 15345, 'notForTranslation': 77, 'unregistered': 0}
- tr: rows=15448 skippedEmpty=229 skippedAbsent=0 categories=25 sources=0 malformed=0 termStatus={'forTranslation': 15367, 'notForTranslation': 76, 'unregistered': 0}
- zh-Hans: rows=15450 skippedEmpty=227 skippedAbsent=0 categories=25 sources=0 malformed=0 termStatus={'forTranslation': 15368, 'notForTranslation': 77, 'unregistered': 0}
- zh-Hant: rows=15451 skippedEmpty=226 skippedAbsent=0 categories=25 sources=0 malformed=0 termStatus={'forTranslation': 15368, 'notForTranslation': 78, 'unregistered': 0}
### 2026-08-25T03:13:04Z — harvest-catalog
- exitCode: 0
- unitypySource: venv-pip
- decodeRoute: textasset-json(primary) (textasset-json primary (TextAsset 'catalog', 11689576 B, m_LocatorId='AddressablesMainContentCatalog'))
- keysTotal: 56660; distinctBundlesReferenced: 176 of 176 roster rows; bundlesUnreferenced: 0
- keySpaceResolutions: 53658 (dependencyKey strings resolved through the key-name index); hashSuffixMatches: 15478 (file-form references resolved after stripping `_<32-hex>`)
- danglingDependencyKeys: 0 (warning ledger, sample: [])
- outOfRosterFileReferences: 19 (warning ledger — references to bundles absent from this install; never fatal)
- decodeStats: keySlots=56660; buckets=56660; entries=66129; bucketMemberships=81146 (multi-key entries put memberships above entries); distinctEntriesReferenced=66129; unreferencedEntries=0
- OUT-OF-ROSTER-REFERENCE: {TPS.Core.Addressables.AddressablesManager.RuntimeDLCPathHospital}/dlc-hospital-art-patch_assets_all.bundle
- OUT-OF-ROSTER-REFERENCE: {TPS.Core.Addressables.AddressablesManager.RuntimeDLCPathHospital}/dlc-hospital-art_assets_all.bundle
- OUT-OF-ROSTER-REFERENCE: {TPS.Core.Addressables.AddressablesManager.RuntimeDLCPathHospital}/dlc-hospital-audio_assets_all.bundle
- OUT-OF-ROSTER-REFERENCE: dlc-hospital-audio_assets_all_198c0699d9933d2be12a3f00c93f12c5.bundle
- OUT-OF-ROSTER-REFERENCE: {TPS.Core.Addressables.AddressablesManager.RuntimeDLCPathHospital}/dlc-hospital-config-patch_assets_all.bundle
- OUT-OF-ROSTER-REFERENCE: {TPS.Core.Addressables.AddressablesManager.RuntimeDLCPathHospital}/dlc-hospital-config_assets_all.bundle
- OUT-OF-ROSTER-REFERENCE: {TPS.Core.Addressables.AddressablesManager.RuntimeDLCPathHospital}/dlc-hospital-environment-debug_assets_all.bundle
- OUT-OF-ROSTER-REFERENCE: {TPS.Core.Addressables.AddressablesManager.RuntimeDLCPathHospital}/dlc-hospital-loadingscreen_assets_all.bundle
- OUT-OF-ROSTER-REFERENCE: dlc-hospital-loadingscreen_assets_all_09f03ceb7e01502eb999d8c11538e81d.bundle
- OUT-OF-ROSTER-REFERENCE: {TPS.Core.Addressables.AddressablesManager.RuntimeDLCPathHospital}/dlc-hospital-scenes_scenes_scene_dlc3_rurallevel_optimised.unity.bundle
- OUT-OF-ROSTER-REFERENCE: {TPS.Core.Addressables.AddressablesManager.RuntimeDLCPathHospital}/dlc-hospital-scenes_scenes_scene_dlc3_snowylevel_optimised.unity.bundle
- OUT-OF-ROSTER-REFERENCE: {TPS.Core.Addressables.AddressablesManager.RuntimeDLCPathHospital}/dlc-hospital-scenes_scenes_scene_dlc3_tropicallevel_optimised.unity.bundle
- OUT-OF-ROSTER-REFERENCE: {TPS.Core.Addressables.AddressablesManager.RuntimeDLCPathHospital}/dlc-hospital-ui-patch_assets_all.bundle
- OUT-OF-ROSTER-REFERENCE: {TPS.Core.Addressables.AddressablesManager.RuntimeDLCPathHospital}/dlc-hospital-ui-spriteatlas_assets_all.bundle
- OUT-OF-ROSTER-REFERENCE: {TPS.Core.Addressables.AddressablesManager.RuntimeDLCPathHospital}/dlc-hospital-ui_assets_all.bundle
- OUT-OF-ROSTER-REFERENCE: {TPS.Core.Addressables.AddressablesManager.RuntimeDLCPathPreOrder}/dlc-preorder-configs_assets_all.bundle
- OUT-OF-ROSTER-REFERENCE: {TPS.Core.Addressables.AddressablesManager.RuntimeDLCPathPreOrder}/dlc-preorder-items_assets_all.bundle
- OUT-OF-ROSTER-REFERENCE: {TPS.Core.Addressables.AddressablesManager.RuntimeDLCPathPreOrder}/dlc-preorder-ui_assets_all.bundle
- OUT-OF-ROSTER-REFERENCE: dlc-preorder-ui_assets_all_9f85177de2431cd0824a7462406341e6.bundle
### 2026-08-25T03:13:17Z — localisation
- exitCode: 0
- emittedLocales: ['en', 'pt-BR', 'zh-Hans', 'zh-Hant', 'fr', 'de', 'it', 'ja', 'ko', 'pl', 'ru', 'es', 'tr']
- baseOverlayRows: 15672 (registry sources: 26, terms walked: 15677); englishRows: 15665
- compositionPolicy: mixed (evidence: {'baseRowCount': 15672, 'englishRowCount': 15665, 'sharedKeys': 15665, 'identicalTextSharedKeys': 0, 'differingTextSharedKeys': 15665, 'baseOnlyKeys': 7, 'englishOnlyKeys': 0, 'registrySources': 26, 'registryTerms': 15677, 'termStatusForTranslation': 15402, 'termStatusNotForTranslation': 275, 'baseCellsSkippedEmpty': 15677, 'baseCellsSkippedAbsent': 0, 'localeRowsEmittedTotal': 200977, 'localeCellsSkippedEmptyTotal': 2824})
- matrixKeys: 15672
- fallbackVersionUsedBundles: 14/14 (FALLBACK_UNITY_VERSION source: identity.json unityVersion 2020.3.47f1)
- relinksWrittenHere: false (stage 5 is sole owner)
- BASE-OVERLAY: rows=15677 skippedEmpty=15677 skippedAbsent=0 categories=0 sources=26 malformed=0
- de: rows=15450 skippedEmpty=227 skippedAbsent=0 categories=25 sources=0 malformed=0 termStatus={'forTranslation': 15367, 'notForTranslation': 78, 'unregistered': 0}
- en: rows=15670 skippedEmpty=7 skippedAbsent=0 categories=25 sources=0 malformed=0 termStatus={'forTranslation': 15394, 'notForTranslation': 271, 'unregistered': 0}
- es: rows=15445 skippedEmpty=232 skippedAbsent=0 categories=25 sources=0 malformed=0 termStatus={'forTranslation': 15367, 'notForTranslation': 73, 'unregistered': 0}
- fr: rows=15450 skippedEmpty=227 skippedAbsent=0 categories=25 sources=0 malformed=0 termStatus={'forTranslation': 15367, 'notForTranslation': 78, 'unregistered': 0}
- it: rows=15450 skippedEmpty=227 skippedAbsent=0 categories=25 sources=0 malformed=0 termStatus={'forTranslation': 15367, 'notForTranslation': 78, 'unregistered': 0}
- ja: rows=15376 skippedEmpty=301 skippedAbsent=0 categories=25 sources=0 malformed=0 termStatus={'forTranslation': 15346, 'notForTranslation': 25, 'unregistered': 0}
- ko: rows=15462 skippedEmpty=215 skippedAbsent=0 categories=25 sources=0 malformed=0 termStatus={'forTranslation': 15366, 'notForTranslation': 91, 'unregistered': 0}
- pl: rows=15450 skippedEmpty=227 skippedAbsent=0 categories=25 sources=0 malformed=0 termStatus={'forTranslation': 15367, 'notForTranslation': 78, 'unregistered': 0}
- pt-BR: rows=15448 skippedEmpty=229 skippedAbsent=0 categories=25 sources=0 malformed=0 termStatus={'forTranslation': 15367, 'notForTranslation': 76, 'unregistered': 0}
- ru: rows=15427 skippedEmpty=250 skippedAbsent=0 categories=25 sources=0 malformed=0 termStatus={'forTranslation': 15345, 'notForTranslation': 77, 'unregistered': 0}
- tr: rows=15448 skippedEmpty=229 skippedAbsent=0 categories=25 sources=0 malformed=0 termStatus={'forTranslation': 15367, 'notForTranslation': 76, 'unregistered': 0}
- zh-Hans: rows=15450 skippedEmpty=227 skippedAbsent=0 categories=25 sources=0 malformed=0 termStatus={'forTranslation': 15368, 'notForTranslation': 77, 'unregistered': 0}
- zh-Hant: rows=15451 skippedEmpty=226 skippedAbsent=0 categories=25 sources=0 malformed=0 termStatus={'forTranslation': 15368, 'notForTranslation': 78, 'unregistered': 0}
### 2026-08-25T03:51:33Z — verify-client
- exitCode: 0
- buildId: 20226581 (TargetBuildID 20226581)
- metadataVersion: 27; dumper: il2cppdumper
- unityVersion: 2020.3.47f1; versionString: `10.3.169253+2024-12-06.1241`
- addressablesVersion: 1.21.10; settingsHash: ff59c4d7914829f354d3efeefc3819f0
- rosterRows: 176 (by class: [('base', 158), ('dlc-ghost', 8), ('dlc-space', 10)]); localeFlagged: 14
- sceneCounts: {'strictUnityBase': 21, 'seasonalSceneCarryingBase': 22, 'strictUnityInstall': 25, 'sceneCarryingInstall': 26}
- extractionLogSeeded: False
### 2026-08-25T03:51:43Z — decompile
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
### 2026-08-25T03:53:30Z — harvest-bundles
- exitCode: 0
- unitypySource: venv-pip
- bundlesAttempted: 176; unreadableBundles: 0
- censusObjectsTotal: 2026658; exports: 167069; catalogueRows: 47939; objectErrors: 0; censusOnlyResidual: 1811650
- carvedClassCensus: {'AnimationClip': 7985, 'AudioClip': 5624, 'Font': 24, 'Mesh': 19249, 'Shader': 213, 'Sprite': 6789, 'SpriteAtlas': 47, 'Texture2D': 7977, 'VideoClip': 31}
- fallbackVersionUsedBundles: 176/176 (FALLBACK_UNITY_VERSION source: identity.json unityVersion 2020.3.47f1)
### 2026-08-25T03:55:37Z — emit-stub-datasets
- exitCode: 1 (duplicate ids within family 'item'; duplicate ids within family 'unlockable'; duplicate ids within family 'room'; duplicate ids within family 'campus-level'; duplicate ids within family 'config'; duplicate ids within family 'student-type')
- stubRowsByKind: {"campus-level": 15, "config": 14305, "course": 0, "item": 8896, "metagame-node": 0, "room": 156, "staff": 0, "student-type": 33, "unlockable": 1412}
- absences: 3; unmappedClasses: 1
- localeAvailabilityRows: 0 (distinctJoinedEntities: 0); regenerated this run
- identifierByteMatch: checked=0 mismatches=0
- structuralInputs: ['assembly-index.json', 'class-hierarchy.jsonl', 'id-registries']
- PROBLEM: duplicate ids within family 'item'
- PROBLEM: duplicate ids within family 'unlockable'
- PROBLEM: duplicate ids within family 'room'
- PROBLEM: duplicate ids within family 'campus-level'
- PROBLEM: duplicate ids within family 'config'
- PROBLEM: duplicate ids within family 'student-type'
### 2026-08-25T05:26:16Z — harvest-bundles
- exitCode: 0
- unitypySource: venv-pip
- bundlesAttempted: 176; unreadableBundles: 0
- censusObjectsTotal: 2026658; exports: 167069; catalogueRows: 47939; objectErrors: 0; censusOnlyResidual: 1811650
- carvedClassCensus: {'AnimationClip': 7985, 'AudioClip': 5624, 'Font': 24, 'Mesh': 19249, 'Shader': 213, 'Sprite': 6789, 'SpriteAtlas': 47, 'Texture2D': 7977, 'VideoClip': 31}
- monoScriptIndex: {'scriptsIndexed': 1140, 'bundlesWithScripts': 1, 'distinctEntries': 1140}; monobehaviourScriptClass: resolved=165972 unresolved(generic)=742
- fallbackVersionUsedBundles: 176/176 (FALLBACK_UNITY_VERSION source: identity.json unityVersion 2020.3.47f1)
### 2026-08-25T05:29:41Z — emit-stub-datasets
- exitCode: 0
- stubRowsByKind: {"campus-level": 17, "config": 7756, "course": 69, "item": 3884, "metagame-node": 456, "room": 116, "staff": 3, "student-type": 54, "unlockable": 409}
- identityPolicy: componentExcluded=152463; identifierLess=1 (ledgered+sampled); mergedDuplicates=21; disambiguatedDuplicates=22
- scriptClassResolution: resolved=165972 generic/unresolved=742
- absences: 1; unmappedClasses: 767
- localeAvailabilityRows: 0 (distinctJoinedEntities: 0); regenerated this run
- identifierByteMatch: checked=2124 mismatches=0
- manifestStemContract: rows=167069 unparsed=0 mismatched=0
- structuralInputs: ['assembly-index.json', 'class-hierarchy.jsonl', 'id-registries']
### 2026-08-25T05:39:58Z — emit-stub-datasets
- exitCode: 0
- stubRowsByKind: {"campus-level": 17, "config": 7756, "course": 69, "item": 3884, "metagame-node": 456, "room": 116, "staff": 3, "student-type": 54, "unlockable": 409}
- identityPolicy: componentExcluded=152463; identifierLess=1 (ledgered+sampled); mergedDuplicates=21; disambiguatedDuplicates=22
- scriptClassResolution: resolved=165972 generic/unresolved=742
- absences: 1; unmappedClasses: 767
- localeAvailabilityRows: 0 (distinctJoinedEntities: 0); regenerated this run; joinEvidence: {"conventionJoins": 0, "entitiesScanned": 12742, "hardJoins": 0, "payloadsResolved": 12742}
- identifierByteMatch: checked=2124 mismatches=0
- manifestStemContract: rows=167069 unparsed=0 mismatched=0
- structuralInputs: ['assembly-index.json', 'class-hierarchy.jsonl', 'id-registries']
### 2026-08-25T05:40:50Z — emit-stub-datasets
- exitCode: 0
- stubRowsByKind: {"campus-level": 17, "config": 7756, "course": 69, "item": 3884, "metagame-node": 456, "room": 116, "staff": 3, "student-type": 54, "unlockable": 409}
- identityPolicy: componentExcluded=152463; identifierLess=1 (ledgered+sampled); mergedDuplicates=21; disambiguatedDuplicates=22
- scriptClassResolution: resolved=165972 generic/unresolved=742
- absences: 1; unmappedClasses: 767
- localeAvailabilityRows: 0 (distinctJoinedEntities: 0); regenerated this run; joinEvidence: {"conventionJoins": 0, "entitiesScanned": 12742, "hardJoins": 0, "payloadsResolved": 12742}
- identifierByteMatch: checked=2124 mismatches=0
- manifestStemContract: rows=167069 unparsed=0 mismatched=0
- structuralInputs: ['assembly-index.json', 'class-hierarchy.jsonl', 'id-registries']
### 2026-08-25T09:03:08Z — harvest-catalog
- exitCode: 0
- unitypySource: venv-pip
- decodeRoute: textasset-json(primary) (textasset-json primary (TextAsset 'catalog', 11689576 B, m_LocatorId='AddressablesMainContentCatalog'))
- keysTotal: 56660; distinctBundlesReferenced: 176 of 176 roster rows; bundlesUnreferenced: 0
- keySpaceResolutions: 53658 (dependencyKey strings resolved through the key-name index); hashSuffixMatches: 15478 (file-form references resolved after stripping `_<32-hex>`)
- danglingDependencyKeys: 0 (warning ledger, sample: [])
- outOfRosterFileReferences: 19 (warning ledger — references to bundles absent from this install; never fatal)
- decodeStats: keySlots=56660; buckets=56660; entries=66129; bucketMemberships=81146 (multi-key entries put memberships above entries); distinctEntriesReferenced=66129; unreferencedEntries=0
- OUT-OF-ROSTER-REFERENCE: {TPS.Core.Addressables.AddressablesManager.RuntimeDLCPathHospital}/dlc-hospital-art-patch_assets_all.bundle
- OUT-OF-ROSTER-REFERENCE: {TPS.Core.Addressables.AddressablesManager.RuntimeDLCPathHospital}/dlc-hospital-art_assets_all.bundle
- OUT-OF-ROSTER-REFERENCE: {TPS.Core.Addressables.AddressablesManager.RuntimeDLCPathHospital}/dlc-hospital-audio_assets_all.bundle
- OUT-OF-ROSTER-REFERENCE: dlc-hospital-audio_assets_all_198c0699d9933d2be12a3f00c93f12c5.bundle
- OUT-OF-ROSTER-REFERENCE: {TPS.Core.Addressables.AddressablesManager.RuntimeDLCPathHospital}/dlc-hospital-config-patch_assets_all.bundle
- OUT-OF-ROSTER-REFERENCE: {TPS.Core.Addressables.AddressablesManager.RuntimeDLCPathHospital}/dlc-hospital-config_assets_all.bundle
- OUT-OF-ROSTER-REFERENCE: {TPS.Core.Addressables.AddressablesManager.RuntimeDLCPathHospital}/dlc-hospital-environment-debug_assets_all.bundle
- OUT-OF-ROSTER-REFERENCE: {TPS.Core.Addressables.AddressablesManager.RuntimeDLCPathHospital}/dlc-hospital-loadingscreen_assets_all.bundle
- OUT-OF-ROSTER-REFERENCE: dlc-hospital-loadingscreen_assets_all_09f03ceb7e01502eb999d8c11538e81d.bundle
- OUT-OF-ROSTER-REFERENCE: {TPS.Core.Addressables.AddressablesManager.RuntimeDLCPathHospital}/dlc-hospital-scenes_scenes_scene_dlc3_rurallevel_optimised.unity.bundle
- OUT-OF-ROSTER-REFERENCE: {TPS.Core.Addressables.AddressablesManager.RuntimeDLCPathHospital}/dlc-hospital-scenes_scenes_scene_dlc3_snowylevel_optimised.unity.bundle
- OUT-OF-ROSTER-REFERENCE: {TPS.Core.Addressables.AddressablesManager.RuntimeDLCPathHospital}/dlc-hospital-scenes_scenes_scene_dlc3_tropicallevel_optimised.unity.bundle
- OUT-OF-ROSTER-REFERENCE: {TPS.Core.Addressables.AddressablesManager.RuntimeDLCPathHospital}/dlc-hospital-ui-patch_assets_all.bundle
- OUT-OF-ROSTER-REFERENCE: {TPS.Core.Addressables.AddressablesManager.RuntimeDLCPathHospital}/dlc-hospital-ui-spriteatlas_assets_all.bundle
- OUT-OF-ROSTER-REFERENCE: {TPS.Core.Addressables.AddressablesManager.RuntimeDLCPathHospital}/dlc-hospital-ui_assets_all.bundle
- OUT-OF-ROSTER-REFERENCE: {TPS.Core.Addressables.AddressablesManager.RuntimeDLCPathPreOrder}/dlc-preorder-configs_assets_all.bundle
- OUT-OF-ROSTER-REFERENCE: {TPS.Core.Addressables.AddressablesManager.RuntimeDLCPathPreOrder}/dlc-preorder-items_assets_all.bundle
- OUT-OF-ROSTER-REFERENCE: {TPS.Core.Addressables.AddressablesManager.RuntimeDLCPathPreOrder}/dlc-preorder-ui_assets_all.bundle
- OUT-OF-ROSTER-REFERENCE: dlc-preorder-ui_assets_all_9f85177de2431cd0824a7462406341e6.bundle
### 2026-08-25T09:26:42Z — harvest-bundles
- exitCode: 0
- unitypySource: venv-pip
- bundlesAttempted: 176; unreadableBundles: 0
- censusObjectsTotal: 2026658; exports: 167069; catalogueRows: 47939; objectErrors: 0; censusOnlyResidual: 1811650
- carvedClassCensus: {'AnimationClip': 7985, 'AudioClip': 5624, 'Font': 24, 'Mesh': 19249, 'Shader': 213, 'Sprite': 6789, 'SpriteAtlas': 47, 'Texture2D': 7977, 'VideoClip': 31}
- monoScriptIndex: {'scriptsIndexed': 1140, 'bundlesWithScripts': 1, 'distinctEntries': 1140}; monobehaviourScriptClass: resolved=166704 unresolved(generic)=10; decodeRoutes: embedded=165982 synthesis=0 residue=732
- fallbackVersionUsedBundles: 176/176 (FALLBACK_UNITY_VERSION source: identity.json unityVersion 2020.3.47f1)
### 2026-08-25T12:12:48Z — harvest-bundles
- exitCode: 0
- unitypySource: venv-pip
- bundlesAttempted: 176; unreadableBundles: 0
- censusObjectsTotal: 2026658; exports: 167069; catalogueRows: 47939; objectErrors: 0; censusOnlyResidual: 1811650
- carvedClassCensus: {'AnimationClip': 7985, 'AudioClip': 5624, 'Font': 24, 'Mesh': 19249, 'Shader': 213, 'Sprite': 6789, 'SpriteAtlas': 47, 'Texture2D': 7977, 'VideoClip': 31}
- externalsTables: 222 serialized files across 176 readable bundles; totalExternalRefs 1781 (harvest/externals.jsonl — R11 G2 cross-file PPtr sidecar)
- monoScriptIndex: {'scriptsIndexed': 1140, 'bundlesWithScripts': 1, 'distinctEntries': 1140}; monobehaviourScriptClass: resolved=166704 unresolved(generic)=10; decodeRoutes: embedded=165982 oracle=0 synthesis=688 residue=44; embeddedTreeOracle: 1127 script trees captured
- fallbackVersionUsedBundles: 176/176 (FALLBACK_UNITY_VERSION source: identity.json unityVersion 2020.3.47f1)
### 2026-08-25T12:13:37Z — emit-stub-datasets
- exitCode: 0
- stubRowsByKind: {"campus-level": 17, "config": 8430, "course": 69, "item": 3885, "metagame-node": 454, "room": 116, "staff": 3, "student-type": 54, "unlockable": 415}
- identityPolicy: componentExcluded=151731; identifierLess=45 (ledgered+sampled); mergedDuplicates=26; disambiguatedDuplicates=17; admittedUnknown=344 (unverified chains)
- scriptClassResolution: resolved=166704 generic/unresolved=10
- absences: 2; unmappedClasses: 768
- localeAvailabilityRows: 0 (distinctJoinedEntities: 0); regenerated this run; joinEvidence: {"conventionJoins": 0, "entitiesScanned": 13426, "hardJoins": 0, "payloadsResolved": 13426}
- identifierByteMatch: checked=2128 mismatches=0
- manifestStemContract: rows=167069 unparsed=0 mismatched=0
- structuralInputs: ['assembly-index.json', 'class-hierarchy.jsonl', 'id-registries']
### 2026-08-25T12:17:47Z — harvest-bundles
- exitCode: 0
- unitypySource: venv-pip
- bundlesAttempted: 176; unreadableBundles: 0
- censusObjectsTotal: 2026658; exports: 167069; catalogueRows: 47939; objectErrors: 0; censusOnlyResidual: 1811650
- carvedClassCensus: {'AnimationClip': 7985, 'AudioClip': 5624, 'Font': 24, 'Mesh': 19249, 'Shader': 213, 'Sprite': 6789, 'SpriteAtlas': 47, 'Texture2D': 7977, 'VideoClip': 31}
- externalsTables: 222 serialized files across 176 readable bundles; totalExternalRefs 1781 (harvest/externals.jsonl — R11 G2 cross-file PPtr sidecar)
- monoScriptIndex: {'scriptsIndexed': 1140, 'bundlesWithScripts': 1, 'distinctEntries': 1140}; monobehaviourScriptClass: resolved=166704 unresolved(generic)=10; decodeRoutes: embedded=165982 oracle=0 synthesis=688 residue=44; embeddedTreeOracle: 1127 script trees captured
- fallbackVersionUsedBundles: 176/176 (FALLBACK_UNITY_VERSION source: identity.json unityVersion 2020.3.47f1)
### 2026-08-25T19:50:14Z — relink
- exitCode: 2 (completed-with-ledger)
- R1: bundlesBridged=176 cabRows=2026658 containerRows=49855 fallbackVersionUsedBundles=176 containerAddressCollisions=45838
- R1-note: fallbackVersionUsedBundles: 176/176 (FALLBACK_UNITY_VERSION source: identity.json unityVersion 2020.3.47f1); unitypyVersion: 1.25.3
- R2: cellsTotal=100 cellsModeled=20 cellsPartial=6 cellsMissing=74 pairFilesEmitted=24 edgesEmitted=24583 sameFileResolved=12125 crossFileResolved=8909 sceneAttributedEdges=0 unresolvedCrossFile=2284 builtinExternalsSkipped=0 twinEndpointEdges=14 unresolvedSameFile=107 probeUnlockableLevelRefs=0
- R2-ledger: _unresolved_pptrs rows=2391 (sorted by (srcKind, srcId, fieldPath, extPath, m_PathID))
- R3: guidRefsTotal=20170 distinctGuids=5584 resolvedToAddress=16110 resolvedToStub=3747 danglingDistinctGuids=1137 danglingVerdicts={'unresolved-open': 1137} resolveRateAddress=0.7987 resolveRateStub=0.1858 sceneGuidEdges=0
- R4: languageSourcesRead=26 registryRows=15675 registryDistinctKeys=15672 matrixKeyDiff=0 instancesTotal=20070 sentinelZero=9101 registryHits=10964 registryMisses=5 coverageOnNonEmpty=0.9995 entityLocaleRows=10964 reverseRows=6526
- R5: surfacesTotal=344 mappedSchema=10 documentedGaps=334 tooltipTargetClasses=3 localizeBindings=11312 hierarchyRowsRead=20037
- R6: sourcesRead=2 sourcesApplied=2 floorMet=False confirmsHard=0 addsDerived=0 flagsMissing=417 wallsRecorded=0 overlayFiles=0
- R7: relationsMdBytes=29321 generatedFrom={"edgesEmitted": 24583, "registryRows": 15675, "guidRefsTotal": 20170, "coverageRows": 344, "competitorLedgerRows": 3}
- DRIFT: GUID bridge measures 20170 refs / 5584 distinct / 1137 dangling against seed F9 (20042/5548/1137) — fresh wins
- LEDGER-CONTRIBUTORS (exit 2): _dangling_guids.jsonl unresolved-open: 1137; registryMisses: 5; competitor floor unmet (<3 applied sources; terminal ledger row ~floor)
### 2026-08-25T19:52:43Z — relink
- exitCode: 2 (completed-with-ledger)
- R1: bundlesBridged=176 cabRows=2026658 containerRows=49855 fallbackVersionUsedBundles=176 containerAddressCollisions=45838
- R1-note: fallbackVersionUsedBundles: 176/176 (FALLBACK_UNITY_VERSION source: identity.json unityVersion 2020.3.47f1); unitypyVersion: 1.25.3
- R2: cellsTotal=100 cellsModeled=20 cellsPartial=6 cellsMissing=74 pairFilesEmitted=24 edgesEmitted=24583 sameFileResolved=12125 crossFileResolved=8909 sceneAttributedEdges=0 unresolvedCrossFile=2284 builtinExternalsSkipped=0 twinEndpointEdges=14 unresolvedSameFile=107 probeUnlockableLevelRefs=0
- R2-ledger: _unresolved_pptrs rows=2391 (sorted by (srcKind, srcId, fieldPath, extPath, m_PathID))
- R3: guidRefsTotal=20170 distinctGuids=5584 resolvedToAddress=16110 resolvedToStub=3747 danglingDistinctGuids=1137 danglingVerdicts={'unresolved-open': 1137} resolveRateAddress=0.7987 resolveRateStub=0.1858 sceneGuidEdges=0
- R4: languageSourcesRead=26 registryRows=15675 registryDistinctKeys=15672 matrixKeyDiff=0 instancesTotal=20070 sentinelZero=9101 registryHits=10964 registryMisses=5 coverageOnNonEmpty=0.9995 entityLocaleRows=10964 reverseRows=6526
- R5: surfacesTotal=344 mappedSchema=10 documentedGaps=334 tooltipTargetClasses=3 localizeBindings=11312 hierarchyRowsRead=20037
- R6: sourcesRead=2 sourcesApplied=2 floorMet=False confirmsHard=0 addsDerived=0 flagsMissing=417 wallsRecorded=0 overlayFiles=0
- R7: relationsMdBytes=29321 generatedFrom={"edgesEmitted": 24583, "registryRows": 15675, "guidRefsTotal": 20170, "coverageRows": 344, "competitorLedgerRows": 3}
- DRIFT: GUID bridge measures 20170 refs / 5584 distinct / 1137 dangling against seed F9 (20042/5548/1137) — fresh wins
- LEDGER-CONTRIBUTORS (exit 2): _dangling_guids.jsonl unresolved-open: 1137; registryMisses: 5; competitor floor unmet (<3 applied sources; terminal ledger row ~floor)
### 2026-08-25T23:49:25Z — relink
- exitCode: 2 (completed-with-ledger)
- R1: bundlesBridged=176 cabRows=222 cabObjects=2026658 containerRows=49855 fallbackVersionUsedBundles=176 containerAddressCollisions=45838
- R1-note: fallbackVersionUsedBundles: 176/176 (FALLBACK_UNITY_VERSION source: identity.json unityVersion 2020.3.47f1); unitypyVersion: 1.25.3
- R2: cellsTotal=100 cellsModeled=24 cellsPartial=3 cellsMissing=73 pairFilesEmitted=24 edgesEmitted=24583 sameFileResolved=12125 crossFileResolved=8909 sceneAttributedEdges=0 unresolvedCrossFile=2284 builtinExternalsSkipped=0 twinEndpointEdges=14 unresolvedSameFile=107 probeUnlockableLevelRefs=0
- R2-ledger: _unresolved_pptrs rows=2391 (sorted by (srcKind, srcId, fieldPath, extPath, m_PathID))
- R2-attribution: chargedCells=0 chargedRefs=0 landed=0 leafKeyNamed=0 nonEntityTargets=2391 unresolvable=0
- R3: guidRefsTotal=20170 distinctGuids=5584 resolvedToAddress=16110 resolvedToStub=3747 danglingDistinctGuids=1137 danglingVerdicts={'unresolved-open': 1137} resolveRateAddress=0.7987 resolveRateStub=0.1858 sceneGuidEdges=0
- R4: languageSourcesRead=26 registryRows=15675 registryDistinctKeys=15672 matrixKeyDiff=0 instancesTotal=20070 sentinelZero=9101 registryHits=10964 registryMisses=5 coverageOnNonEmpty=0.9995 entityLocaleRows=10964 reverseRows=6526
- R5: surfacesTotal=344 mappedSchema=9 documentedGaps=335 tooltipTargetClasses=0 tooltipGenericContainers=4 localizeBindings=11312 hierarchyRowsRead=20037
- R6: sourcesRead=2 sourcesApplied=0 floorMet=False confirmsHard=0 addsDerived=0 flagsMissing=417 wallsRecorded=0 overlayFiles=0
- R7: relationsMdBytes=29346 generatedFrom={"edgesEmitted": 24583, "registryRows": 15675, "guidRefsTotal": 20170, "coverageRows": 344, "competitorLedgerRows": 3}
- DRIFT: GUID bridge measures 20170 refs / 5584 distinct / 1137 dangling against seed F9 (20042/5548/1137) — fresh wins
- DRIFT: seeded campus-level->metagame-node pair fact 13 vs measured 0 — the seed's carrier (.MetagameConfig.m_AssetGUID → Config_Metagame) is kinded `config` by stage-5 and its 13 rows land in campus-level_config.jsonl — fresh numbers win
- LEDGER-CONTRIBUTORS (exit 2): _dangling_guids.jsonl unresolved-open: 1137; registryMisses: 5; competitor floor unmet (<3 applied sources; terminal ledger row ~floor)
