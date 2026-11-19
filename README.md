# PS2 USB compatibility database

## Usage
Requires Python 3 and PyYAML (`pip install pyyaml`).

- Scan the games (only needed once):
```bash
python ps2_scanner.py --in "D:\path\to\ps2\games" --out "docs" --extract-filter "usbd"
```
- Optionally, extract the modules:
```bash
python ps2_scanner.py --in "D:\path\to\ps2\games" --out "modules" --extract-modules --extract-filter "usbd"
```
- Add details to `modules.yml`, then rebuild the database without scanning:
```bash
python ps2_scanner.py --out "docs"
```
- Test the website locally (http://localhost:8000):
```bash
cd docs
python -m http.server 8000
```

## Files
- Inputs, next to the script:
  - `modules.yml` maps modules to a type and supported devices.
  - `unused.yml` lists generic modules to ignore, those that pass `--extract-filter` but are not relevant.
- Outputs, in `docs/`:
  - `game_controllers.yml` lists the modules and devices per game.
  - `gameid_to_name.yml` maps game IDs to names. Existing names are never overwritten, so you can edit them by hand.
  - `accessories.yml` lists devices by type, and is rebuilt from `modules.yml` on every run.
- Scans add new games and modules to the existing database. Devices are recomputed from the current `modules.yml` on every run.

## Todo
- [ ] Split SingStar/Logitech/universal mic drivers
