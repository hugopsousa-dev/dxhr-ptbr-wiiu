# Tradução PT-BR — Deus Ex: Human Revolution Director's Cut (Wii U)

**Documentação técnica e de engenharia reversa**

Primeira tradução conhecida do *Deus Ex: Human Revolution — Director's Cut* para Wii U rodando em hardware real, via Aroma/SDCafiine, com o texto carregado de dentro do próprio bigfile do jogo.

- **Plataforma:** Nintendo Wii U (PowerPC, big-endian)
- **Jogo:** Deus Ex: Human Revolution — Director's Cut (NTSC-U / USA)
- **Title ID:** `000500001012BA00`
- **Product code:** WUP-P-ADXE
- **Método de carga:** SDCafiine (redirecionamento de conteúdo por SD), ambiente Aroma
- **Idioma do mod:** Português do Brasil (PT-BR), sobre o slot de texto Inglês
- **Duração do projeto:** ~2 semanas

---

## 1. Resumo do problema

No PC, o *DXHR Director's Cut* é fácil de modificar: existe o **ModHook do Gibbed (DXHRDC)**, uma DLL que intercepta a leitura do jogo e permite carregar arquivos soltos e "patch bigfiles". Quase todos os tutoriais de tradução assumem isso.

**No Wii U esse caminho não existe.** Não há ModHook; o engine só lê texto de dentro do bigfile empacotado. Colocar um `local/locals.bin` solto na pasta do SDCafiine **não funciona** — o jogo ignora. A única forma de traduzir no console é **substituir os próprios arquivos de bigfile que o jogo lê**.

O bigfile do Wii U tem ~12 GB divididos em 25 partes (`bigfile-wiiu.000` … `bigfile-wiiu.024`). Reescrever os 12 GB inteiros é inviável (lento e o SD não comporta com folga). A solução foi um **truque de relocação**: inserir o `locals.bin` traduzido num espaço livre no fim da última parte e repointar a entrada no header — assim só 2 arquivos precisam ser redirecionados pelo SDCafiine (~613 MB no total) em vez de 12 GB.

---

## 2. Identificação do jogo (Title ID)

O passo que mais atrasou no começo foi usar o Title ID errado. Os IDs `00050000101C9400` (USA) e `00050000101C9500` (EUR) são do **Zelda: Breath of the Wild**, não do DXHR — colocar a tradução nessas pastas fazia o menu do SDCafiine não aparecer (ou aparecer no jogo errado).

O Title ID correto foi extraído do `meta.xml` do próprio dump:

```
/Volumes/UNTITLED/.../Deus Ex Human Rev DC/meta/meta.xml
  -> title_id     = 000500001012BA00
  -> product_code = WUP-P-ADXE   (E = NTSC-U)
```

A pasta correta do SDCafiine é:

```
sd:/wiiu/sdcafiine/000500001012BA00/PTBR/content/
```

O segmento `PTBR` é só o nome do "pacote" (pack) e aparece como opção no menu do SDCafiine. O que está dentro de `content/` espelha `/vol/content` do jogo.

---

## 3. Formato do bigfile do Wii U

### 3.1 Estrutura geral

- O bigfile é dividido em **partes de tamanho fixo**. Cada parte tem exatamente **`data_alignment` bytes** = `0x1F400000` = **524.288.000 bytes** (500 MiB).
- Os offsets dos arquivos são contados em **blocos de `0x800` (2048) bytes**, não em bytes.
- Conversão de um offset (em blocos) para localização física:

```
byte_global   = offset * 0x800
índice_parte  = byte_global // data_alignment      # qual bigfile-wiiu.NNN
offset_parte  = byte_global %  data_alignment       # posição dentro daquela parte
```

- O engine lê **`uncompressed_size` bytes crus** a partir de `offset_parte`. Para o `locals.bin`, **não há descompressão** (ver 3.4).

### 3.2 Header (`bigfile-wiiu.000`) — layout byte-a-byte

