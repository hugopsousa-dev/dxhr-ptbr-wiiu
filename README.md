# Deus Ex: Human Revolution — Director's Cut · PT-BR Translation (Wii U)

> 🇧🇷 First known Brazilian-Portuguese translation of *Deus Ex: Human Revolution — Director's Cut* running on **real Wii U hardware** (Aroma + SDCafiine), with text loaded from inside the game's own bigfile.
>
> 🇧🇷 Primeira tradução conhecida de *Deus Ex: Human Revolution — Director's Cut* para PT-BR rodando em **Wii U de verdade**, com o texto carregado de dentro do próprio bigfile do jogo.

| | |
|---|---|
| **Platform** | Nintendo Wii U (Aroma + SDCafiine) |
| **Game** | Deus Ex: Human Revolution — Director's Cut |
| **Region** | NTSC-U / USA |
| **Title ID** | `000500001012BA00` (WUP-P-ADXE) |
| **Language** | English → Brazilian Portuguese (PT-BR) |
| **Status** | ✅ Running on console · 🔧 polishing pass in progress |

---

## 🇬🇧 English

### What this is

A fan translation project that achieves something most tutorials say is "PC-only": translating DXHR Director's Cut on a **real Wii U**. The common PC route relies on **Gibbed's DXHRDC ModHook** (a Windows DLL) to load loose files. That hook **does not exist on Wii U** — the engine only reads text from inside the packed bigfile, and SDCafiine ignores loose `local/locals.bin` files.

The solution: **relocate the translated `locals.bin` into free space at the end of the last bigfile part and repoint its header entry**, so SDCafiine only needs to redirect **2 files** (`bigfile-wiiu.000` + `bigfile-wiiu.024`, ~613 MB) instead of repacking the full ~12 GB archive.

Full byte-level reverse-engineering write-up: **[docs/TECNICO.md](docs/TECNICO.md)** (PT-BR).

### Highlights of the method

- Correct Title ID `000500001012BA00` (extracted from the dump's `meta.xml`).
- Bigfile format is **big-endian** (PowerPC); offsets counted in `0x800` blocks; each part is exactly 500 MiB.
- `locals.bin` is stored **uncompressed** (`len_compressed = 0`).
- Filename hashing is **CRC-32/BZIP2** over `"wiiu-w\local\locals.bin"`.
- Wii U `locals.bin` has its own layout (4-byte big-endian count, BE offset table).
- Relocation trick keeps the SD payload small and the other 23 parts untouched.

### What's in this repo

```
README.md            ← you are here
docs/
  TECNICO.md         ← full technical / reverse-engineering doc (PT-BR)
  INSTALL.md         ← install guide (bilingual)
tools/               ← the build pipeline (Python + shell)
data/
  strings_pt.json    ← the PT-BR translation table (18,069 strings)
```

> ⚠️ **No game files are distributed here.** The bigfiles are copyrighted content of the game. This repo ships only the scripts and the translation table — you generate the patched files from **your own legal dump**.

### Quick install (you already have a dump)

1. Wii U with **Aroma + SDCafiine**.
2. Copy the two generated files to:
   `sd:/wiiu/sdcafiine/000500001012BA00/PTBR/content/`
   (`bigfile-wiiu.000` and `bigfile-wiiu.024`)
3. Launch the game and pick the **PTBR** package in the SDCafiine menu.

Build-from-source steps are in **[docs/INSTALL.md](docs/INSTALL.md)**.

### Credits

Fan translation project (~2 weeks of work). *Add your name(s)/handle(s) here.*

---

## 🇧🇷 Português

### O que é isto

Um projeto de tradução amador que faz algo que a maioria dos tutoriais diz ser "só no PC": traduzir o DXHR Director's Cut num **Wii U de verdade**. O caminho comum no PC depende do **ModHook do Gibbed (DXHRDC)**, uma DLL de Windows que carrega arquivos soltos. Esse hook **não existe no Wii U** — o engine só lê texto de dentro do bigfile empacotado, e o SDCafiine ignora arquivos `local/locals.bin` soltos.

A solução: **relocar o `locals.bin` traduzido num espaço livre no fim da última parte do bigfile e repointar a entrada no header**, de forma que o SDCafiine só precise redirecionar **2 arquivos** (`bigfile-wiiu.000` + `bigfile-wiiu.024`, ~613 MB) em vez de reempacotar os ~12 GB inteiros.

Documento completo com a engenharia reversa byte-a-byte: **[docs/TECNICO.md](docs/TECNICO.md)**.

### Destaques do método

- Title ID correto `000500001012BA00` (extraído do `meta.xml` do dump).
- O bigfile é **big-endian** (PowerPC); offsets contados em blocos de `0x800`; cada parte tem exatos 500 MiB.
- O `locals.bin` é guardado **sem compressão** (`len_compressed = 0`).
- O hash de nome é **CRC-32/BZIP2** sobre `"wiiu-w\local\locals.bin"`.
- O `locals.bin` do Wii U tem layout próprio (count de 4 bytes BE, tabela de offsets BE).
- O truque de relocação mantém o payload do SD pequeno e as outras 23 partes intactas.

### O que tem neste repositório

```
README.md            ← você está aqui
docs/
  TECNICO.md         ← documento técnico / engenharia reversa completo
  INSTALL.md         ← guia de instalação
tools/               ← o pipeline de build (Python + shell)
data/
  strings_pt.json    ← a tabela de tradução PT-BR (18.069 strings)
```

> ⚠️ **Nenhum arquivo do jogo é distribuído aqui.** Os bigfiles são conteúdo protegido do jogo. Este repositório traz só os scripts e a tabela de tradução — você gera os arquivos modificados a partir do **seu próprio dump legal**.

### Instalação rápida (você já tem um dump)

1. Wii U com **Aroma + SDCafiine**.
2. Copie os dois arquivos gerados para:
   `sd:/wiiu/sdcafiine/000500001012BA00/PTBR/content/`
   (`bigfile-wiiu.000` e `bigfile-wiiu.024`)
3. Inicie o jogo e selecione o pacote **PTBR** no menu do SDCafiine.

Passos de build estão em **[docs/INSTALL.md](docs/INSTALL.md)**.

### Créditos

Projeto de tradução amador (~2 semanas de trabalho). *Adicione aqui seu(s) nome(s)/handle(s).*

---

## License / Licença

The **code** (scripts in `tools/`) is released under the MIT License — see [LICENSE](LICENSE).
The **translation table** (`data/strings_pt.json`) is a fan-made derivative work provided for non-commercial use; it does not include any original game assets. *Deus Ex: Human Revolution* is © Square Enix / Eidos-Montréal. This project is not affiliated with or endorsed by them.
