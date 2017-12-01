
-- List actions to perform
set actions to {¬
	{action:"telnet tme-termserver-1 2033"}, ¬
	{action:"telnet tme-termserver-1 2034"}, ¬
	{action:"telnet tme-termserver-1 2037"}, ¬
	{action:"telnet tme-termserver-1 2038"}, ¬
	{action:"telnet tme-termserver-1 2039"}, ¬
	{action:"telnet tme-termserver-1 2040"}, ¬
	{action:"telnet tme-termserver-1 2041"}, ¬
	{action:"telnet tme-termserver-1 2042"} ¬
		}

-- Count number of actions
set num_actions to count of actions

-- Set cols and lines
set num_cols to round (num_actions ^ 0.5)
set num_lines to round (num_actions / num_cols) rounding up

-- Start iTerm
tell application "iTerm"
	activate
	
	# Create new tab
	tell current window
		create tab with default profile
	end tell
	
	-- Prepare horizontal panes
	repeat with i from 1 to num_lines
		tell session 1 of current tab of current window
			if i < num_lines then
				split horizontally with default profile
			end if
		end tell
	end repeat
	
	-- Prepare vertical panes
	set sessid to 1
	repeat with i from 1 to num_lines
		if i is not 1 then set sessid to sessid + num_cols
		if i is not num_lines or num_actions is num_cols * num_lines then
			set cols to num_cols - 1
		else
			set cols to (num_actions - ((num_lines - 1) * num_cols)) - 1
		end if
		repeat with j from 1 to (cols)
			tell session sessid of current tab of current window
				split vertically with default profile
			end tell
		end repeat
	end repeat
	
	-- Execute actions
	repeat with i from 1 to num_actions
		tell session i of current tab of current window
			write text (action of item i of actions)
		end tell
	end repeat
end tell
