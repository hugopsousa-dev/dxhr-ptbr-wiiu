#!/usr/bin/env bash
# Setup do pyDXHR + dependências do pipeline
# Roda uma vez no Mac antes de usar dxhr_pipeline.py

set -e

PYDXHR_DIR="${HOME}/pyDXHR"

echo "=== Setup do pipeline de tradução DXHR ==="
echo ""

# Clona pyDXHR se ainda não existe
if [ ! -d "$PYDXHR_DIR" ]; then
    echo "[setup] Clonando pyDXHR em $PYDXHR_DIR…"
    git clone https://github.com/vardonir/pyDXHR.git "$PYDXHR_DIR"
else
    echo "[setup] pyDXHR já existe em $PYDXHR_DIR — pulando clone"
    echo "[setup] (se quiser atualizar: cd $PYDXHR_DIR && git pull)"
fi

# Cria venv local (não polui Python do sistema)
VENV_DIR="$(dirname "$0")/../.venv"
if [ ! -d "$VENV_DIR" ]; then
    echo "[setup] Criando venv em $VENV_DIR…"
    python3 -m venv "$VENV_DIR"
fi

# Ativa venv e instala
echo "[setup] Instalando dependências…"
# shellcheck disable=SC1091
source "$VENV_DIR/bin/activate"

pip install --quiet --upgrade pip
pip install --quiet -r "$PYDXHR_DIR/requirements.txt"
pip install --quiet -e "$PYDXHR_DIR"
pip install --quiet requests

echo ""
echo "✅ Setup completo!"
echo ""
echo "Pra usar o pipeline:"
echo "  source $VENV_DIR/bin/activate"
echo "  python dxhr_pipeline.py extract <dump_dir> strings.json"
echo ""
echo "Onde <dump_dir> é a pasta que contém bigfile-wiiu.000 (ex.: o caminho"
echo "do Dumpling pro DXHR no seu SD UNTITLED)."
