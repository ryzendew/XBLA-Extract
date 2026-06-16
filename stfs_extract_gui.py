import sys
import os
import time
from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QTreeWidget, QTreeWidgetItem,
    QHeaderView, QFileDialog, QMessageBox, QFrame, QTabWidget,
    QProgressDialog
)
from PyQt6.QtCore import Qt, QSize
from PyQt6.QtGui import QFont
from stfs_extract import list_live_pirs, extract_live_pirs, read_game_name as stfs_read_game_name
from stfs_extract import _parse_stfs_header, _read_entry_bytes, get_cluster
from xiso import list_iso, extract_iso, create_iso, _find_volume, SECTOR_SIZE, XisoError

JUNK_NAMES = {"Thumbs.db", ".DS_Store", "desktop.ini", "ehthumbs.db"}


def _format_size(size):
    if size >= 1024 * 1024:
        return f"{size / (1024 * 1024):.1f} MB"
    elif size >= 1024:
        return f"{size / 1024:.1f} KB"
    else:
        return f"{size} bytes"


class SortableTreeItem(QTreeWidgetItem):
    def __lt__(self, other):
        col = self.treeWidget().sortColumn() if self.treeWidget() else 0
        if col == 3:
            a = self.data(3, Qt.ItemDataRole.UserRole) or 0
            b = other.data(3, Qt.ItemDataRole.UserRole) or 0
            return a < b
        return super().__lt__(other)


