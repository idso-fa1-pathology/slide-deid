# slide-deid
Pathology whole slide imaging (WSI) de-identification

### Build App
- Follow these steps to build the app
```
$ git clone https://github.com/idso-fa1-pathology/slide-deid
$ cd slide-deid
$ pip install -r requirements.txt
$ python -m PyInstaller --onefile --noconsole SlideDeID.py --icon=assets/deid_icon.ico
```
- Generated app (SlideDeID) will be saved under **dist** subfolder

### Notes
- **Supported scanners:** Leica AT2, Leica GT450, and Motic.
- **De‑identification:** Performed directly on the raw slide—be sure a backup copy is retained.