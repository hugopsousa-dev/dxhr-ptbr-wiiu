#!/usr/bin/env python3
"""
Diagnóstico: descobre onde está locals.bin no bigfile do Wii U e com qual locale.
"""
import sys
from pathlib import Path
from collections import Counter
from pyDXHR.Bigfile import Bigfile

if len(sys.argv) != 2:
    sys.exit("Uso: python find_locals.py /caminho/do/dump/")

dump_dir = Path(sys.argv[1])

bf = Bigfile()
bf._path = dump_dir
bf.unpack_from = "bigfile-wiiu"
bf.platform = Bigfile.Platform.WII_U
bf.version = Bigfile.Version.DIRECTORS_CUT
bf.open()

print(f"=== Bigfile aberto ===")
print(f"Platform key: {bf.key}")
print(f"Endianness: {bf.endian}")
print(f"Total named entries:   {len(bf.named_entries)}")
print(f"Total unknown entries: {len(bf.unknown_entries)}")
print()

# Locales únicos
print("=== Locales únicos no bigfile (top 20) ===")
locale_counter = Counter()
for (h, loc), _ in bf.named_entries.items():
    locale_counter[loc] += 1
for (h, loc), _ in bf.unknown_entries.items():
    locale_counter[loc] += 1
for loc, count in locale_counter.most_common(20):
    print(f"  {hex(loc):>14}  ({count} entries)")
print()

# Procurar locals.bin / locals
print("=== Entries com 'local' no filename ===")
found_locals = []
for (h, loc), entry in bf.named_entries.items():
    if 'local' in entry.filename.lower():
        found_locals.append((entry.filename, loc, entry.uncompressed_size))
for fn, loc, sz in sorted(found_locals):
    print(f"  filename={fn:50s} locale={hex(loc):>14}  size={sz:>10,} bytes")

if not found_locals:
    print("  (nenhum encontrado em named_entries — pode estar em unknown_entries)")
    print()
    print("=== Tentando 'locals.bin' direto com diversos paths ===")
    from pyDXHR.Bigfile.filelist import crc32bzip2
    test_paths = [
        r"wiiu-w\local\locals.bin",
        r"wiiu-w\locals\locals.bin",
        r"wiiu-w\locals.bin",
        r"pc-w\local\locals.bin",
        r"wiiu-w\local\locals_en.bin",
        r"wiiu-w\local\locals_us.bin",
    ]
    for path in test_paths:
        h = crc32bzip2(path)
        # Procurar todos locales pra esse hash
        for loc in locale_counter.keys():
            if (h, loc) in bf.named_entries or (h, loc) in bf.unknown_entries:
                entry = bf.named_entries.get((h, loc)) or bf.unknown_entries[(h, loc)]
                src = "named" if (h, loc) in bf.named_entries else "unknown"
                print(f"  ACHEI: {path}  hash={hex(h)}  locale={hex(loc)}  size={entry.uncompressed_size:,} ({src})")
