"""
Automated Microsoft Forms submitter using Playwright.
(v3: Professional Refactor)

Features:
- Quota-based submission system (min/max per faculty)
- Total max submission cap
- Realistic "Persona" based answers (officer, default, disengaged)
- Realistic conditional logic (e.g., years affiliated affects prior participation)
- Realistic "Other" field entry (5% chance)
- 4-minute (approx.) submission speed to simulate human use
- Resilient page-loading with 3x retry
- Professional logging to both console and file (automation.log)
- Shuffled quota queue for better distribution
"""

import time
import random
import csv
import re
import asyncio
import copy
import logging
from playwright.async_api import async_playwright
from faker import Faker

# ===================================================================
# =================== LOGGING SETUP (Replaces print) ================
# ===================================================================
# This sets up logging to file and console
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)-8s] %(message)s",
    handlers=[
        logging.FileHandler("automation.log"), # Saves logs to a file
        logging.StreamHandler()                # Prints logs to the console
    ]
)

# =HA_UNSURE_COMMENT_BLOCK_0=

fake = Faker()

# ===================================================================
# ========================== CONFIG =================================
# ===================================================================

# --- 🎯 Respondent Quotas (EDIT THESE) ---
FACULTY_TARGETS = {
    "CITHM": {"min": 201, "max": 268, "count": 0},
    "COT":   {"min": 21,  "max": 28,  "count": 0},
    "CIR":   {"min": 7,   "max": 9,   "count": 0},
    "CBA":   {"min": 41,  "max": 55,  "count": 0},
    "CAS":   {"min": 30,  "max": 40,  "count": 0},
}
# ----------------------------------------

# --- ⏱️ Submission Speed (EDIT THESE) ---
QUESTION_MIN_DELAY = 5.0
QUESTION_MAX_DELAY = 7.0
SUBMISSION_MIN_DELAY = 3.0
SUBMISSION_MAX_DELAY = 5.0
# ----------------------------------------

# --- ⚙️ General Settings (EDIT THESE) ---
TOTAL_MAX_SUBMISSIONS = 400
FORM_URL = "https://forms.office.com/r/tq1WJ0CWT0"
# --- (Set to True for faster, background execution) ---
HEADLESS = False
LOG_CSV = "submitted_responses.csv"

# --- 🤖 Persona / Answer Configuration ---

# Probabilities for picking a persona
PERSONA_CHOICES = ['default', 'officer', 'disengaged']
PERSONA_WEIGHTS = [0.60,       0.25,      0.15] # 60% default, 25% officer, 15% disengaged

# Likert choices for each persona
PERSONA_LIKERT_WEIGHTS = {
    "officer": [0.05, 0.10, 0.20, 0.45, 0.20], # Positive
    "default": [0.15, 0.30, 0.35, 0.15, 0.05], # Neutral
    "disengaged": [0.40, 0.30, 0.20, 0.05, 0.05]  # Negative
}
LIKERT_CHOICES = ["Strongly Disagree", "Disagree", "Somewhat Agree", "Agree", "Strongly Agree"]

# Question options
faculty = ["CITHM", "COT", "CAS", "CIR", "CBA"]
role = ["Student", "Student with position in student organization (officer to member)"]
sex = ["Male", "Female", "Prefer not to say"]
years_affiliated = ["Less than 1 year", "1 - 3 Years", "4 - 6 Years"]
prior_csr = ["None", "1 - 2", "3 - 5", "More than 5"]
csr_info_sources = ["Social Media", "Emails", "Peer to peer/ Word of mouth", "University website/portal", "Other"]

# ===================================================================
# ====================== END OF CONFIG ==============================
# ===================================================================


async def rand_sleep(min_delay, max_delay):
    """(Async) Waits for a random duration between min and max seconds."""
    await asyncio.sleep(random.uniform(min_delay, max_delay))

def pick_likert(persona='default'):
    """
    (Sync) Selects a Likert choice based on the persona.
    """
    # Get the weights for the given persona, or use 'default' if unknown
    weights = PERSONA_LIKERT_WEIGHTS.get(persona, PERSONA_LIKERT_WEIGHTS['default'])
    return random.choices(LIKERT_CHOICES, weights=weights, k=1)[0]


