#!/usr/bin/env python3
"""
Xbox ISO (XDVDFS/XISO) extraction and creation.

Supports original Xbox and Xbox 360 (XGD1, XGD2, XGD3) game ISOs.

Format reference: https://xboxdevwiki.net/XDVDFS
"""
import os
import struct
import sys
import time


SECTOR_SIZE = 2048
HEADER_DATA = b"MICROSOFT*XBOX*MEDIA"
HEADER_DATA_LEN = 20
HEADER_OFFSET = 0x10000

XGD1_OFFSET = 0x18300000
XGD2_OFFSET = 0x0FD90000
XGD3_OFFSET = 0x02080000

ATTR_DIRECTORY = 0x10
ATTR_NORMAL = 0x80

FILETIME_EPOCH = 11644473600


class XisoError(Exception):
    pass


def _find_volume(iso_path):
    """Find the XDVDFS volume descriptor and return (lseek_offset, root_sector, root_size)."""
    for lseek_off in (0, XGD2_OFFSET, XGD3_OFFSET, XGD1_OFFSET):
        with open(iso_path, "rb") as f:
            f.seek(HEADER_OFFSET + lseek_off)
            magic = f.read(HEADER_DATA_LEN)
            if magic == HEADER_DATA:
                root_sector, = struct.unpack("<I", f.read(4))
                root_size, = struct.unpack("<I", f.read(4))
                return lseek_off, root_sector, root_size
    raise XisoError("Not a valid Xbox ISO image (no XDVDFS volume descriptor found)")


