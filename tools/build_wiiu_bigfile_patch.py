#!/usr/bin/env python3
# =============================================================================
# build_wiiu_bigfile_patch.py
# -----------------------------------------------------------------------------
# Gera arquivos de bigfile MODIFICADOS pro DXHR (Wii U) que funcionam via
# SDCafiine — SEM precisar do modhook do PC.
#
# Por quê: no Wii U o jogo só lê o texto de dentro do bigfile-wiiu.* . Ele NÃO
# carrega arquivos soltos nem "patch bigfiles" (isso é coisa do modhook do
# Gibbed, que só existe no PC). A única forma de traduzir via SDCafiine é
# substituir os próprios arquivos de bigfile que o jogo lê.
#
# Como: o locals.bin é guardado SEM compressão no bigfile. O engine acha ele
# pela tabela de offsets no header (bigfile-wiiu.000). Em vez de reescrever os
# 12 GB inteiros, a gente:
#   1. Acrescenta o locals.bin TRADUZIDO no fim da última parte (sobra espaço).
#   2. Repoint a entrada no header (.000) pro novo offset/tamanho.
#   3. SDCafiine redireciona só 2 arquivos: .000 (header) e a última parte.
#
# Uso (com o SD UNTITLED / dump plugado):
#   python build_wiiu_bigfile_patch.py <dump_dir> <locals_traduzido.bin> <out_dir>
# =============================================================================
import sys, os, struct, shutil
from pathlib import Path

ALIGN_BLOCK = 0x800  # 2048 — unidade dos offsets
LOCALE = 0xfffffde1  # English DC Wii U

