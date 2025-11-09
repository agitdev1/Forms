"""
Automated Microsoft Forms submitter using Playwright.
(v5: Crash-Proof, Human-like Behavior)

Features:
- STATE PERSISTENCE: Saves progress to submission_state.json and resumes on restart.
- Quota-based submission system (min/max per faculty)
- Total max submission cap
- Advanced, realistic "Persona" system:
  - 'officer', 'default', 'disengaged', 'straight_liner'
- Conditional logic (e.G., years affiliated matches prior participation)
- Realistic "Other" field entry with HUMAN-LIKE TYPING.
- "THINKING" DELAYS: Simulates reading time *before* answering.
- Resilient page-loading with 3x retry
- Professional logging to both console and file (automation.log)
"""
from config import *
import time
import random
import csv
import re
import asyncio
import copy
import logging
import json # NEW: For state persistence
import os   # NEW: For checking if files exist
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
# Quiets Playwright's own logs to keep ours clean
logging.getLogger("playwright").setLevel(logging.WARNING) 

fake = Faker()




async def rand_sleep(min_delay, max_delay):
    await asyncio.sleep(random.uniform(min_delay, max_delay))

def pick_likert(persona, question_text):
    """
    (NEW) Selects a Likert choice based on the persona AND the question theme.
    """
    # 1. Handle special "straight_liner" case
    if persona == 'straight_liner':
        return "Somewhat Agree"
    
    # 2. Handle "inconsistent officer" case (10% chance of random negative answer)
    if persona == 'officer' and random.random() < 0.10:
        return random.choice(["Disagree", "Strongly Disagree"])
    
    # 3. Handle Themed Personas
    
    if persona == 'uninformed':
        if any(k in question_text for k in COMMUNICATION_KEYWORDS):
            return random.choice(["Strongly Disagree", "Disagree"])
        if any(k in question_text for k in FEATURE_KEYWORDS):
            return random.choice(["Agree", "StrongLY Agree"])
        return random.choice(["Somewhat Agree", "Agree"]) # They are motivated, just uninformed

    elif persona == 'apathetic': # This persona is truly disengaged
        if any(k in question_text for k in MOTIVATION_KEYWORDS):
            return random.choice(["Strongly Disagree", "Disagree"])
        if any(k in question_text for k in FEATURE_KEYWORDS):
            return random.choice(["Strongly Disagree", "Disagree"])
        if any(k in question_text for k in COMMUNICATION_KEYWORDS):
            return random.choice(["Agree", "Somewhat Agree"]) # "Yeah, I see the emails, I just delete them."
        return random.choice(["Somewhat Agree", "Disagree"])

    elif persona == 'busy':
        if any(k in question_text for k in ACCESSIBILITY_KEYWORDS):
            return random.choice(["Strongly Disagree", "Disagree"]) # "The schedule always sucks."
        if any(k in question_text for k in MOTIVATION_KEYWORDS):
            return random.choice(["Agree", "StrongLY Agree"]) # "I want to, but I can't."
        return random.choice(["Somewhat Agree", "Agree"])

    # 4. Handle 'officer' (normal positive) and 'default' (neutral)
    weights_key = 'officer' if persona == 'officer' else 'default'
    weights = PERSONA_LIKERT_WEIGHTS.get(weights_key, PERSONA_LIKERT_WEIGHTS['default'])
    return random.choices(LIKERT_CHOICES, weights=weights, k=1)[0]

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
    
    elif persona_type == 'disengaged' or persona_type == 'apathetic':
        profile["role"] = "Student"
        profile["years_affiliated"] = random.choice(years_affiliated)
        profile["prior_csr"] = "None"
    
    else: # 'default', 'busy', 'uninformed', 'straight_liner'
        profile["role"] = "Student"
        profile["years_affiliated"] = random.choice(years_affiliated)
        # Make 'prior_csr' consistent with 'years_affiliated'
        if profile["years_affiliated"] == "Less than 1 year":
            profile["prior_csr"] = random.choice(["None", "1 - 2"])
        else:
            profile["prior_csr"] = random.choice(["None", "1 - 2", "3 - 5"])
            
    return profile

