# -*- coding: utf-8 -*-

import os, sys
import argparse, struct, shutil, pytz, tifffile
from datetime import datetime
from pathlib import Path
from PyQt5.QtGui import QIcon
from PyQt5.QtWidgets import QApplication, QWidget, QVBoxLayout, QPushButton, QFileDialog, QLabel, QMessageBox


def check_slide_scanner(slide_path):
    with tifffile.TiffFile(slide_path, mode="r+b") as svs:
        assert svs.is_svs
        raw_description = svs.pages[0].description
        if "AT2" in raw_description:
            return "AT2"
        elif "GT450" in raw_description:
            return "GT450"
        elif "Barcode" in raw_description:
            return "Motic"
        else:
            return "Unknown"
        

def copy_rename_slide(slide_path):
    file_fullname = os.path.basename(slide_path)
    file_name, file_extension = os.path.splitext(file_fullname)
    file_dir = os.path.dirname(slide_path)
    deid_dir = os.path.join(file_dir, file_name)
    if os.path.exists(deid_dir):
        shutil.rmtree(deid_dir)
    os.makedirs(deid_dir)
    timestamp = datetime.now(tz=pytz.timezone("America/Chicago")).strftime("%Y%m%d_%H%M%S")
    deid_path = os.path.join(deid_dir, timestamp + file_extension)
    shutil.copyfile(slide_path, deid_path)
    return deid_path


def anonymize_slide_at2(slide_path, replace_name="MDACC"):
    with tifffile.TiffFile(slide_path, mode="r+b") as svs:
        assert svs.is_svs
        fh = svs.filehandle
        tiff = svs.tiff

        raw_description = svs.pages[0].description
        description_split = raw_description.split("|Filename = ", 1)
        f_name = description_split[1].split("|", 1)[0]
        # print("file name found: " + f_name)
        svs.pages[0].tags['ImageDescription'].overwrite(svs.pages[0].description.replace(f_name, replace_name))
        svs.pages[1].tags['ImageDescription'].overwrite(svs.pages[1].description.replace(f_name, replace_name))        

        # remove label and macro
        for page in svs.pages[::-1]:
            if page.subfiletype not in (1, 9):
                break  # not a label or macro image
            # zero image data in page
            for offset, bytecount in zip(page.dataoffsets, page.databytecounts):
                fh.seek(offset)
                fh.write(b'\0' * bytecount)
            # seek to position where offset to label/macro page is stored
            previous_page = svs.pages[page.index - 1]  # previous page
            fh.seek(previous_page.offset)
            tagno = struct.unpack(tiff.tagnoformat, fh.read(tiff.tagnosize))[0]
            offset = previous_page.offset + tiff.tagnosize + tagno * tiff.tagsize
            fh.seek(offset)
            # terminate IFD chain
            fh.write(struct.pack(tiff.offsetformat, 0))
            # print(f"wiped {page}")


def anonymize_slide_gt450(slide_path, replace_name="MDACC"):
    with tifffile.TiffFile(slide_path, mode="r+b") as svs:
        assert svs.is_svs
        fh = svs.filehandle
        tiff = svs.tiff

        raw_description = svs.pages[0].description
        description_split = raw_description.split("|ScanScope ID = ", 1)
        f_name = description_split[1].split("|", 1)[0]
        # print("file name found: " + f_name)
        svs.pages[0].tags['ImageDescription'].overwrite(svs.pages[0].description.replace(f_name, replace_name))
        svs.pages[1].tags['ImageDescription'].overwrite(svs.pages[1].description.replace(f_name, replace_name))        

        # remove label and macro
        for page in svs.pages[::-1]:
            if page.subfiletype not in (1, 9):
                break  # not a label or macro image
            # zero image data in page
            for offset, bytecount in zip(page.dataoffsets, page.databytecounts):
                fh.seek(offset)
                fh.write(b'\0' * bytecount)
            # seek to position where offset to label/macro page is stored
            previous_page = svs.pages[page.index - 1]  # previous page
            fh.seek(previous_page.offset)
            tagno = struct.unpack(tiff.tagnoformat, fh.read(tiff.tagnosize))[0]
            offset = previous_page.offset + tiff.tagnosize + tagno * tiff.tagsize
            fh.seek(offset)
            # terminate IFD chain
            fh.write(struct.pack(tiff.offsetformat, 0))
            # print(f"wiped {page}")


