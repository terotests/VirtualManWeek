Couple of issues noticed:

- ✅ FIXED: Import database Should not do anything else than copy the imported database to the AppData ... Roaming folder and then Switch to the new database that was imported. If a database with same name exists, ask if you want to overwrite or not.

  - Modified `import_database()` method to copy to AppData instead of overwriting current database
  - Added check for existing files with overwrite confirmation
  - Now preserves the original current database and switches to the imported one
  - Starts file dialog from user's home directory instead of current database location
  - Added forced icon update after database switch to immediately show stopped (red) status

- ✅ FIXED: When I switch mode, the tray icon is not automatically re-rendered so it stays in the idle color ( yellow ) some time.

  - Added `force_update` parameter to `_apply_icon()` method
  - Force icon updates when switching modes, stopping tracking, or changing projects

- ✅ FIXED: The menu item "Stop Tracking" menu item should be just under the "Current:" and maybe if possible of icon about "Stop"

  - Moved "Stop Tracking" to be right under "Current:" status
  - Added system stop icon (SP_MediaStop) to the menu item

- ✅ FIXED: The menu item "Exit" should have a separator before it.
  - Added separator before the "Exit" menu item
