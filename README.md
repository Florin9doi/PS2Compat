# PS2 USB compatibility database

## Usage
Requires Python 3 and PyYAML (`pip install pyyaml`).

- Scan the games (only needed once):
```bash
python ps2_scanner.py --in "D:\path\to\ps2\games" --out "docs" --extract-filter "usbd"
```
- Add details to `modules.yml`, then rebuild the database without scanning:
```bash
python ps2_scanner.py --out "docs"
```
- Test the website locally:
```bash
cd docs
python -m http.server 8000
```

## Files
- Inputs, next to the script:
  - `modules.yml` maps modules to a type and supported controllers.
  - `unused.yml` lists generic modules to ignore, those that pass `--extract-filter` but are not relevant.
- Outputs, in `docs/`:
  - `game_controllers.yml` lists the modules and controllers per game.
  - `gameid_to_name.yml` maps game IDs to names. Existing names are never overwritten, so you can edit them by hand.
  - `accessories.yml` lists controllers by type, and is rebuilt from `modules.yml` on every run.
- Scans add new games and modules to the existing database. Controllers are recomputed from the current `modules.yml` on every run.

## Todo
- [ ] Rename or merge the Logitech and TMS wheel entries
- [ ] Document the Logitech wheel driver versions and the controllers each one supports
- [ ] Split SingStar/Logitech/universal mic drivers
- [ ] Check DMC storage support
