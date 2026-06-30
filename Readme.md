XBLA Extract
===============

A tool for extracting and creating Xbox 360 content. Supports two file formats:

- **STFS Package files** (LIVE, PIRS, and CON formats) — the container files used by Xbox 360 digital games and DLC
- **Xbox ISO images** (XGD1, XGD2, XGD3, original Xbox) — game disc images

The GUI lets you browse the contents of a package or ISO and extract individual files, as well as create new ISO images from a folder.

What you need
-------------

- Python 3 (version 3.6 or newer)
- PyQt6 for the graphical interface
- The files in this folder

Installing PyQt6
----------------

Choose the command for your operating system:

## Windows

head here install python and click add to path : https://www.python.org/downloads/windows/ 

open the powershell/termainal

Type:
```
pip install PyQt6
``` 

## Linux

Arch/Artix/CachyOS/EndeavourOS/XeroLinux:
```
  sudo pacman -S python-pyqt6
```
Fedora/Nobara:
```
  sudo dnf install python3-pyqt6 python3-pyqt6-svg
```
openSUSE (Tumbleweed/Leap):
```
  sudo zypper install python313-PyQt6
```
PikaOS:
```
  sudo apt install python3-pyqt6.qtsvg
```
Ubuntu 25.10 (if you encounter GUI issues, also install):
```
  sudo apt install python3-pyqt6
```
If your distribution is not listed, install PyQt6 via pip:
```
  pip install PyQt6
```
What this does
--------------

### STFS Packages

Xbox 360 games and DLC are distributed inside STFS package files. These files have no file extension or sometimes have a `.pirs` extension. Inside them are the actual game files like `default.xex` (the game executable), textures, sounds, and other assets. This tool opens the STFS package and writes those files to a folder on your computer so you can view or modify them.

### Xbox ISO Images

Xbox and Xbox 360 game discs use the XDVDFS filesystem (also called XISO). This tool can list, extract, and create these ISO images. It supports original Xbox discs and Xbox 360 discs across all XGD revisions (XGD1, XGD2, XGD3). The ISO tab in the GUI works the same way as the STFS tab: browse the file tree, check what you want, and extract. You can also create an Xbox ISO from any folder on your computer.

How to use the graphical version
---------------------------------

1. Open a terminal (Command Prompt on Windows, Terminal on Mac/Linux).

2. Navigate to the folder containing these files. For example:

   ```
   cd C:\Users\YourName\Downloads\XBLA-Extract
   ```

3. Run the GUI program:

   ```
   start.bat
   ```
## Linux

   On some systems you might need to use `python` instead of `python3`:

   ```
   XBLA.run
   ```

4. A window will appear with two tabs at the top:

   **STFS Package tab:**
   - **STFS Package** -- a text box and "Browse" button to select the input file
   - **Output Folder** -- a text box and "Browse" button to choose where to save files
   - **Package Contents** -- a list showing every file and directory inside the package, each with a checkbox
   - **Select All / Deselect All** -- buttons to check or uncheck all files at once
   - **Extract Selected** -- extracts only the files you have checked
   - **Extract All** -- extracts every file in the package regardless of checkboxes

   **ISO Image tab:**
   - **ISO File** -- a text box and "Browse" button to select a `.iso` file
   - **Output Folder** -- a text box and "Browse" button to choose where to save files
   - **ISO Contents** -- a tree showing every file and directory inside the ISO, each with a checkbox (directories can be checked to extract everything inside them)
   - **Select All / Deselect All** -- buttons to check or uncheck all files at once
   - **Extract Selected** -- extracts only the checked files
   - **Extract All** -- extracts every file in the ISO
   - **Create ISO from Folder...** -- packs a folder on your computer into a valid Xbox ISO image

5. **STFS tab:** Click "Browse" next to "STFS Package" and select your STFS file (a LIVE, PIRS, or CON file). If the file has no extension, set the file browser to show "All Files" so you can see it.

6. **STFS tab:** The output folder path will automatically fill in. It will be a folder named after your input file inside the output folder you choose. For example, if your input file is "007 - World Is Not Enough", the files will go into "007 - World Is Not Enough" inside your chosen output folder. You can change this by clicking "Browse" next to "Output Folder".

7. Check the boxes next to the files you want to extract, or leave them unchecked to select none.

8. Click "Extract Selected" to extract only the checked files, or "Extract All" to extract everything.

9. A progress dialog shows the current file being extracted, the total count and size, and the transfer speed.

10. When finished, the tool cleans up the output folder by removing junk files (like Thumbs.db) and any empty folders that are not needed.

**ISO tab:**

1. Switch to the "ISO Image" tab at the top of the window.

2. Click "Browse" next to "ISO File" and select a `.iso` file (original Xbox or Xbox 360 game disc image).

3. The tree will populate with the files and directories from the ISO. Directories have checkboxes too -- checking a directory selects all files inside it.

4. Choose an output folder and click "Extract Selected" or "Extract All" to extract files.

5. To create an ISO from a folder on your computer, click **"Create ISO from Folder..."**, pick a source folder, then pick a destination path for the `.iso` file. The tool will create a valid Xbox ISO image containing all the files from that folder.

How to use the command-line version
-----------------------------------

### STFS Extraction

If you prefer the command line or cannot run the GUI:

1. Open a terminal and navigate to the folder.

2. Run:

   ```
   python3 stfs_extract.py "path/to/your/STFS/file"
   ```

   This will create a folder named after the input file with "_extracted" added.

   To specify the output folder:

   ```
   python3 stfs_extract.py "path/to/your/STFS/file" "path/to/output/folder"
   ```

### ISO Operations

The ISO module (`xiso.py`) can also be used from the command line:

List files in an ISO:

```
python3 xiso.py list "path/to/game.iso"
```

Extract all files from an ISO:

```
python3 xiso.py extract "path/to/game.iso" "output/folder"
```

Create an ISO from a folder:

```
python3 xiso.py create "source/folder" "output.iso"
```

What gets extracted
-------------------

The tool extracts all files stored inside the STFS package. Typically these include:

- `default.xex` -- the game executable
- PNG images -- textures or title screens
- Other game asset files

The tool will print what it finds, including the file size and type.

Troubleshooting
---------------

"I get 'python3' is not recognized": Try using `python` instead of `python3`. On Windows, you might need `py`:

  py stfs_extract_gui.py

"ModuleNotFoundError: No module named 'PyQt6'": PyQt6 is not installed. See the "Installing PyQt6" section above for your operating system.

"The window opens but nothing happens when I click Extract": The progress prints to the terminal where you launched the program. Check the terminal for error messages.

"It says 'Not a LIVE/PIRS/CON file'": The file you selected is not a valid STFS package. Make sure you have the correct file. Xbox 360 game containers start with the bytes LIVE, PIRS, or CON.

"It says 'File too small'": The file is damaged or is not a complete STFS package. The file must be at least 53,248 bytes (0xD000).

"No files were extracted": The STFS package might be empty or use a format this tool does not support. Some packages have a different internal structure.

"Not a valid Xbox ISO image (no XDVDFS volume descriptor found)": The file is not a valid Xbox or Xbox 360 ISO. Make sure you have a genuine game disc image.

"Source directory not found": When creating an ISO, the source folder you specified does not exist.

"No files found in source directory": When creating an ISO, the source folder is empty or contains no files.

License
-------

MIT License. See the LICENSE file for details.
