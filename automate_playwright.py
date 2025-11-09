"""
Automated Microsoft Forms submitter using Playwright.
(Final Version - All settings in CONFIG block)
"""

import time
import random
import csv
import re  # Used for finding text in locators
import asyncio  # Required for Playwright
import copy # Used to copy the quota dictionary
from playwright.async_api import async_playwright
from faker import Faker

fake = Faker()

# ===================================================================
# ========================== CONFIG =================================
# ===================================================================

# --- 🎯 Respondent Quotas (EDIT THESE) ---
# Set the min/max number of submissions for each faculty.
# The script will run until all 'min' targets are met.
FACULTY_TARGETS = {
    "CITHM": {"min": 201, "max": 268, "count": 0},
    "COT":   {"min": 21,  "max": 28,  "count": 0},
    "CIR":   {"min": 7,   "max": 9,   "count": 0},
    "CBA":   {"min": 41,  "max": 55,  "count": 0},
    "CAS":   {"min": 30,  "max": 40,  "count": 0},
}
# ----------------------------------------

# --- Submission Speed (EDIT THESE) ---
# This controls the ~4-minute submission time.
# Averages ~6 seconds per question (5.0-7.0)
QUESTION_MIN_DELAY = 4.0
QUESTION_MAX_DELAY = 7.0

# Delay between one submission finishing and the next one starting
SUBMISSION_MIN_DELAY = 3.0
SUBMISSION_MAX_DELAY = 5.0
# ----------------------------------------

# --- General Settings (EDIT THESE) ---
# The script will stop when it hits
# this total number, OR when all minimums are met, whichever happens first.
TOTAL_MAX_SUBMISSIONS = 4

FORM_URL = "https://forms.office.com/r/tq1WJ0CWT0"
HEADLESS = False  # Set to True to run in the background
LOG_CSV = "submitted_responses.csv"

# --- Persona / Answer Configuration ---
# Weights for Likert-scale answers (5-point)
LIKERT_CHOICES = ["Strongly Disagree", "Disagree", "Somewhat Agree", "Agree", "Strongly Agree"]

# Question options
faculty = ["CITHM", "COT", "CAS", "CIR", "CBA"]
role = ["Student", "Student with position in student organization (officer to member)"]
sex = ["Male", "Female", "Prefer not to say"]
years_affiliated = ["Less than 1 year", "1 - 3 Years", "4 - 6 Years"]
prior_csr = ["None", "1 - 2", "3 - 5", "More than 5"]
csr_info_sources = ["Social Media", "Emails", "Peer to peer/ Word of mouth", "University website/portal", "Other"]

# Keywords to identify Likert questions
LIKERT_KEYWORDS = [
    "csr", "particip", "informed", "volunteer", "engage", "feedback",
    "motivat", "access", "convenience", "feature", "increase my participation"
]

# ===================================================================
# ====================== END OF CONFIG ==============================
# ===================================================================


async def rand_sleep(min_delay, max_delay):
    """(Async) Waits for a random duration between min and max seconds."""
    await asyncio.sleep(random.uniform(min_delay, max_delay))

def pick_likert(persona='default'):
    """
    (Sync) Selects a Likert choice based on the persona.
    'default' = A regular student
    'officer' = An engaged student officer
    """
    if persona == 'officer':
        # Officers are more engaged and positive
        weights = [0.05, 0.10, 0.20, 0.45, 0.20] # Sum = 1.0
    else:
        # Default student, more neutral or has some complaints
        weights = [0.15, 0.30, 0.35, 0.15, 0.05] # Sum = 1.0

    return random.choices(LIKERT_CHOICES, weights=weights, k=1)[0]


