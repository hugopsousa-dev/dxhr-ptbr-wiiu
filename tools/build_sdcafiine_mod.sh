#!/usr/bin/env bash
# =============================================================================
# build_sdcafiine_mod.sh — Gera o locals.bin traduzido SOLTO e copia pro SD
# =============================================================================
# O SDCafiine (Aroma) não usa bigfile-patch: substitui arquivos soltos nos
# caminhos internos do jogo. Nosso texto está em  local/locals.bin .
#
# Funciona em 2 FASES (caso você só tenha 1 slot de SD):
#
#   FASE 1 — com o SD UNTITLED (dump do jogo) plugado:
#     o script reconstrói o locals.bin traduzido a partir do bigfile ORIGINAL
#     + as traduções (strings_pt.json) e salva em:
#       output/mod_ptbr/content/local/locals.bin
#
#   FASE 2 — troque pro SD NO NAME (do Wii U) e rode de novo:
#     o script detecta que o locals.bin já está pronto e só COPIA pro SD:
#       wiiu/sdcafiine/<titleid>/PTBR/content/local/locals.bin
#
# Se os dois SDs estiverem plugados ao mesmo tempo, ele faz tudo de uma vez.
#
# Uso:
#   bash "/Users/teste/Desktop/Nintendo Wii U/dxhr-translator/tools/build_sdcafiine_mod.sh"
# =============================================================================
set -euo pipefail

PROJ="/Users/teste/Desktop/Nintendo Wii U/dxhr-translator"
TOOLS="$PROJ/tools"
TRANSLATED_JSON="$PROJ/output/strings_pt.json"
STAGE="$PROJ/output/mod_ptbr"
LOOSE="$STAGE/content/local/locals.bin"
LOCALE="0xfffffde1"

echo "==============================================="
echo " DXHR — Montar mod SDCafiine (locals.bin solto)"
echo "==============================================="

# --- achar Python com pyDXHR -------------------------------------------------
PY=""
for cand in \
    "$HOME/dxhr_venv/bin/python" \
    "$PROJ/.venv/bin/python" \
    "$(command -v python3 || true)"
do
    if [ -n "$cand" ] && [ -x "$cand" ] && "$cand" -c "import pyDXHR" >/dev/null 2>&1; then
        PY="$cand"; break
    fi
done
if [ -z "$PY" ]; then
    echo "ERRO: não achei um Python com pyDXHR. Rode o inject.sh antes (ele instala)."
    exit 1
fi
echo "[mod] Python: $PY"

# =============================================================================
# FASE 1 — gerar o locals.bin traduzido (se ainda não existe)
# =============================================================================
if [ -f "$LOOSE" ]; then
    echo "[mod] locals.bin traduzido já existe ($(wc -c <"$LOOSE" | tr -d ' ') bytes) — pulando geração."
else
    echo "[mod] gerando locals.bin traduzido a partir do bigfile original…"
    DUMP="$(find /Volumes -maxdepth 7 -path '*Deus Ex*content/bigfile-wiiu.000' 2>/dev/null | head -1 || true)"
    [ -z "$DUMP" ] && DUMP="$(find /Volumes -maxdepth 7 -name 'bigfile-wiiu.000' 2>/dev/null | head -1 || true)"
    if [ -z "$DUMP" ]; then
        echo
        echo "⚠️  Não achei o dump do jogo. Plugue o SD UNTITLED (que tem a pasta"
        echo "    Dumpling/Games/Deus Ex…) e rode este script de novo."
        echo "    (Depois troque pro SD NO NAME e rode mais uma vez pra copiar.)"
        exit 1
    fi
    DUMPDIR="$(dirname "$DUMP")"
    echo "[mod] dump: $DUMPDIR"
    mkdir -p "$(dirname "$LOOSE")"
    "$PY" - "$DUMPDIR" "$LOOSE" "$TOOLS" "$TRANSLATED_JSON" "$LOCALE" <<'PY'
import sys, json
from pathlib import Path
dumpdir, out, tools_dir, json_path, locale_s = sys.argv[1:6]
locale = int(locale_s, 0)
sys.path.insert(0, tools_dir)
from pyDXHR.Bigfile import Bigfile
from wiiu_locals import WiiULocals

bf = Bigfile()
bf._path = Path(dumpdir)
bf.unpack_from = "bigfile-wiiu"
bf.platform = Bigfile.Platform.WII_U
bf.version = Bigfile.Version.DIRECTORS_CUT
bf.open()

raw = bf.read(r"local\locals.bin", locale=locale)
print(f"[mod] locals.bin original: {len(raw):,} bytes")
lo = WiiULocals(raw)

d = json.load(open(json_path, encoding="utf-8"))
if len(lo) != d["count"]:
    sys.exit(f"ERRO: contagem diferente (bigfile {len(lo)} vs json {d['count']})")

n = 0
for s in d["strings"]:
    if s["translated"] and not s["skip"] and s["translated"] != s["original"]:
        lo.modify(s["idx"], s["translated"]); n += 1

data = lo.rebuild()
Path(out).write_bytes(data)
print(f"[mod] {n:,} strings aplicadas; locals.bin traduzido: {len(data):,} bytes")
print(f"[mod] gravado em: {out}")
PY
fi

# --- sanidade: as traduções estão lá? ---------------------------------------
echo "[mod] conferindo strings PT-BR no arquivo:"
for w in REINICIANDO Aumentado Invadir Furtividade; do
    c="$(LC_ALL=C grep -a -o "$w" "$LOOSE" | wc -l | tr -d ' ')"
    echo "      '$w': $c"
done

# =============================================================================
# FASE 2 — copiar pro SD do Wii U (NO NAME), se estiver plugado
# =============================================================================
# IMPORTANTE: este é o title id do DXHR Director's Cut (USA / WUP-P-ADXE),
# lido direto do dump (meta/meta.xml). NÃO é 101C9400/101C9500 — esses são
# do Zelda: Breath of the Wild!
DXHR_TID="000500001012BA00"
SD="/Volumes/NO NAME/wiiu/sdcafiine"
DEST="$SD/$DXHR_TID/PTBR/content/local/locals.bin"
copied=0
if [ -d "/Volumes/NO NAME/wiiu" ]; then
    mkdir -p "$(dirname "$DEST")"
    cp "$LOOSE" "$DEST"
    echo "[mod] copiado -> $DEST"
    copied=1
fi

echo
echo "==============================================="
if [ "$copied" -gt 0 ]; then
    echo "✅ Pronto! locals.bin traduzido copiado pra $copied pasta(s) PTBR no SD."
    echo "   Ejete o SD com segurança e teste no Wii U."
else
    echo "✅ locals.bin traduzido pronto em:"
    echo "   $LOOSE"
    echo
    echo "   O SD NO NAME (do Wii U) não está plugado agora."
    echo "   -> Troque pro SD NO NAME e rode este script de novo pra copiar."
fi
echo "==============================================="
