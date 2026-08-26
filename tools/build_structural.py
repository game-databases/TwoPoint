#!/usr/bin/env python3
"""Structural artifacts for stage 1 (decompile).

Emits, under `extracted/decompiled/structural/`:
  - assembly-index.json        every ScriptingAssemblies.json entry →
                               dummy-present | dummy-absent(stripped)
  - class-hierarchy.jsonl      one row per type {assembly, namespace, name,
                               baseType, interfaces[], methodCount, fieldCount}
  - id-registries/*.jsonl      enum / literal-constant registries
                               (name → value), member names verbatim

Hierarchy count source (spec §3 acceptance): PRIMARY = typedef enumeration
across DummyDll/*.dll via the pure-Python ECMA-335 reader in ilmetadata.py;
FALLBACK (only when the reader resolves nothing) = top-level type
declarations in dump.cs. The chosen source is returned to the caller for
the EXTRACTION-LOG run section.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import ilmetadata
import log_util
import tpc_common as tc


def _load_scripting_assemblies(path: Path) -> list[str]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(raw, dict):
        for v in raw.values():
            if isinstance(v, list) and v:
                raw = v
                break
    names = []
    for entry in raw:
        if not isinstance(entry, str):
            continue
        name = entry[:-len(".dll")] if entry.lower().endswith(".dll") else entry
        if name and name not in names:
            names.append(name)
    return names


def _primary_hierarchy(dummy_dll_dir: Path) -> tuple[list[dict], list[str]]:
    rows: list[dict] = []
    registries: list[tuple[str, list[dict]]] = []
    errors: list[str] = []
    dlls = sorted(dummy_dll_dir.glob("*.dll"), key=lambda p: p.name)
    for dll in dlls:
        try:
            types = ilmetadata.read_types(dll)
        except Exception as exc:  # noqa: BLE001 — collected, decides fallback
            errors.append(f"{dll.name}: {type(exc).__name__}: {exc}")
            continue
        asm = dll.stem
        for t in types:
            rows.append({
                "assembly": asm,
                "namespace": t.namespace,
                "name": t.name,
                "baseType": t.base_fullname,
                "interfaces": sorted(t.interfaces),
                "methodCount": t.method_count,
                "fieldCount": t.field_count,
            })
        for t in types:
            if t.members:
                reg_name = re.sub(r"[^A-Za-z0-9_.]", "_", f"{asm}.{t.fullname}")
                registries.append((
                    reg_name,
                    [{"name": n, "value": t.members[n]}
                     for n in sorted(t.members)]))
    rows.sort(key=lambda r: (r["assembly"], r["namespace"], r["name"]))
    registries.sort(key=lambda kv: kv[0])
    return rows, errors, registries


_DUMP_TOP_DECL_RE = re.compile(
    r"^(class|struct|interface|enum)\s+([\w.`]+)(?:<[^>]*>)?\s*"
    r"(?::\s*(.+?))?\s*(?://|$)")
# Il2CppDumper writes one of these before each assembly image's types:
# `// Image 47: TPS.Game.dll - 2` (Revision 4: hierarchy over ALL present
# game-code images, so the fallback parser must carry the distinction)
_DUMP_IMAGE_RE = re.compile(r"^//\s*Image\s+\d+:\s*(.+?)\s*-\s*\d+\s*$")


def _fallback_hierarchy(dump_cs: Path) -> list[dict]:
    rows = []
    namespace = ""
    image = None
    for line in dump_cs.read_text(encoding="utf-8", errors="replace").splitlines():
        stripped = line.strip()
        img_m = _DUMP_IMAGE_RE.match(stripped)
        if img_m:
            image = img_m.group(1).strip()
            if image.lower().endswith(".dll"):
                image = image[:-len(".dll")]
            continue
        ns_m = re.match(r"^// Namespace: (.+)$", stripped)
        if ns_m:
            namespace = ns_m.group(1)
            continue
        m = _DUMP_TOP_DECL_RE.match(stripped) if line.startswith(("class", "struct",
                                                                  "interface", "enum")) else None
        if not m or "(" in line.split("//")[0]:
            continue
        kind, name, clause = m.group(1), m.group(2), m.group(3)
        base, interfaces = None, []
        if clause:
            parts = [p.strip() for p in clause.replace(":", " ").split(",") if p.strip()]
            base = parts[0] if kind != "interface" else None
            interfaces = sorted(p for p in parts[1:])
        rows.append({
            "assembly": image or "unknown-image(dump.cs)",
            "namespace": namespace,
            "name": name,
            "baseType": base,
            "interfaces": interfaces,
            "methodCount": None,
            "fieldCount": None,
        })
    rows.sort(key=lambda r: (r["assembly"], r["namespace"], r["name"]))
    return rows


def run(dummy_out_dir: Path, scripting_assemblies_path: Path,
        extracted_root: Path) -> dict:
    dummy_dll_dir = dummy_out_dir / "DummyDll"
    dump_cs = dummy_out_dir / "dump.cs"
    structural = extracted_root / "decompiled" / "structural"
    registries_dir = structural / "id-registries"

    assemblies = _load_scripting_assemblies(scripting_assemblies_path)
    present = {p.stem: p for p in sorted(dummy_dll_dir.glob("*.dll"))}
    index_rows = [{
        "assembly": name,
        "status": "dummy-present" if name in present else "dummy-absent(stripped)",
    } for name in sorted(assemblies)]

    build_id = None
    identity_path = extracted_root / "identity.json"
    if identity_path.is_file():
        try:
            build_id = json.loads(identity_path.read_text(encoding="utf-8")).get("buildId")
        except ValueError:
            build_id = None

    hierarchy_rows, errors, registry_rows = _primary_hierarchy(dummy_dll_dir)
    if hierarchy_rows or not dump_cs.is_file():
        source = ("dummydll-typedef-enumeration",
                  "pure-python ECMA-335 metadata reader over DummyDll/*.dll")
        if errors:
            source = (source[0], source[1] + f"; per-dll parse failures: "
                                              f"{len(errors)}")
    else:
        hierarchy_rows = _fallback_hierarchy(dump_cs)
        registry_rows = []
        source = ("dumpcs-top-level-type-declarations",
                  "zero-indent class/struct/interface/enum declarations in dump.cs")

    meta = {"buildId": build_id, "hierarchySource": source[0],
            "hierarchyCountMethod": source[1],
            "hierarchyRowCount": len(hierarchy_rows)}
    log_util.write_json(structural / "assembly-index.json", {
        "meta": meta, "assemblies": index_rows})
    log_util.write_jsonl(structural / "class-hierarchy.jsonl", hierarchy_rows)

    # rewrite the registries dir contract-cleanly (stale files from a prior
    # run must never survive a rerun — byte-identical tree rule)
    import shutil
    if registries_dir.exists():
        shutil.rmtree(registries_dir)
    registries_dir.mkdir(parents=True, exist_ok=True)
    for reg_name, members in registry_rows:
        log_util.write_jsonl(registries_dir / f"{reg_name}.jsonl", members)

    covered = sum(1 for r in index_rows if r["status"] == "dummy-present")
    return {
        "assemblyIndexTotal": len(index_rows),
        "assemblyIndexPresent": covered,
        "hierarchyRowCount": len(hierarchy_rows),
        "hierarchySource": source[0],
        # piece-05 §6 item 2 (RED-3): the count's UNIT is stated beside the
        # key — stage 1 renders this as
        # `registryCount(covered classes; files = N): M` because the log's
        # counter counts covered CLASSES while the id-registries DIRECTORY
        # holds FILES (two units, one number — F15's inline-units case).
        "registryCount": len(registry_rows),
        "registryFiles": sum(len(members) for _n, members in registry_rows),
        "dllParseErrors": len(errors),
    }


def main(argv=None) -> int:
    log_util.bootstrap_console()
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("dummy_out_dir", help="dir holding DummyDll/ + dump.cs")
    parser.add_argument("--scripting-assemblies", required=True)
    parser.add_argument("--extracted-root", required=True)
    args = parser.parse_args(argv)
    try:
        summary = run(Path(args.dummy_out_dir),
                      Path(args.scripting_assemblies),
                      Path(args.extracted_root))
    except tc.StageError as exc:
        print(f"[build_structural] ERROR: {exc}", file=sys.stderr)
        return exc.exit_code
    print(f"[build_structural] {summary}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
