# 🤖 Automated Forms Submitter (v6 - Advanced)

This script uses **Playwright** to automatically fill out and submit a Microsoft Forms survey. It is an advanced tool designed to generate a highly realistic set of test data based on specific quotas.

It avoids bot detection by simulating human behavior, including "thinking" time, persona-based delays, and logical answer patterns. It is also "crash-proof" and can be stopped and restarted without losing progress.

## ✨ Key Features
* **State Persistence (Crash-Proof):** Saves progress to `submission_state.json` after every submission. If the script is stopped, it will resume from where it left off.
* **Handles "Virtual Scrolling":** The script is smart enough to handle forms that load questions dynamically as you scroll.
* **Quota System:** Submits a specific `min`/`max` number of responses for different groups (e.g., "CITHM", "COT").
* **Total Max Limit:** A master kill-switch to stop the script after a total number of submissions (e.g., 400).
* **Advanced Themed Personas:** Creates logical profiles for each submission:
    * **`officer`**: Engaged, positive, high participation.
    * **`uninformed`**: Motivated but critical of communication.
    * **`apathetic`**: Disengaged, negative on motivation questions.
    * **`busy`**: Motivated but critical of event scheduling/accessibility.
    * **`skeptic`**: Believes the CSR is just for PR and has no real impact.
    * **`incentive_driven`**: Only cares about rewards (certificates, etc.).
    * **`straight_liner`**: Clicks "Somewhat Agree" for all Likert questions.
* **Human-like Behavior:**
    * **"Thinking" Time:** Pauses *before* answering each question to simulate reading.
    * **Persona Delays:** "Disengaged" personas answer much faster than "officer" personas.
* **Resilient Loading:** Retries up to 3 times if the page fails to load.
* **Professional Logging:** Logs all actions to both the console and a file (`automation.log`).

---

## 📂 File Structure

When you run the script, your folder will look like this:

* **`automate_playwright.py`**: The main Python script you edit and run.
* **`venv/`**: The Python virtual environment folder.
* **`automation.log`**: A log file with a detailed history of every action the script takes.
* **`submitted_responses.csv`**: The final output file with all the data. You can open this in Excel.
* **`submission_state.json`**: The crash-proof save file. It stores the current submission counts. **Do not delete this** if you want to resume a run.

---

## ⚙️ Setup Instructions (One-time Only)

You must follow these steps *exactly* to set up the script for the first time.

### 1. Install Official Python (Crucial!)

This script **will not work** with the Python version from the Microsoft Store due to permission issues.

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

7.  **Install Required Packages:** With the environment active, run this command to install `playwright` and `faker`.
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
4.  Run the script by its file name:
    ```bash
    python automate_playwright.py
    ```

A browser window will open and begin the automation. You will see its progress in the terminal and in the `automation.log` file. The script will run until all minimum quotas are met or it hits the `TOTAL_MAX_SUBMISSIONS` limit.

**To resume a stopped script,** just run the command again. It will read the `submission_state.json` file and continue.

---

## 🔧 Configuration (How to Edit)

Open the `automate_playwright.py` file in any text editor. All settings are in the `CONFIG` block at the top.

* **To change respondent numbers:**
    Edit the `min` and `max` values in `FACULTY_TARGETS`.
    ```python
    FACULTY_TARGETS = {
        "CITHM": {"min": 201, "max": 268, "count": 0},
        # ...etc
    }
    ```

* **To change the total number of submissions:**
    Edit the `TOTAL_MAX_SUBMISSIONS` number.
    ```python
    TOTAL_MAX_SUBMISSIONS = 400
    ```

* **To change the "thinking" speed:**
    Edit the min/max second values in `PERSONA_DELAYS`.
    ```python
    PERSONA_DELAYS = {
        "officer": (5.0, 8.0),  # Slow and careful
        "straight_liner": (0.5, 1.5)   # Very fast
        # ...etc
    }
    ```
* **To change persona probabilities:**
    Edit the weights in `PERSONA_WEIGHTS` (must sum to 1.0).
    ```python
    PERSONA_WEIGHTS = [0.35, 0.10, 0.15, 0.10, 0.10, 0.05, 0.10, 0.05]
    ```

* **To run in the background:**
    Change `HEADLESS` to `True`. The browser window will not open.
    ```python
    HEADLESS = True
    ```

---

## ⚠️ Troubleshooting

**Problem:** You get an error like `[WinError 193] %1 is not a valid Win32 application` or `Python was not found...`

**Cause:** You are still using the Microsoft Store version of Python.

**Solution:**
1.  Go to "Add or remove programs" and **uninstall** any version of Python you see.
2.  Follow **Step 1** of the Setup Instructions again to install the official version from `python.org`, making sure to check **"Add to PATH"**.
3.  If it *still* fails, type **"App execution aliases"** into your Start Menu, open the settings, and **turn off** the aliases for `python.exe` and `python3.exe`.
4.  Delete your `venv` folder and run the setup steps again from `python -m venv venv`.