Tudo no Wii U é **big-endian** (PowerPC). O parser de referência é o `bigfile_header.py` (Kaitai) do pyDXHR.

| Offset | Tamanho | Campo | Observação |
|-------:|--------:|-------|------------|
| `0x00` | 4 | `alignment` (bruto) | Lido como `u4le` pelo Kaitai p/ decidir endianness (ver nota) |
| `0x04` | 8 | `platform` | ASCII, ex.: `"wiiu-w\0\0"` |
| `0x0C` | 56 | `zeroes` | preenchimento |
| `0x44` | 4 | `len_files` | **u4 big-endian** — nº de entradas |
| `0x48` | 4×`len_files` | `hash_table` | um `u4 BE` por arquivo (CRC do nome) |
| `0x48 + 4·len_files` | 16×`len_files` | `file_headers` | tabela de entradas (ver 3.3) |

**Nota sobre endianness (detalhe importante):** o Kaitai lê os 4 primeiros bytes como `u4le` e usa a regra `is_le = NOT (valor_lido < 65535)`. No Wii U o alignment está gravado em big-endian como `1F 40 00 00`; lido como little-endian dá `0x0000401F = 16415`, que é `< 65535`, então o parser entra em **modo big-endian** para todo o resto. O valor real do alignment é `int.from_bytes(bytes[0:4], "big") = 0x1F400000 = 524.288.000`.

Posição em bytes de uma entrada `idx` na tabela:

```
entry_table_start = 72 + 4 * len_files          # 0x48 + hash_table
entry_pos(idx)    = entry_table_start + 16 * idx
```

### 3.3 Entrada de arquivo (`file_header`) — 16 bytes, big-endian

| Offset rel. | Tipo | Campo |
|-----------:|------|-------|
| `+0` | `u4 BE` | `len_uncompressed` |
| `+4` | `u4 BE` | `offset` (em blocos de `0x800`) |
| `+8` | `u4 BE` | `locale` |
| `+12`| `u4 BE` | `len_compressed` |

Empacotamento em Python: `struct.pack(">4L", unc, offset, locale, cmp)`.

### 3.4 Convenção de compressão do `locals.bin`

O `locals.bin` é guardado **sem compressão**. A marcação disso é:

- `len_compressed == 0`  → guardado cru (convenção do DXHR Wii U) — **este é o caso**; ou
- `len_compressed == len_uncompressed` → também cru.

Qualquer outro valor de `len_compressed` indica compressão real (não é o caso aqui, e o build aborta por segurança se encontrar). Ao reescrever o header, **preserva-se o `0`**.

### 3.5 Hash de nome — CRC-32/BZIP2

A `hash_table` indexa os arquivos por um hash do caminho. O algoritmo é **CRC-32/BZIP2**:

- polinômio `0x04C11DB7`, init `0xFFFFFFFF`, **sem** reflexão de entrada/saída (`refin=false`, `refout=false`), `xorout=0xFFFFFFFF`.

O nome usado no hash inclui a chave de plataforma, com barra invertida do estilo Windows:

```
hash = crc32bzip2( "wiiu-w" + "\\local\\locals.bin" )
```

(no pyDXHR: `crc32bzip2(key + r"\local\locals.bin")`).

### 3.6 Locale

