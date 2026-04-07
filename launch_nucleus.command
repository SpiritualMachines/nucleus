#!/bin/bash

# 1. Navigate to the directory where this script (or its alias) is located
# This ensures we find the 'venv' and 'nucleus.py' correctly.
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$DIR"

# 2. Run the Python Application
# We use the python interpreter inside the virtual environment.
"./venv/bin/python3" nucleus.py

# 3. Capture the Exit Code immediately
EXIT_CODE=$?

# 4. Logic: Only pause if there was an error
if [ $EXIT_CODE -ne 0 ]; then
    echo ""
    echo "======================================================="
    echo "❌ CRITICAL ERROR: The application crashed."
    echo "-------------------------------------------------------"
    echo "Exit Code: $EXIT_CODE"
    echo "Please review the error message above."
    echo "======================================================="
    echo ""
    echo "Press [ENTER] to close this terminal window..."
    read
fi

# If EXIT_CODE was 0 (Success), the script ends here instantly.
# Note: Ensure your Terminal.app settings (Profiles > Shell) are set
# to "Close if the shell exited cleanly" for the window to vanish.
