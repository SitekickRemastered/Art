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

# archive.ripper.ps1
This powershell script will rip all .swf files from archive.org from ytv.com/gamepad/games/.  You can modify the url to effectively do any website, but keep in mind that it renames the file to the folder it's found in, so if a website had multiple games in one directory, the script will only save the last game it finds.  Works great for ytv.com due to how they structured the site.

This script was needed due to how archive.org now handles swf files.  This basically just adds "oe_" to the url when it finds an swf file, and saves/renames it if the file exists, then moves on to the next file.

## Usage
- Be a Windows user
- Run in Powershell
- Check the newly created SWFDownloads folder in the location you ran the script from.  One at a time, you'll see new swf files appear.  At time of writing, there are 71 games from YTV.com's archive.org page.