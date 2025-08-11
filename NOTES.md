Couple of issues noticed:

- ✅ FIXED: Editing the modes is now possible in the "Manage Modes" and "Edit selected" where you can change tha name. If node is renames: all the modes stored in to the time_entries table should also be renamed. Also, before renaming, it should be checked that the name is unique in case insensitive manner and also after removing spaces ( trimming ), so "Abc" and " abc" should be the same name and renaming the mode to the same name should never be allowed. In that case there should be error dialog saying that can not change the name to mode which already exists in the database.

  - Created `rename_mode_everywhere()` function in models.py that updates both modes table and time_entries table
  - Created `check_mode_name_conflict()` function for robust name validation (case-insensitive, trimmed)
  - Updated mode dialog's edit functionality to use new validation and renaming
  - When renaming a mode, all existing time entries using that mode are automatically updated
  - Error dialog shows clear message about name conflicts with case-insensitive/trimmed comparison
  - Success dialog confirms that time entries have been updated automatically
  - Improved validation also applied to adding new modes

- ✅ FIXED: I would like to have a Dialog where I could have a menu item "Edit hours" where I can have all the recordings for today and then I can edit the recorded time for each entry so that if I make the time "less" then 1) if next recorded time starts immediately after the time ( 3 min considered thresold ) then move the next time slot to start earlier, for example if I have forgotten some mode on for 1 hour and then switch to second mode, which was the real work I was doing,I can adjust the first recording to end earlier and at the sime time the next recording will be automatically moved to start a bit earlier the same amount.

  - Created `EditHoursDialog` class in `edit_hours_dialog.py`
  - Added "Edit Hours" menu item to tray context menu with file detail icon
  - Dialog shows all today's time entries in a table with Mode, Project, Start Time, End Time, Duration, and Description
  - End times are editable using QTimeEdit widgets with improved wider layout
  - Smart time adjustment: when shortening an entry, if the next entry starts within 3 minutes, it automatically adjusts the next entry's start time
  - **Color coding**: Modified entries are highlighted in light blue for visual feedback
  - **Real-time updates**: Duration automatically updates when end time is changed for both current and next entries
  - **Validation**: Prevents setting end time before start time with user-friendly error message
  - **Confirmation dialog**: Shows detailed summary of all changes before applying with "Are you sure?" confirmation
  - **Proportional time scaling**: When adjusting entries, properly scales active/idle/manual time components
  - All changes are saved to the database when clicking "Save Changes"
  - Proper error handling and user feedback

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