async def fill_all_questions(page, role_persona, selected_faculty):
    """
    Finds all VISIBLE question blocks on the page and fills them.
    (UPDATED with conditional logic and "Other" field)
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
                logging.warning(f"Could not click DEMO option '{value_text}'. Error: {e}")
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
            logging.warning(f"Could not click LIKERT option '{choice_string}' at index {index}. Error: {e}")
            return False
            
    # --- Helper 3: For "Other" text input ---
    async def fill_text_input(block_locator, text):
        try:
            await block_locator.locator("input[type='text']").fill(text)
            return True
        except Exception as e:
            logging.warning(f"Could not fill 'Other' text. Error: {e}")
            return False

    # --- End of helpers ---

    blocks_locator = page.locator("div[data-automation-id='questionItem']")
    count = await blocks_locator.count()
    if count == 0:
        logging.warning("No question blocks found on this page.")
        return {}
    logging.info(f"Found {count} question blocks to fill...")

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
            # === NEW: Conditional Logic ===
            # Check the answer for 'years_affiliated' to give a realistic answer
            years = all_answers.get("years_affiliated")
            if years == "Less than 1 year":
                val = random.choice(["None", "1 - 2"]) # Force a realistic choice
            else:
                val = random.choice(prior_csr)
            
            if await click_option(block, val): all_answers["prior_csr"] = val

        elif "primary source" in txt:
            # === NEW: 5% Chance to fill "Other" ===
            if random.random() < 0.05: # 5% chance
                if await click_option(block, "Other"):
                    other_text = fake.bs() # e.g., "cross-platform e-commerce"
                    await fill_text_input(block, other_text)
                    all_answers["csr_sources"] = f"Other: {other_text}"
            else:
                # Standard checkbox logic
                choices = random.sample(csr_info_sources[:-1], k=random.randint(1, 3)) # [:-1] excludes "Other"
                for c in choices:
                    await click_option(block, c)
                    await asyncio.sleep(0.2)
                all_answers["csr_sources"] = ", ".join(choices)
        
        else:
            # This is a Likert question
            choice = pick_likert(role_persona) 
            if await click_likert_option(block, choice):
                all_likert_answers.append(choice)
        
        # === Use realistic delay from CONFIG ===
        logging.info(f"  ... answered question {i+1}/{count}, sleeping {QUESTION_MIN_DELAY}-{QUESTION_MAX_DELAY}s...")
        await rand_sleep(QUESTION_MIN_DELAY, QUESTION_MAX_DELAY) 
        
    all_answers["likert_answers"] = ", ".join(all_likert_answers)
    all_answers["role"] = role_persona
    all_answers["faculty"] = selected_faculty
    return all_answers


async def main():
    """
    Main function with a quota-based system.
    (UPDATED with logging, retries, and shuffling)
    """
    logging.info("Starting automation with respondent quotas...")
    
    faculty_targets = copy.deepcopy(FACULTY_TARGETS)
    total_min_needed = sum(d["min"] for d in faculty_targets.values())
    logging.info(f"Target: At least {total_min_needed} total submissions.")
    logging.info(f"Absolute Stop: Script will stop if it reaches {TOTAL_MAX_SUBMISSIONS} total submissions.")

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

                while True:
                    if submission_counter >= TOTAL_MAX_SUBMISSIONS:
                        logging.info(f"\nHit the TOTAL_MAX_SUBMISSIONS limit of {TOTAL_MAX_SUBMISSIONS}. Stopping.")
                        break

                    submission_counter += 1
                    logging.info(f"\n--- Starting Submission {submission_counter} ---")

                    available_faculties = [f for f, d in faculty_targets.items() if d["count"] < d["max"]]
                    if not available_faculties:
                        logging.info("All faculties have reached their max. Stopping.")
                        break 

                    priority_faculties = [f for f in available_faculties if faculty_targets[f]["count"] < faculty_targets[f]["min"]]
                    
                    if priority_faculties:
                        # === NEW: Shuffle priority list for better distribution ===
                        random.shuffle(priority_faculties)
                        selected_faculty = priority_faculties[0]
                    else:
                        selected_faculty = random.choice(available_faculties)
                    
                    # Create the persona
                    selected_role_text = random.choice(role)
                    persona_type = 'officer' if "organization" in selected_role_text else random.choices(PERSONA_CHOICES, PERSONA_WEIGHTS, k=1)[0]
                    
                    logging.info(f"Running for: {selected_faculty} (Persona: {persona_type})")
                    
                    try:
                        # === NEW: Resilient Page Load with 3 Retries ===
                        for attempt in range(3):
                            try:
                                await page.goto(FORM_URL, timeout=30000) # 30s timeout
                                await page.wait_for_selector("div[data-automation-id='questionItem']", timeout=10000)
                                logging.info(f"Page loaded successfully on attempt {attempt+1}.")
                                break # Success
                            except Exception as e:
                                logging.warning(f"  Attempt {attempt+1}/3 failed to load page: {e}. Retrying...")
                                await asyncio.sleep(5)
                        else: # 'else' on a 'for' loop runs if the loop completes without 'break'
                            raise Exception("Page failed to load after 3 attempts.")
                        # ===============================================
                        
                        all_answers = await fill_all_questions(page, persona_type, selected_faculty)

                        submit_button = page.locator("button[data-automation-id='submitButton']")
                        if await submit_button.is_visible():
                            await submit_button.click()
                        else:
                            logging.error("Could not find Submit button.")
                            continue 

                        if all_answers:
                            writer.writerow([
                                all_answers.get("faculty"), all_answers.get("role"),
                                all_answers.get("sex"), all_answers.get("years_affiliated"),
                                all_answers.get("prior_csr"), all_answers.get("csr_sources"),
                                all_answers.get("likert_answers")
                            ])
                            faculty_targets[selected_faculty]["count"] += 1
                            logging.info(f"Submission {submission_counter} complete and logged for {selected_faculty}.")
                        else:
                            logging.warning(f"Submission {submission_counter} failed, skipping log.")

                        all_mins_met = all(d["count"] >= d["min"] for d in faculty_targets.values())
                        if all_mins_met:
                            logging.info("\nAll minimum quotas have been met! Stopping.")
                            break 
                        
                        await page.locator("a:has-text('Submit another response')").click()
                        logging.info(f"Waiting {SUBMISSION_MIN_DELAY}-{SUBMISSION_MAX_DELAY}s before next submission...")
                        await rand_sleep(SUBMISSION_MIN_DELAY, SUBMISSION_MAX_DELAY) 

                    except Exception as e:
                        logging.error(f"Error during submission {submission_counter}: {e}", exc_info=True)
                        logging.info("Reloading page and skipping to next submission.")
                        await rand_sleep(5, 7)

                logging.info("All submissions complete. Closing browser.")
                await browser.close()
                
    except Exception as e:
        logging.critical(f"A critical error occurred: {e}", exc_info=True)
    finally:
        logging.info("\n--- FINAL SUBMISSION REPORT ---")
        for faculty, data in faculty_targets.items():
            logging.info(f"  {faculty}: {data['count']} (Target: {data['min']}-{data['max']})")
        logging.info(f"Total Submissions: {submission_counter}")
        logging.info("Automation finished.")

if __name__ == "__main__":
    asyncio.run(main())