async def fill_all_questions(page, profile):
    """
    Finds all VISIBLE question blocks on the page and fills them.
    (CORRECTED to use PERSONA_DELAYS from CONFIG)
    """
    all_answers = profile.copy() 
    all_likert_answers = []
    
    # === FIX: Get the persona type and delays from the profile ===
    persona_type = all_answers.get("persona_type", "default")
    # Get the min/max delays for this persona from the CONFIG
    min_delay, max_delay = PERSONA_DELAYS.get(persona_type, (3.0, 5.0)) # Fallback to 3-5s
    # ==========================================================

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
            # Use a faster typing delay for "rushing" personas
            typing_delay = random.randint(10, 50) if persona_type in ['busy', 'disengaged', 'straight_liner'] else random.randint(50, 150)
            
            await block_locator.locator("input[type='text']").press_sequentially(
                text, delay=typing_delay
            )
            return True
        except Exception as e:
            logging.warning(f"Could not fill 'Other' text. Error: {e}")
            return False
    # --- End of helpers ---

    blocks_locator = page.locator(
    "div[data-automation-id='questionItem'], " +
    "div[class*='question-item-content']"
)
    count = await blocks_locator.count()
    if count == 0:
        logging.warning("No question blocks found on this page.")
        return {}
    logging.info(f"Found {count} question blocks to fill... (Persona: {persona_type}, Speed: {min_delay}-{max_delay}s)")

    for i in range(count):
        block = blocks_locator.nth(i)
        
        # === FIX: Use persona-based "Thinking" Time ===
        logging.info(f"  ... 'reading' question {i+1}/{count}, sleeping {min_delay}-{max_delay}s...")
        await rand_sleep(min_delay, max_delay)
        # ============================================
        
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
            if random.random() < 0.05: # 5% Chance
                if await click_option(block, "Other"):
                    other_text = random.choice(REALISTIC_OTHER_SOURCES)
                    await fill_text_input(block, other_text)
                    all_answers["csr_sources"] = f"Other: {other_text}"
            else:
                choices = random.sample(csr_info_sources[:-1], k=random.randint(1, 3))
                for c in choices:
                    await click_option(block, c)
                    await asyncio.sleep(0.2)
                all_answers["csr_sources"] = ", ".join(choices)
        else:
            # Use smart, themed Likert picker
            choice = pick_likert(persona_type, txt) 
            if await click_likert_option(block, choice):
                all_likert_answers.append(choice)
        
    all_answers["likert_answers"] = ", ".join(all_likert_answers)
    return all_answers


async def main():
    """
    Main function with a quota-based system.
    (UPDATED with State Persistence)
    """
    logging.info("=============================================")
    logging.info("Starting automation with respondent quotas...")
    
    # === NEW: Load State from File ===
    faculty_targets = copy.deepcopy(FACULTY_TARGETS)
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, 'r') as f:
                saved_state = json.load(f)
            logging.info(f"Found state file '{STATE_FILE}'. Resuming progress...")
            for faculty_name, data in saved_state.items():
                if faculty_name in faculty_targets:
                    faculty_targets[faculty_name]["count"] = data.get("count", 0)
        except Exception as e:
            logging.warning(f"Could not load state file: {e}. Starting a fresh run.")
    else:
        logging.info(f"No state file '{STATE_FILE}' found. Starting a fresh run.")
    # ==================================
    
    total_min_needed = sum(d["min"] for d in faculty_targets.values())
    logging.info(f"Target: At least {total_min_needed} total submissions.")
    logging.info(f"Absolute Stop: Script will stop if it reaches {TOTAL_MAX_SUBMISSIONS} total submissions.")

    headers = [
        "faculty", "role", "sex", "years_affiliated",
        "prior_csr", "csr_sources", "likert_answers", "persona_type"
    ]
    
    # Check if CSV exists to decide on writing headers
    csv_file_exists = os.path.exists(LOG_CSV)
    
    submission_counter = sum(d["count"] for d in faculty_targets.values()) # Start count from saved state
    logging.info(f"Resuming with {submission_counter} total submissions already logged.")

    try:
        # === NEW: Open CSV in 'append' mode ===
        with open(LOG_CSV, "a", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            if not csv_file_exists or f.tell() == 0:
                writer.writerow(headers) # Write headers only if file is new/empty
            # ====================================

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
                        random.shuffle(priority_faculties)
                        selected_faculty = priority_faculties[0]
                    else:
                        selected_faculty = random.choice(available_faculties)
                    
                    profile = create_persona_profile()
                    profile["faculty"] = selected_faculty
                    
                    logging.info(f"Running for: {selected_faculty} (Persona: {profile['persona_type']})")
                    
                    try:
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
                        
                        all_answers = await fill_all_questions(page, profile)

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
                                all_answers.get("likert_answers"),
                                all_answers.get("persona_type")
                            ])
                            f.flush() # Ensure it's written to disk immediately
                            
                            faculty_targets[selected_faculty]["count"] += 1
                            logging.info(f"Submission {submission_counter} complete and logged for {selected_faculty}.")

                            # === NEW: Save State to File ===
                            try:
                                with open(STATE_FILE, 'w') as sf:
                                    json.dump(faculty_targets, sf, indent=4)
                                logging.info(f"Progress saved to {STATE_FILE}.")
                            except Exception as e:
                                logging.warning(f"Could not save state file: {e}")
                            # ===============================
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
                        logging.error(f"Error during submission {submission_counter}: {e}", exc_info=False)
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