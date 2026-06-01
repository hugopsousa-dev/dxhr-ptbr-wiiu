#!/usr/bin/env python3
"""
DXHR Translation Pipeline — Wii U (versão final)
================================================

Pipeline completo de tradução automática do Deus Ex: Human Revolution
Director's Cut (Wii U) — usa parser customizado WiiULocals (compatível
com formato BE de 4-byte count do PowerPC).

Etapas:
  1. Lê locals.bin do bigfile-wiiu via pyDXHR (apenas pra extrair os bytes)
  2. Parsa via WiiULocals (custom, formato Wii U BE)
  3. Coleta strings em JSON
  4. Envia em lotes pro servidor de tradução IA
  5. Aplica traduções via WiiULocals.modify
  6. Rebuilda locals.bin via WiiULocals.rebuild
  7. Reempacota bigfile via pyDXHR write_new_bigfile

Uso:
  python dxhr_pipeline.py extract   <dump_dir>  strings.json
  python dxhr_pipeline.py translate strings.json  strings_pt.json
  python dxhr_pipeline.py inject    <dump_dir>  strings_pt.json  <output_dir>
  python dxhr_pipeline.py all       <dump_dir>  <output_dir>
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Optional

try:
    import requests
except ImportError:
    sys.exit("Falta requests: pip install requests")

# pyDXHR e o parser custom só são necessários nas etapas extract/inject.
# Importamos preguiçosamente (lazy) para que a etapa `translate` rode apenas
# com `requests` instalado — sem precisar do pyDXHR pesado pra retomar a tradução.
sys.path.insert(0, str(Path(__file__).parent))


def _import_dxhr():
    """Importa pyDXHR + WiiULocals sob demanda (extract/inject)."""
    try:
        from pyDXHR.Bigfile import Bigfile, write_new_bigfile, BigfileEntry
    except ImportError:
        sys.exit("Falta pyDXHR. Veja setup_pydxhr.sh ou tools/README.md")
    from wiiu_locals import WiiULocals
    return Bigfile, write_new_bigfile, BigfileEntry, WiiULocals

# ============================================================================
# Config
# ============================================================================

TRANSLATE_SERVER = "http://localhost:8765"
BATCH_SIZE = 8  # reduzido de 32 — lotes grandes + beam search estouravam a RAM no Mac
LOCALE_EN_WIIU_DC = 0xfffffde1  # English DC Wii U (descoberto via inspect_locals)


def make_bigfile(dump_dir: Path):
    Bigfile, _, _, _ = _import_dxhr()
    bf = Bigfile()
    bf._path = Path(dump_dir)
    bf.unpack_from = "bigfile-wiiu"
    bf.platform = Bigfile.Platform.WII_U
    bf.version = Bigfile.Version.DIRECTORS_CUT
    bf.open()
    return bf


def should_skip(s: Optional[str]) -> bool:
    """Filtra strings que não devem traduzir."""
    if not s or s.strip() == "":
        return True
    if s.replace(".", "").replace("-", "").replace("_", "").isdigit():
        return True
    st = s.strip()
    if (st.startswith("{") and st.endswith("}")) or \
       (st.startswith("[") and st.endswith("]")) or \
       (st.startswith("<") and st.endswith(">")):
        return True
    return False


# ============================================================================
# Etapa 1+2: Extrair strings
# ============================================================================

def extract_strings(dump_dir: Path, output_json: Path,
                    locale: int = LOCALE_EN_WIIU_DC):
    _, _, _, WiiULocals = _import_dxhr()
    print(f"[extract] Lendo bigfile (locale={hex(locale)})…")
    bf = make_bigfile(dump_dir)
    print(f"[extract] Platform={bf.platform.value}, Version={bf.version.value}, Key={bf.key}")

    raw = bf.read(r"local\locals.bin", locale=locale)
    print(f"[extract] locals.bin: {len(raw):,} bytes")

    locals_obj = WiiULocals(raw)
    print(f"[extract] {len(locals_obj):,} strings totais")

    out = {
        "locale": locale,
        "platform_key": bf.key,
        "count": len(locals_obj),
        "strings": [],
    }
    for idx, s in enumerate(locals_obj.strings):
        out["strings"].append({
            "idx": idx,
            "offset": locals_obj.offsets[idx],
            "original": s,
            "translated": None,
            "skip": should_skip(s),
        })

    output_json.parent.mkdir(parents=True, exist_ok=True)
    with open(output_json, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)

    translatable = sum(1 for s in out["strings"] if not s["skip"])
    total_chars = sum(len(s["original"]) for s in out["strings"] if not s["skip"])
    print(f"[extract] {translatable:,} strings traduzíveis ({len(out['strings']) - translatable:,} skipped)")
    print(f"[extract] {total_chars:,} caracteres a traduzir")
    print(f"[extract] Salvo em {output_json}")


# ============================================================================
# Etapa 3+4: Traduzir via servidor IA
# ============================================================================

def translate_strings(input_json: Path, output_json: Path, dry_run: bool = False):
    with open(input_json, "r", encoding="utf-8") as f:
        data = json.load(f)

    if not dry_run:
        try:
            r = requests.get(f"{TRANSLATE_SERVER}/health", timeout=5)
            r.raise_for_status()
            print(f"[translate] Servidor OK: {r.json()}")
        except Exception as e:
            sys.exit(f"Servidor não responde em {TRANSLATE_SERVER}: {e}")

    pending = [s for s in data["strings"] if not s["skip"] and s["translated"] is None]
    print(f"[translate] {len(pending):,} strings em lotes de {BATCH_SIZE}")

    if dry_run:
        print("[translate] DRY RUN")
        return

    def save():
        output_json.parent.mkdir(parents=True, exist_ok=True)
        with open(output_json, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    t0 = time.time()
    cache_hits_total = 0
    for batch_start in range(0, len(pending), BATCH_SIZE):
        batch = pending[batch_start:batch_start + BATCH_SIZE]
        texts = [s["original"] for s in batch]

        # Tenta o lote com retry — timeout generoso (a 1a chamada pode incluir
        # warmup do MPS). Se falhar 3x, salva o progresso e sai limpo pra retomar depois.
        result = None
        for attempt in range(1, 4):
            try:
                r = requests.post(
                    f"{TRANSLATE_SERVER}/translate",
                    json={"texts": texts, "use_cache": True, "use_glossary": True},
                    timeout=1800,
                )
                r.raise_for_status()
                result = r.json()
                break
            except Exception as e:
                print(f"[translate] lote falhou (tentativa {attempt}/3): {e}")
                time.sleep(3)
        if result is None:
            save()
            sys.exit(f"[translate] Abortando apos 3 falhas. Progresso salvo em "
                     f"{output_json}. Rode o mesmo comando pra retomar.")

        for s, t in zip(batch, result["translations"]):
            s["translated"] = t

        cache_hits_total += result["cache_hits"]
        done = batch_start + len(batch)
        elapsed = time.time() - t0
        eta = (elapsed / done) * (len(pending) - done) if done > 0 else 0
        print(f"[translate] {done:,}/{len(pending):,}  "
              f"hits={cache_hits_total}  "
              f"backend={result['backend']}  "
              f"elapsed={elapsed:.0f}s eta={eta:.0f}s")

        # Salva a cada lote — perde no maximo 1 lote se cair
        save()

    save()
    print(f"[translate] Salvo em {output_json}")


# ============================================================================
# Etapa 5+6+7: Reinjetar e reempacotar
# ============================================================================

def inject_translations(dump_dir: Path, translated_json: Path,
                        output_dir: Path,
                        locale: int = LOCALE_EN_WIIU_DC):
    _, write_new_bigfile, BigfileEntry, WiiULocals = _import_dxhr()
    with open(translated_json, "r", encoding="utf-8") as f:
        data = json.load(f)

    print(f"[inject] Carregando bigfile…")
    bf = make_bigfile(dump_dir)

    raw = bf.read(r"local\locals.bin", locale=locale)
    locals_obj = WiiULocals(raw)

    if len(locals_obj) != data["count"]:
        sys.exit(f"Contagem mudou: bigfile {len(locals_obj)} vs JSON {data['count']}")

    modified = 0
    for s in data["strings"]:
        if s["translated"] is None or s["skip"]:
            continue
        if s["translated"] != s["original"]:
            locals_obj.modify(s["idx"], s["translated"])
            modified += 1
    print(f"[inject] {modified:,} strings modificadas")

    # Rebuild locals.bin
    new_locals_bytes = locals_obj.rebuild()
    print(f"[inject] locals.bin reconstruído: {len(new_locals_bytes):,} bytes "
          f"(original: {len(raw):,})")

    # Cria BigfileEntry pra novo locals.bin
    orig_entry = bf.get_entry_from_filename(r"local\locals.bin", locale=locale)
    new_entry = BigfileEntry()
    new_entry.name_hash = orig_entry.name_hash
    new_entry.locale = locale
    new_entry.byte_data = new_locals_bytes
    new_entry.uncompressed_size = len(new_locals_bytes)
    new_entry.compressed_size = orig_entry.compressed_size
    new_entry.offset = orig_entry.offset

    # Reempacota bigfile (só com a entry modificada — modo mod patch)
    print(f"[inject] Reempacotando bigfile…")
    chunks = write_new_bigfile([new_entry], source_bigfile=bf)

    output_dir.mkdir(parents=True, exist_ok=True)
    for i, chunk in enumerate(chunks):
        out_path = output_dir / f"bigfile-wiiu.{i:03d}"
        with open(out_path, "wb") as f:
            f.write(chunk)
        print(f"[inject]   {out_path}  ({len(chunk)/1024/1024:.1f} MB)")

    print(f"[inject] Bigfile traduzido em {output_dir}")


def run_all(dump_dir: Path, output_dir: Path):
    output_dir.mkdir(parents=True, exist_ok=True)
    raw_json = output_dir / "strings_raw.json"
    translated_json = output_dir / "strings_translated.json"
    bigfile_out = output_dir / "bigfile_translated"

    extract_strings(dump_dir, raw_json)
    translate_strings(raw_json, translated_json)
    inject_translations(dump_dir, translated_json, bigfile_out)

    print("\n✅ PIPELINE COMPLETO")
    print(f"   - strings_raw.json:       {raw_json}")
    print(f"   - strings_translated.json: {translated_json}")
    print(f"   - bigfile traduzido:       {bigfile_out}")


def main():
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="cmd", required=True)

    e = sub.add_parser("extract")
    e.add_argument("dump_dir", type=Path)
    e.add_argument("output_json", type=Path)
    e.add_argument("--locale", type=lambda s: int(s, 0), default=LOCALE_EN_WIIU_DC)

    t = sub.add_parser("translate")
    t.add_argument("input_json", type=Path)
    t.add_argument("output_json", type=Path)
    t.add_argument("--dry-run", action="store_true")

    i = sub.add_parser("inject")
    i.add_argument("dump_dir", type=Path)
    i.add_argument("translated_json", type=Path)
    i.add_argument("output_dir", type=Path)
    i.add_argument("--locale", type=lambda s: int(s, 0), default=LOCALE_EN_WIIU_DC)

    a = sub.add_parser("all")
    a.add_argument("dump_dir", type=Path)
    a.add_argument("output_dir", type=Path)

    args = p.parse_args()

    if args.cmd == "extract":
        extract_strings(args.dump_dir, args.output_json, args.locale)
    elif args.cmd == "translate":
        translate_strings(args.input_json, args.output_json, args.dry_run)
    elif args.cmd == "inject":
        inject_translations(args.dump_dir, args.translated_json,
                            args.output_dir, args.locale)
    elif args.cmd == "all":
        run_all(args.dump_dir, args.output_dir)


if __name__ == "__main__":
    main()
