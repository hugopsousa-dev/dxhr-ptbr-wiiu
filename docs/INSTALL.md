# Install / Instalação

> ⚠️ You need your **own legal dump** of the game. No game files are distributed in this repository.
> ⚠️ Você precisa do **seu próprio dump legal** do jogo. Nenhum arquivo do jogo é distribuído neste repositório.

---

## 🇬🇧 English

### A. Quick install (you already have the two patched files)

1. Wii U running **Aroma** with the **SDCafiine** plugin enabled.
2. On the Wii U SD card, create/use the folder:
   ```
   sd:/wiiu/sdcafiine/000500001012BA00/PTBR/content/
   ```
3. Copy both patched files into it:
   - `bigfile-wiiu.000`
   - `bigfile-wiiu.024`
4. Safely eject, boot the game, and select the **PTBR** package in the SDCafiine menu.

### B. Build from source

**Requirements:** a PC with Python 3.11, the game dumped (e.g. with Dumpling) into a folder containing `bigfile-wiiu.000 … .024`.

1. Set up `pyDXHR`:
   ```bash
   bash tools/setup_pydxhr.sh
   ```
2. (Optional) Re-extract strings and translate. Translation uses an OpenAI model:
   ```bash
   export OPENAI_API_KEY="sk-..."          # never commit this key
   python tools/translate_openai.py strings_raw.json strings_pt.json
   ```
   Or just use the included `data/strings_pt.json`.
3. Build the translated `locals.bin` and the relocated bigfile parts:
   ```bash
   bash tools/build_wiiu_bigfile_sdcafiine.sh
   ```
   - **Phase 1** (dump SD plugged): generates `bigfile-wiiu.000` and `.024`.
   - **Phase 2** (Wii U SD plugged): copies them to the SDCafiine folder.

> The scripts contain absolute paths from the original author's machine — edit the `PROJ` / path variables at the top of each script to match your setup.

### Incremental fixes (no dump needed)

If you only change a few strings after the files exist, you can re-patch in place:
re-apply the changes to `locals.bin` with `tools/wiiu_locals.py`, truncate `.024`
back to the known append offset, rewrite it plus padding, and patch the 16-byte
header entry in `.000`. See `docs/TECNICO.md` §6.3.

---

## 🇧🇷 Português

### A. Instalação rápida (você já tem os dois arquivos modificados)

1. Wii U com **Aroma** e o plugin **SDCafiine** ativado.
2. No cartão SD do Wii U, crie/use a pasta:
   ```
   sd:/wiiu/sdcafiine/000500001012BA00/PTBR/content/
   ```
3. Copie os dois arquivos modificados pra dentro dela:
   - `bigfile-wiiu.000`
   - `bigfile-wiiu.024`
4. Ejete com segurança, inicie o jogo e selecione o pacote **PTBR** no menu do SDCafiine.

### B. Gerar a partir do código

**Requisitos:** um PC com Python 3.11 e o jogo dumpado (ex.: com Dumpling) numa pasta com `bigfile-wiiu.000 … .024`.

1. Instale o `pyDXHR`:
   ```bash
   bash tools/setup_pydxhr.sh
   ```
2. (Opcional) Re-extrair e traduzir. A tradução usa um modelo da OpenAI:
   ```bash
   export OPENAI_API_KEY="sk-..."          # nunca suba essa chave
   python tools/translate_openai.py strings_raw.json strings_pt.json
   ```
   Ou use direto o `data/strings_pt.json` incluído.
3. Gere o `locals.bin` traduzido e as partes relocadas:
   ```bash
   bash tools/build_wiiu_bigfile_sdcafiine.sh
   ```
   - **Fase 1** (SD do dump plugado): gera `bigfile-wiiu.000` e `.024`.
   - **Fase 2** (SD do Wii U plugado): copia pra pasta do SDCafiine.

> Os scripts têm caminhos absolutos da máquina do autor original — edite as variáveis `PROJ` / de caminho no topo de cada script pra combinar com o seu ambiente.

### Correções incrementais (sem precisar do dump)

Se você mudar só algumas strings depois dos arquivos prontos, dá pra repatchar no lugar:
reaplique as mudanças no `locals.bin` com `tools/wiiu_locals.py`, trunque o `.024`
de volta ao offset de append conhecido, regrave-o com padding, e corrija os 16 bytes
da entrada no header `.000`. Veja `docs/TECNICO.md` §6.3.
