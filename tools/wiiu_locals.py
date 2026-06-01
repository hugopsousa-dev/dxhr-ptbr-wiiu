"""
Parser customizado pro locals.bin do DXHR Wii U.

Formato Wii U difere do PC:
  - PC:    4B unk0 + 2B count + 2B unk6 + offsets u4 + strings null-term
  - Wii U: 4B unk0 + 4B count(BE) + offsets u4(BE) + strings null-term

Big-endian em todo lugar (PowerPC).
"""
import struct
from typing import List, Optional, Tuple


class WiiULocals:
    """Lê e escreve locals.bin no formato Wii U (big-endian, 4-byte count)."""

    def __init__(self, data: bytes):
        self.data = data
        self.unk0 = data[0:4]
        self.count = struct.unpack(">I", data[4:8])[0]

        self.offsets: List[int] = []
        for i in range(self.count):
            o = struct.unpack(">I", data[8 + i * 4 : 12 + i * 4])[0]
            self.offsets.append(o)

        self.strings: List[str] = []
        self.byte_strings: List[bytes] = []
        for offset in self.offsets:
            if offset == 0:
                self.strings.append("")
                self.byte_strings.append(b"")
                continue
            end = data.find(b"\x00", offset)
            if end < 0:
                end = len(data)
            raw = data[offset:end]
            self.byte_strings.append(raw)
            try:
                self.strings.append(raw.decode("utf-8"))
            except UnicodeDecodeError:
                self.strings.append(raw.decode("latin-1", errors="replace"))

    def __len__(self):
        return self.count

    def __getitem__(self, idx):
        return self.strings[idx]

    def modify(self, idx: int, new_string: str):
        """Modifica string em índice. Re-encode na hora do rebuild."""
        self.strings[idx] = new_string
        try:
            self.byte_strings[idx] = new_string.encode("utf-8")
        except Exception:
            self.byte_strings[idx] = new_string.encode("latin-1", errors="replace")

    def rebuild(self) -> bytes:
        """Reconstrói locals.bin com strings modificadas (mantendo BE)."""
        # Header: 4B unk0 + 4B count
        out = bytearray()
        out += self.unk0
        out += struct.pack(">I", self.count)

        # Calcula offsets novos
        text_start = 8 + 4 * self.count  # header + offset table
        new_offsets = []
        text_blob = bytearray()
        cursor = text_start
        for raw in self.byte_strings:
            if len(raw) == 0:
                new_offsets.append(0)  # placeholder
            else:
                new_offsets.append(cursor)
                text_blob += raw + b"\x00"
                cursor += len(raw) + 1

        # Escreve offset table (BE)
        for o in new_offsets:
            out += struct.pack(">I", o)

        # Escreve strings
        out += text_blob
        return bytes(out)


if __name__ == "__main__":
    # Teste rápido: usa pyDXHR pra ler bytes do bigfile, parsa com WiiULocals
    import sys
    from pathlib import Path
    from pyDXHR.Bigfile import Bigfile

    if len(sys.argv) < 2:
        sys.exit("Uso: python wiiu_locals.py /caminho/do/dump/ [locale_hex]")

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
    print(f"Tamanho: {len(data):,} bytes")

    locals_obj = WiiULocals(data)
    print(f"Strings: {len(locals_obj):,}")
    print()

    print("=== Primeiras 30 strings não-vazias ===")
    shown = 0
    for i, s in enumerate(locals_obj.strings):
        if s.strip():
            print(f"  [{i:5d}] {s[:80]}")
            shown += 1
            if shown >= 30:
                break

    print()
    print("=== Buscas conhecidas ===")
    for needle in ["Adam Jensen", "Sarif Industries", "Picus", "Augmentation",
                   "Hack", "Welcome", "Press"]:
        hits = [i for i, s in enumerate(locals_obj.strings) if needle in s]
        print(f"  '{needle}': {len(hits)} matches  (ex: {hits[:3]})")

    print()
    print("=== Teste de roundtrip (rebuild == original?) ===")
    rebuilt = locals_obj.rebuild()
    if rebuilt == data:
        print("  ✅ rebuild() produz bytes idênticos ao original")
    else:
        print(f"  ⚠️  diff: original={len(data):,}B, rebuilt={len(rebuilt):,}B")
        # Compara os primeiros bytes diferentes pra debug
        for i in range(min(len(data), len(rebuilt))):
            if data[i] != rebuilt[i]:
                print(f"  Primeira diferença no byte {i} (0x{i:x}): orig=0x{data[i]:02x}, new=0x{rebuilt[i]:02x}")
                break