class StfsTab(QWidget):
    def __init__(self, main_window):
        super().__init__()
        self.main = main_window
        self.entries_cache = []
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        row1 = QHBoxLayout()
        row1.setSpacing(8)
        label1 = QLabel("STFS Package:")
        label1.setFixedWidth(110)
        self.input_edit = QLineEdit()
        self.input_edit.setPlaceholderText("Select an STFS package file...")
        browse_btn = QPushButton("Browse")
        browse_btn.clicked.connect(self.browse_input)
        browse_btn.setFixedWidth(100)
        row1.addWidget(label1)
        row1.addWidget(self.input_edit, 1)
        row1.addWidget(browse_btn)
        layout.addLayout(row1)

        row2 = QHBoxLayout()
        row2.setSpacing(8)
        label2 = QLabel("Output Folder:")
        label2.setFixedWidth(110)
        self.output_edit = QLineEdit()
        self.output_edit.setPlaceholderText("Select an output folder...")
        browse_out_btn = QPushButton("Browse")
        browse_out_btn.clicked.connect(self.browse_output)
        browse_out_btn.setFixedWidth(100)
        row2.addWidget(label2)
        row2.addWidget(self.output_edit, 1)
        row2.addWidget(browse_out_btn)
        layout.addLayout(row2)

        sep1 = QFrame()
        sep1.setObjectName("separator")
        sep1.setFrameShape(QFrame.Shape.HLine)
        layout.addWidget(sep1)

        section_label = QLabel("Package Contents")
        section_label.setStyleSheet("font-weight: bold; font-size: 10pt; color: #cccccc; padding: 2px 0;")
        layout.addWidget(section_label)

        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(["", "Type", "Name", "Size"])
        self.tree.setColumnCount(4)
        self.tree.setRootIsDecorated(False)
        self.tree.setAnimated(True)
        self.tree.setAlternatingRowColors(True)
        self.tree.setStyleSheet("""
            QTreeWidget { alternate-background-color: #2a2a2a; }
        """)
        self.tree.setSortingEnabled(True)
        self.tree.itemClicked.connect(self.on_item_clicked)

        header = self.tree.header()
        header.setStretchLastSection(False)
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        header.resizeSection(0, 36)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed)
        header.resizeSection(1, 90)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Fixed)
        header.resizeSection(3, 110)
        layout.addWidget(self.tree, 1)

        toolbar = QHBoxLayout()
        toolbar.setSpacing(8)
        self.select_all_btn = QPushButton("Select All")
        self.select_all_btn.clicked.connect(self.select_all)
        self.select_all_btn.setEnabled(False)
        self.deselect_all_btn = QPushButton("Deselect All")
        self.deselect_all_btn.clicked.connect(self.deselect_all)
        self.deselect_all_btn.setEnabled(False)
        self.game_label = QLabel("")
        self.game_label.setStyleSheet("color: #88ccff; font-weight: bold; font-size: 9pt;")
        self.game_label.hide()
        self.status_label = QLabel("Ready")
        self.status_label.setObjectName("status")
        toolbar.addWidget(self.select_all_btn)
        toolbar.addWidget(self.deselect_all_btn)
        toolbar.addWidget(self.game_label)
        toolbar.addStretch()
        toolbar.addWidget(self.status_label)
        layout.addLayout(toolbar)

        sep2 = QFrame()
        sep2.setObjectName("separator")
        sep2.setFrameShape(QFrame.Shape.HLine)
        layout.addWidget(sep2)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(12)
        btn_row.addStretch()
        self.extract_sel_btn = QPushButton("Extract Selected")
        self.extract_sel_btn.clicked.connect(self.extract_selected)
        self.extract_sel_btn.setEnabled(False)
        self.extract_sel_btn.setMinimumWidth(160)
        self.extract_all_btn = QPushButton("Extract All")
        self.extract_all_btn.clicked.connect(self.extract_all)
        self.extract_all_btn.setEnabled(False)
        self.extract_all_btn.setMinimumWidth(160)
        btn_row.addWidget(self.extract_sel_btn)
        btn_row.addWidget(self.extract_all_btn)
        btn_row.addStretch()
        layout.addLayout(btn_row)

    def browse_input(self):
        path, _ = QFileDialog.getOpenFileName(self, "Select STFS Package")
        if path:
            self.input_edit.setText(path)
            gname = stfs_read_game_name(path)
            if gname:
                safe_name = "".join(c if c.isalnum() or c in " -._" else "_" for c in gname).strip()
                self.output_edit.setText(os.path.join(os.path.dirname(path) or ".", safe_name))
            else:
                stem = os.path.splitext(os.path.basename(path))[0]
                self.output_edit.setText(os.path.join(os.path.dirname(path) or ".", stem + "_extracted"))
            self.populate_tree(path)

    def browse_output(self):
        path = QFileDialog.getExistingDirectory(self, "Select Output Directory")
        if path:
            self.output_edit.setText(path)

    def populate_tree(self, path):
        self.tree.clear()
        self.entries_cache.clear()
        gname = stfs_read_game_name(path)
        if gname:
            self.main.setWindowTitle(f"XBLA Tool - {gname}")
            self.game_label.setText(gname)
            self.game_label.show()
        else:
            self.game_label.hide()
        try:
            entries = list_live_pirs(path)
            self.entries_cache.extend(entries)
            for e in entries:
                item = SortableTreeItem()
                if not e["is_dir"]:
                    item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
                    item.setCheckState(0, Qt.CheckState.Unchecked)
                else:
                    item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsUserCheckable)
                item.setText(1, "Directory" if e["is_dir"] else "File")
                item.setText(2, e["path"])
                if e["is_dir"]:
                    item.setText(3, "")
                    item.setData(3, Qt.ItemDataRole.UserRole, -1)
                else:
                    item.setText(3, _format_size(e["size"]))
                    item.setData(3, Qt.ItemDataRole.UserRole, e["size"])
                item.setData(0, Qt.ItemDataRole.UserRole, e["id"])
                self.tree.addTopLevelItem(item)
            self.update_status()
            self.extract_sel_btn.setEnabled(True)
            self.extract_all_btn.setEnabled(True)
            self.select_all_btn.setEnabled(True)
            self.deselect_all_btn.setEnabled(True)
        except Exception as ex:
            QMessageBox.critical(self, "Error", str(ex))
            self.status_label.setText("Failed to read package")
            self.game_label.hide()

    def on_item_clicked(self, item, column):
        if column == 0:
            entry_id = item.data(0, Qt.ItemDataRole.UserRole)
            for e in self.entries_cache:
                if e["id"] == entry_id and not e["is_dir"]:
                    self.update_status()
                    return

    def update_status(self):
        total = sum(1 for e in self.entries_cache if not e["is_dir"])
        checked = sum(
            1 for i in range(self.tree.topLevelItemCount())
            if self.tree.topLevelItem(i).checkState(0) == Qt.CheckState.Checked
        )
        if checked:
            self.status_label.setText(f"{checked} of {total} file(s) selected")
        else:
            self.status_label.setText(f"{len(self.entries_cache)} item(s) found")

    def select_all(self):
        for i in range(self.tree.topLevelItemCount()):
            item = self.tree.topLevelItem(i)
            entry_id = item.data(0, Qt.ItemDataRole.UserRole)
            for e in self.entries_cache:
                if e["id"] == entry_id and not e["is_dir"]:
                    item.setCheckState(0, Qt.CheckState.Checked)
                    break
        self.update_status()

    def deselect_all(self):
        for i in range(self.tree.topLevelItemCount()):
            item = self.tree.topLevelItem(i)
            entry_id = item.data(0, Qt.ItemDataRole.UserRole)
            for e in self.entries_cache:
                if e["id"] == entry_id and not e["is_dir"]:
                    item.setCheckState(0, Qt.CheckState.Unchecked)
                    break
        self.update_status()

    def _get_checked_ids(self):
        ids = set()
        for i in range(self.tree.topLevelItemCount()):
            item = self.tree.topLevelItem(i)
            if item.checkState(0) == Qt.CheckState.Checked:
                ids.add(item.data(0, Qt.ItemDataRole.UserRole))
        return ids

    def _do_extract(self, selected_ids):
        src = self.input_edit.text().strip()
        dst = self.output_edit.text().strip()
        if not src or not dst:
            QMessageBox.critical(self, "Error", "Select an input file and output folder.")
            return
        if not self.entries_cache:
            QMessageBox.critical(self, "Error", "No package contents loaded.")
            return
        try:
            self._progress_stfs_extract(src, dst, selected_ids)
            self.clean_extracted(dst)
        except Exception as ex:
            QMessageBox.critical(self, "Error", str(ex))

    def _progress_stfs_extract(self, src, dst, selected_ids):
        magic, start, offset, ft_data = _parse_stfs_header(src)
        os.makedirs(dst, exist_ok=True)

        file_entries = [e for e in self.entries_cache if not e["is_dir"]]
        if selected_ids is not None:
            file_entries = [e for e in file_entries if e["id"] in selected_ids]

        if not file_entries:
            return

        total = len(file_entries)
        progress = QProgressDialog("Extracting files...", "Cancel", 0, total, self)
        progress.setWindowTitle("Extracting STFS Package")
        progress.setWindowModality(Qt.WindowModality.WindowModal)
        progress.setMinimumDuration(0)
        progress.setFixedWidth(700)
        progress.setValue(0)

        start_time = time.time()
        total_bytes = 0

        for idx, entry in enumerate(file_entries):
            if progress.wasCanceled():
                break

            elapsed = time.time() - start_time
            speed = total_bytes / (1024 * 1024) / elapsed if elapsed > 0 else 0
            label = f"({idx + 1}/{total}) {entry['path']}\n{_format_size(total_bytes)} extracted  @  {speed:.1f} MB/s"
            progress.setLabelText(label)
            progress.setValue(idx)
            QApplication.processEvents()

            out_path = os.path.join(dst, entry["path"])
            os.makedirs(os.path.dirname(out_path), exist_ok=True)

            data = _read_entry_bytes(src, entry, start, offset)
            with open(out_path, "wb") as f:
                f.write(data)

            total_bytes += entry["size"]

        progress.setValue(total)
        if not progress.wasCanceled():
            elapsed = time.time() - start_time
            speed = total_bytes / (1024 * 1024) / elapsed if elapsed > 0 else 0
            QMessageBox.information(
                self, "Done",
                f"Extracted {len(file_entries)} file(s) to:\n{dst}\n"
                f"({_format_size(total_bytes)} in {elapsed:.1f}s @ {speed:.1f} MB/s)"
            )

    def extract_selected(self):
        ids = self._get_checked_ids()
        self._do_extract(ids or None)

    def extract_all(self):
        self._do_extract(None)

    def clean_extracted(self, root_dir):
        for root, dirs, files in os.walk(root_dir, topdown=False):
            for name in files:
                if name in JUNK_NAMES:
                    os.remove(os.path.join(root, name))
            for name in dirs:
                p = os.path.join(root, name)
                try:
                    if not os.listdir(p):
                        os.rmdir(p)
                except OSError:
                    pass


