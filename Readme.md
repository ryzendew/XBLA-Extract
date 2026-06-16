STFS Extractor
==============

A tool to extract files from Xbox 360 STFS package files (LIVE, PIRS, and CON formats). These are the container files used by Xbox 360 digital games and DLC. The GUI lets you browse the contents of a package and extract individual files.

What you need
-------------

- Python 3 (version 3.6 or newer)
- PyQt6 for the graphical interface
- The files in this folder

Installing PyQt6
----------------

Choose the command for your operating system:

Arch/Artix/CachyOS/EndeavourOS/XeroLinux:

  sudo pacman -S python-pyqt6

Fedora/Nobara:

  sudo dnf install python3-pyqt6 python3-pyqt6-svg

openSUSE (Tumbleweed/Leap):

  sudo zypper install python313-PyQt6

PikaOS:

  sudo apt install python3-pyqt6.qtsvg

Ubuntu 25.10 (if you encounter GUI issues, also install):

  sudo apt install python3-pyqt6

If your distribution is not listed, install PyQt6 via pip:

  pip install PyQt6

What this does
--------------

Xbox 360 games and DLC are distributed inside STFS package files. These files have no file extension or sometimes have a `.pirs` extension. Inside them are the actual game files like `default.xex` (the game executable), textures, sounds, and other assets. This tool opens the STFS package and writes those files to a folder on your computer so you can view or modify them.

How to use the graphical version
---------------------------------

1. Open a terminal (Command Prompt on Windows, Terminal on Mac/Linux).

2. Navigate to the folder containing these files. For example:

   ```
   cd C:\Users\YourName\Downloads\XBLA-Automation-master
   ```

3. Run the GUI program:

   ```
   python3 stfs_extract_gui.py
   ```

   On some systems you might need to use `python` instead of `python3`:

   ```
   python stfs_extract_gui.py
   ```

4. A window will appear with the following controls:
   - **STFS Package** -- a text box and "Browse" button to select the input file
   - **Output Folder** -- a text box and "Browse" button to choose where to save files
   - **Package Contents** -- a list showing every file and directory inside the package, each with a checkbox
   - **Select All / Deselect All** -- buttons to check or uncheck all files at once
   - **Extract Selected** -- extracts only the files you have checked
   - **Extract All** -- extracts every file in the package regardless of checkboxes

5. Click "Browse" next to "STFS Package" and select your STFS file (a LIVE, PIRS, or CON file). If the file has no extension, set the file browser to show "All Files" so you can see it.

6. The output folder path will automatically fill in. It will be a folder named after your input file inside the output folder you choose. For example, if your input file is "007 - World Is Not Enough", the files will go into "007 - World Is Not Enough" inside your chosen output folder. You can change this by clicking "Browse" next to "Output Folder".

7. Check the boxes next to the files you want to extract, or leave them unchecked to select none.

8. Click "Extract Selected" to extract only the checked files, or "Extract All" to extract everything.

9. The extraction progress prints to the terminal where you launched the program. When it finishes, a pop-up will say "Extraction complete".

10. The tool will clean up the output folder by removing junk files (like Thumbs.db) and any empty folders that are not needed.

How to use the command-line version
-----------------------------------

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

License
-------

MIT License. See the LICENSE file for details.
