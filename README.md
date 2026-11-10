### Usage:
- Scan the games:
```bash
python ps2_scanner.py --in "D:\path\to\ps2\games" --out "www" --extract-filter "usbd"
```
- Update the `modules.yml` file with more details.
- Run the script again to rebuild the database with the new `modules.yml` changes.
```bash
python ps2_scanner.py --out "www"
```
- Test the server locally:
```bash
python -m http.server 8000
```

### Notes:
- `modules.yml` is the main input file, and `unused.yml`  is also an input file used to ignore generic modules that escape the `--extract-filter`.
- `game_controllers.yml`, `gameid_to_name.yml` and `accessories.yml` are output files, the new data is mixed with the existing content to improve the database.
