# Automated Forms Submitter

This script uses **Playwright** to automatically fill out and submit a Microsoft Forms survey. It's designed to generate a realistic set of test data based on specific quotas.

It avoids being detected as a bot by using "smart" personas (e.g., a "student officer" will answer more positively) and by taking a realistic amount of time to fill out each form (approx. 4-5 minutes per submission).

## Key Features
* **No More Driver Errors:** Uses Playwright, which manages its own browser drivers.
* **Quota System:** Submits a specific `min`/`max` number of responses for different groups (e.t., "CITHM", "COT").
* **Total Max Limit:** A master kill-switch to stop the script after a total number of submissions (e.g., 400).
* **Smart Personas:** Randomly chooses between a "default" student and an "officer" persona to give different sets of answers.
* **Realistic Delays:** Waits 5-7 seconds after answering *each* question to simulate a human reading the form.
* **Logs Output:** Saves all submitted data to `submitted_responses.csv`.

---

## ⚙️ Setup Instructions (One-time Only)

You must follow these steps *exactly* to set up the script for the first time.

### 1. Install Official Python (Crucial!)

This script **will not work** with the Python version from the Microsoft Store.

1.  Go to the official Python website: [**https://www.python.org/downloads/**](https://www.python.org/downloads/)
2.  Download the installer (e.g., Python 3.12).
3.  Run the installer. **This is the most important step:**
    On the first screen, check the box that says **"Add python.exe to PATH"**.
4.  Click "Install Now" and finish the installation.

### 2. Set Up the Project Folder

1.  **Create a folder:** Create a new folder in a simple location, like `C:\Forms`.
2.  **Copy the script:** Place the `automate_playwright.py` file inside this `C:\Forms` folder.
3.  **Open your terminal:** Open **Command Prompt** or **PowerShell**.
4.  **Navigate to your folder:**
    ```bash
    cd C:\Forms
    ```
5.  **Create a Virtual Environment:** This creates a private "sandbox" for the Python packages.
    ```bash
    python -m venv venv
    ```
6.  **Activate the Environment:** You must do this *every time* you open a new terminal to run the script.
    ```bash
    .\venv\Scripts\activate
    ```
    *(Your terminal prompt will now look like `(.venv) PS C:\Forms> `)*

7.  **Install Libraries:** With the environment active, run this:
    ```bash
    pip install playwright faker
    ```
8.  **Install Browsers:** This command downloads the special browsers that Playwright controls.
    ```bash
    playwright install
    ```

You are now set up and ready to run the script.

---

## 🚀 How to Run the Script

1.  Open a new terminal.
2.  Navigate to your folder: `cd C:\Forms`
3.  Activate the environment: `.\venv\Scripts\activate`
4.  Run the script:
    ```bash
    python automate_playwright.py
    ```

A browser window will open and begin the automation. You will see its progress in the terminal. The script will run until all minimum quotas are met or it hits the `TOTAL_MAX_SUBMISSIONS` limit, and then it will stop by itself.

---

## 🔧 Configuration (How to Edit)

Open the `automate_playwright.py` file in any text editor. All the settings you'd want to change are in the `CONFIG` block at the very top.

* **To change respondent numbers:**
    Edit the `min` and `max` values in `FACULTY_TARGETS`.
    ```python
    FACULTY_TARGETS = {
        "CITHM": {"min": 201, "max": 268, "count": 0},
        "COT":   {"min": 21,  "max": 28,  "count": 0},
        # ...etc
    }
    ```

* **To change the total number of submissions:**
    Edit the `TOTAL_MAX_SUBMISSIONS` number. The script will stop when it hits this *or* when all minimums are met, whichever happens first.
    ```python
    TOTAL_MAX_SUBMISSIONS = 400
    ```

* **To make it faster or slower:**
    Change the delay (in seconds) for each question.
    ```python
    QUESTION_MIN_DELAY = 5.0
    QUESTION_MAX_DELAY = 7.0
    ```

* **To run in the background:**
    Change `HEADLESS` to `True`. The browser window will not open, but the script will still run (and be much faster).
    ```python
    HEADLESS = True
    ```

---

## Troubleshooting

**Problem:** You get an error like `[WinError 193] %1 is not a valid Win32 application` or `Python was not found...`

**Cause:** You are still using the Microsoft Store version of Python.

**Solution:**
1.  Go to "Add or remove programs" and **uninstall** any version of Python you see.
2.  Follow **Step 1** of the Setup Instructions again to install the official version from `python.org`, making sure to check **"Add to PATH"**.
3.  If it *still* fails, type **"App execution aliases"** into your Start Menu, open the settings, and **turn off** the aliases for `python.exe` and `python3.exe`.
4.  Delete your `venv` folder and run the setup steps again.
