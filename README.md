# Transcribe Utility

## Setup
To get started, make sure you have installed the necessary requirements:
```bash
pip install -r requirements.txt
```

## About `voice_to_cursor.py`
The `voice_to_cursor.py` script listens for audio input (voice) and transcribes it in real-time. The transcribed text is then automatically placed at the cursor in whichever app you’re using, effectively “voice typing” for you.

## Creating an Automator Workflow
1. Open the Automator app on your Mac and create a new workflow named **`transcribe.workflow`**.
2. In the Automator panel, add a “Run Shell Script” action.
3. Use the following lines in the shell script text area (replacing each `[ ... ]` appropriately):
   ```bash
   export GOOGLE_APPLICATION_CREDENTIALS="[file_path.json]"
   python "[script_location.py]"
   ```
   - `[file_path.json]` should point to your Google Cloud credentials (if you’re using a Google-based Speech-to-Text service).
   - `[script_location.py]` must be the full path to `voice_to_cursor.py`.

After saving, you can run this Automator workflow whenever you want to activate the transcribe functionality.

## Configuring Hotkeys
To trigger the workflow, open **System Settings** → **Keyboard Shortcuts** → **Services** → **General** → and look for **transcribe**.
Set a preferred keyboard shortcut, and then use that hotkey to quickly run the `voice_to_cursor.py` script via the Automator workflow.
