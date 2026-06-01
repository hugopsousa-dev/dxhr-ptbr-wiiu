#!/usr/bin/env python3
"""
Extrai os bytes brutos do locals.bin do Wii U pra inspecionar endianness e formato.
"""
import sys
import struct
from pathlib import Path
from pyDXHR.Bigfile import Bigfile

if len(sys.argv) < 2:
    sys.exit("Uso: python inspect_locals.py /caminho/do/dump/ [locale_hex]")

dump_dir = Path(sys.argv[1])
locale = int(sys.argv[2], 0) if len(sys.argv) > 2 else 0xfffffde1

bf = Bigfile()
bf._path = dump_dir
bf.unpack_from = "bigfile-wiiu"
bf.platform = Bigfile.Platform.WII_U
bf.version = Bigfile.Version.DIRECTORS_CUT
bf.open()

print(f"Lendo locals.bin (locale={hex(locale)})…")
data = bf.read(r"local\locals.bin", locale=locale)
print(f"Tamanho dos bytes: {len(data):,}")
print()

print("=== Primeiros 64 bytes em hex ===")
for i in range(0, min(64, len(data)), 16):
    hex_part = " ".join(f"{b:02x}" for b in data[i:i+16])
    ascii_part = "".join(chr(b) if 32 <= b < 127 else "." for b in data[i:i+16])
    print(f"  {i:04x}: {hex_part:<48s}  |{ascii_part}|")
print()

print("=== Interpretação Little-Endian (PC) ===")
unk0_le = struct.unpack("<L", data[0:4])[0]
n_le = struct.unpack("<H", data[4:6])[0]
unk6_le = struct.unpack("<H", data[6:8])[0]
print(f"  unk0       = 0x{unk0_le:08x}")
print(f"  len_strings = {n_le:,}")
print(f"  unk6       = 0x{unk6_le:04x}")
print()

print("=== Interpretação Big-Endian (Wii U / PowerPC) ===")
unk0_be = struct.unpack(">L", data[0:4])[0]
n_be = struct.unpack(">H", data[4:6])[0]
unk6_be = struct.unpack(">H", data[6:8])[0]
print(f"  unk0       = 0x{unk0_be:08x}")
print(f"  len_strings = {n_be:,}")
print(f"  unk6       = 0x{unk6_be:04x}")
print()

# Estimar tamanho razoável: ~50k strings num arquivo de 2.1MB com média de 40 chars
# = ~2MB de strings + offset table (4 bytes por string)
# Se 50k strings: offset table = 200KB, header = 8 bytes, restante ~1.9MB de string data
# Faz sentido pro tamanho de 2.15MB
print("Esperado: ~30k-80k strings (entre 30000 e 80000)")
print()

# Tentar achar uma string ASCII conhecida pra confirmar
print("=== Procurando 'Adam Jensen' nos bytes (deve aparecer várias vezes) ===")
needle = b"Adam Jensen"
positions = []
start = 0
while True:
    pos = data.find(needle, start)
    if pos < 0:
        break
    positions.append(pos)
    start = pos + 1
print(f"  Encontrado em {len(positions)} posições: {positions[:5]}{'...' if len(positions) > 5 else ''}")
if positions:
    pos = positions[0]
    # Mostrar contexto
    ctx_start = max(0, pos - 16)
    ctx_end = min(len(data), pos + 32)
    print(f"  Primeira ocorrência em offset {pos} (0x{pos:x})")
    print(f"  Contexto: {data[ctx_start:ctx_end]}")

# Procurar Sarif também
print()
print("=== Procurando 'Sarif' ===")
needle = b"Sarif"
positions = []
start = 0
while True:
    pos = data.find(needle, start)
    if pos < 0:
        break
    positions.append(pos)
    start = pos + 1
print(f"  Encontrado em {len(positions)} posições")
