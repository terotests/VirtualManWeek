# VirtualManWeek Changelog

This changelog tracks all notable changes to the VirtualManWeek time tracking application.

## Recent Issues and Fixes

- ✅ COMPLETED: There is still issue, when starting the application, during startp there is the Project + select mode dialog, if I select "Start tracking" the system tray icon is not immediately updated so it stays "red" even if I have started tracking. The icon will update after some seconds when the clock moves forward.

  - **Fixed startup dialog icon update**:
    - Added `force_update=True` parameter to `_apply_icon()` calls in `_show_startup_dialog()` method
    - Tray icon now updates immediately when tracking starts from the startup dialog
    - No longer need to wait for the polling timer to update the icon

- ✅ COMPLETED: When I stop and start the program OR change the database, during startup the program should give immediately the select Project + Select Mode Dialog ( a new dialog ) where the last time entry has been pre-selected as the Project and last time entrys mode has been pre-selected as the new active mode. Basicly this should very similar to the "Switch mode" dialog, but in the startup there should also be possiblity to select the Project so that it is pre-selected based on the last entry in the database. This way you do not
  need to always select the Project again if switching between databases.

  - **Created startup project and mode selection dialog**:
    - Created `StartupDialog` class that appears on app startup and database switches
    - Pre-selects project and mode based on the last time entry in the database
    - Allows selecting "No Project" or any available project from the dropdown
    - Supports both existing modes from dropdown and custom mode entry
    - Gracefully handles empty databases with sensible defaults
    - User can cancel to start with default settings (No Project, Idle mode)

- ✅ COMPLETED: When editing the hours using the "Edit Hours" , the edits are not reflected in the table, for example, if I change the project, the new selected project is not visible in the table.

  - **Fixed Edit Hours table refresh issue**:
    - Updated `refresh_table_display()` method to properly look up project information
    - When project ID is changed, the method now queries the database for current project details
    - Table now correctly displays updated project names and codes after editing
    - All changes (mode, project, times, duration, description) are properly reflected in the table

- ✅ COMPLETED: I would like to move the "Exit" to the top of the menu because you click the exit quite easily. Move the Exit to the top and move the disabled database name from the top of the Tray menu to the bottom so that accidental click does not cause any UI action. This is a bit of a usability problem for me at least. Also, I would like to have the databases listed to the Database menu so that I do not need to go to the filesystem to select them. So, just like with other menus, have a separator and the potential databases that you can select could be on top of that separator.

  - **Reorganized tray menu for better usability**:
    - Moved "Exit" action to the top of the menu for safety
    - Moved database name display to the bottom as a disabled (non-clickable) item
    - Added `_get_available_databases()` method to discover database files in AppData folder
    - Enhanced Database menu to list all available databases at the top
    - Current database is marked with "● (current)" and is non-clickable
    - Other databases are clickable and switch to that database when selected
    - Added `_switch_to_database()` method for seamless database switching
    - Database switching triggers the startup dialog for immediate project/mode selection

- ✅ COMPLETED: The editing mode for the time entries is still a bit problematic and needs better usability. It is too easy to just accidentally click the entries. I think it would be better if the Editing mode table items would be by default "non editable" and there is a checkbox in the beginning of the row, which you can click. If you select a single row and then click "Edit" button on the top of the screen you get a new window where you can edit the properties of the selected row. There you should be able to 1) Change the project 2) Change the mode 3) Change the ending time with similar logic that will move the next item forward and backward if it is close enough ( 3 min thresold ) just like in the current edit mode. Also in the Edit window there should be a possibility to pick the date which entries you want to modify, now it defaults to "Today" but in the future you want to edit some other previous day. At this point do not consider the situation where multiple rows are selected, if multiple rows are selected then Edit button should be disabled.

  - **Complete redesign of Edit Hours Dialog with checkbox-based selection**:

    - Created `EditSingleEntryDialog` class for editing individual time entries
    - Updated `EditHoursDialog` to use checkbox selection instead of direct table editing
    - Added date picker to select which day's entries to edit (defaults to today)
    - Edit button is only enabled when exactly one row is selected
    - Edit button shows selection count and is disabled for multiple selections
    - All table items are now read-only by default - no accidental edits

  - **EditSingleEntryDialog features**:

    - Change project using dropdown with all available projects
    - Change mode using editable combo box with existing mode suggestions
    - Change start and end times with date picker support
    - **Edit description using multi-line text field with placeholder text**
    - Smart time validation prevents invalid time ranges
    - Day boundary crossing support (e.g., 23:00 to 01:00 next day)
    - Proportional time component adjustment (active/idle/manual seconds)
    - Real-time duration calculation and display
    - Comprehensive validation with user-friendly error messages

  - **Enhanced usability and safety**:
    - Checkbox-based selection prevents accidental edits
    - Single-row editing requirement enforced with clear feedback
    - Date picker allows editing entries from any previous day
    - Modified entries highlighted in dark blue with white text for visibility
    - Confirmation dialog shows summary of all changes before saving
    - Unsaved changes warning when switching dates
    - All changes validated before database updates
    - **Description changes are saved to database and displayed in table**

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
  - **Color coding**: Modified entries are highlighted in blue for visual feedback with good text readability
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