async def fill_all_questions(page, role_persona, selected_faculty):
    """
    Finds all VISIBLE question blocks on the page and fills them.
    Takes a 'role_persona' and 'selected_faculty' to make smart choices.
    """
    all_answers = {}
    all_likert_answers = []

    # --- Helper 1: For standard radio/checkboxes ---
    async def click_option(block_locator, value_text):
        try:
            await block_locator.scroll_into_view_if_needed()
            pattern = re.compile(re.escape(value_text), re.IGNORECASE)
            await block_locator.locator("span", has_text=pattern).click()
            return True
        except Exception:
            try:
                await block_locator.locator(f"input[value='{value_text}']").click()
                return True
            except Exception as e:
                print(f"Warning: Could not click DEMO option '{value_text}'. Error: {e}")
                return False

    # --- Helper 2: For Likert scales ---
    likert_map = {
        "Strongly Disagree": 0, "Disagree": 1, "Somewhat Agree": 2,
        "Agree": 3, "Strongly Agree": 4
    }

    async def click_likert_option(block_locator, choice_string):
        try:
            await block_locator.scroll_into_view_if_needed()
            index = likert_map[choice_string]
            await block_locator.locator("input[type='radio']").nth(index).click()
            return True
        except Exception as e:
            print(f"Warning: Could not click LIKERT option '{choice_string}' at index {index}. Error: {e}")
            return False
    # --- End of helpers ---

    blocks_locator = page.locator("div[data-automation-id='questionItem']")
    count = await blocks_locator.count()
    if count == 0:
        print("Warning: No question blocks found on this page.")
        return {}
    print(f"Found {count} question blocks to fill...")

    for i in range(count):
        block = blocks_locator.nth(i)
        txt_content = await block.text_content()
        if not txt_content: continue
        txt = txt_content.lower()

        is_answered = await block.locator("input[type='radio'][checked]").count() > 0 or \
                      await block.locator("input[type='checkbox'][checked]").count() > 0
        if is_answered: continue

        # === Smart Logic ===
        if "faculty" in txt:
            if await click_option(block, selected_faculty): all_answers["faculty"] = selected_faculty

        elif "describes you" in txt:
            if await click_option(block, role_persona): all_answers["role"] = role_persona

        elif "sex" in txt and "birth" in txt:
            val = random.choice(sex)
            if await click_option(block, val): all_answers["sex"] = val

        elif "years affiliated" in txt:
            val = random.choice(years_affiliated)
            if await click_option(block, val): all_answers["years_affiliated"] = val

        elif "prior participation" in txt: 
            val = random.choice(prior_csr)
            if await click_option(block, val): all_answers["prior_csr"] = val

        elif "primary source" in txt:
            choices = random.sample(csr_info_sources, k=random.randint(1, 3))
            for c in choices:
                await click_option(block, c)
                await asyncio.sleep(0.2) # small delay between checkbox clicks
            all_answers["csr_sources"] = ", ".join(choices)

        else:
            choice = pick_likert(role_persona) 
            if await click_likert_option(block, choice):
                all_likert_answers.append(choice)
        
        # === Use realistic delay from CONFIG ===
        print(f"  ... answered question {i+1}/{count}, sleeping {QUESTION_MIN_DELAY}-{QUESTION_MAX_DELAY}s...")
        await rand_sleep(QUESTION_MIN_DELAY, QUESTION_MAX_DELAY) 
        # =======================================
        
    all_answers["likert_answers"] = ", ".join(all_likert_answers)
    all_answers["role"] = role_persona
    all_answers["faculty"] = selected_faculty
    return all_answers


