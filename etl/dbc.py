"""Leitura de arquivos .dbc do DATASUS em Python puro.

Um .dbc é um arquivo DBF cujo corpo foi comprimido com o algoritmo PKWare DCL
"implode" (o mesmo que o `blast.c` de Mark Adler descomprime). Formato:

    [cabeçalho DBF (tamanho em bytes 8-9)] [CRC32 (4 bytes)] [dados comprimidos]

Este módulo evita dependências que precisam de compilador C (pyreaddbc,
datasus-dbc), que não instalam no Windows sem build tools.
"""
from __future__ import annotations

import struct
from pathlib import Path

import numpy as np
import pandas as pd

# ---------------------------------------------------------------- blast ----
_LITLEN = bytes([
    11, 124, 8, 7, 28, 7, 188, 13, 76, 4, 10, 8, 12, 10, 12, 10, 8, 23, 8,
    9, 7, 6, 7, 8, 7, 6, 55, 8, 23, 24, 12, 11, 7, 9, 11, 12, 6, 7, 22, 5,
    7, 24, 6, 11, 9, 6, 7, 22, 7, 11, 38, 7, 9, 8, 25, 11, 8, 11, 9, 12,
    8, 12, 5, 38, 5, 38, 5, 11, 7, 5, 6, 21, 6, 10, 53, 8, 7, 24, 10, 27,
    44, 253, 253, 253, 252, 252, 252, 13, 12, 45, 12, 45, 12, 61, 12, 45,
    44, 173])
_LENLEN = bytes([2, 35, 36, 53, 38, 23])
_DISTLEN = bytes([2, 20, 53, 230, 247, 151, 248])
_BASE = (3, 2, 4, 5, 6, 7, 8, 9, 10, 12, 16, 24, 40, 72, 136, 264)
_EXTRA = (0, 0, 0, 0, 0, 0, 0, 0, 1, 2, 3, 4, 5, 6, 7, 8)
_MAXBITS = 13


def _lengths(rep: bytes) -> list[int]:
    out: list[int] = []
    for b in rep:
        out.extend([b & 15] * ((b >> 4) + 1))
    return out


def _table(rep: bytes) -> list[tuple[int, int]]:
    """Tabela de lookup indexada pelos próximos 13 bits (LSB primeiro).

    Os códigos do blast são canônicos e gravados com os bits invertidos;
    cada entrada guarda (símbolo, comprimento do código).
    """
    lengths = _lengths(rep)
    count = [0] * (_MAXBITS + 1)
    for ln in lengths:
        count[ln] += 1
    offs = [0] * (_MAXBITS + 2)
    for ln in range(1, _MAXBITS + 1):
        offs[ln + 1] = offs[ln] + count[ln]
    symbols = [0] * len(lengths)
    for sym, ln in enumerate(lengths):
        if ln:
            symbols[offs[ln]] = sym
            offs[ln] += 1

    size = 1 << _MAXBITS
    table: list[tuple[int, int]] = [(-1, 0)] * size
    code = first = index = 0
    for ln in range(1, _MAXBITS + 1):
        cnt = count[ln]
        for k in range(cnt):
            c = first + k
            sym = symbols[index + k]
            # bits como aparecem no fluxo: primeiro bit lido = MSB do código, invertido
            raw = 0
            for i in range(ln):
                raw |= (((c >> (ln - 1 - i)) & 1) ^ 1) << i
            for hi in range(0, size, 1 << ln):
                table[raw | hi] = (sym, ln)
        index += cnt
        first = (first + cnt) << 1
    return table


_LITCODE = _table(_LITLEN)
_LENCODE = _table(_LENLEN)
_DISTCODE = _table(_DISTLEN)