O texto ativo do jogo está sob o locale **`0xFFFFFDE1`** (inglês, Director's Cut Wii U). É esse slot que a tradução sobrescreve. `0xFFFFFFFF` = "default".

---

## 4. Formato do `locals.bin` (tabela de strings)

O `locals.bin` do Wii U difere do PC:

```
PC:    4B unk0 + 2B count + 2B unk6 + offsets(u4 LE) + strings null-terminated
Wii U: 4B unk0 + 4B count(BE)       + offsets(u4 BE) + strings null-terminated
```

Layout Wii U:

| Offset | Tamanho | Campo |
|-------:|--------:|-------|
| `0x00` | 4 | `unk0` (preservar) |
| `0x04` | 4 | `count` (`u4 BE`) — nº de strings |
| `0x08` | 4×`count` | tabela de offsets (`u4 BE`), relativos ao início do arquivo |
| … | — | blob de strings, cada uma terminada em `\x00` (UTF-8) |

Offset `0` na tabela = string vazia. Na reconstrução, o blob de texto começa em `8 + 4*count` e os offsets são recalculados conforme as strings (que podem mudar de tamanho na tradução). O parser/reconstrutor está em `tools/wiiu_locals.py` (classe `WiiULocals`, métodos `.modify(idx, str)` e `.rebuild()`), e o roundtrip `rebuild()==original` foi validado.

Neste projeto: `count = 18069` strings.

---

## 5. O truque de relocação (a solução real do Wii U)

Em vez de reescrever 12 GB:

1. **Acrescentar** o `locals.bin` traduzido num espaço livre **no fim da última parte** (`bigfile-wiiu.024`), alinhado a `0x800`.
2. **Repointar** a entrada do `locals.bin` no header (`.000`): novo `offset` (em blocos), novo `len_uncompressed`, `len_compressed = 0`.
3. O **SDCafiine redireciona só 2 arquivos**: `bigfile-wiiu.000` (header) e `bigfile-wiiu.024` (última parte com o texto novo). As outras 23 partes continuam sendo lidas do disco/dump original.

### 5.1 Geometria (números reais deste projeto)

```
data_alignment   = 524.288.000            (0x1F400000, 500 MiB por parte)
última parte     = bigfile-wiiu.024  (índice 24)
ponto de append  = 88.141.824 bytes dentro da .024  (alinhado a 0x800)
offset global    = 24 * 524.288.000 + 88.141.824 = 12.671.053.824 bytes
offset (blocos)  = 12.671.053.824 / 0x800 = 6.187.038
entrada no .000  = idx 46886 de 62856  ->  byte 0xF48C8
```

Verificações de consistência aplicadas no build:
- `offset_global % 0x800 == 0` (alinhamento);
- `(offset_blocos * 0x800) // data_alignment == 24` (reabre na parte certa);
- `ponto_append + tamanho_locals <= data_alignment` (cabe na parte; senão, abortar e criar parte nova).

### 5.2 Tamanhos finais entregues ao SD

```
bigfile-wiiu.000 = 521.994.240 bytes  (~522 MB)  — header repointado
bigfile-wiiu.024 =  90.507.264 bytes  (~90 MB)   — última parte + locals.bin traduzido
locals.bin (PTBR)=   2.364.328 bytes  (18069 strings)
```

---

## 6. Pipeline de build

### 6.1 Scripts

- `tools/wiiu_locals.py` — parser/reconstrutor do `locals.bin` (BE, 4-byte count).
- `tools/build_wiiu_bigfile_patch.py` — núcleo do método de relocação. Abre o bigfile via pyDXHR, localiza a entrada do `locals.bin`, acha o byte exato dela no `.000`, acrescenta o `locals.bin` traduzido no fim da `.024` e repointa o header. Gera os 2 arquivos prontos pro SD.
- `tools/build_wiiu_bigfile_sdcafiine.sh` — wrapper em 2 fases:
  - **FASE 1 (SD UNTITLED / dump):** gera os 2 arquivos a partir do dump.
  - **FASE 2 (SD NO NAME / cartão do Wii U):** copia os 2 arquivos pra `wiiu/sdcafiine/000500001012BA00/PTBR/content/`.
- `tools/build_sdcafiine_mod.sh` — gera o `locals.bin` traduzido (a partir do dump + `strings_pt.json`).

### 6.2 Fluxo completo (do zero)

```
1.  Dumpar o jogo (Dumpling) -> bigfile-wiiu.000 … .024  (no SD UNTITLED)
2.  Extrair/identificar strings -> output/strings_raw.json
3.  Traduzir EN->PT-BR          -> output/strings_pt.json (18069 strings)
4.  Reconstruir o locals.bin    -> output/mod_ptbr/content/local/locals.bin
5.  Relocação + repoint do header (build_wiiu_bigfile_patch.py)
        -> output/bigfile_sdcafiine/bigfile-wiiu.000 e .024
6.  Copiar os 2 arquivos pro SD NO NAME (FASE 2)
7.  Testar no Wii U: selecionar o pack "PTBR" no menu do SDCafiine
```

### 6.3 Atualização incremental (sem precisar do dump)

Para corrigir strings depois de já ter os arquivos gerados, **não é preciso o dump**. Como o `.000` em `output/bigfile_sdcafiine/` é cópia íntegra do header e o `.024` já contém o `locals.bin` no ponto de append conhecido, dá pra:

1. Reaplicar as correções no `locals.bin` traduzido (`wiiu_locals.WiiULocals`, `.modify` + `.rebuild`).
2. **Truncar** o `.024` de volta ao ponto de append (`88.141.824`) e regravar o novo `locals.bin` + padding a `0x800`.
3. Reescrever só os 16 bytes da entrada no `.000` (offset igual, novo tamanho, `cmp=0`).
4. Copiar os 2 arquivos pro SD.

Foi assim que a correção das strings ruins foi feita sem trocar de cartão SD.

---

## 7. Correção de artefatos da tradução automática

O modelo de tradução automática (LLM — `gpt-4o-mini` via API OpenAI, ver `tools/translate_openai.py`) ocasionalmente respondeu com a frase genérica de recusa **"Desculpe, não posso ajudar com isso."** no lugar da tradução real — tipicamente em entradas curtas/ambíguas (nomes isolados, logins, palavrões, texto cifrado). Foram **360 entradas** afetadas:

- **~260** eram nomes próprios (Adam Jensen, David Sarif…), e-mails, *usernames* (logins) e até um **texto cifrado que é um quebra-cabeça do próprio jogo** (a carta do "Kline") — todos restaurados ao texto original em inglês (não devem ser traduzidos).
- **~100** eram diálogos curtos e rótulos de menu — traduzidos corretamente. Exemplos:

| Original | Antes (errado) | Depois |
|----------|----------------|--------|
| `Talk` | Desculpe, não posso ajudar com isso. | Conversar |
| `Continue` | Desculpe, não posso ajudar com isso. | Continuar |
| `Resume` | Desculpe, não posso ajudar com isso. | Retomar |
| `Convince` | … | Convencer |
| `Scroll` | … | Rolar |
| `Reset` | … | Redefinir |

**Lição:** ao usar tradução por LLM em lote, filtrar a saída por frases de recusa conhecidas ("Desculpe, não posso ajudar…", "I can't help with…", "I'm sorry, but…") **antes** de empacotar. Nomes, e-mails, logins e textos cifrados devem ser excluídos da tradução de antemão (passar adiante o original) — eles disparam recusas e nunca deveriam ir pro modelo.

---

## 8. Ambiente e dependências

- **Console:** Wii U com Aroma + SDCafiine (testado).
- **PC (build):** Python 3.11 com `pyDXHR` instalado (venv). Dependências relevantes: `numpy`, `kaitaistruct`.
- **Dump:** feito com Dumpling, no cartão "UNTITLED".
- **Cartão do Wii U:** "NO NAME" (FAT32), com a estrutura `wiiu/sdcafiine/…`.

---

## 9. Avisos e limitações

- Tradução **não-oficial** feita por fãs; não redistribuir os arquivos de bigfile (são conteúdo protegido do jogo). Distribuir, no máximo, o **patch/diferença** ou os scripts + `strings_pt.json`.
- Específico para a build **NTSC-U** (`000500001012BA00`). Outras regiões teriam Title ID e possivelmente offsets diferentes.
- Sempre manter backup dos arquivos originais do dump.
- Revisão futura recomendada: passar o texto inteiro procurando outros artefatos da IA, estouros de tamanho e problemas de acentuação/encoding.

---

*Documento gerado como registro técnico e reprodutível do projeto. Data de referência: 31/05/2026.*
