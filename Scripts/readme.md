# Process.bat
This script should be placed in the sprites folder after exporting all sprites from a chip library SWF with [JPEXS Decompiler](https://github.com/jindrapetrik/jpexs-decompiler). When run, it will properly rename all chip icons based on the folder that they were placed in after the decompiler exports them.  It will place them in **%sourceDir%\Processed** 
## Usage
- Open a chiplibrary .swf with [JPEXS Decompiler](https://github.com/jindrapetrik/jpexs-decompiler)
- Select the <ins>sprites</ins> directory
- Select all sprites, right click, export selection.  Select both checkboxes, PNG, 2500%.  Press OK.
- Select your save directory, press Open.
- Wait patiently for the process to complete.
- Copy Process.bat to the <ins>sprites</ins> directory.
- Run Process.bat, check the Processed folder when complete.