class IsoTab(QWidget):
    def __init__(self, main_window):
        super().__init__()
        self.main = main_window
        self.entries_cache = []
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        row1 = QHBoxLayout()
        row1.setSpacing(8)
        label1 = QLabel("ISO Image:")
        label1.setFixedWidth(110)
        self.input_edit = QLineEdit()
        self.input_edit.setPlaceholderText("Select an Xbox ISO file...")
        browse_btn = QPushButton("Browse")
        browse_btn.clicked.connect(self.browse_input)
        browse_btn.setFixedWidth(100)
        row1.addWidget(label1)
        row1.addWidget(self.input_edit, 1)
        row1.addWidget(browse_btn)
        layout.addLayout(row1)

        row2 = QHBoxLayout()
        row2.setSpacing(8)
        label2 = QLabel("Output Folder:")
        label2.setFixedWidth(110)
        self.output_edit = QLineEdit()
        self.output_edit.setPlaceholderText("Select an output folder...")
        browse_out_btn = QPushButton("Browse")
        browse_out_btn.clicked.connect(self.browse_output)
        browse_out_btn.setFixedWidth(100)
        row2.addWidget(label2)
        row2.addWidget(self.output_edit, 1)
        row2.addWidget(browse_out_btn)
        layout.addLayout(row2)

        sep1 = QFrame()
        sep1.setObjectName("separator")
        sep1.setFrameShape(QFrame.Shape.HLine)
        layout.addWidget(sep1)

        section_label = QLabel("ISO Contents")
        section_label.setStyleSheet("font-weight: bold; font-size: 10pt; color: #cccccc; padding: 2px 0;")
        layout.addWidget(section_label)

        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(["", "Type", "Name", "Size"])
        self.tree.setColumnCount(4)
        self.tree.setRootIsDecorated(False)
        self.tree.setAnimated(True)
        self.tree.setAlternatingRowColors(True)
        self.tree.setStyleSheet("""
            QTreeWidget { alternate-background-color: #2a2a2a; }
        """)
        self.tree.setSortingEnabled(True)
        self.tree.itemClicked.connect(self.on_item_clicked)

        header = self.tree.header()
        header.setStretchLastSection(False)
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        header.resizeSection(0, 36)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed)
        header.resizeSection(1, 90)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Fixed)
        header.resizeSection(3, 110)
        layout.addWidget(self.tree, 1)

        toolbar = QHBoxLayout()
        toolbar.setSpacing(8)
        self.select_all_btn = QPushButton("Select All")
        self.select_all_btn.clicked.connect(self.select_all)
        self.select_all_btn.setEnabled(False)
        self.deselect_all_btn = QPushButton("Deselect All")
        self.deselect_all_btn.clicked.connect(self.deselect_all)
        self.deselect_all_btn.setEnabled(False)
        self.game_label = QLabel("")
        self.game_label.setStyleSheet("color: #88ccff; font-weight: bold; font-size: 9pt;")
        self.game_label.hide()
        self.status_label = QLabel("Ready")
        self.status_label.setObjectName("status")
        toolbar.addWidget(self.select_all_btn)
        toolbar.addWidget(self.deselect_all_btn)
        toolbar.addWidget(self.game_label)
        toolbar.addStretch()
        toolbar.addWidget(self.status_label)
        layout.addLayout(toolbar)

        sep2 = QFrame()
        sep2.setObjectName("separator")
        sep2.setFrameShape(QFrame.Shape.HLine)
        layout.addWidget(sep2)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(12)
        self.extract_sel_btn = QPushButton("Extract Selected")
        self.extract_sel_btn.clicked.connect(self.extract_selected)
        self.extract_sel_btn.setEnabled(False)
        self.extract_sel_btn.setMinimumWidth(160)
        self.extract_all_btn = QPushButton("Extract All")
        self.extract_all_btn.clicked.connect(self.extract_all)
        self.extract_all_btn.setEnabled(False)
        self.extract_all_btn.setMinimumWidth(160)
        self.create_btn = QPushButton("Create ISO from Folder...")
        self.create_btn.clicked.connect(self.create_iso_from_folder)
        self.create_btn.setMinimumWidth(180)
        btn_row.addStretch()
        btn_row.addWidget(self.extract_sel_btn)
        btn_row.addWidget(self.extract_all_btn)
        btn_row.addWidget(self.create_btn)
        btn_row.addStretch()
        layout.addLayout(btn_row)

    def browse_input(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Select Xbox ISO Image",
            filter="ISO Files (*.iso);;All Files (*)"
        )
        if path:
            self.input_edit.setText(path)
            stem = os.path.splitext(os.path.basename(path))[0]
            self.output_edit.setText(os.path.join(os.path.dirname(path) or ".", stem + "_extracted"))
            self.populate_tree(path)

    def browse_output(self):
        path = QFileDialog.getExistingDirectory(self, "Select Output Directory")
        if path:
            self.output_edit.setText(path)

    def populate_tree(self, path):
        self.tree.clear()
        self.entries_cache.clear()
        try:
            entries = list_iso(path)
            self.entries_cache.extend(entries)
            game_name = os.path.splitext(os.path.basename(path))[0]
            self.main.setWindowTitle(f"XBLA Tool - {game_name}")
            self.game_label.setText(game_name)
            self.game_label.show()
            for e in entries:
                item = SortableTreeItem()
                item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
                item.setCheckState(0, Qt.CheckState.Unchecked)
                item.setText(1, "Directory" if e["is_dir"] else "File")
                item.setText(2, e["path"])
                if e["is_dir"]:
                    item.setText(3, "")
                    item.setData(3, Qt.ItemDataRole.UserRole, -1)
                else:
                    item.setText(3, _format_size(e["size"]))
                    item.setData(3, Qt.ItemDataRole.UserRole, e["size"])
                item.setData(0, Qt.ItemDataRole.UserRole, e["path"])
                self.tree.addTopLevelItem(item)
            self.update_status()
            self.extract_sel_btn.setEnabled(True)
            self.extract_all_btn.setEnabled(True)
            self.select_all_btn.setEnabled(True)
            self.deselect_all_btn.setEnabled(True)
        except XisoError as ex:
            QMessageBox.critical(self, "Error", str(ex))
            self.status_label.setText("Failed to read ISO")
            self.game_label.hide()

    def on_item_clicked(self, item, column):
        if column == 0:
            self.update_status()

    def update_status(self):
        checked = sum(
            1 for i in range(self.tree.topLevelItemCount())
            if self.tree.topLevelItem(i).checkState(0) == Qt.CheckState.Checked
        )
        if checked:
            self.status_label.setText(f"{checked} item(s) selected")
        else:
            self.status_label.setText(f"{len(self.entries_cache)} item(s) found")

    def select_all(self):
        for i in range(self.tree.topLevelItemCount()):
            item = self.tree.topLevelItem(i)
            item.setCheckState(0, Qt.CheckState.Checked)
        self.update_status()

    def deselect_all(self):
        for i in range(self.tree.topLevelItemCount()):
            self.tree.topLevelItem(i).setCheckState(0, Qt.CheckState.Unchecked)
        self.update_status()

    def _get_checked_paths(self):
        paths = set()
        for i in range(self.tree.topLevelItemCount()):
            item = self.tree.topLevelItem(i)
            if item.checkState(0) == Qt.CheckState.Checked:
                paths.add(item.data(0, Qt.ItemDataRole.UserRole))
        return paths

    def _expand_dir_selections(self, checked):
        if checked is None:
            return None
        expanded = set()
        for path in checked:
            entry = next((e for e in self.entries_cache if e["path"] == path), None)
            if entry and entry["is_dir"]:
                prefix = path if path.endswith("/") else path + "/"
                for e in self.entries_cache:
                    if not e["is_dir"] and e["path"].startswith(prefix):
                        expanded.add(e["path"])
            else:
                expanded.add(path)
        return expanded if expanded else None

    def _progress_extract(self, src, dst, file_paths):
        lseek_off, root_sector, _ = _find_volume(src)
        os.makedirs(dst, exist_ok=True)

        all_files = [e for e in self.entries_cache if not e["is_dir"]]
        if file_paths is not None:
            target = set(file_paths)
            all_files = [e for e in all_files if e["path"] in target]

        if not all_files:
            return

        total = len(all_files)
        progress = QProgressDialog("Extracting files...", "Cancel", 0, total, self)
        progress.setWindowTitle("Extracting ISO")
        progress.setWindowModality(Qt.WindowModality.WindowModal)
        progress.setMinimumDuration(0)
        progress.setFixedWidth(700)
        progress.setValue(0)

        start_time = time.time()
        total_bytes = 0

        for idx, entry in enumerate(all_files):
            if progress.wasCanceled():
                break

            elapsed = time.time() - start_time
            speed = total_bytes / (1024 * 1024) / elapsed if elapsed > 0 else 0

            label = f"({idx + 1}/{total}) {entry['path']}\n{_format_size(total_bytes)} extracted  @  {speed:.1f} MB/s"
            progress.setLabelText(label)
            progress.setValue(idx)
            QApplication.processEvents()

            file_out = os.path.join(dst, entry["path"])
            os.makedirs(os.path.dirname(file_out), exist_ok=True)
            data_start = entry["start_sector"] * SECTOR_SIZE + lseek_off
            with open(src, "rb") as f_src:
                f_src.seek(data_start)
                data = f_src.read(entry["size"])
            with open(file_out, "wb") as f_dst:
                f_dst.write(data)
            total_bytes += entry["size"]

        progress.setValue(total)
        if not progress.wasCanceled():
            elapsed = time.time() - start_time
            speed = total_bytes / (1024 * 1024) / elapsed if elapsed > 0 else 0
            QMessageBox.information(
                self, "Done",
                f"Extracted {len(all_files)} file(s) to:\n{dst}\n"
                f"({_format_size(total_bytes)} in {elapsed:.1f}s @ {speed:.1f} MB/s)"
            )

    def extract_selected(self):
        src = self.input_edit.text().strip()
        dst = self.output_edit.text().strip()
        if not src or not dst:
            QMessageBox.critical(self, "Error", "Select an input file and output folder.")
            return
        if not self.entries_cache:
            QMessageBox.critical(self, "Error", "No ISO contents loaded.")
            return
        checked = self._get_checked_paths() or None
        checked = self._expand_dir_selections(checked)
        try:
            self._progress_extract(src, dst, checked)
        except XisoError as ex:
            QMessageBox.critical(self, "Error", str(ex))

    def extract_all(self):
        src = self.input_edit.text().strip()
        dst = self.output_edit.text().strip()
        if not src or not dst:
            QMessageBox.critical(self, "Error", "Select an input file and output folder.")
            return
        try:
            self._progress_extract(src, dst, None)
        except XisoError as ex:
            QMessageBox.critical(self, "Error", str(ex))

    def create_iso_from_folder(self):
        src_dir = QFileDialog.getExistingDirectory(self, "Select Folder to Convert to ISO")
        if not src_dir:
            return
        stem = os.path.basename(src_dir.rstrip("/\\"))
        default_name = os.path.join(os.path.dirname(src_dir), stem + ".iso")
        dst_path, _ = QFileDialog.getSaveFileName(
            self, "Save ISO As",
            default_name,
            "ISO Files (*.iso);;All Files (*)"
        )
        if not dst_path:
            return
        try:
            create_iso(src_dir, dst_path)
            QMessageBox.information(self, "Done", f"ISO created:\n{dst_path}")
        except XisoError as ex:
            QMessageBox.critical(self, "Error", str(ex))


class MainWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("XBLA Tool - Select a file to begin")
        self.setMinimumSize(720, 560)
        self.resize(780, 600)
        self.setStyleSheet(self._dark_style())
        self._build_ui()

    def _dark_style(self):
        return """
        QWidget {
            background-color: #1e1e1e;
            color: #e0e0e0;
            font-family: "Segoe UI", "Noto Sans", sans-serif;
            font-size: 10pt;
        }
        QTabWidget::pane {
            border: 1px solid #3d3d3d;
            border-radius: 4px;
            background-color: #1e1e1e;
        }
        QTabBar::tab {
            background-color: #2a2a2a;
            color: #aaaaaa;
            border: 1px solid #3d3d3d;
            border-bottom: none;
            border-top-left-radius: 4px;
            border-top-right-radius: 4px;
            padding: 8px 20px;
            margin-right: 2px;
        }
        QTabBar::tab:selected {
            background-color: #1e1e1e;
            color: #e0e0e0;
            border-bottom: 1px solid #1e1e1e;
        }
        QTabBar::tab:hover:!selected {
            background-color: #333333;
        }
        QLineEdit {
            background-color: #2d2d2d;
            color: #e0e0e0;
            border: 1px solid #3d3d3d;
            border-radius: 4px;
            padding: 6px 8px;
            selection-background-color: #3d6a9c;
        }
        QLineEdit:focus {
            border-color: #3d6a9c;
        }
        QPushButton {
            background-color: #333333;
            color: #e0e0e0;
            border: 1px solid #444444;
            border-radius: 4px;
            padding: 6px 18px;
            min-height: 22px;
        }
        QPushButton:hover {
            background-color: #3d3d3d;
            border-color: #555555;
        }
        QPushButton:pressed {
            background-color: #4a4a4a;
        }
        QPushButton:disabled {
            background-color: #282828;
            color: #555555;
            border-color: #333333;
        }
        QTreeWidget {
            background-color: #252525;
            color: #e0e0e0;
            border: 1px solid #333333;
            border-radius: 4px;
            outline: none;
        }
        QTreeWidget::item {
            padding: 4px 0px;
            border-bottom: 1px solid #2a2a2a;
        }
        QTreeWidget::item:selected {
            background-color: transparent;
        }
        QTreeWidget::item:hover {
            background-color: #2a2a2a;
        }
        QHeaderView::section {
            background-color: #2a2a2a;
            color: #cccccc;
            border: none;
            border-bottom: 1px solid #3d3d3d;
            border-right: 1px solid #3d3d3d;
            padding: 6px 8px;
            font-weight: bold;
        }
        QFrame#separator {
            background-color: #333333;
            max-height: 1px;
        }
        QLabel#status {
            color: #888888;
            font-size: 9pt;
        }
        """

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        self.tabs = QTabWidget()
        self.stfs_tab = StfsTab(self)
        self.iso_tab = IsoTab(self)
        self.tabs.addTab(self.stfs_tab, "STFS Package")
        self.tabs.addTab(self.iso_tab, "ISO Image")
        layout.addWidget(self.tabs)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setAttribute(Qt.ApplicationAttribute.AA_UseStyleSheetPropagationInWidgetStyles, False)
    win = MainWindow()
    win.show()
    sys.exit(app.exec())