async def main():
    """
    Main function with a quota-based system.
    """
    print("Starting automation with respondent quotas...")
    
    # --- Load targets from CONFIG ---
    faculty_targets = copy.deepcopy(FACULTY_TARGETS)
    
    total_min_needed = sum(d["min"] for d in faculty_targets.values())
    print(f"Target: At least {total_min_needed} total submissions.")
    print(f"Absolute Stop: Script will stop if it reaches {TOTAL_MAX_SUBMISSIONS} total submissions.")


    headers = [
        "faculty", "role", "sex", "years_affiliated",
        "prior_csr", "csr_sources", "likert_answers"
    ]
    
    submission_counter = 0

    try:
        with open(LOG_CSV, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(headers)

            async with async_playwright() as p:
                browser = await p.chromium.launch(
                    headless=HEADLESS,
                    args=['--start-maximized']
                )
                context = await browser.new_context(viewport=None)
                page = await context.new_page()

                # --- Main Quota Loop ---
                while True:
                    # === Check TOTAL_MAX_SUBMISSIONS limit first ===
                    if submission_counter >= TOTAL_MAX_SUBMISSIONS:
                        print(f"\nHit the TOTAL_MAX_SUBMISSIONS limit of {TOTAL_MAX_SUBMISSIONS}. Stopping.")
                        break
                    # ===============================================

                    submission_counter += 1
                    print(f"\n--- Starting Submission {submission_counter} ---")

                    # 1. Check which faculties are NOT at their max
                    available_faculties = [f for f, d in faculty_targets.items() if d["count"] < d["max"]]
                    
                    if not available_faculties:
                        print("All faculties have reached their max. Stopping.")
                        break # All done

                    # 2. From the available, find which ones are still below min (priority)
                    priority_faculties = [f for f in available_faculties if faculty_targets[f]["count"] < faculty_targets[f]["min"]]
                    
                    if priority_faculties:
                        selected_faculty = random.choice(priority_faculties)
                    else:
                        selected_faculty = random.choice(available_faculties)
                    
                    # 3. Create the persona
                    selected_role = random.choice(role)
                    persona_type = 'officer' if "organization" in selected_role else 'default'
                    
                    print(f"Running for: {selected_faculty} (Persona: {persona_type})")
                    
                    try:
                        await page.goto(FORM_URL, timeout=60000)
                        await page.wait_for_selector("div[data-automation-id='questionItem']", timeout=10000)
                        
                        # 4. Pass the selected faculty and role
                        all_answers = await fill_all_questions(page, selected_role, selected_faculty)

                        submit_button = page.locator("button[data-automation-id='submitButton']")
                        if await submit_button.is_visible():
                            await submit_button.click()
                        else:
                            print("Error: Could not find Submit button.")
                            continue 

                        # 5. Log and UPDATE THE COUNT
                        if all_answers:
                            writer.writerow([
                                all_answers.get("faculty"), all_answers.get("role"),
                                all_answers.get("sex"), all_answers.get("years_affiliated"),
                                all_answers.get("prior_csr"), all_answers.get("csr_sources"),
                                all_answers.get("likert_answers")
                            ])
                            faculty_targets[selected_faculty]["count"] += 1
                            print(f"Submission {submission_counter} complete and logged for {selected_faculty}.")
                        else:
                            print(f"Submission {submission_counter} failed, skipping log.")

                        # 6. Check if all MINIMUMS are met
                        all_mins_met = all(d["count"] >= d["min"] for d in faculty_targets.values())
                        if all_mins_met:
                            print("\nAll minimum quotas have been met! Stopping.")
                            break # We are done!
                        
                        # --- Click "Submit another response" ---
                        await page.locator("a:has-text('Submit another response')").click()
                        print(f"Waiting {SUBMISSION_MIN_DELAY}-{SUBMISSION_MAX_DELAY}s before next submission...")
                        await rand_sleep(SUBMISSION_MIN_DELAY, SUBMISSION_MAX_DELAY) 

                    except Exception as e:
                        print(f"Error during submission {submission_counter}: {e}")
                        print("Reloading page and skipping to next submission.")
                        await rand_sleep(5, 7) # Use a basic delay for error recovery

                print("All submissions complete. Closing browser.")
                await browser.close()
                
    except Exception as e:
        print(f"A critical error occurred: {e}")
    finally:
        # Print a final report of the counts
        print("\n--- FINAL SUBMISSION REPORT ---")
        for faculty, data in faculty_targets.items():
            print(f"  {faculty}: {data['count']} (Target: {data['min']}-{data['max']})")
        print(f"Total Submissions: {submission_counter}")
        print("Automation finished.")

if __name__ == "__main__":
    asyncio.run(main())