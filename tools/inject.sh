#!/usr/bin/env bash
# =============================================================================
# inject.sh — Reinjeta as traduções PT-BR no bigfile do DXHR (Wii U)
# =============================================================================
# Roda no Mac, com o SD UNTITLED plugado. Faz tudo sozinho:
#   1. Localiza o dump (bigfile-wiiu.000) no SD
#   2. Acha um Python que tenha o pyDXHR instalado (ou instala se faltar)
#   3. Confere se há espaço em disco suficiente
#   4. Roda  dxhr_pipeline.py inject  -> gera o bigfile traduzido
#
# Uso:
#   bash "/Users/teste/Desktop/Nintendo Wii U/dxhr-translator/tools/inject.sh"
# =============================================================================
set -euo pipefail

PROJ="/Users/teste/Desktop/Nintendo Wii U/dxhr-translator"
TOOLS="$PROJ/tools"
TRANSLATED="$PROJ/output/strings_pt.json"
OUTDIR="$PROJ/output/bigfile_translated"

echo "============================================"
echo " DXHR — Injeção das traduções no bigfile"
echo "============================================"

# --- 0. sanidade: o JSON traduzido existe? -----------------------------------
if [ ! -f "$TRANSLATED" ]; then
    echo "ERRO: não achei $TRANSLATED"
    exit 1
fi

# --- 1. localizar o dump no SD -----------------------------------------------
DUMP=""
CAND="/Volumes/UNTITLED/Dumpling/Games/Deus Ex Human Rev DC/content"
if [ -f "$CAND/bigfile-wiiu.000" ]; then
    DUMP="$CAND"
else
    echo "[inject] caminho padrão não bateu, procurando bigfile-wiiu.000 em /Volumes…"
    hit="$(find /Volumes -maxdepth 7 -name 'bigfile-wiiu.000' 2>/dev/null | head -1 || true)"
    [ -n "$hit" ] && DUMP="$(dirname "$hit")"
fi
if [ -z "$DUMP" ]; then
    echo "ERRO: não encontrei 'bigfile-wiiu.000'. O SD UNTITLED está plugado?"
    exit 1
fi
echo "[inject] dump encontrado em:"
echo "         $DUMP"
nparts="$(ls "$DUMP"/bigfile-wiiu.* 2>/dev/null | wc -l | tr -d ' ')"
echo "[inject] $nparts partes do bigfile detectadas"

# --- 2. checar espaço livre (precisa ~12 GB pro bigfile reconstruído) --------
free="$(df -g / | awk 'NR==2{print $4}')"
echo "[inject] espaço livre no disco interno: ${free} GB"
if [ "$free" -lt 12 ]; then
    echo "ERRO: pouco espaço livre (<12 GB). Libere disco e rode de novo."
    exit 1
fi

# --- 3. achar um Python com pyDXHR -------------------------------------------
PY=""
for cand in \
    "$HOME/dxhr_venv/bin/python" \
    "$PROJ/.venv/bin/python" \
    "$(command -v python3 || true)"
do
    if [ -n "$cand" ] && [ -x "$cand" ] && "$cand" -c "import pyDXHR" >/dev/null 2>&1; then
        PY="$cand"
        break
    fi
done

if [ -z "$PY" ]; then
    echo "[setup] pyDXHR não encontrado em nenhum Python — instalando (1x só)…"
    if [ ! -d "$HOME/pyDXHR" ]; then
        echo "[setup] clonando pyDXHR…"
        git clone https://github.com/vardonir/pyDXHR.git "$HOME/pyDXHR"
    fi
    if [ ! -d "$PROJ/.venv" ]; then
        python3 -m venv "$PROJ/.venv"
    fi
    PY="$PROJ/.venv/bin/python"
    "$PY" -m pip install --quiet --upgrade pip
    "$PY" -m pip install --quiet -r "$HOME/pyDXHR/requirements.txt"
    "$PY" -m pip install --quiet -e "$HOME/pyDXHR"
    "$PY" -m pip install --quiet requests
fi
echo "[inject] usando Python: $PY"

# --- 4. rodar a injeção -------------------------------------------------------
echo
echo "[inject] iniciando reempacotamento (pode demorar alguns minutos)…"
echo "         dica: feche apps pesados pra não faltar RAM."
echo
cd "$TOOLS"
"$PY" dxhr_pipeline.py inject "$DUMP" "$TRANSLATED" "$OUTDIR"

echo
echo "============================================"
echo "✅ Bigfile traduzido gerado em:"
echo "   $OUTDIR"
echo "============================================"
ls -lh "$OUTDIR"
