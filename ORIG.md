The purpose of this software is to implement a system Tray icon to Track where time each day is spent.

Plain is to implement this using Python and package as Windows executable. The system can use for example SQLIte for the database. IT can implement Azure AD login to Jira to fetch the projects, but that is optional, alternative is to use CSV export from Jira to read the proejcts.

User can also add projects manually ( Project Name + Project Code ) if nothing else works.

The data is tracked per two or more classes active at the same time:

1. Activity type classes, which are configure by uploading a text file to the system
2. Tickets, which are configured by givng an CSV export of the issues to the system

Optionally: implement Azure AD login + fetch the users active tasks from Jira in the menu of the system tray.

Activity type classes are initialized when user starts the program, the default mode is "Idle"

If user clicks the tray icon the prompt appears where you can select the project from the project list
or "No project" and then you can write:

Select Project: <dropdon to select project>
What are you doing?: <text input to ask or autocomplete>
[ Lunch ] [ Meeting ] [ IT-issue ]

So here, I am calling the Project "project" and "mode" is what you are doing.

The field has autocomplete of the old modes that were entered, so you for example you can add there
"Lunch" and then next time program remembers that "Lunch" is one of the options that can be used.

The most commonly used options become available as "Tag cloud" under the text field, so you can click
them from there.

Pre-populate the "modes" with some reasonable values like "Lunch", "Meeting", "Break", "Coffee", "Waiting for Build", "Waiting for Tests".

If the program notices the user has been "idle" for 5 minutes (no mouse activity, no keyboard activity etc.) then the mode will go into "(Idle)" for example "Meeting (Idle)".

If the system hibernates ( Windows goes to sleep ) the time tracking is stopped.

User can manually edit the times if necessary, so user can add "Overrides" to the automatically recorded
times. There is a button "Add entry" or "Modify Entry" in the UI.

The System is always handling one week at a time, but data is stored per month and each active week we are using will have it's own empty week database entry where the hour recordings are linked.

The time tracking entries will have

1. ID of the row ( record number, 1...N)
2. Date
3. Start time
4. Active minutes
5. Project ( or no project )
6. Mode
7. Idle minutes

The manual entries have the same kind of information, the manual entries have two tables

Add rows table:

1. ID of the row ( record number, 1...N)
2. Date
3. Start time
4. Active minutes
5. Project ( or no project )
6. Mode

Modify rows table will rewrite the old row with new information.

1. ID
2. Row ID to modify
3. New Date
4. New Start Time
5. New Active Minutes lasted
6. New Project
7. New Mode
8. New Idle minutes

From the Systme Tray you can view the Chart of the Week when you open the app from the Tray. You can see either Project breakdown and time breakdown for the week based on the categories selected.
