# ===================================================================
# ========================== CONFIG =================================
# ===================================================================

# ---  Respondent Quotas (EDIT THESE) ---
FACULTY_TARGETS = {
    "CITHM": {"min": 201, "max": 268, "count": 0},
    "COT":   {"min": 21,  "max": 28,  "count": 0},
    "CIR":   {"min": 7,   "max": 9,   "count": 0},
    "CBA":   {"min": 41,  "max": 55,  "count": 0},
    "CAS":   {"min": 30,  "max": 40,  "count": 0},
}
# ----------------------------------------

# --- Submission Speed (EDIT THESE) ---
# NEW: Persona-based "thinking" time (min, max seconds)
PERSONA_DELAYS = {
    "officer": (5.0, 8.0),  # Careful, thoughtful
    "default": (4.0, 7.0),  # Average
    "uninformed": (4.0, 6.0), # Average, maybe a bit faster
    "busy": (2.0, 4.0),  # Rushing a bit
    "apathetic": (2.0, 4.0),  # Rushing a bit
    "disengaged": (1.5, 3.0),  # Clicking quickly
    "straight_liner": (0.5, 1.5)   # Machine-gun clicking
}

# Delay between one submission finishing and the next one starting
SUBMISSION_MIN_DELAY = 3.0
SUBMISSION_MAX_DELAY = 5.0
# ----------------------------------------

# --- ⚙️ General Settings (EDIT THESE) ---
TOTAL_MAX_SUBMISSIONS = 10 
FORM_URL = "https://forms.office.com/r/tq1WJ0CWT0"
HEADLESS = False  # Set to True for faster, background execution
LOG_CSV = "submitted_responses.csv"
STATE_FILE = "submission_state.json" 

# --- 🤖 Persona / Answer Configuration ---
PERSONA_CHOICES = ['default', 'officer', 'uninformed', 'apathetic', 'busy', 'straight_liner']
PERSONA_WEIGHTS = [0.40,       0.20,      0.15,         0.10,        0.10,   0.05]
# (40% default, 20% officer, 15% uninformed, 10% apathetic, 10% busy, 5% straight-liner)

# ===================================================================
# ====================== END OF CONFIG ==============================
# ===================================================================

# NEW: Likert keyword lists
# These keywords match the question groups you provided.
COMMUNICATION_KEYWORDS = ["communication", "notifies", "well-informed", "find details", "plan ahead"]
ENGAGEMENT_KEYWORDS = ["voice ideas", "input is asked", "co-create", "accommodate diverse", "approaching organizers", "feedback is openly"]
MOTIVATION_KEYWORDS = ["belonging", "understanding of community", "build my personal", "aligns with my personal", "social value"]
ACCESSIBILITY_KEYWORDS = ["Sign-up... is easy", "scheduled at times", "Location... is accessible", "know whom to contact", "preparations... communicated"]
FEATURE_KEYWORDS = ["centralized dashboard", "feature to RSVP", "showcase my past", "incentivize my attendance"]
IMPACT_KEYWORDS = ["marginalized or indigenous", "direct positive impact", "feel proud"]

# Likert choices for each persona
PERSONA_LIKERT_WEIGHTS = {
    "officer": [0.05, 0.10, 0.20, 0.45, 0.20], # Positive
    "default": [0.15, 0.30, 0.35, 0.15, 0.05], # Neutral
    "disengaged": [0.40, 0.30, 0.20, 0.05, 0.05]  # Negative (Used by 'apathetic')
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