def anonymize_slide_motic(slide_path, replace_name="MDACC"):
    slide_path = Path(slide_path)
    with tifffile.TiffFile(slide_path, mode="r+b") as svs:
        assert svs.is_svs

        # Update the file name in the description to MDACC
        raw_description = svs.pages[0].description
        description_split = raw_description.split("|Barcode = ", 1)
        barcode = description_split[1].split("|", 1)[0]
        # print("barcode name found: " + barcode)
        svs.pages[0].tags['ImageDescription'].overwrite(svs.pages[0].description.replace(barcode, replace_name))

        # Collect indices that belong to the pyramid
        keep_indices = []
        for i, page in enumerate(svs.pages):
            if page.is_tiled:
                # All tiled pages = WSI + pyramid levels + thumbnail
                keep_indices.append(i)
                continue

        last_keep_idx = max(keep_indices)
        last_keep = svs.pages[last_keep_idx]

        # Basic TIFF sizing info
        is_big = svs.is_bigtiff
        byteorder = "<" if svs.byteorder == "<" else ">"
        tagnosize = 8 if is_big else 2
        tagsize = 20 if is_big else 12
        off_fmt = byteorder + ("Q" if is_big else "I")

    # Patch the file on disk
    with slide_path.open("r+b") as fh:
        # 2a) Terminate IFD chain after last pyramid page
        next_ifd_ptr_pos = (
            last_keep.offset + tagnosize + len(last_keep.tags) * tagsize
        )
        fh.seek(next_ifd_ptr_pos)
        fh.write(struct.pack(off_fmt, 0))


def deid_slide(slide_path, copy=True):
    scanner = check_slide_scanner(slide_path)
    if copy:
        # Copy and rename the slide
        slide_path = copy_rename_slide(slide_path)
    # Anonymize the slide based on the scanner type
    if scanner == "AT2":
        anonymize_slide_at2(slide_path)
    elif scanner == "GT450":
        anonymize_slide_gt450(slide_path)
    elif scanner == "Motic":
        anonymize_slide_motic(slide_path)
    else:
        raise ValueError("Unknown slide scanner type.")


class DeIDApp(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Slide DeID")
        self.setGeometry(100, 100, 400, 200)
        self.initUI()

    def initUI(self):
        layout = QVBoxLayout()

        # Instruction label
        self.label = QLabel("Select a svs file or a folder containing svs files")
        layout.addWidget(self.label)

        # Buttons for file and folder selection
        self.file_button = QPushButton("Select a svs file")
        self.file_button.clicked.connect(self.select_file)
        layout.addWidget(self.file_button)

        self.folder_button = QPushButton("Select a folder with svs files")
        self.folder_button.clicked.connect(self.select_folder)
        layout.addWidget(self.folder_button)

        # Button to rename files
        self.deid_button = QPushButton("Slide DeID")
        self.deid_button.clicked.connect(self.deid_files)
        layout.addWidget(self.deid_button)

        # Selected path display
        self.path_label = QLabel("No file or folder selected.")
        layout.addWidget(self.path_label)

        self.selected_path = None
        self.setLayout(layout)

    def select_file(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Select SVS File", "", "Slide Files (*.svs)")
        if file_path:
            self.selected_path = file_path
            self.path_label.setText(f"Selected File: {file_path}")

    def select_folder(self):
        folder_path = QFileDialog.getExistingDirectory(self, "Select Folder Containing SVS Files")
        if folder_path:
            self.selected_path = folder_path
            self.path_label.setText(f"Selected Folder: {folder_path}")

    def deid_files(self):
        if not self.selected_path:
            QMessageBox.warning(self, "Warning", "Please select a file or folder first.")
            return

        if os.path.isfile(self.selected_path):
            self.deid_file(self.selected_path)
        elif os.path.isdir(self.selected_path):
            svs_files = sorted([f for f in os.listdir(self.selected_path) if f.endswith(".svs")])
            if not svs_files:
                QMessageBox.information(self, "Info", "No svs files found in the selected folder.")
                return
            for svs_file in svs_files:
                full_path = os.path.join(self.selected_path, svs_file)
                self.deid_file(full_path)
            # Show complete message afer processing all files
            QMessageBox.information(self, "Success", "All slides de-identification completed.")
        else:
            QMessageBox.warning(self, "Error", "Invalid path selected.")


    def deid_file(self, file_path):
        filename = os.path.split(file_path)[1]
        try:
            deid_slide(file_path, copy=False)
            QMessageBox.information(self, "Success", f"{filename} has been de-ided.")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to de-id {filename}: {e}")


if __name__ == "__main__":
    app = QApplication(sys.argv)

    # locate icon path
    app_dir = Path(__file__).resolve().parent 
    icon_path = os.path.join(app_dir, "assets", "deid_icon.ico")
    app.setWindowIcon(QIcon(icon_path))

    window = DeIDApp()
    window.show()
    sys.exit(app.exec_())
