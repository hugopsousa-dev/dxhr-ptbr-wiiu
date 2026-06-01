#!/bin/bash
# ── DXHR PT-BR Wii U · publish helper ──
# Duplo-clique neste arquivo (ou rode: bash publish_to_github.command)
# Ele prepara o repositório Git local. O push para o GitHub voce faz no final.

cd "$(dirname "$0")" || exit 1
echo "Pasta: $(pwd)"
echo

# 1) Trava de seguranca: nada de bigfiles, locals.bin nem chaves
echo "==> Conferindo que nenhum arquivo proibido sera commitado..."
BAD=$(find . -type f \( -name '*.000' -o -name 'bigfile-wiiu.*' -o -name 'locals.bin' -o -name '*.env' -o -name '.env' \) -not -path './.git/*')
if [ -n "$BAD" ]; then
  echo "!! ABORTANDO. Encontrei arquivos que NAO devem ir pro GitHub:"
  echo "$BAD"
  exit 1
fi
if grep -rIl --exclude-dir=.git -e 'sk-[A-Za-z0-9]' . 2>/dev/null | grep -q .; then
  echo "!! ABORTANDO. Encontrei algo parecido com uma chave de API (sk-...). Revise antes de subir."
  grep -rIl --exclude-dir=.git -e 'sk-[A-Za-z0-9]' . 2>/dev/null
  exit 1
fi
echo "    OK, nada proibido."
echo

# 2) Inicializa o repositorio e faz o primeiro commit
echo "==> Inicializando Git e fazendo o commit..."
git init -q
git add .
git commit -q -m "DXHR Director's Cut PT-BR translation for Wii U" || {
  echo "Nada para commitar (ja estava commitado?)."
}
git branch -M main
echo "    Commit feito."
echo
git --no-pager log --oneline -1
echo

# 3) Proximos passos (voce faz na sua conta)
cat <<'EOF'

==========================================================
PROXIMO PASSO — subir pro SEU GitHub:

1) Crie um repositorio VAZIO em https://github.com/new
   (sem README, sem .gitignore, sem licenca)
   Sugestao de nome: dxhr-ptbr-wiiu

2) Copie a URL dele e rode aqui (troque SEU_USUARIO e o nome se mudou):

   git remote add origin https://github.com/SEU_USUARIO/dxhr-ptbr-wiiu.git
   git push -u origin main

3) O GitHub vai pedir seu usuario e um TOKEN (nao a senha).
   Gere o token em: https://github.com/settings/tokens
   (classic, com escopo "repo"). Cole o token no lugar da senha.
==========================================================
EOF
echo
echo "Pressione ENTER para fechar."
read _
