# Snapchat Automation

Python automation tool for Snapchat with GUI interface. Automates photo sending to multiple friends using multiple browser sessions.

## Requirements

- Python 3.7+
- Windows 10/11

## Installation

1. **Install Python** (if not installed)
   - Download from [python.org](https://www.python.org/downloads/)
   - ✅ Check "Add Python to PATH" during installation

2. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Install Playwright browser**
   ```bash
   playwright install chromium
   ```

## Environment Variables (Optional)

If Python or pip commands don't work, add them to PATH:

**Windows:**
1. Press `Win + X` → Select "System"
2. Click "Advanced system settings"
3. Click "Environment Variables"
4. Under "System variables", find and select "Path" → Click "Edit"
5. Click "New" → Add Python installation path (e.g., `C:\Python39` or `C:\Users\YourName\AppData\Local\Programs\Python\Python39`)
6. Also add Scripts folder (e.g., `C:\Python39\Scripts`)
7. Click "OK" on all windows
8. **Restart** terminal/PowerShell for changes to take effect

**Verify:**
```bash
python --version
pip --version
```

## Start Project

```bash
python snapchat_automation.py
```

## How to Use

1. **Add friends**: Click "View Friends" → Add usernames → Click "Add" **OR** create `friends.txt` file (one username per line)
2. **Launch**: Select number of sessions (1-10) → Click "Launch Sessions"
3. **Allow camera**: When browser opens and loads Snapchat, click "Allow" when prompted for camera access (or set to "Always allow" in browser settings)
4. **Login**: Manually log in to Snapchat in each browser window
5. **Wait**: Automation starts after 3 minutes (for friends to load)
6. **Done**: Photos will be sent automatically to all friends

## Troubleshooting

- **Playwright error**: Run `playwright install chromium`
- **Import errors**: Run `pip install -r requirements.txt`
- **No friends**: Add at least one friend before launching sessions
