#!/usr/bin/env bash
# =============================================================================
# build_wiiu_bigfile_sdcafiine.sh
# -----------------------------------------------------------------------------
# Monta a tradução do DXHR (Wii U) do jeito que REALMENTE funciona no console:
# substituindo os arquivos de bigfile que o jogo lê, via SDCafiine.
# (O arquivo solto local/locals.bin NÃO funciona no Wii U — aquilo só vale no
#  PC com o modhook do Gibbed.)
#
# 2 FASES (pra quem tem 1 slot de SD):
#   FASE 1 — SD UNTITLED (dump) plugado:
#       gera output/bigfile_sdcafiine/bigfile-wiiu.000 e a última parte,
#       com o locals.bin traduzido embutido e o header repointado.
#   FASE 2 — SD NO NAME (do Wii U) plugado:
#       copia esses 2 arquivos pra
#       wiiu/sdcafiine/000500001012BA00/PTBR/content/
#
# Uso:
#   bash "/Users/teste/Desktop/Nintendo Wii U/dxhr-translator/tools/build_wiiu_bigfile_sdcafiine.sh"
# =============================================================================
set -euo pipefail

PROJ="/Users/teste/Desktop/Nintendo Wii U/dxhr-translator"
TOOLS="$PROJ/tools"
NEW_LOCALS="$PROJ/output/mod_ptbr/content/local/locals.bin"
OUT="$PROJ/output/bigfile_sdcafiine"
DXHR_TID="000500001012BA00"

echo "==================================================="
echo " DXHR — Mod SDCafiine via bigfile (método Wii U real)"
echo "==================================================="

# --- locals.bin traduzido precisa existir -----------------------------------
if [ ! -f "$NEW_LOCALS" ]; then
    echo "ERRO: não achei o locals.bin traduzido em:"
    echo "      $NEW_LOCALS"
    echo "      Rode antes o build_sdcafiine_mod.sh (FASE 1) com o SD UNTITLED."
    exit 1
fi

# --- Python com pyDXHR ------------------------------------------------------
PY=""
for cand in "$HOME/dxhr_venv/bin/python" "$PROJ/.venv/bin/python" "$(command -v python3 || true)"; do
    if [ -n "$cand" ] && [ -x "$cand" ] && "$cand" -c "import pyDXHR" >/dev/null 2>&1; then
        PY="$cand"; break
    fi
done
[ -z "$PY" ] && { echo "ERRO: Python com pyDXHR não encontrado. Rode o inject.sh antes."; exit 1; }
echo "[bf] Python: $PY"

# =============================================================================
# FASE 1 — gerar os arquivos (precisa do dump / SD UNTITLED)
# =============================================================================
need_build=1
if ls "$OUT"/bigfile-wiiu.* >/dev/null 2>&1; then
    echo "[bf] arquivos já gerados em $OUT — pulando FASE 1."
    need_build=0
fi

if [ "$need_build" = "1" ]; then
    DUMP="$(find /Volumes -maxdepth 7 -path '*Deus Ex*content/bigfile-wiiu.000' 2>/dev/null | head -1 || true)"
    [ -z "$DUMP" ] && DUMP="$(find /Volumes -maxdepth 7 -name 'bigfile-wiiu.000' 2>/dev/null | head -1 || true)"
    if [ -z "$DUMP" ]; then
        echo
        echo "⚠️  Dump não encontrado. Plugue o SD UNTITLED (com Dumpling/Games/Deus Ex…)"
        echo "    e rode de novo. (Depois troque pro NO NAME pra copiar.)"
        exit 1
    fi
    DUMPDIR="$(dirname "$DUMP")"
    echo "[bf] dump: $DUMPDIR"
    "$PY" "$TOOLS/build_wiiu_bigfile_patch.py" "$DUMPDIR" "$NEW_LOCALS" "$OUT" "$TOOLS"
fi

# =============================================================================
# FASE 2 — copiar pro SD do Wii U (NO NAME)
# =============================================================================
DEST="/Volumes/NO NAME/wiiu/sdcafiine/$DXHR_TID/PTBR/content"
if [ -d "/Volumes/NO NAME/wiiu" ]; then
    mkdir -p "$DEST"
    for f in "$OUT"/bigfile-wiiu.*; do
        echo "[bf] copiando $(basename "$f") -> $DEST/ …"
        cp "$f" "$DEST/$(basename "$f")"
    done
    echo
    echo "==================================================="
    echo "✅ Pronto! Bigfiles traduzidos copiados pro SD em:"
    echo "   $DEST"
    echo "   Ejete com segurança e teste no Wii U (selecione PTBR)."
    echo "==================================================="
else
    echo
    echo "==================================================="
    echo "✅ Arquivos gerados em: $OUT"
    echo "   O SD NO NAME não está plugado agora."
    echo "   -> Troque pro SD NO NAME e rode de novo pra copiar."
    echo "==================================================="
fi