def blast(data: bytes | memoryview) -> bytes:
    """Descomprime um fluxo PKWare DCL implode."""
    src = memoryview(data)
    n = len(src)
    pos = 0
    bitbuf = 0
    bitcnt = 0
    out = bytearray()
    mask13 = (1 << _MAXBITS) - 1
    litcode, lencode, distcode = _LITCODE, _LENCODE, _DISTCODE

    def need(k: int) -> None:
        nonlocal pos, bitbuf, bitcnt
        while bitcnt < k:
            if pos < n:
                bitbuf |= src[pos] << bitcnt
                pos += 1
            bitcnt += 8  # completa com zeros no fim do fluxo

    need(16)
    lit = bitbuf & 0xFF
    dict_bits = (bitbuf >> 8) & 0xFF
    bitbuf >>= 16
    bitcnt -= 16
    if lit > 1 or not 4 <= dict_bits <= 6:
        raise ValueError("cabeçalho blast inválido")

    while True:
        if bitcnt < 32:
            # recarrega até ~4 bytes de uma vez (cobre o pior caso de um passo)
            while bitcnt <= 56 and pos < n:
                bitbuf |= src[pos] << bitcnt
                pos += 1
                bitcnt += 8
            if bitcnt < 32:
                need(32)
        flag = bitbuf & 1
        bitbuf >>= 1
        bitcnt -= 1
        if flag:
            sym, ln = lencode[bitbuf & mask13]
            bitbuf >>= ln
            bitcnt -= ln
            e = _EXTRA[sym]
            length = _BASE[sym] + (bitbuf & ((1 << e) - 1))
            bitbuf >>= e
            bitcnt -= e
            if length == 519:
                break
            if bitcnt < 24:
                need(24)
            shift = 2 if length == 2 else dict_bits
            sym, ln = distcode[bitbuf & mask13]
            bitbuf >>= ln
            bitcnt -= ln
            dist = ((sym << shift) | (bitbuf & ((1 << shift) - 1))) + 1
            bitbuf >>= shift
            bitcnt -= shift
            start = len(out) - dist
            if start < 0:
                raise ValueError("distância além do início da saída")
            if dist >= length:
                out += out[start:start + length]
            else:  # cópia sobreposta (repetição)
                chunk = out[start:]
                reps, rest = divmod(length, dist)
                out += chunk * reps + chunk[:rest]
        else:
            if lit:
                sym, ln = litcode[bitbuf & mask13]
                bitbuf >>= ln
                bitcnt -= ln
            else:
                sym = bitbuf & 0xFF
                bitbuf >>= 8
                bitcnt -= 8
            out.append(sym)
    return bytes(out)


def dbc_to_dbf_bytes(path: str | Path) -> bytes:
    raw = Path(path).read_bytes()
    header_size = struct.unpack_from("<H", raw, 8)[0]
    return raw[:header_size] + blast(memoryview(raw)[header_size + 4:])


# ------------------------------------------------------------------ dbf ----
def read_dbf_bytes(buf: bytes, columns: list[str] | None = None,
                   encoding: str = "latin-1") -> pd.DataFrame:
    """Lê um DBF da memória com numpy (todas as colunas como texto)."""
    nrec, hsize, rsize = struct.unpack_from("<IHH", buf, 4)
    fields = []
    off = 1  # byte 0 de cada registro = flag de deleção
    p = 32
    while buf[p] != 0x0D:
        name = buf[p:p + 11].split(b"\x00")[0].decode("ascii").strip()
        flen = buf[p + 16]
        fields.append((name, off, flen))
        off += flen
        p += 32
    want = set(c.upper() for c in columns) if columns else None
    recs = np.frombuffer(buf, dtype=np.uint8, count=nrec * rsize,
                         offset=hsize).reshape(nrec, rsize)
    keep = recs[:, 0] != ord("*")
    recs = recs[keep]
    data = {}
    for name, off, flen in fields:
        if want is not None and name.upper() not in want:
            continue
        col = np.ascontiguousarray(recs[:, off:off + flen]).view(f"S{flen}").ravel()
        s = pd.Series(col).str.decode(encoding).str.strip()
        data[name.upper()] = s
    return pd.DataFrame(data)


def read_dbc(path: str | Path, columns: list[str] | None = None) -> pd.DataFrame:
    return read_dbf_bytes(dbc_to_dbf_bytes(path), columns)