def _read_dir_table(iso_path, lseek_off, sector, parent_path="", callback=None, _depth=0, _table_size=None):
    """Read all directory entries from a table by scanning linearly.

    Scans the directory table byte-by-byte, parsing each entry.
    Recurses into sub-directory tables.

    callback(path, name, start_sector, file_size, is_dir, parent)
    Returns list of callback results.
    """
    if _depth > 64:
        return []

    dir_start = sector * SECTOR_SIZE + lseek_off
    results = []
    seen = {}
    _table_size = _table_size or SECTOR_SIZE * 64

    with open(iso_path, "rb") as f:
        pos = 0

        while pos < _table_size:
            f.seek(dir_start + pos)
            data = f.read(2)
            if len(data) < 2:
                break
            left_off = struct.unpack("<H", data)[0]

            if left_off == 0xFFFF:
                pos = (pos // SECTOR_SIZE + 1) * SECTOR_SIZE
                continue

            data = f.read(2 + 4 + 4 + 1 + 1)
            if len(data) < 12:
                break
            right_off, start_sector, file_size, attrs, name_len = struct.unpack("<HIIBB", data)

            if name_len == 0 or name_len > 255:
                break

            name = f.read(name_len).decode("ascii", errors="replace")
            entry_size = 14 + name_len
            entry_size = (entry_size + 3) & ~3

            is_dir = bool(attrs & ATTR_DIRECTORY)
            full_path = parent_path + name

            if callback:
                cb_result = callback(full_path, name, start_sector, file_size, is_dir, parent_path)
                results.append(cb_result)

            if is_dir:
                key = (start_sector, parent_path)
                if key not in seen and 0 < start_sector < 0x300000:
                    seen[key] = True
                    sub_table_size = file_size or SECTOR_SIZE
                    sub = _read_dir_table(iso_path, lseek_off, start_sector, full_path + "/",
                                         callback, _depth + 1, sub_table_size)
                    results.extend(sub)

            pos += entry_size

    return results


def list_iso(iso_path):
    """List all files in an Xbox ISO.

    Returns list of dicts:
        {name, path, size, is_dir, start_sector}
    """
    lseek_off, root_sector, root_size = _find_volume(iso_path)
    entries = []

    def callback(path, name, start_sector, file_size, is_dir, parent):
        e = {
            "name": name,
            "path": path,
            "size": 0 if is_dir else file_size,
            "is_dir": is_dir,
            "start_sector": start_sector,
        }
        entries.append(e)
        return e

    _read_dir_table(iso_path, lseek_off, root_sector, callback=callback, _table_size=root_size)
    return entries


def extract_iso(iso_path, output_dir, file_paths=None):
    """Extract files from an Xbox ISO.

    If file_paths is None, extracts all files.
    file_paths is a set of paths (as returned by list_iso) to extract.

    Returns list of (path, output_path, size) tuples.
    """
    lseek_off, root_sector, root_size = _find_volume(iso_path)
    os.makedirs(output_dir, exist_ok=True)
    extracted = []

    def callback(path, name, start_sector, file_size, is_dir, parent):
        if is_dir:
            dir_out = os.path.join(output_dir, path)
            os.makedirs(dir_out, exist_ok=True)
        elif file_paths is None or path in file_paths:
            file_out = os.path.join(output_dir, path)
            os.makedirs(os.path.dirname(file_out), exist_ok=True)
            data_start = start_sector * SECTOR_SIZE + lseek_off
            with open(iso_path, "rb") as src:
                src.seek(data_start)
                data = src.read(file_size)
            with open(file_out, "wb") as dst:
                dst.write(data)
            extracted.append((path, file_out, file_size))
        return True

    _read_dir_table(iso_path, lseek_off, root_sector, callback=callback, _table_size=root_size)
    return extracted


def read_game_name(iso_path):
    """Try to read the game name from an Xbox ISO by finding default.xex."""
    entries = list_iso(iso_path)
    # Look for default.xex at the root
    for e in entries:
        if e["name"].lower() == "default.xex" and not e["is_dir"]:
            return os.path.basename(iso_path).replace(".iso", "").replace(".ISO", "")
    return None


def _make_volume_descriptor(root_sector, root_size):
    """Build a volume descriptor sector."""
    sector = bytearray(SECTOR_SIZE)
    sector[:HEADER_DATA_LEN] = HEADER_DATA
    struct.pack_into("<I", sector, 0x14, root_sector)
    struct.pack_into("<I", sector, 0x18, root_size)
    now = int((time.time() + FILETIME_EPOCH) * 10000000)
    struct.pack_into("<Q", sector, 0x1C, now)
    sector[0x7EC:0x7EC + HEADER_DATA_LEN] = HEADER_DATA
    return bytes(sector)


def create_iso(source_dir, output_path):
    """Create an Xbox ISO (XISO) from a directory.

    Args:
        source_dir: Path to directory containing game files
        output_path: Path for the output ISO file
    """
    if not os.path.isdir(source_dir):
        raise XisoError(f"Source directory not found: {source_dir}")

    vol_name = os.path.basename(source_dir)

    # Collect all files and dirs
    file_entries = []
    total_size = 0
    for root, dirs, files in os.walk(source_dir):
        rel = os.path.relpath(root, source_dir)
        if rel == ".":
            rel = ""
        for f in sorted(files):
            fp = os.path.join(root, f)
            rp = os.path.join(rel, f) if rel else f
            sz = os.path.getsize(fp)
            file_entries.append((rp, fp, sz, False))
            total_size += sz
        for d in sorted(dirs):
            rp = os.path.join(rel, d) if rel else d
            file_entries.append((rp, None, 0, True))

    # Filter to only files (directories are implicit from paths)
    file_entries = [(rp, fp, sz) for rp, fp, sz, is_dir in file_entries if not is_dir and fp is not None]
    if not file_entries:
        raise XisoError("No files found in source directory")

    file_entries.sort(key=lambda x: (x[0].count("/"), x[0]))

    # Calculate directory table size (use full relative path as entry name)
    cur_offset = 0
    entry_offsets = {}
    for rp, fp, sz in file_entries:
        entry_offsets[rp] = cur_offset
        entry_size = 14 + len(rp)
        entry_size = (entry_size + 3) & ~3
        cur_offset += entry_size

    root_dir_sector = 0x108
    root_dir_size = cur_offset
    dir_sectors = (root_dir_size + SECTOR_SIZE - 1) // SECTOR_SIZE

    # Start file data after directory table
    sector = root_dir_sector + dir_sectors
    file_sectors = {}
    for rp, fp, sz in file_entries:
        file_sectors[rp] = sector
        sector += (sz + SECTOR_SIZE - 1) // SECTOR_SIZE

    with open(output_path, "wb") as iso:
        pad_end = (root_dir_sector + dir_sectors) * SECTOR_SIZE
        iso.write(b"\x00" * pad_end)

        iso.seek(root_dir_sector * SECTOR_SIZE)
        for i, (rp, fp, sz) in enumerate(file_entries):
            name = rp
            next_off = entry_offsets[file_entries[i + 1][0]] if i + 1 < len(file_entries) else 0
            right_off = next_off // 4 if next_off else 0
            entry = struct.pack("<HHIIBB", 0, right_off, file_sectors[rp], sz, ATTR_NORMAL, len(name))
            entry += name.encode("ascii")
            entry += b"\x00" * ((4 - len(entry) % 4) % 4)
            iso.write(entry)

        sec_end = (root_dir_sector + dir_sectors) * SECTOR_SIZE
        if sec_end > iso.tell():
            iso.write(b"\x00" * (sec_end - iso.tell()))

        for rp, fp, sz in file_entries:
            sec = file_sectors[rp]
            iso.seek(sec * SECTOR_SIZE)
            with open(fp, "rb") as src:
                while True:
                    chunk = src.read(SECTOR_SIZE)
                    if not chunk:
                        break
                    iso.write(chunk.ljust(SECTOR_SIZE, b"\x00"))

        # Pad to 64KB boundary
        end = iso.tell()
        pad = (0x10000 - end % 0x10000) % 0x10000
        iso.write(b"\x00" * pad)

        total_sectors = (iso.tell() + SECTOR_SIZE - 1) // SECTOR_SIZE

        # Write XDVDFS volume descriptor at sector 32
        iso.seek(HEADER_OFFSET)
        iso.write(_make_volume_descriptor(root_dir_sector, root_dir_size))

        # Write ISO 9660 Primary Volume Descriptor + Terminator
        for desc_sector in (16, 17):
            iso.seek(desc_sector * SECTOR_SIZE)
            sector = bytearray(SECTOR_SIZE)
            sector[0] = 1 if desc_sector == 16 else 255  # PVD or terminator
            sector[1:6] = b"CD001"
            sector[6] = 1
            if desc_sector == 16:
                vol_b = vol_name.encode("ascii", errors="replace")[:32]
                sector[8:8 + len(vol_b)] = vol_b
                struct.pack_into("<I", sector, 80, total_sectors)
                struct.pack_into(">I", sector, 84, total_sectors)
                struct.pack_into("<H", sector, 120, 1)
                struct.pack_into(">H", sector, 122, 1)
                struct.pack_into("<H", sector, 124, 1)
                struct.pack_into(">H", sector, 126, 1)
                struct.pack_into("<H", sector, 128, SECTOR_SIZE)
                struct.pack_into(">H", sector, 130, SECTOR_SIZE)
                root_rec = bytearray(34)
                root_rec[0] = 34
                struct.pack_into("<I", root_rec, 2, root_dir_sector)
                struct.pack_into(">I", root_rec, 6, root_dir_sector)
                struct.pack_into("<I", root_rec, 10, root_dir_size)
                struct.pack_into(">I", root_rec, 14, root_dir_size)
                root_rec[25] = 1
                sector[156:190] = root_rec
                app = b"XBLA-Automation XISO Creator"
                sector[574:574 + len(app)] = app
            iso.write(sector)


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print(f"Usage:")
        print(f"  {sys.argv[0]} list <iso_path>")
        print(f"  {sys.argv[0]} extract <iso_path> [output_dir]")
        print(f"  {sys.argv[0]} create <source_dir> <output_iso>")
        sys.exit(1)

    cmd = sys.argv[1]

    if cmd == "list":
        try:
            entries = list_iso(sys.argv[2])
            for e in entries:
                kind = "DIR " if e["is_dir"] else "FILE"
                size = f"{e['size']:>12d}" if not e["is_dir"] else "           -"
                print(f"  [{kind}] {e['path']:<50s} {size}")
            print(f"\n{len(entries)} item(s)")
        except XisoError as ex:
            print(f"Error: {ex}")
            sys.exit(1)

    elif cmd == "extract":
        iso_path = sys.argv[2]
        output_dir = sys.argv[3] if len(sys.argv) > 3 else os.path.splitext(os.path.basename(iso_path))[0] + "_extracted"
        try:
            extracted = extract_iso(iso_path, output_dir)
            for path, out, size in extracted:
                print(f"  {path} -> {out} ({size} bytes)")
            print(f"\nExtracted {len(extracted)} file(s) to {output_dir}")
        except XisoError as ex:
            print(f"Error: {ex}")
            sys.exit(1)

    elif cmd == "create":
        try:
            create_iso(sys.argv[2], sys.argv[3])
            print(f"Created ISO: {sys.argv[3]}")
        except XisoError as ex:
            print(f"Error: {ex}")
            sys.exit(1)
