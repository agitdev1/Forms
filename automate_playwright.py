"""
Automated Microsoft Forms submitter using Playwright.
(v4: Advanced Personas & Conditional Logic)

Features:
- Quota-based submission system (min/max per faculty)
- Total max submission cap
- Advanced, realistic "Persona" system:
  - 'officer': Engaged, positive, high participation
  - 'default': Neutral, low participation
  - 'disengaged': Negative, no participation
  - 'straight_liner': Answers "Somewhat Agree" to all
- Conditional logic (e.g., years affiliated matches prior participation)
- Realistic "Other" field entry
- 4-minute (approx.) submission speed
- Resilient page-loading with 3x retry
- Professional logging to both console and file (automation.log)
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
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)-8s] %(message)s",
    handlers=[
        logging.FileHandler("automation.log"), # Saves logs to a file
        logging.StreamHandler()                # Prints logs to the console
    ]
)
logging.getLogger("playwright").setLevel(logging.WARNING) # Quiets Playwright's own logs

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
HEADLESS = False  # Set to True for faster, background execution
LOG_CSV = "submitted_responses.csv"

# --- 🤖 Persona / Answer Configuration ---

# Probabilities for picking a persona
PERSONA_CHOICES = ['default', 'officer', 'disengaged', 'straight_liner']
PERSONA_WEIGHTS = [0.50,       0.25,      0.15,         0.10] # 50% default, 25% officer, 15% disengaged, 10% straight-liner

# Likert choices for each persona
PERSONA_LIKERT_WEIGHTS = {
    "officer": [0.05, 0.10, 0.20, 0.45, 0.20], # Positive
    "default": [0.15, 0.30, 0.35, 0.15, 0.05], # Neutral
    "disengaged": [0.40, 0.30, 0.20, 0.05, 0.05]  # Negative
    # "straight_liner" is handled with a special case
}
LIKERT_CHOICES = ["Strongly Disagree", "Disagree", "Somewhat Agree", "Agree", "Strongly Agree"]

# NEW: Realistic "Other" answers
REALISTIC_OTHER_SOURCES = [
    "From a professor in class",
    "Saw a poster on campus",
    "A friend told me",
    "From the student handbook",
    "A text from the university"
]

# Base question options
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
    await asyncio.sleep(random.uniform(min_delay, max_delay))

def pick_likert(persona='default'):
    """
    (Sync) Selects a Likert choice based on the persona.
    (UPDATED with 'straight_liner' and 'inconsistent' logic)
    """
    # 1. Handle special "straight_liner" case
    if persona == 'straight_liner':
        return "Somewhat Agree"
    
    # 2. Handle "inconsistent officer" case (10% chance of random negative answer)
    if persona == 'officer' and random.random() < 0.10:
        return random.choice(["Disagree", "Strongly Disagree"])

    # 3. Handle normal cases
    weights = PERSONA_LIKERT_WEIGHTS.get(persona, PERSONA_LIKERT_WEIGHTS['default'])
    return random.choices(LIKERT_CHOICES, weights=weights, k=1)[0]

# --- NEW: Function to build a consistent profile ---
def create_persona_profile():
    """
    Generates a logically consistent profile for a single submission.
    Returns a dictionary of pre-selected demographic answers.
    """
    profile = {}
    
    # 1. Pick the core persona
    persona_type = random.choices(PERSONA_CHOICES, PERSONA_WEIGHTS, k=1)[0]
    profile["persona_type"] = persona_type

    # 2. Generate consistent demographics based on persona
    if persona_type == 'officer':
        profile["role"] = "Student with position in student organization (officer to member)"
        profile["years_affiliated"] = random.choice(["1 - 3 Years", "4 - 6 Years"])
        profile["prior_csr"] = random.choice(["3 - 5", "More than 5"])
    
    elif persona_type == 'disengaged':
        profile["role"] = "Student"
        profile["years_affiliated"] = random.choice(years_affiliated)
        profile["prior_csr"] = "None"
    
    elif persona_type == 'straight_liner':
        profile["role"] = "Student"
        profile["years_affiliated"] = random.choice(years_affiliated)
        profile["prior_csr"] = random.choice(["None", "1 - 2"])

    else: # 'default'
        profile["role"] = "Student"
        profile["years_affiliated"] = random.choice(years_affiliated)
        # Make 'prior_csr' consistent with 'years_affiliated'
        if profile["years_affiliated"] == "Less than 1 year":
            profile["prior_csr"] = random.choice(["None", "1 - 2"])
        else:
            profile["prior_csr"] = random.choice(["None", "1 - 2", "3 - 5"])
            
    return profile
# --- End of new function ---


async def fill_all_questions(page, profile):
    """
    Finds all VISIBLE question blocks on the page and fills them.
    (UPDATED: Takes a pre-built 'profile' dictionary)
    """
    # Start with the profile, add more answers as we go
    all_answers = profile.copy() 
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

        # === Smart Logic: Use pre-built profile ===
        if "faculty" in txt:
            await click_option(block, all_answers["faculty"])

        elif "describes you" in txt:
            await click_option(block, all_answers["role"])

        elif "years affiliated" in txt:
            await click_option(block, all_answers["years_affiliated"])

        elif "prior participation" in txt: 
            await click_option(block, all_answers["prior_csr"])

        # === Answers not in the profile ===
        elif "sex" in txt and "birth" in txt:
            val = random.choice(sex)
            if await click_option(block, val): all_answers["sex"] = val

        elif "primary source" in txt:
            # 5% Chance to fill "Other" with a realistic answer
            if random.random() < 0.05:
                if await click_option(block, "Other"):
                    other_text = random.choice(REALISTIC_OTHER_SOURCES)
                    await fill_text_input(block, other_text)
                    all_answers["csr_sources"] = f"Other: {other_text}"
            else:
                choices = random.sample(csr_info_sources[:-1], k=random.randint(1, 3)) # [:-1] excludes "Other"
                for c in choices:
                    await click_option(block, c)
                    await asyncio.sleep(0.2)
                all_answers["csr_sources"] = ", ".join(choices)
        
        else:
            # This is a Likert question
            choice = pick_likert(all_answers["persona_type"]) 
            if await click_likert_option(block, choice):
                all_likert_answers.append(choice)
        
        logging.info(f"  ... answered question {i+1}/{count}, sleeping {QUESTION_MIN_DELAY}-{QUESTION_MAX_DELAY}s...")
        await rand_sleep(QUESTION_MIN_DELAY, QUESTION_MAX_DELAY) 
        
    all_answers["likert_answers"] = ", ".join(all_likert_answers)
    return all_answers


async def main():
    """
    Main function with a quota-based system.
    (UPDATED to use create_persona_profile)
    """
    logging.info("Starting automation with respondent quotas...")
    
    faculty_targets = copy.deepcopy(FACULTY_TARGETS)
    total_min_needed = sum(d["min"] for d in faculty_targets.values())
    logging.info(f"Target: At least {total_min_needed} total submissions.")
    logging.info(f"Absolute Stop: Script will stop if it reaches {TOTAL_MAX_SUBMISSIONS} total submissions.")

    headers = [
        "faculty", "role", "sex", "years_affiliated",
        "prior_csr", "csr_sources", "likert_answers", "persona_type"
    ]
    
    submission_counter = 0

    try:
        with open(LOG_CSV, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(headers) # Write headers

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

                    # 1. Select faculty based on quota
                    available_faculties = [f for f, d in faculty_targets.items() if d["count"] < d["max"]]
                    if not available_faculties:
                        logging.info("All faculties have reached their max. Stopping.")
                        break 
                    priority_faculties = [f for f in available_faculties if faculty_targets[f]["count"] < faculty_targets[f]["min"]]
                    
                    if priority_faculties:
                        random.shuffle(priority_faculties)
                        selected_faculty = priority_faculties[0]
                    else:
                        selected_faculty = random.choice(available_faculties)
                    
                    # 2. Create the full, consistent profile
                    profile = create_persona_profile()
                    profile["faculty"] = selected_faculty # Add the chosen faculty to the profile
                    
                    logging.info(f"Running for: {selected_faculty} (Persona: {profile['persona_type']})")
                    
                    try:
                        # 3. Resilient Page Load with 3 Retries
                        for attempt in range(3):
                            try:
                                await page.goto(FORM_URL, timeout=30000)
                                await page.wait_for_selector("div[data-automation-id='questionItem']", timeout=10000)
                                logging.info(f"Page loaded successfully on attempt {attempt+1}.")
                                break 
                            except Exception as e:
                                logging.warning(f"  Attempt {attempt+1}/3 failed to load page: {e}. Retrying...")
                                await asyncio.sleep(5)
                        else: 
                            raise Exception("Page failed to load after 3 attempts.")
                        
                        # 4. Pass the whole profile to the fill function
                        all_answers = await fill_all_questions(page, profile)

                        submit_button = page.locator("button[data-automation-id='submitButton']")
                        if await submit_button.is_visible():
                            await submit_button.click()
                        else:
                            logging.error("Could not find Submit button.")
                            continue 

                        # 5. Log and UPDATE THE COUNT
                        if all_answers:
                            # Log the full profile
                            writer.writerow([
                                all_answers.get("faculty"), all_answers.get("role"),
                                all_answers.get("sex"), all_answers.get("years_affiliated"),
                                all_answers.get("prior_csr"), all_answers.get("csr_sources"),
                                all_answers.get("likert_answers"),
                                all_answers.get("persona_type") # Log the persona
                            ])
                            faculty_targets[selected_faculty]["count"] += 1
                            logging.info(f"Submission {submission_counter} complete and logged for {selected_faculty}.")
                        else:
                            logging.warning(f"Submission {submission_counter} failed, skipping log.")

                        # 6. Check if all MINIMUMS are met
                        all_mins_met = all(d["count"] >= d["min"] for d in faculty_targets.values())
                        if all_mins_met:
                            logging.info("\nAll minimum quotas have been met! Stopping.")
                            break 
                        
                        await page.locator("a:has-text('Submit another response')").click()
                        logging.info(f"Waiting {SUBMISSION_MIN_DELAY}-{SUBMISSION_MAX_DELAY}s before next submission...")
                        await rand_sleep(SUBMISSION_MIN_DELAY, SUBMISSION_MAX_DELAY) 

                    except Exception as e:
                        logging.error(f"Error during submission {submission_counter}: {e}", exc_info=False) # exc_info=True for full trace
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