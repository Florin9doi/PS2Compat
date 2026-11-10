#!/usr/bin/env python3
# python ps2_scanner.py "/path/to/images" "/path/to/output" --extract-modules --extract-filter "usbd"
# Inputs (next to this script, override with --modules / --unused): modules.yml, unused.yml (global ignore list)
import argparse
import hashlib
import re
import sys
from pathlib import Path

import yaml

SECTOR = 2048
HERE = Path(__file__).resolve().parent
BOOT2_RE = re.compile(rb"^\s*BOOT2\s*=\s*cdrom0:\\([^;\s]+)", re.I | re.M)


class ISOReader:
    def __init__(self, path):
        self.file = open(path, "rb")

    def close(self):
        self.file.close()

    def read(self, lba, size):
        self.file.seek(lba * SECTOR)
        return self.file.read(size)

    def read_directory(self, lba, size):
        data = self.read(lba, size)
        entries, pos = [], 0
        while pos < len(data):
            length = data[pos]
            if not length:
                pos = (pos // SECTOR + 1) * SECTOR
                continue
            r = data[pos:pos + length]
            if len(r) < 34:
                break
            name = r[33:33 + r[32]]
            if name not in (b"\0", b"\1"):
                entries.append({
                    "name": name.decode("ascii", errors="replace"),
                    "lba": int.from_bytes(r[2:6], "little"),
                    "size": int.from_bytes(r[10:14], "little"),
                    "dir": bool(r[25] & 2)
                })
            pos += length
        return entries

    def get_root(self):
        for sector in range(16, 40):
            d = self.read(sector, SECTOR)
            if d[1:6] == b"CD001" and d[0] == 1:
                return (int.from_bytes(d[158:162], "little"),
                        int.from_bytes(d[166:170], "little"))
            if d[0] == 255:
                break
        raise RuntimeError("Invalid ISO9660 image")

    def find_file(self, wanted):
        for e in self.read_directory(*self.get_root()):
            if e["name"].split(";")[0].upper() == wanted.upper():
                return e

    def walk(self):
        def recurse(lba, size, prefix=""):
            for e in self.read_directory(lba, size):
                path = prefix + e["name"].split(";")[0]
                if e["dir"]:
                    yield from recurse(e["lba"], e["size"], path + "/")
                else:
                    yield path, e["lba"], e["size"]
        yield from recurse(*self.get_root())


class VirtualISO(ISOReader):
    def __init__(self, path):
        tracks, cur_file, cur = [], None, None
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            m = re.match(r'^\s*FILE\s+"([^"]+)"|^\s*FILE\s+(\S+)', line, re.I)
            if m:
                cur_file = m.group(1) or m.group(2)
                continue
            m = re.match(r"^\s*TRACK\s+\d+\s+(\S+)", line, re.I)
            if m:
                cur = {"file": cur_file, "mode": m.group(1).upper(), "index": 0}
                tracks.append(cur)
                continue
            m = re.match(r"^\s*INDEX\s+01\s+(\d+):(\d+):(\d+)", line, re.I)
            if m and cur:
                a, b, c = map(int, m.groups())
                cur["index"] = (a * 60 + b) * 75 + c
        modes = {"MODE1/2048": (2048, 0), "MODE1/2352": (2352, 16), "MODE2/2352": (2352, 24)}
        for t in tracks:
            if t["mode"] in modes:
                self.sector_size, self.data_offset = modes[t["mode"]]
                bin_path = path.parent / t["file"]
                if not bin_path.is_file():
                    raise FileNotFoundError(bin_path)
                self.file = open(bin_path, "rb")
                self.start = t["index"]
                return
        raise RuntimeError("No supported data track found")

    def read(self, lba, size):
        result = bytearray()
        while size > 0:
            self.file.seek((self.start + lba) * self.sector_size + self.data_offset)
            chunk = self.file.read(min(size, SECTOR))
            if not chunk:
                break
            result.extend(chunk)
            size -= len(chunk)
            lba += 1
        return bytes(result)


def read_game_id(iso):
    e = iso.find_file("SYSTEM.CNF")
    m = e and BOOT2_RE.search(iso.read(e["lba"], e["size"]))
    return m.group(1).decode("ascii", errors="replace") if m else None


def chunks(iso, lba, size):
    while size > 0:
        n = min(size, 1 << 20)
        sectors = -(-n // SECTOR)
        data = iso.read(lba, sectors * SECTOR)[:n]
        if not data:
            raise IOError("Unexpected end of image")
        yield data
        size -= len(data)
        lba += sectors


def md5_file(iso, lba, size):
    h = hashlib.md5()
    for c in chunks(iso, lba, size):
        h.update(c)
    return h.hexdigest()


def contains_filter(iso, lba, size, needle):
    if not needle:
        return True
    needle, prev = needle.lower().encode(), b""
    for c in chunks(iso, lba, size):
        buf = prev + c.lower()
        if needle in buf:
            return True
        prev = buf[-(len(needle) - 1):] if len(needle) > 1 else b""
    return False


def extract_module(iso, lba, size, out):
    if out.exists():
        return False
    try:
        with out.open("wb") as f:
            for c in chunks(iso, lba, size):
                f.write(c)
    except Exception:
        out.unlink(missing_ok=True)
        raise
    return True


def find_modules(iso):
    for path, lba, size in iso.walk():
        name = path.rsplit("/", 1)[-1]
        if name.lower().endswith(".irx") or re.fullmatch(r"ioprp...\.img", name, re.I):
            try:
                yield name, md5_file(iso, lba, size), lba, size
            except Exception as e:
                print(f"  Warning: {path}: {e}")


def as_list(v):
    return [] if v is None else v if isinstance(v, list) else [v]


def load_yml(path):
    return (yaml.safe_load(path.read_text(encoding="utf-8")) or {}) if path.exists() else {}


def dump_yml(path, data):
    path.write_text(yaml.safe_dump(data, sort_keys=True, allow_unicode=True,
                                   default_flow_style=False), encoding="utf-8")


def expand(raw):
    out = {}
    for k, v in raw.items():
        v = v or {}
        keys = [m.strip() for x in as_list(v["modules"]) for m in str(x).split(",")] if "modules" in v else [k]
        info = {i: j for i, j in v.items() if i != "modules"}
        for m in filter(None, keys):
            cur = out.setdefault(m.casefold(), {})
            sup = as_list(cur.get("support"))
            cur.update(info)
            cur["support"] = sup + [x for x in as_list(info.get("support")) if x not in sup]
    return out


def module_info(modules, name, digest):
    return {**modules.get(name.casefold(), {}),
            **modules.get(f"{name}__{digest}".casefold(), {})}


def is_unused(m, skip):
    return bool({m.casefold(), m.split("__")[0].casefold()} & skip)


def derive(mods, modules):
    out = set()
    for m in mods:
        name = m.split("__")[0]
        out.update(as_list(module_info(modules, name, m[len(name) + 2:]).get("support")))
    return out


def process_image(path, a, names, games, unused):
    iso = None
    try:
        iso = ISOReader(path) if path.suffix.lower() == ".iso" else VirtualISO(path)
        gid = read_game_id(iso)
        if not gid:
            print("  SYSTEM.CNF / BOOT2 not found")
            return
        found = set()
        for name, digest, lba, size in find_modules(iso):
            if is_unused(f"{name}__{digest}", unused) or not contains_filter(iso, lba, size, a.extract_filter):
                continue
            found.add(f"{name}__{digest}")
            if a.extract_modules:
                try:
                    if extract_module(iso, lba, size, a.output_folder / f"{name}__{digest}"):
                        print(f"  Extracted: {name}__{digest}")
                except Exception as e:
                    print(f"  Extraction error: {name}: {e}")
        if found:
            games.setdefault(gid, set()).update(found)
        names[gid] = path.stem.strip()
        print(f"  {gid} -> {names[gid]} ({len(found)} modules)")
    except Exception as e:
        print(f"  ERROR: {path.name}: {e}")
    finally:
        if iso:
            iso.close()


def main():
    p = argparse.ArgumentParser(description="PS2 ISO/BIN/CUE scanner")
    p.add_argument("input_folder", type=Path)
    p.add_argument("output_folder", type=Path)
    p.add_argument("--extract-modules", action="store_true", help="Extract IRX and IOPRP files")
    p.add_argument("--extract-filter", help="Only process modules containing this binary content")
    p.add_argument("--modules", type=Path, default=HERE / "modules.yml")
    p.add_argument("--unused", type=Path, default=HERE / "unused.yml")
    a = p.parse_args()
    src, dst = a.input_folder.resolve(), a.output_folder.resolve()
    a.output_folder = dst
    if not src.is_dir() or not dst.is_dir():
        sys.exit("Input and output folders must exist")
    if src == dst:
        sys.exit("Input and output folders must be different")

    raw = load_yml(a.modules)
    modules = expand(raw)
    u = load_yml(a.unused) if a.unused.exists() else []
    unused = {str(x).casefold() for x in (u if isinstance(u, (dict, list)) else [u])}

    names_f, acc_f, ctrl_f = (dst / n for n in ("gameid_to_name.yml", "accessories.yml", "game_controllers.yml"))
    names = load_yml(names_f)
    acc = {t: set(as_list(v)) for t, v in load_yml(acc_f).items()}
    games = {g: {m for m in as_list(v.get("modules")) if not is_unused(m, unused)} for g, v in load_yml(ctrl_f).items() if isinstance(v, dict)}

    images = sorted((f for f in src.rglob("*") if f.is_file() and f.suffix.lower() in (".iso", ".cue")),
                    key=lambda f: f.name.lower())
    print(f"Found {len(images)} images")
    for path in images:
        process_image(path, a, names, games, unused)

    for info in raw.values():
        if info and info.get("support"):
            acc.setdefault(info.get("type") or "Other", set()).update(as_list(info["support"]))

    y = lambda s: yaml.safe_dump(s, allow_unicode=True, width=10**6).splitlines()[0]
    dump_yml(names_f, names)
    dump_yml(acc_f, {t: sorted(v, key=str.casefold) for t, v in acc.items()})
    with ctrl_f.open("w", encoding="utf-8") as f:
        for gid in sorted(games, key=str.casefold):
            ctrl = derive(games[gid], modules)
            f.write(f"{gid}:" + (f" # {names[gid]}" if gid in names else "") + "\n  modules:\n")
            f.writelines(f"    - {y(m)}\n" for m in sorted(games[gid], key=str.casefold))
            if ctrl:
                f.write("  controllers:\n")
                f.writelines(f"    - {y(c)}\n" for c in sorted(ctrl, key=str.casefold))

    unpaired = sorted({m for g in games.values() for m in g
                       if not {m.casefold(), m.split("__")[0].casefold()} & modules.keys()}, key=str.casefold)
    print(f"\nModules without metadata in {a.modules.name}: {len(unpaired)}")
    print(*unpaired, sep="\n")
    print(f"\nCompleted.\nGames: {len(names)}, in controller db: {len(games)}\nOutput: {dst}")


if __name__ == "__main__":
    main()
