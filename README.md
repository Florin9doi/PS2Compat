### Usage:
- Scan the games:
```bash
python ps2_scanner.py "D:\path\to\ps2\games" . --extract-filter "usbd"
```
- Update the `modules.yml` file with more details.
- Run the script again to rebuild the database, eventually with an empty folder as input (FIXME):
```bash
python ps2_scanner.py "D:\path\to\empty\folder" . --extract-filter "usbd"
```
- Test the server locally:
```bash
python -m http.server 8000
```

### Notes:
- `modules.yml` is the main input file, and `unused.yml`  is also an input file used to ignore generic modules that escape the `--extract-filter`.
- `game_controllers.yml`, `gameid_to_name.yml` and `accessories.yml` are output files, the new data is mixed with the existing content to improve the database.
- If any controllers are removed or renamed inside the `modules.yml` file, it is necessary to manually delete the `accessories.yml` file (FIXME). It will be rebuilt next time.