def main():
    if len(sys.argv) < 4:
        sys.exit("Uso: build_wiiu_bigfile_patch.py <dump_dir> <locals_traduzido.bin> <out_dir> [tools_dir]")
    dump_dir = Path(sys.argv[1])
    new_locals_path = Path(sys.argv[2])
    out_dir = Path(sys.argv[3])
    tools_dir = sys.argv[4] if len(sys.argv) > 4 else str(Path(__file__).parent)
    sys.path.insert(0, tools_dir)

    from pyDXHR.Bigfile import Bigfile
    from pyDXHR.Bigfile.read_header import BigfileHeader
    from pyDXHR.Bigfile.filelist import crc32bzip2

    # --- abre o bigfile original -------------------------------------------
    bf = Bigfile()
    bf._path = dump_dir
    bf.unpack_from = "bigfile-wiiu"
    bf.platform = Bigfile.Platform.WII_U
    bf.version = Bigfile.Version.DIRECTORS_CUT
    bf.open()

    alignment = bf.alignment            # 0x1F400000 = 524288000 (500 MiB/parte)
    key = bf.key                        # ex.: "wiiu-w"
    print(f"[patch] platform_key={key!r}  alignment={alignment} (0x{alignment:X})")

    entry = bf.get_entry_from_filename(r"local\locals.bin", locale=LOCALE)
    print(f"[patch] locals.bin original: offset={entry.offset} blocos  "
          f"uncompressed={entry.uncompressed_size}  compressed={entry.compressed_size}")

    # Sanidade: precisa estar SEM compressão.
    #   compressed_size == 0  -> guardado cru (convenção do DXHR Wii U)  [OK]
    #   compressed_size == uncompressed_size -> também cru               [OK]
    #   qualquer outro valor  -> realmente comprimido                    [aborta]
    if entry.compressed_size not in (0, entry.uncompressed_size):
        print(f"⚠️  ATENÇÃO: compressed_size={entry.compressed_size} indica COMPRESSÃO. "
              "O plano assume SEM compressão. Abortando por segurança.")
        sys.exit(1)
    keep_compressed_zero = (entry.compressed_size == 0)

    # --- lê o header bruto pra achar o índice exato da entrada -------------
    p000 = dump_dir / "bigfile-wiiu.000"
    bh = BigfileHeader.from_file(p000)
    len_files = bh.bigfile_data.len_files
    hashes = bh.file_hashes
    headers = bh.file_headers

    target_hash = crc32bzip2(key + r"\local\locals.bin")
    idx = None
    for i in range(len_files):
        if hashes[i] == target_hash and headers[i].locale == LOCALE:
            idx = i
            break
    if idx is None:
        sys.exit("ERRO: não achei a entrada do locals.bin no header.")

    # posição em bytes da entrada no .000 (layout Kaitai):
    #   4 (alignment) + 8 (platform) + 56 (zeros) + 4 (len_files) = 72
    #   + 4*len_files (hash table) + 16*idx
    entry_table_start = 72 + 4 * len_files
    entry_pos = entry_table_start + 16 * idx
    print(f"[patch] entrada #{idx} de {len_files}  ->  byte 0x{entry_pos:X} no .000")

    # confere que lemos certo (offset/locale batem)
    be = ">"  # wiiu é big-endian
    with open(p000, "rb") as f:
        f.seek(entry_pos)
        rec = f.read(16)
    old_unc, old_off, old_loc, old_cmp = struct.unpack(f"{be}4L", rec)
    assert old_off == entry.offset and old_loc == LOCALE, \
        f"header desalinhado: {old_off} vs {entry.offset}, loc {old_loc:#x}"
    print(f"[patch] confirmado no .000: off={old_off} unc={old_unc} cmp={old_cmp} loc={old_loc:#x}")

    # --- novo locals.bin traduzido ----------------------------------------
    new_data = new_locals_path.read_bytes()
    new_len = len(new_data)
    print(f"[patch] locals.bin traduzido: {new_len} bytes "
          f"(orig {entry.uncompressed_size}, +{new_len-entry.uncompressed_size})")

    # --- descobre quantas partes e o tamanho da última --------------------
    parts = sorted(dump_dir.glob("bigfile-wiiu.[0-9][0-9][0-9]"))
    last_idx = max(int(p.suffix[1:]) for p in parts)
    last_part = dump_dir / f"bigfile-wiiu.{last_idx:03d}"
    last_size = last_part.stat().st_size
    print(f"[patch] {len(parts)} partes; última = .{last_idx:03d} ({last_size} bytes)")

    # nova posição = fim da última parte, alinhado a 0x800
    new_in_part = (last_size + ALIGN_BLOCK - 1) // ALIGN_BLOCK * ALIGN_BLOCK
    if new_in_part + new_len > alignment:
        sys.exit(f"ERRO: não cabe na última parte ({new_in_part}+{new_len} > {alignment}). "
                 f"Precisaria criar uma parte nova — me avise.")
    new_global_byte = last_idx * alignment + new_in_part
    assert new_global_byte % ALIGN_BLOCK == 0
    new_offset_blocks = new_global_byte // ALIGN_BLOCK
    # checagem: o engine reabriria esse offset na parte certa?
    assert (new_offset_blocks * ALIGN_BLOCK) // alignment == last_idx
    print(f"[patch] novo offset: parte .{last_idx:03d} @ {new_in_part} bytes  "
          f"(bloco global {new_offset_blocks})")

    # --- escreve os arquivos de saída -------------------------------------
    out_dir.mkdir(parents=True, exist_ok=True)
    out_000 = out_dir / "bigfile-wiiu.000"
    out_last = out_dir / f"bigfile-wiiu.{last_idx:03d}"

    print(f"[patch] copiando .000 ({p000.stat().st_size/1e6:.0f} MB)…")
    shutil.copyfile(p000, out_000)
    print(f"[patch] copiando .{last_idx:03d} ({last_size/1e6:.0f} MB)…")
    shutil.copyfile(last_part, out_last)

    # acrescenta o locals.bin traduzido no fim da última parte (com padding)
    with open(out_last, "r+b") as f:
        f.seek(0, os.SEEK_END)
        cur = f.tell()
        if cur < new_in_part:
            f.write(b"\x00" * (new_in_part - cur))
        f.write(new_data)
        # padding final até múltiplo de 0x800 (organização)
        pad = (ALIGN_BLOCK - (f.tell() % ALIGN_BLOCK)) % ALIGN_BLOCK
        if pad:
            f.write(b"\x00" * pad)

    # patch do header no .000: len_uncompressed, offset, locale, len_compressed
    # preserva a convenção original de "sem compressão" (0 ou == uncompressed)
    new_cmp = 0 if keep_compressed_zero else new_len
    new_rec = struct.pack(f"{be}4L", new_len, new_offset_blocks, LOCALE, new_cmp)
    with open(out_000, "r+b") as f:
        f.seek(entry_pos)
        f.write(new_rec)
    print(f"[patch] header repointado: off={new_offset_blocks} unc={new_len} cmp={new_cmp}")

    print()
    print("===============================================")
    print("✅ Arquivos prontos pra SDCafiine:")
    print(f"   {out_000}")
    print(f"   {out_last}")
    print()
    print("   Copie os DOIS pra (no SD do Wii U):")
    print(f"   wiiu/sdcafiine/000500001012BA00/PTBR/content/")
    print("   (mantendo os nomes bigfile-wiiu.000 e "
          f"bigfile-wiiu.{last_idx:03d})")
    print("===============================================")

if __name__ == "__main__":
    main()
