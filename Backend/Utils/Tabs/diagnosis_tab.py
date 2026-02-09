import sys
import os
import json
import re
import requests
import vertexai
from datetime import datetime
from vertexai.generative_models import GenerativeModel, Part

# Add Backend to path for imports
BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../"))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from Utils.Tabs.llmparser import llmresponsedetailed
from Utils.logger_config import setup_logger, log_extraction_start, log_extraction_complete, log_extraction_output

# Setup logger
logger = setup_logger(__name__)

# Initialize Vertex AI
vertexai.init(project="prior-auth-portal-dev", location="us-central1")


## What all is to be extracted from the relevant documents for the diagnosis tab
"""1. Header Details (Patient Summary)
primary_diagnosis: Non-Small Cell Lung Cancer (NSCLC)
histologic_type: Adenocarcinoma
diagnosis_date: March 12, 2023
initial_tnm_stage: T2aN1M0 (Stage IIB)
current_tnm_stage: T2aN2M1a (Stage IVA)
metastatic_status: Yes - Active metastases
metastatic_sites: Contralateral lung, pleural nodules
recurrence_status: Progressive disease

2. Stage Evolution Timeline
timeline_event_date: March 2023, June 2024, Current Status
timeline_stage_group: Stage IIB, Stage IVA, Stage IVA
timeline_tnm_status: T2aN1M0, T2aN2M1a, Metastatic
timeline_description: Initial diagnosis after biopsy, Disease progression detected, Multiple metastatic sites

3. Disease Course Duration (Footer)
duration_since_diagnosis: 21 months since initial diagnosis
duration_since_progression: 6 months since progression to metastatic disease
"""


pdf_url = ""


def extract_diagnosis_header_with_gemini(pdf_input):
    """
    Extract diagnosis header data using Vertex AI Gemini SDK.

    Args:
        pdf_input: Either bytes (PDF content) or URL/path to the PDF file

    Returns:
        Dictionary containing extracted diagnosis header data
    """
    # Handle both bytes and file path/URL inputs
    if isinstance(pdf_input, bytes):
        logger.info(f"📤 Using PDF bytes ({len(pdf_input)} bytes)")
        pdf_bytes = pdf_input
    elif pdf_input.startswith("http"):
        # Handle Google Drive URLs
        logger.info(f"📥 Downloading PDF from URL: {pdf_input}")
        if "drive.google.com" in pdf_input:
            match = re.search(r'/file/d/([^/]+)', pdf_input)
            if match:
                file_id = match.group(1)
                download_url = f"https://drive.google.com/uc?export=download&id={file_id}"
            else:
                raise ValueError("Could not extract file ID from Google Drive URL")
        else:
            download_url = pdf_input

        response = requests.get(download_url, allow_redirects=True)
        response.raise_for_status()
        pdf_bytes = response.content
        logger.info(f"✅ Downloaded {len(pdf_bytes)} bytes")
    else:
        # Assume it's a file path
        logger.info(f"📤 Reading PDF from path: {pdf_input}")
        with open(pdf_input, "rb") as f:
            pdf_bytes = f.read()

    # REFINED INSTRUCTIONS
    # Build prompt from extraction instructions and description

    extraction_instruction = ("Extract comprehensive clinical summary data for the patient's primary cancer diagnosis from the medical records."
    "1. CANCER IDENTIFICATION: Identify the primary cancer type (e.g., Non-Small Cell Lung Cancer, Pleural Mesothelioma) AND the specific histologic subtype (e.g., Adenocarcinoma, Epithelioid, Sarcomatoid). "
    "CRITICAL FORMATTING: Use proper medical terminology with correct spacing and capitalization. For example: 'Non-Small Cell Lung Cancer' (NOT 'Nonsmall cell lung cancer' or 'NSCLC' alone), 'Small Cell Lung Cancer' (NOT 'Smallcell'), 'Renal Cell Carcinoma' (NOT 'Renalcell'). "
    "Check ALL document sections for histology: Pathology reports, Biopsy results, Diagnosis section, Clinical notes. The histology may be embedded in the diagnosis text. "
    "Extract the diagnosis date."
    "2. INITIAL STAGING: Find the staging information documented at the time of INITIAL/FIRST diagnosis. This is the baseline staging when the cancer was first identified. Look for terms like 'at diagnosis', 'initial presentation', or the earliest mentioned staging in the timeline."
    "3. CURRENT STAGING: Find the MOST RECENT or CURRENT staging information. This reflects the latest disease status. Look for terms like 'current', 'most recent', 'latest', 'now shows', 'restaging', 'progression', or dates closest to the document date. "
    "IMPORTANT: If no recent staging is explicitly mentioned (no restaging, no progression noted, no new TNM documented), this likely means the staging has NOT changed from initial diagnosis. In this case, use the same values from initial_staging for current_staging."
    "4. STAGING FORMAT - CRITICAL RULES:"
    " - TNM field: Extract ONLY the TNM classification (e.g., 'T2a N1 M0', 'T2aN1M0', 'T4N3M1c'). "
    "   Include all components (T, N, M) with their modifiers (prefixes like c/p/y and suffixes like letters/numbers). "
    "   ABSOLUTELY NEVER use the word 'Stage' in the TNM field. TNM is separate from stage."
    " - AJCC Stage field: Extract the full AJCC stage designation and it MUST start with 'Stage' (e.g., 'Stage IIB', 'Stage IVA', 'Stage 4', 'Stage IIIA'). "
    "   Include stage type prefix if mentioned (e.g., 'Pathologic Stage IIIA', 'Clinical Stage IB'). "
    "   The word 'Stage' is MANDATORY in this field."
    "5. DISEASE STATUS: Extract metastatic status (whether cancer has spread), specific metastatic sites (organs/locations), and recurrence/disease progression status."
    "CRITICAL METASTATIC SITE RULE: DO NOT list the primary organ as a metastatic site. The primary cancer site is where the cancer originated - metastatic sites are where it has SPREAD TO."
    "Examples:"
    "  - Lung cancer patient: Valid metastatic sites = Brain, Bone, Liver, Adrenal, Pleura, Contralateral lung. INVALID: 'Lung' alone."
    "  - Breast cancer patient: Valid metastatic sites = Bone, Lung, Liver, Brain. INVALID: 'Breast'."
    "  - Prostate cancer patient: Valid metastatic sites = Bone, Lymph nodes, Lung. INVALID: 'Prostate'."
    "6. KEY RULES:"
    " - If only one staging is documented in the record, use it for both initial_staging and current_staging."
    " - If no recent/current staging is mentioned and there's no documentation of progression or restaging, assume no change occurred and copy initial_staging to current_staging."
    " - If the document mentions 'upstaging', 'downstaging', 'progression', or 'restaging', ensure these changes are reflected in current_staging with the new TNM/stage values."
    " - Return null for any field not explicitly stated in the document."
    " - Do not infer or calculate values."
    "- If some data is not available then mention that the data is not available and do not hallucinate."
    ""
    "CRITICAL FORMATTING ENFORCEMENT:"
    "- TNM fields: NEVER EVER include 'Stage' - only T, N, M components"
    "- AJCC stage fields: ALWAYS start with 'Stage'"
    "Return as a JSON object matching the schema below.")



    description = {
    "primary_diagnosis": "The formal clinical name of the primary cancer. This should be the main cancer type being treated. IMPORTANT: Use proper medical terminology with correct spacing (e.g., 'Non-Small Cell Lung Cancer' NOT 'Nonsmall cell lung cancer', 'Small Cell Lung Cancer' NOT 'Smallcell lung cancer'). Standardize diagnosis names: capitalize each major word, use hyphens appropriately, and ensure proper spacing. Examples: 'Non-Small Cell Lung Cancer', 'Pleural Mesothelioma', 'Breast Carcinoma', 'Colorectal Adenocarcinoma', 'Small Cell Lung Cancer', 'Renal Cell Carcinoma'. Look in: Problem List, Diagnosis section, ICD-10 codes, Assessment section, or explicit diagnostic statements in clinical notes.",
    "histologic_type": "The specific microscopic cell type or histologic subtype documented in the medical record. This can come from pathology report, biopsy, or clinical diagnosis. Examples: 'Adenocarcinoma', 'Squamous cell carcinoma', 'Epithelioid', 'Sarcomatoid', 'Biphasic', 'Small cell', 'Large cell', 'Ductal carcinoma', 'Invasive lobular'. If the histology is embedded in the primary diagnosis (e.g., 'Epithelioid Pleural Mesothelioma'), extract just the histologic subtype ('Epithelioid'). Look in: Pathology section, Biopsy results, Diagnosis section, Clinical notes. Return null ONLY if absolutely no histologic information exists in the document.",
    "diagnosis_date": "The exact date when the cancer was first diagnosed in ISO format YYYY-MM-DD (e.g., '2023-03-15'). Look for phrases like 'diagnosed on', 'initial diagnosis date', or earliest mention of cancer detection.",
    "initial_staging": {
    "tnm": "CRITICAL: TNM classification ONLY - this field must NEVER contain the word 'Stage'. This is the T-N-M tumor staging classification at initial/first diagnosis. Format examples: 'T2a N1 M0', 'T2aN1M0', 'pT1c pN2 cM0', 'cT3 cN2 cM1a', 'T4 N3 M1c'. Include prefixes (c=clinical, p=pathologic, y=post-therapy) and all modifiers. The TNM field describes Tumor size (T), Node involvement (N), and Metastasis status (M). DO NOT put stage groups like 'Stage IV' or 'Stage IIB' here - those go in ajcc_stage field. If staging evolved from initial diagnosis, this should capture the EARLIEST TNM mentioned. IMPORTANT: Return null (not empty string, not 'N/A', not 'NA') if no TNM classification is documented in the record.",
    "ajcc_stage": "CRITICAL: AJCC stage group ONLY - this field must ALWAYS contain the word 'Stage'. Format examples: 'Stage IIB', 'Stage IIIA', 'Pathologic Stage IB', 'Clinical Stage IVA', 'Stage IV'. Include the stage type prefix (Clinical/Pathologic) if documented. This is the baseline stage when cancer was first found. DO NOT put TNM classifications like 'T2 N1 M0' here - those go in the tnm field."
    },
    "current_staging": {
    "tnm": "CRITICAL: TNM classification ONLY - this field must NEVER contain the word 'Stage'. This is the MOST RECENT T-N-M tumor staging classification. Format examples: 'T4 N3 M1c', 'cT2 cN1 cM1b', 'ypT0 ypN0 cM0', 'T2a N1 M0'. This should reflect the latest disease extent documented in the record with Tumor size (T), Node involvement (N), and Metastasis status (M). Look for most recent imaging, pathology, or clinical assessment. DO NOT put stage groups like 'Stage IV' or 'Stage IIA' here - those go in ajcc_stage field. Return null if no TNM is documented.",
    "ajcc_stage": "CRITICAL: AJCC stage group ONLY - this field must ALWAYS contain the word 'Stage'. This is the MOST RECENT stage group. Format examples: 'Stage IVB', 'Stage IIA', 'Clinical Stage IVA', 'Pathologic Stage IIIB', 'Stage IV'. This is the current or latest stage reflecting current disease status. If disease progressed or responded to treatment, this should show the updated stage. DO NOT put TNM classifications like 'T4 N3 M1c' here - those go in the tnm field."
    },
    "metastatic_status": "Clear statement of metastatic spread. Examples: 'Yes - Active metastases', 'No metastatic disease', 'Metastatic', 'Limited stage', 'Extensive stage', 'M0 - No distant metastasis'. This indicates if cancer has spread beyond the primary site.",
    "metastatic_sites": "Array of specific anatomical sites where metastases are present. CRITICAL RULES: (1) If metastatic_status indicates metastasis but NO specific sites are documented, return ['Sites not specified in report']. (2) If specific metastatic sites are documented, list them (e.g., ['Brain', 'Liver', 'Bone'], ['Bone', 'Lymph nodes']). (3) If NO metastasis (M0 or 'No metastatic disease'), return empty array []. (4) CRITICAL: DO NOT list the primary organ as a metastatic site. For example, if primary cancer is lung cancer, do NOT include 'Lung' as a metastatic site unless it's specifically 'Contralateral lung' (opposite lung from primary). For lung cancer, valid metastatic sites include: Brain, Bone, Liver, Adrenal glands, Contralateral lung, Pleura, etc. - but NOT just 'Lung'. Similarly, for breast cancer, do NOT list 'Breast' as a metastatic site. Never return null.",
    "recurrence_status": "Current disease behavior or progression state. Examples: 'Initial diagnosis - no prior cancer history', 'Progressive disease', 'Stable disease', 'Recurrent disease', 'Complete response', 'Partial response', 'Local recurrence', 'Distant recurrence'. This describes the disease trajectory."
    }
    GEMINI_PROMPT = f"""
    {extraction_instruction}

    OUTPUT SCHEMA (STRICT JSON):
    {json.dumps(description, indent=2)}

    CRITICAL FORMATTING VALIDATION RULES - YOU MUST FOLLOW THESE:
    1. TNM fields (initial_staging.tnm, current_staging.tnm): NEVER EVER include the word 'Stage'
       - Example of CORRECT format: "T2a N1 M0", "T4N3M1c"
       - Example of WRONG format: "Stage T2a N1 M0", "Stage IVA"
    2. AJCC Stage fields (initial_staging.ajcc_stage, current_staging.ajcc_stage): MUST ALWAYS start with 'Stage'
       - Example of CORRECT format: "Stage IVA", "Stage 4", "Stage IIB"
       - Example of WRONG format: "IVA", "4", "IIB"
    3. Before outputting JSON, verify each staging field follows these rules
    4. Return valid JSON only.
    """

    logger.info("🤖 Generating diagnosis header extraction with Vertex AI Gemini...")

    # Initialize the model
    model = GenerativeModel("gemini-2.5-flash")

    # Wrap PDF bytes in Part object
    doc_part = Part.from_data(data=pdf_bytes, mime_type="application/pdf")

    # Make API request
    try:
        response = model.generate_content(
            [doc_part, GEMINI_PROMPT],
            generation_config={
                "temperature": 0,
                "top_p": 1
            }
        )
        logger.info("✅ Gemini diagnosis header extraction complete")
    except Exception as e:
        logger.error(f"❌ API request failed: {e}")
        raise

    # Parse JSON response
    try:
        response_text = response.text.strip()
        logger.info(f"📄 Extracted response text ({len(response_text)} chars)")

        # Use regex to extract JSON from markdown code blocks
        json_pattern = r'```(?:json)?\s*([\s\S]*?)\s*```'
        match = re.search(json_pattern, response_text)

        if match:
            response_text = match.group(1).strip()
            logger.info("🧹 Cleaned markdown code blocks from response using regex")
        else:
            response_text = response_text.strip()
            logger.info("ℹ️  No markdown code blocks found, using response as is")

        extracted_data = json.loads(response_text)
        logger.info("✅ JSON parsed successfully")
        return extracted_data

    except (json.JSONDecodeError, AttributeError) as e:
        logger.error(f"❌ Failed to parse Gemini response: {e}")
        logger.error(f"Raw response text (first 500 chars): {response_text[:500] if 'response_text' in locals() else 'N/A'}")
        raise


def extract_diagnosis_evolution_with_gemini(pdf_input):
    """
    Extract diagnosis evolution timeline data using Vertex AI Gemini SDK.

    Args:
        pdf_input: Either bytes (PDF content) or URL/path to the PDF file

    Returns:
        Dictionary containing extracted diagnosis evolution timeline data
    """
    # Handle both bytes and file path/URL inputs
    if isinstance(pdf_input, bytes):
        logger.info(f"📤 Using PDF bytes ({len(pdf_input)} bytes)")
        pdf_bytes = pdf_input
    elif pdf_input.startswith("http"):
        logger.info(f"📥 Downloading PDF from URL: {pdf_input}")
        if "drive.google.com" in pdf_input:
            match = re.search(r'/file/d/([^/]+)', pdf_input)
            if match:
                file_id = match.group(1)
                download_url = f"https://drive.google.com/uc?export=download&id={file_id}"
            else:
                raise ValueError("Could not extract file ID from Google Drive URL")
        else:
            download_url = pdf_input

        response = requests.get(download_url, allow_redirects=True)
        response.raise_for_status()
        pdf_bytes = response.content
        logger.info(f"✅ Downloaded {len(pdf_bytes)} bytes")
    else:
        logger.info(f"📤 Reading PDF from path: {pdf_input}")
        with open(pdf_input, "rb") as f:
            pdf_bytes = f.read()

    extraction_instruction = """
    Extract a Treatment and Stage Evolution Timeline for the patient.

    ⚠️ CRITICAL: ADVANCED CLINICAL REASONING RULES - READ THIS FIRST ⚠️

    GENERAL CLINICAL REASONING RULES:

    1. SYNTHESIZE, DON'T JUST SCRAPE:
       - DO NOT rely solely on 'Regimen' tables or timeline visualizations
       - You MUST cross-reference the 'Assessment', 'Plan', 'Disease History', 'Interim History', and 'Treatment History' sections
       - Build a chronological map of therapy by synthesizing information across ALL sections
       - If a specific date is requested, scan the entire narrative to find treatment mentions around that timeframe
       - Tables are SUMMARIES - the full truth is in the clinical narrative

    2. WINDOW-BASED LOGIC FOR TREATMENT DATES:
       - Identify drug START and END dates explicitly mentioned (e.g., 'from 01/15/2024 to 06/20/2024')
       - Identify 'Cycle' mentions with dates (e.g., 'Cycle #6 completed on 12/4/24', 'Cycle 3 Day 1 on 11/10/24')
       - If a requested date falls WITHIN a treatment window (between start and end dates), that treatment was ACTIVE
       - If a requested date coincides with a cycle date, that regimen was the 'Active Regimen' at that time
       - Example: If 'Carboplatin + Pemetrexed Cycle 6 on 12/4/24' is mentioned, then for December 2024, the active regimen is 'Carboplatin + Pemetrexed'
       - Look for phrases: 'started on', 'initiated', 'began', 'completed on', 'finished', 'last dose', 'discontinued on', 'stopped'

    3. HANDLE DATA GAPS - DEEP SCAN REQUIREMENT:
       - If a 'Treatment' field in a table says 'No data', is empty, or is blank for a specific month/timeframe, YOU MUST perform a 'DEEP SCAN'
       - DEEP SCAN means: Read through the entire clinical narrative (Assessment, Plan, Interim History, Progress Notes) to find ANY mention of drugs administered during that timeframe
       - Look for treatment mentions in sentences like:
         * 'Patient continued on [drug] during [month]'
         * 'Completed Cycle [#] of [regimen] on [date]'
         * '[Drug] was administered on [date]'
         * 'Patient receiving [drug] as of [date]'
         * 'Proceeded with [regimen] in [month]'
       - CRITICAL: If the visual timeline is blank for a month but the narrative mentions treatment during that month, YOU MUST extract and report that treatment
       - Example: Timeline shows 'No data' for December 2024, but Assessment says 'finished Cycle 6 on 12/4/24' → Output should be the regimen with that cycle

    4. CONCURRENT & MAINTENANCE THERAPY DETECTION:
       - Look for phrases indicating MULTIPLE simultaneous drugs:
         * 'along with', 'in combination with', 'plus', 'with', 'and'
         * 's/p' (status post - meaning after completing one treatment, another follows)
         * 'maintenance' (ongoing treatment after initial therapy)
         * 'concurrent' (given at the same time)
       - Ensure BOTH/ALL drugs are captured in the systemic_regimen field
       - Example: 'Carboplatin + Pemetrexed along with Pembrolizumab' → systemic_regimen should be 'Carboplatin + Pemetrexed + Pembrolizumab'
       - Example: 'Maintenance Pembrolizumab after induction chemotherapy' → Capture both the induction chemo and maintenance immunotherapy
       - Do NOT miss secondary drugs like immunotherapy or targeted agents given alongside primary chemotherapy

    5. STATUS CONFIRMATION FROM RECENT HISTORY:
       - Use the most recent 'Interim History', 'Plan', or 'Assessment' section NEAR the target date to confirm treatment status
       - Look for status phrases:
         * 'Continued on [drug]' = treatment is ONGOING
         * 'Completed [regimen]' = treatment has ENDED
         * 'Proceeded with [drug]' = treatment was INITIATED or CONTINUED
         * 'Currently receiving [drug]' = treatment is ACTIVE
         * 'Treatment ongoing' = still on therapy
         * 'Finished therapy' = treatment completed
       - If the status near a date indicates 'Continued' or 'Proceeded', the treatment is ACTIVE at that time
       - Use this status confirmation to override blank table cells

    EXAMPLE APPLICATION OF RULES:

    Scenario: Visual timeline table shows 'No data' for December 2024. However, in the Assessment section dated 12/4/24, you find:
    'Patient completed Cycle 6 of Carboplatin AUC 5 + Pemetrexed 500mg/m2 on 12/4/24. Treatment ongoing. Plan to proceed with maintenance Pembrolizumab.'

    CORRECT EXTRACTION:
    - For December 2024 timeline entry:
      * systemic_regimen: 'Carboplatin AUC 5 + Pemetrexed 500mg/m2 (Cycle 6 completed 12/4/24)'
      * key_findings: Include mention that Cycle 6 was completed on this date
      * Do NOT output 'No data' or leave blank

    WRONG EXTRACTION:
    - systemic_regimen: 'No data' or null or blank
    - Reason: You failed to perform deep scan of narrative text

    ⚠️ CRITICAL: RELAPSE DETECTION - READ THIS FIRST ⚠️

    BEFORE creating the timeline, determine if this is a relapse case by examining the ENTIRE document:

    1. CHECK INITIAL DIAGNOSIS STAGE:
       - Look at the FIRST cancer diagnosis mentioned in the document
       - Was the initial stage early/localized? (Stage I, Stage II, Stage III, Stage IIIA, Stage IIIB, etc.)
       - Or was it already metastatic at diagnosis? (Stage IV, Stage IVA, Stage IVB, M1)

    2. CHECK INITIAL TREATMENT INTENT:
       - Was curative intent treatment given initially?
       - Look for: Surgery (lobectomy, resection, excision), Radiation therapy, Adjuvant/neoadjuvant chemotherapy
       - Early-stage disease + curative treatment = potential for cure

    3. CHECK FOR LATER METASTATIC DISEASE:
       - Does the patient later develop metastatic disease (Stage IV, distant metastases, M1)?
       - Look for: "new metastases", "progression to Stage IV", "now metastatic", "distant spread"
       - Compare timing: Was there a gap (months/years) between initial treatment and metastatic presentation?

    4. RELAPSE IDENTIFICATION RULE:
       ⚠️ IF initial diagnosis = Stage I/II/III (early-stage, localized)
       AND patient received curative intent treatment (surgery/radiation/chemo)
       AND later developed metastatic disease (Stage IV, distant mets)
       → THIS IS A RELAPSE CASE

       The timeline entry where metastatic disease first appears should have:
       - disease_status: "Recurrence" (NOT "Initial diagnosis", NOT "Disease progression")
       - is_relapse: true
       - relapse_pattern: Document where disease returned (e.g., "Distant recurrence - new sites: bone, brain")
       - comparison_to_initial: Compare to original stage (e.g., "More extensive than initial Stage II - now Stage IV with bone and brain metastases")
       - remission_duration: Calculate time from end of initial treatment to recurrence detection

    EXAMPLE RELAPSE SCENARIO:
    - 2009: Diagnosed with Stage II NSCLC → Right lower lobectomy + chemotherapy (curative intent)
    - 2017: PET scan shows new bone metastases, multiple lung nodules → Stage IV
    - CORRECT interpretation: This is RECURRENCE/RELAPSE after 8 years
    - INCORRECT interpretation: Do NOT call 2009 "Stage IV" or treat 2017 as just "progression"

    Create a new timeline entry ONLY when there is a major oncologic transition, including:
    1. Initial cancer diagnosis
    2. Objective disease progression (explicitly mentioned recurrence or worsening)
    3. Explicitly documented AJCC stage or TNM change
    4. Major treatment strategy change ONLY when accompanied by disease progression or stage change

    ⚠️ CRITICAL: DO NOT CREATE SEPARATE TIMELINE ENTRIES FOR THESE SCENARIOS ⚠️

    DO NOT create separate entries for:
    - Drug dose changes (e.g., reducing Osimertinib from 80mg to 40mg)
    - Drug schedule modifications (e.g., daily → 3x/week dosing)
    - Stopping a drug due to toxicity when the disease stage remains the same
    - Starting a new drug after stopping another when both are in the SAME LINE of therapy and disease has NOT progressed
    - Temporary treatment holds/pauses due to side effects
    - Switching between drugs within the same treatment line (e.g., switching from one TKI to another TKI)

    WHEN THESE CHANGES SHOULD BE IGNORED:
    - The disease stage remains UNCHANGED (e.g., Stage IV → Stage IV)
    - The disease status is STABLE or showing response (NOT progressing)
    - The change is due to toxicity management, side effects, or tolerability adjustments
    - The treatment change is within the same line of therapy without disease progression

    EXAMPLES OF WHAT NOT TO CREATE SEPARATE ENTRIES FOR:
    ❌ BAD: Separate entry for "Lorlatinib stopped" when patient remains Stage IV stable disease
    ❌ BAD: Separate entry for "Zykadia (Ceritinib) initiated" when patient remains Stage IV stable disease
    ❌ BAD: Separate entry for "Zykadia stopped" when patient remains Stage IV stable disease
    ❌ BAD: Separate entry for "Osimertinib dose reduced from 80mg to 40mg" when Stage IV unchanged

    ✅ CORRECT: Single entry showing the LINE of therapy with regimen changes noted in the details
    ✅ CORRECT: "Stage IV Disease progression" as a new entry when imaging shows worsening
    ✅ CORRECT: "Recurrence" as a new entry when cancer returns after remission

    ONLY CREATE SEPARATE ENTRIES WHEN:
    ✓ Disease has PROGRESSED (new metastases, tumor growth, worsening disease)
    ✓ Stage has CHANGED (e.g., Stage II → Stage IV, Stage IVA → Stage IVB)
    ✓ Disease has RECURRED after remission
    ✓ Initial diagnosis
    ✓ Significant treatment phase change WITH disease progression (e.g., first-line → second-line due to progression)

    Do NOT create timeline entries for routine follow-ups, supportive care, symptom management (pain meds, steroids), or labs without a change in oncologic intent.

    RELAPSE/PROGRESSION DETECTION:
    - If you detect disease progression, recurrence, or relapse (check disease_status, key_findings, stage changes), ensure the disease_status field reflects this accurately ('Disease progression', 'Recurrence').
    - A regimen change coinciding with disease progression should be treated as a major oncologic transition and warrant a new timeline entry.
    - A regimen change without disease progression (same stage, stable disease) should NEVER create a new timeline entry, regardless of whether it's a dose change, drug switch, or complete class change. Treatment modifications without disease progression are NOT timeline-worthy events.

    FOR EACH TIMELINE ENTRY, YOU MUST EXTRACT THE FOLLOWING REQUIRED FIELDS:

    1. DATE: Extract the date when this oncologic phase began. Use ONLY these formats:
       - Specific date: 'YYYY-MM-DD' (e.g., '2024-06-15', '2023-03-12')
       - Month and year: 'Month YYYY' (e.g., 'June 2024', 'March 2023', 'February 2022')
       - Year only (if month unknown): 'YYYY' (e.g., '2023', '2022')
       NEVER use vague terms like 'Late 2025', 'Early 2023', 'Late 2025 - Early 2026'.
       If exact date is unknown but you know it's around a certain time, use the middle of that period:
       - 'Late 2025' → 'December 2025' or '2025-12-01'
       - 'Early 2023' → 'January 2023' or '2023-01-01'
       - 'Mid-2024' → 'June 2024' or '2024-06-01'
       For the most recent entry, use 'Current Status' as the date label.

    2. STAGE INFORMATION (CRITICAL - DO NOT OMIT):
       - stage_header: Extract the AJCC stage. MUST start with 'Stage'. Format: 'Stage IIB', 'Stage IVB', 'Stage 4'.
         * If 'IVA' is found, output 'Stage IVA'.
         * If no stage is explicitly mentioned for this time point, look for the most recently mentioned stage in the document and use that.
         * For pre-diagnosis findings (e.g., initial nodule discovery before formal cancer diagnosis), use 'Pre-diagnosis finding' as the stage_header.
         * For entries where staging was truly not performed or documented, use 'Staging not performed'.
         * Set to null ONLY as a last resort if you cannot determine any context.
       - tnm_status: Extract the complete TNM classification. NEVER include the word 'Stage'.
         * Format: 'T2aN1M0', 'T4N3M1c'.
         * If no TNM is explicitly mentioned for this time point, look for the most recently mentioned TNM in the document and use that.
         * For pre-diagnosis findings or entries without TNM, set to null (it's acceptable to have null TNM for pre-diagnosis entries).
         * Set to null if no TNM information is available for this timeline point.

    3. DISEASE STATUS (REQUIRED): Choose exactly one:
       - 'Initial diagnosis'
       - 'Disease progression' (worsening/spread WITHOUT prior remission)
       - 'Recurrence' (cancer returns AFTER a period of remission/complete response/NED)
       - 'Stable disease' (ONLY if explicitly stated or imaging confirms no change)
       - 'Partial response' (tumor shrinkage per RECIST criteria, but cancer remains)
       - 'Complete remission' (all signs of cancer have disappeared)

       CRITICAL CLINICAL DISTINCTIONS:

       PARTIAL RESPONSE vs COMPLETE REMISSION (Based on RECIST Criteria):
       - Use 'Partial response' when:
         * Objective tumor shrinkage is documented (typically ≥30% decrease in sum of target lesion diameters)
         * Imaging shows decreased tumor size, decreased FDG/SUV uptake, or smaller masses
         * Cancer is still present but responding to treatment
         * Examples: "Mass decreased from 4.1cm to 2.8cm", "Decreased SUV uptake from 17.4 to 14", "Tumor shrinkage on imaging"
         * This is the CORRECT term during active treatment when tumors are shrinking

       - Use 'Complete remission' ONLY when:
         * ALL signs of cancer have disappeared on imaging
         * No detectable tumors or lesions remain
         * Often documented as "complete response (CR)", "no evidence of disease (NED)", "complete metabolic response"
         * This is rare and should only be used when explicitly stated or when imaging shows complete disappearance

       IMPORTANT: Do NOT use 'Complete remission' when there's still evidence of disease, even if it's responding well. Use 'Partial response' instead.

       ⚠️ RECURRENCE vs DISEASE PROGRESSION vs INITIAL DIAGNOSIS - CRITICAL DISTINCTION:

       Use 'Initial diagnosis' when:
       - This is the FIRST TIME cancer is being diagnosed in this patient
       - The patient has never had this cancer before
       - Use ONLY for the very first timeline entry when cancer was discovered

       Use 'Recurrence' when:
       - Patient had EARLY-STAGE disease (Stage I/II/III) initially
       - Patient received CURATIVE INTENT treatment (surgery, radiation, adjuvant chemo)
       - Cancer has NOW RETURNED after a disease-free period
       - Even if the recurrence presents as Stage IV (metastatic), this is still 'Recurrence'
       - Look for clues: Initial stage was I/II/III, curative treatment given, then later metastatic disease appears
       - Examples: "Stage II NSCLC in 2015 → lobectomy + chemo → Now 2023 with brain metastases"
       - Time gap between initial treatment and metastatic presentation suggests RELAPSE

       Use 'Disease progression' when:
       - Cancer was ALREADY metastatic (Stage IV) at initial diagnosis, and now worsening
       - Patient has had continuous disease without achieving remission
       - Cancer is spreading or growing in patients with ongoing disease
       - Examples: Stage IV at diagnosis → remained Stage IV with new mets appearing

       RELAPSE DETECTION CHECKLIST:
       ✓ Was initial diagnosis early-stage? (Stage I/II/III) → If YES, continue
       ✓ Was curative treatment given? (surgery, radiation, chemo) → If YES, continue
       ✓ Did patient later develop metastatic disease? (Stage IV, distant mets) → If YES, this is RECURRENCE
       ✓ Look for time gap between initial treatment and metastatic presentation

    4. RELAPSE INFORMATION (CRITICAL - EXTRACT ONLY IF disease_status = 'Recurrence'):
       If you identified disease_status as 'Recurrence', you MUST populate the relapse_info object:

       - is_relapse: Set to true (this is a relapse case)

       - relapse_pattern: WHERE did the cancer return? Extract the specific location pattern:
         * If cancer returned at the same anatomical site as initial diagnosis: "Local recurrence at [site]"
         * If cancer appeared at NEW sites not involved initially: "Distant recurrence - new sites: [list sites]"
         * If both: "Both local and distant - [details]"
         * CRITICAL: If initial diagnosis was localized (Stage I/II/III) and recurrence is metastatic (Stage IV), this is DISTANT RECURRENCE
         * Example: "Distant recurrence at new sites: brain (3 lesions) and L3 vertebra"
         * Example: "Distant recurrence - bone metastases and multiple lung nodules, whereas initial diagnosis was localized Stage II"
         * Example: "Local recurrence at original right upper lobe site"
         * Look in: Current imaging vs initial staging/imaging, pathology notes, physician assessment

       - comparison_to_initial: HOW does this relapse compare to the initial diagnosis?
         * CRITICAL: If initial stage was I/II/III and relapse is Stage IV, you MUST note this progression
         * Compare stage: "More extensive than initial [stage] - now [new stage]"
         * Compare burden: "Similar disease burden", "More aggressive presentation", "Limited compared to initial"
         * Compare sites: "New metastatic sites (brain, bone) vs initial localized disease"
         * Example: "More extensive than initial Stage II - now Stage IV with bone and lung metastases"
         * Example: "More extensive than initial Stage IIB - now Stage IV with brain and bone metastases"
         * Example: "Progressed from localized Stage IIIA to metastatic Stage IV with distant spread"
         * Example: "Less extensive - single brain lesion vs original Stage IIIB with mediastinal involvement"
         * Look for: Comparison statements in notes, review of initial vs current staging

       - remission_duration: Calculate or extract the disease-free interval:
         * Calculate time from end of initial treatment to recurrence detection
         * Look for phrases: "disease-free for 18 months", "recurrence after 2-year remission", "8 years after initial treatment"
         * If you can calculate from dates (initial treatment completion date → recurrence detection date), do so
         * Format: "18 months", "2 years", "8 years", "approximately 5 years"
         * Example: If initial surgery was 2009 and metastases detected in 2017, remission_duration = "approximately 8 years"

       - relapse_detected_by: HOW was the relapse discovered?
         * "Routine surveillance PET-CT", "New neurologic symptoms prompted MRI", "Rising tumor markers prompted restaging"
         * "Surveillance imaging", "Symptom-driven workup (bone pain)", "Routine follow-up CT scan"
         * Extract from clinical narrative, imaging orders, or reason for presentation

       If disease_status is NOT 'Recurrence', set is_relapse to false and other relapse fields to null.

    5. TREATMENT SPLIT (CRITICAL - READ CAREFULLY):
       You must separate systemic drug treatments from local modalities to ensure accurate Line of Therapy counting.

       - systemic_regimen: Extract ONLY drug-based anti-cancer therapies.
         * Include: Chemotherapy, Immunotherapy, Targeted Therapy.
         * Exclude: Radiation, Surgery, Pain meds, Supportive care.
         * If treatment is paused/stopped, indicate here.
         * CRITICAL - APPLY DEEP SCAN RULES:
           1. If table/timeline shows 'No data' or blank, scan Assessment/Plan/Interim History sections
           2. Look for cycle mentions (e.g., 'Cycle 6 on 12/4/24') to identify active treatment
           3. Look for treatment window mentions (e.g., 'from Date A to Date B')
           4. If a requested date falls in a treatment window or matches a cycle date, extract that treatment
           5. Look for concurrent therapy phrases: 'along with', 'plus', 'in combination with', 'maintenance'
           6. Capture ALL drugs mentioned together (e.g., 'Carboplatin + Pemetrexed + Pembrolizumab')
         * CRITICAL - STATUS CONFIRMATION:
           1. Check most recent Assessment/Plan near the target date
           2. Look for 'Continued', 'Completed', 'Proceeded', 'Currently receiving'
           3. Use this status to confirm if treatment is active

       - local_therapy: Extract ONLY focal/local treatments.
         * Include: Radiation Therapy (WBRT, SBRT, SRS), Cancer-Directed Surgery (Lobectomy, Resection).
         * Exclude: Systemic drugs.

    6. KEY FINDINGS: Extract 2-3 specific clinical findings (imaging, pathology, molecular) that justify this entry.
       CRITICAL EXCLUSIONS - Do NOT include:
       - Symptoms or subjective feelings
       - TNM staging information (e.g., "TNM: cT3, cN0, cM1b") - already displayed separately
       - AJCC stage information (e.g., "Clinical Stage IVA", "Stage IV") - already displayed separately
       - Generic diagnosis statements that just repeat the cancer type
       - Relapse comparison information (already in relapse_info.comparison_to_initial)

       INCLUDE only objective clinical findings:
       - Specific imaging measurements (e.g., "Mass decreased from 4.1 cm to 2.8 cm")
       - Pathology results (e.g., "Biopsy confirmed small cell carcinoma")
       - Molecular markers (e.g., "PD-L1 expression 60%")
       - Treatment response indicators (e.g., "SUV uptake decreased from 17.4 to 14")
       - New metastatic sites or disease changes

       Max 3 findings.

    7. TOXICITIES: Extract treatment-related toxicities only if explicitly documented.

    CRITICAL REQUIREMENTS:
    - stage_header MUST start with 'Stage'.
    - tnm_status MUST NOT contain 'Stage'.
    - Distinguish strictly between 'systemic_regimen' (drugs) and 'local_therapy' (radiation/surgery).
    - If disease_status = 'Recurrence', populate ALL relapse_info fields (is_relapse, relapse_pattern, comparison_to_initial).
    - If disease_status is NOT 'Recurrence', set is_relapse = false in relapse_info.
    - Return valid JSON matching the schema.

    RELAPSE EXAMPLES:

    EXAMPLE 1 - Complete Remission → Metastatic Recurrence:
    If you find: "Patient had achieved complete remission after initial chemo. Now 18 months later, PET shows new brain metastases. Initial diagnosis was Stage IIIA localized NSCLC, now Stage IV with CNS involvement."

    Extract as:
    {
      "disease_status": "Recurrence",
      "relapse_info": {
        "is_relapse": true,
        "relapse_pattern": "Distant recurrence at new sites: brain (multiple metastases)",
        "comparison_to_initial": "More extensive than initial Stage IIIA localized disease - now Stage IV with brain metastases",
        "remission_duration": "18 months",
        "relapse_detected_by": "Surveillance PET-CT"
      }
    }

    EXAMPLE 2 - Early-Stage Curative Treatment → Years Later Metastatic Recurrence:
    If you find: "2009: Diagnosed with Stage II NSCLC, treated with right lower lobectomy and adjuvant chemotherapy (Gemcitabine + Taxol). 2017: Patient presented with bone pain. PET scan revealed new bone metastases and multiple lung nodules. Biopsy confirmed adenocarcinoma, consistent with recurrent NSCLC."

    Timeline Entry for 2009:
    {
      "date_label": "2009",
      "stage_header": "Stage II",
      "disease_status": "Initial diagnosis",
      "systemic_regimen": "Gemcitabine + Taxol",
      "local_therapy": "Right lower lobectomy",
      "relapse_info": {
        "is_relapse": false,
        "relapse_pattern": null,
        "comparison_to_initial": null,
        "remission_duration": null,
        "relapse_detected_by": null
      }
    }

    Timeline Entry for December 2017 (CRITICAL - This is RECURRENCE, not "Initial diagnosis Stage IV"):
    {
      "date_label": "December 2017",
      "stage_header": "Stage IV",
      "disease_status": "Recurrence",
      "systemic_regimen": "Cisplatin + Alimta + Avastin",
      "relapse_info": {
        "is_relapse": true,
        "relapse_pattern": "Distant recurrence - new sites: bone metastases and diffuse pulmonary metastases",
        "comparison_to_initial": "More extensive than initial Stage II localized disease - now Stage IV with bone and lung metastases",
        "remission_duration": "approximately 8 years",
        "relapse_detected_by": "Symptom-driven workup (bone pain) and imaging"
      }
    }

    KEY POINT: Even though 8 years passed, this is still RECURRENCE because the patient had early-stage disease with curative treatment initially.
    """

    description = {
        "timeline": [
            {
                "date_label": "String. REQUIRED. The specific date this phase began. MUST use one of these formats ONLY: 'YYYY-MM-DD' (e.g., '2024-06-15'), 'Month YYYY' (e.g., 'June 2024', 'March 2023'), or 'YYYY' (e.g., '2023'). For the most recent entry, use 'Current Status'. NEVER use vague terms like 'Late 2025', 'Early 2023', or date ranges like 'Late 2025 - Early 2026'.",
                "stage_header": "String. REQUIRED. MUST start with 'Stage' (e.g., 'Stage IVB'). For pre-diagnosis findings, use 'Pre-diagnosis finding'. For entries without staging, use 'Staging not performed'. Use most recent stage if available.",
                "tnm_status": "String. REQUIRED. TNM classification (e.g., 'T4N3M1c'). MUST NOT contain 'Stage'. Use most recent if missing.",
                "disease_status": "String. REQUIRED. One of: 'Initial diagnosis', 'Disease progression', 'Recurrence', 'Stable disease', 'Partial response', 'Complete remission'. Use 'Partial response' when tumors have shrunk but cancer remains (RECIST ≥30% decrease). Use 'Complete remission' ONLY when all signs of cancer have disappeared. During active treatment with tumor shrinkage, use 'Partial response' not 'Complete remission'.",

                # UPDATED FIELDS START HERE
                "systemic_regimen": "String. Drug-based treatments ONLY. Include Chemo, Immuno, Targeted therapy (e.g., 'Carboplatin + Pemetrexed'). CRITICAL EXTRACTION RULES: (1) DO NOT rely only on tables - SCAN Assessment, Plan, Disease History, Interim History sections. (2) If table shows 'No data' or blank, perform DEEP SCAN of narrative for treatment mentions during that timeframe. (3) Look for cycle mentions (e.g., 'Cycle 6 on 12/4/24') and extract the regimen. (4) Look for treatment windows (start/end dates) - if timeline date falls within window, extract that treatment. (5) Look for concurrent therapy phrases: 'along with', 'plus', 'in combination with', 'maintenance' - capture ALL drugs. (6) Check recent Assessment/Plan for status: 'Continued', 'Completed', 'Proceeded' to confirm if treatment is active. (7) NEVER output null/'No data' if narrative mentions treatment during that time. Set to null ONLY if this event is only surgery/radiation.",
                "local_therapy": "String. Focal treatments ONLY. Include Radiation (e.g., 'WBRT', 'SBRT') or Surgery (e.g., 'Lobectomy'). Set to null if none occurred.",
                # UPDATED FIELDS END HERE

                # RELAPSE FIELDS - ONLY POPULATE IF disease_status is 'Recurrence'
                "relapse_info": {
                    "is_relapse": "Boolean. True if this entry represents disease recurrence/relapse after remission or complete response. False otherwise.",
                    "relapse_pattern": "String. REQUIRED if is_relapse=true. Describe where disease returned: 'Local recurrence at original site', 'Distant recurrence at new sites', 'Both local and distant', 'Same anatomical location as initial diagnosis', 'New metastatic sites not present initially'. Include specific locations.",
                    "comparison_to_initial": "String. REQUIRED if is_relapse=true. Compare current disease state to initial diagnosis. Examples: 'More extensive than initial Stage IIIA presentation - now Stage IV with brain mets', 'Similar burden to initial diagnosis - isolated lung nodule', 'Less extensive - single brain lesion vs original Stage IIIB disease', 'New sites: brain and bone, whereas initial diagnosis was localized lung only'.",
                    "remission_duration": "String. Optional. Duration of disease-free interval if documented (e.g., '18 months', '2 years'). Calculate from last documentation of remission/NED to current relapse date if both dates available.",
                    "relapse_detected_by": "String. Optional. How relapse was discovered: 'Routine surveillance imaging', 'Symptom-driven workup', 'Rising tumor markers', 'Clinical examination', 'PET-CT restaging'."
                },

                "key_findings": [
                    "String. Critical finding 1. DO NOT include TNM or AJCC stage here - they are displayed separately.",
                    "String. Critical finding 2. Focus on imaging measurements, pathology results, molecular markers, or treatment response.",
                    "String. Critical finding 3 (optional). Exclude any staging information.",
                    "String. Critical finding 4 (optional).",
                    "String. Critical finding 5 (optional)."
                ],
                "toxicities": [
                    {
                        "effect": "String (e.g., 'Neutropenia')",
                        "grade": "String (e.g., 'Grade 3')"
                    }
                ],
                "summary_count_check": "Integer. Hard verification of how many findings are listed (Must be between 3 and 5).",
                "Justification": "String. Why have you selected this as a timeline entry."
            }
        ]
    }

    GEMINI_PROMPT = f"""
You are a deterministic clinical data extraction engine for oncology medical records.

{extraction_instruction}

OUTPUT SCHEMA (STRICT):
{json.dumps(description, indent=2)}

FINAL VALIDATION CHECKLIST - VERIFY BEFORE RETURNING:
1. All timeline events are in chronological order
2. All required fields are present for each timeline entry
3. CRITICAL: stage_header fields start with 'Stage' (e.g., 'Stage IVA', NOT 'IVA'), OR use 'Pre-diagnosis finding' for pre-diagnosis entries, OR 'Staging not performed' if truly not documented
4. CRITICAL: tnm_status fields do NOT contain 'Stage' (e.g., 'T4N3M1c', NOT 'Stage T4N3M1c')
5. CRITICAL: key_findings do NOT contain TNM or AJCC stage information - these are displayed separately
6. key_findings should focus on imaging measurements, pathology results, molecular markers, and treatment response
7. For all timeline entries, attempt to provide meaningful stage_header values (either actual stage, 'Pre-diagnosis finding', or 'Staging not performed') rather than null
8. CRITICAL: Ensure you have NOT created separate timeline entries for:
   - Dose adjustments, drug stopping/starting, or schedule changes when stage and disease status remain unchanged
   - Treatment changes within the same line of therapy without disease progression
   - Drug switches due to toxicity when disease remains stable
9. Verify that each timeline entry represents a TRUE oncologic transition:
   - Initial diagnosis
   - Disease progression (new mets, tumor growth, worsening)
   - Stage change (e.g., Stage II → Stage IV)
   - Disease recurrence after remission
   - NOT treatment changes without progression
10. RELAPSE VALIDATION: If disease_status = 'Recurrence', ensure relapse_info is fully populated with:
    - is_relapse = true
    - relapse_pattern describing where disease returned
    - comparison_to_initial comparing current state to initial diagnosis
    - remission_duration if documented
11. RELAPSE VALIDATION: If disease_status is NOT 'Recurrence', ensure is_relapse = false
12. CLINICAL REASONING VALIDATION - CRITICAL:
    a. SYNTHESIS CHECK: Did you cross-reference Assessment, Plan, Disease History, and Interim History sections?
    b. DEEP SCAN CHECK: For ANY timeline entry where you initially found 'No data' or blank treatment:
       - Did you scan the entire narrative for treatment mentions during that timeframe?
       - Did you look for cycle mentions (e.g., 'Cycle 6 on 12/4/24')?
       - Did you look for treatment window mentions (e.g., 'started Date A, ended Date B')?
       - If narrative mentions treatment during that time, systemic_regimen MUST NOT be null/'No data'
    c. WINDOW-BASED LOGIC CHECK:
       - Did you identify drug start and end dates?
       - Did you check if requested dates fall within treatment windows?
       - Did you extract treatments when cycle dates match the timeline date?
    d. CONCURRENT THERAPY CHECK:
       - Did you look for 'along with', 'plus', 'in combination with', 'maintenance' phrases?
       - Did you capture ALL drugs mentioned together (not just the primary drug)?
       - Did you check for immunotherapy or targeted agents given alongside chemotherapy?
    e. STATUS CONFIRMATION CHECK:
       - Did you check the most recent Assessment/Plan/Interim History near each timeline date?
       - Did you look for 'Continued', 'Completed', 'Proceeded', 'Currently receiving' phrases?
       - Did you use this status to override blank table cells?
    f. EXAMPLE VALIDATION: If visual timeline shows 'No data' for December 2024, but Assessment says 'completed Cycle 6 on 12/4/24':
       - CORRECT: systemic_regimen = the regimen with cycle information
       - WRONG: systemic_regimen = null or 'No data'

OUTPUT FORMAT:
Return VALID JSON ONLY.
No explanations.
No markdown code blocks.
No commentary.
Just the JSON object following the schema above.
"""

    logger.info("🤖 Generating diagnosis evolution timeline extraction with Vertex AI Gemini...")

    model = GenerativeModel("gemini-2.5-flash")
    doc_part = Part.from_data(data=pdf_bytes, mime_type="application/pdf")

    try:
        response = model.generate_content(
            [doc_part, GEMINI_PROMPT],
            generation_config={
                "temperature": 0,
                "top_p": 1
            }
        )
        logger.info("✅ Gemini diagnosis evolution extraction complete")
    except Exception as e:
        logger.error(f"❌ API request failed: {e}")
        raise

    try:
        response_text = response.text.strip()
        logger.info(f"📄 Extracted response text ({len(response_text)} chars)")

        json_pattern = r'```(?:json)?\s*([\s\S]*?)\s*```'
        match = re.search(json_pattern, response_text)

        if match:
            response_text = match.group(1).strip()
            logger.info("🧹 Cleaned markdown code blocks from response using regex")
        else:
            response_text = response_text.strip()
            logger.info("ℹ️  No markdown code blocks found, using response as is")

        extracted_data = json.loads(response_text)
        logger.info("✅ JSON parsed successfully")

        # Post-process date labels to normalize formats
        if 'timeline' in extracted_data and isinstance(extracted_data['timeline'], list):
            for event in extracted_data['timeline']:
                if 'date_label' in event and event['date_label']:
                    event['date_label'] = normalize_date_label(event['date_label'])

        return extracted_data

    except (json.JSONDecodeError, AttributeError) as e:
        logger.error(f"❌ Failed to parse Gemini response: {e}")
        logger.error(f"Raw response text (first 500 chars): {response_text[:500] if 'response_text' in locals() else 'N/A'}")
        raise


def normalize_date_label(date_str):
    """
    Normalize date labels to consistent, parseable formats.

    Converts vague date terms to specific month/year formats:
    - 'Late 2025' → 'December 2025'
    - 'Early 2023' → 'January 2023'
    - 'Mid-2024' → 'June 2024'
    - 'Late 2025 - Early 2026' → 'December 2025'

    Args:
        date_str: Original date string

    Returns:
        Normalized date string in 'Month YYYY', 'YYYY-MM-DD', or 'YYYY' format
    """
    if not date_str:
        return date_str

    date_lower = date_str.lower().strip()

    # Handle "Current Status" - don't modify
    if 'current' in date_lower:
        return date_str

    # Extract year from the string
    import re
    year_match = re.search(r'\b(20\d{2})\b', date_str)
    if not year_match:
        return date_str  # Can't parse, return as-is

    year = year_match.group(1)

    # Handle vague date terms
    if 'late' in date_lower and '-' in date_str and ('early' in date_lower or 'mid' in date_lower):
        # "Late 2025 - Early 2026" → use the first year, late = December
        return f'December {year}'
    elif 'late' in date_lower:
        # "Late 2025" → "December 2025"
        return f'December {year}'
    elif 'early' in date_lower:
        # "Early 2023" → "January 2023"
        return f'January {year}'
    elif 'mid' in date_lower or 'middle' in date_lower:
        # "Mid-2024" → "June 2024"
        return f'June {year}'
    elif 'end' in date_lower:
        # "End 2024" → "December 2024"
        return f'December {year}'
    elif 'beginning' in date_lower or 'start' in date_lower:
        # "Beginning 2023" → "January 2023"
        return f'January {year}'

    # If it's already in a good format (Month YYYY, YYYY-MM-DD, YYYY), return as-is
    return date_str


def recalculate_durations(diagnosis_footer_data):
    """
    Recalculate duration_since_diagnosis, duration_since_progression, and duration_since_relapse
    based on actual dates and today's date, overriding any potentially incorrect durations from the document.

    Args:
        diagnosis_footer_data: Dictionary containing reference_dates with initial_diagnosis_date,
                              last_progression_date, and last_relapse_date

    Returns:
        Updated diagnosis_footer_data with corrected durations
    """
    try:
        today = datetime.now()
        reference_dates = diagnosis_footer_data.get('reference_dates', {})

        # Recalculate duration_since_diagnosis
        initial_diagnosis_date_str = reference_dates.get('initial_diagnosis_date')
        if initial_diagnosis_date_str and initial_diagnosis_date_str != 'null':
            try:
                # Parse the date (handles YYYY-MM-DD or YYYY-MM format)
                if len(initial_diagnosis_date_str) == 10:  # YYYY-MM-DD
                    initial_diagnosis_date = datetime.strptime(initial_diagnosis_date_str, '%Y-%m-%d')
                elif len(initial_diagnosis_date_str) == 7:  # YYYY-MM
                    initial_diagnosis_date = datetime.strptime(initial_diagnosis_date_str, '%Y-%m')
                else:
                    logger.warning(f"Unrecognized date format for initial_diagnosis_date: {initial_diagnosis_date_str}")
                    return diagnosis_footer_data

                # Calculate duration manually
                total_days = (today - initial_diagnosis_date).days

                # Calculate years and remaining days
                years = total_days // 365
                remaining_days = total_days % 365

                # Calculate months from remaining days (approximate: 30 days per month)
                months = remaining_days // 30
                remaining_days = remaining_days % 30

                # Format duration in human-readable format
                if years > 0:
                    if months > 0:
                        duration_str = f"{years} year{'s' if years > 1 else ''}, {months} month{'s' if months > 1 else ''}"
                    else:
                        duration_str = f"{years} year{'s' if years > 1 else ''}"
                elif months > 0:
                    duration_str = f"{months} month{'s' if months > 1 else ''}"
                elif remaining_days >= 7:
                    weeks = remaining_days // 7
                    duration_str = f"{weeks} week{'s' if weeks > 1 else ''}"
                elif remaining_days > 0:
                    duration_str = f"{remaining_days} day{'s' if remaining_days > 1 else ''}"
                else:
                    duration_str = "Less than 1 day"

                diagnosis_footer_data['duration_since_diagnosis'] = duration_str
                logger.info(f"✅ Recalculated duration_since_diagnosis: {duration_str} (from {initial_diagnosis_date_str} to {today.strftime('%Y-%m-%d')})")

            except Exception as e:
                logger.error(f"Error parsing initial_diagnosis_date: {e}")

        # Recalculate duration_since_progression
        last_progression_date_str = reference_dates.get('last_progression_date')
        if last_progression_date_str and last_progression_date_str != 'null' and last_progression_date_str is not None:
            try:
                # Parse the date
                if len(last_progression_date_str) == 10:  # YYYY-MM-DD
                    last_progression_date = datetime.strptime(last_progression_date_str, '%Y-%m-%d')
                elif len(last_progression_date_str) == 7:  # YYYY-MM
                    last_progression_date = datetime.strptime(last_progression_date_str, '%Y-%m')
                else:
                    logger.warning(f"Unrecognized date format for last_progression_date: {last_progression_date_str}")
                    return diagnosis_footer_data

                # Calculate duration manually
                total_days = (today - last_progression_date).days

                # Calculate years and remaining days
                years = total_days // 365
                remaining_days = total_days % 365

                # Calculate months from remaining days (approximate: 30 days per month)
                months = remaining_days // 30
                remaining_days = remaining_days % 30

                # Format duration
                if years > 0:
                    if months > 0:
                        duration_str = f"{years} year{'s' if years > 1 else ''}, {months} month{'s' if months > 1 else ''}"
                    else:
                        duration_str = f"{years} year{'s' if years > 1 else ''}"
                elif months > 0:
                    duration_str = f"{months} month{'s' if months > 1 else ''}"
                elif remaining_days >= 7:
                    weeks = remaining_days // 7
                    duration_str = f"{weeks} week{'s' if weeks > 1 else ''}"
                elif remaining_days > 0:
                    duration_str = f"{remaining_days} day{'s' if remaining_days > 1 else ''}"
                else:
                    duration_str = "Less than 1 day"

                diagnosis_footer_data['duration_since_progression'] = duration_str
                logger.info(f"✅ Recalculated duration_since_progression: {duration_str} (from {last_progression_date_str} to {today.strftime('%Y-%m-%d')})")

            except Exception as e:
                logger.error(f"Error parsing last_progression_date: {e}")

        # Recalculate duration_since_relapse
        last_relapse_date_str = reference_dates.get('last_relapse_date')
        if last_relapse_date_str and last_relapse_date_str != 'null' and last_relapse_date_str is not None:
            try:
                # Parse the date
                if len(last_relapse_date_str) == 10:  # YYYY-MM-DD
                    last_relapse_date = datetime.strptime(last_relapse_date_str, '%Y-%m-%d')
                elif len(last_relapse_date_str) == 7:  # YYYY-MM
                    last_relapse_date = datetime.strptime(last_relapse_date_str, '%Y-%m')
                else:
                    logger.warning(f"Unrecognized date format for last_relapse_date: {last_relapse_date_str}")
                    return diagnosis_footer_data

                # Calculate duration manually
                total_days = (today - last_relapse_date).days

                # Calculate years and remaining days
                years = total_days // 365
                remaining_days = total_days % 365

                # Calculate months from remaining days (approximate: 30 days per month)
                months = remaining_days // 30
                remaining_days = remaining_days % 30

                # Format duration
                if years > 0:
                    if months > 0:
                        duration_str = f"{years} year{'s' if years > 1 else ''}, {months} month{'s' if months > 1 else ''}"
                    else:
                        duration_str = f"{years} year{'s' if years > 1 else ''}"
                elif months > 0:
                    duration_str = f"{months} month{'s' if months > 1 else ''}"
                elif remaining_days >= 7:
                    weeks = remaining_days // 7
                    duration_str = f"{weeks} week{'s' if weeks > 1 else ''}"
                elif remaining_days > 0:
                    duration_str = f"{remaining_days} day{'s' if remaining_days > 1 else ''}"
                else:
                    duration_str = "Less than 1 day"

                diagnosis_footer_data['duration_since_relapse'] = duration_str
                logger.info(f"✅ Recalculated duration_since_relapse: {duration_str} (from {last_relapse_date_str} to {today.strftime('%Y-%m-%d')})")

            except Exception as e:
                logger.error(f"Error parsing last_relapse_date: {e}")

    except Exception as e:
        logger.error(f"Error in recalculate_durations: {e}")

    return diagnosis_footer_data


def extract_diagnosis_footer_with_gemini(pdf_input):
    """
    Extract diagnosis footer data using Vertex AI Gemini SDK.

    Args:
        pdf_input: Either bytes (PDF content) or URL/path to the PDF file

    Returns:
        Dictionary containing extracted diagnosis footer data
    """
    if isinstance(pdf_input, bytes):
        logger.info(f"📤 Using PDF bytes ({len(pdf_input)} bytes)")
        pdf_bytes = pdf_input
    elif pdf_input.startswith("http"):
        logger.info(f"📥 Downloading PDF from URL: {pdf_input}")
        if "drive.google.com" in pdf_input:
            match = re.search(r'/file/d/([^/]+)', pdf_input)
            if match:
                file_id = match.group(1)
                download_url = f"https://drive.google.com/uc?export=download&id={file_id}"
            else:
                raise ValueError("Could not extract file ID from Google Drive URL")
        else:
            download_url = pdf_input

        response = requests.get(download_url, allow_redirects=True)
        response.raise_for_status()
        pdf_bytes = response.content
        logger.info(f"✅ Downloaded {len(pdf_bytes)} bytes")
    else:
        logger.info(f"📤 Reading PDF from path: {pdf_input}")
        with open(pdf_input, "rb") as f:
            pdf_bytes = f.read()

    extraction_instruction = ("Extract temporal information about the patient's cancer diagnosis, disease progression, and relapse/recurrence. "
                                    "1. DIAGNOSIS DATE: Identify the date of the first cancer diagnosis and calculate the total duration from that date to the document signature date or current date mentioned in the document. "
                                    "2. PROGRESSION DATE: Identify the date of the most recent disease progression event (e.g., new metastases detected, disease advancement without prior remission, upstaging) and calculate the duration from that progression date to the document signature date. "
                                    "   If there is no documented progression, set duration_since_progression to 'N/A'. "
                                    "3. RELAPSE/RECURRENCE DATE (CRITICAL): Identify if there was a documented relapse or recurrence event. Relapse/recurrence means the cancer RETURNED after a period of remission, complete response, disease-free status, OR after curative intent treatment of early-stage disease. "
                                    "   CRITICAL RELAPSE DETECTION RULES: "
                                    "   ⚠️ PATTERN 1 - Early-Stage → Metastatic Recurrence: "
                                    "     If the document shows: "
                                    "     - Initial diagnosis was EARLY-STAGE (Stage I, II, or III - localized disease) "
                                    "     - Patient received CURATIVE INTENT treatment (surgery like lobectomy/resection + chemotherapy) "
                                    "     - Years later, patient developed METASTATIC disease (Stage IV, distant metastases) "
                                    "     → THIS IS RELAPSE/RECURRENCE, even if not explicitly called 'recurrence' in the document "
                                    "     → Extract the date when metastatic disease was first detected as the relapse date "
                                    "   "
                                    "   ⚠️ PATTERN 2 - Explicit Remission → Return of Disease: "
                                    "     Look for phrases like: 'recurrence', 'relapse', 'disease returned', 'cancer came back', 'recurrent disease', 'after remission', 'disease-free interval', 'following complete response' "
                                    "     → Extract the date when recurrence was documented "
                                    "   "
                                    "   IMPORTANT DISTINCTION: "
                                    "     - RELAPSE: Cancer returns AFTER achieving remission/complete response/NED OR after curative treatment of early-stage disease. There was a disease-free period or curative intent treatment. "
                                    "     - PROGRESSION: Cancer worsens or spreads in patients who had metastatic disease (Stage IV) from the start, continuous disease WITHOUT prior remission. "
                                    "   "
                                    "   If a relapse/recurrence event is identified (EITHER pattern above): "
                                    "     - Extract the date when the relapse/metastatic disease was detected or documented "
                                    "     - Calculate the duration from that relapse date to the document signature date "
                                    "     - Store the date in reference_dates.last_relapse_date "
                                    "   If NO relapse/recurrence (patient had Stage IV at initial diagnosis with continuous metastatic disease): "
                                    "     - Set duration_since_relapse to 'N/A' "
                                    "     - Set reference_dates.last_relapse_date to null "
                                    "   "
                                    "   EXAMPLE: "
                                    "   - 2009: Stage II NSCLC, lobectomy + chemo (curative intent) "
                                    "   - 2017: New bone metastases detected → Stage IV "
                                    "   - CORRECT: This is RELAPSE, last_relapse_date = 2017 date, duration_since_relapse = time from 2017 to now "
                                    "   - WRONG: Do NOT treat 2009 as 'Stage IV from the beginning' "
                                    "Return the output strictly as a JSON object matching the schema described. "
                                    "Express durations in human-readable format (e.g., '14 months', '3 months', '2 years', '18 months'). "
                                    "Do not infer values; if a value is not explicitly stated, return null.")

    description = {
                        "duration_since_diagnosis": "Total time from first ever diagnosis to the document signature date in human-readable format (e.g., '14 months', '2 years').",
                        "duration_since_progression": "Time elapsed from the most recent progression or new primary event to the document signature date in human-readable format (e.g., '3 months', '6 weeks'). Use 'N/A' if no progression is documented. NOTE: This is for continuous disease progression WITHOUT prior remission.",
                        "duration_since_relapse": "Time elapsed from the most recent relapse/recurrence event to the document signature date in human-readable format (e.g., '18 months', '6 months'). Use 'N/A' if no relapse/recurrence is documented. CRITICAL: This field is ONLY for cases where cancer RETURNED after a period of remission/complete response/NED. If the disease has been continuously present or progressively worsening without a remission period, use 'N/A'.",
                        "reference_dates": {
                            "initial_diagnosis_date": "The date of the first cancer diagnosis in ISO format (YYYY-MM-DD) or partial format (YYYY-MM).",
                            "last_progression_date": "The date of the most recent disease progression event in ISO format (YYYY-MM-DD) or partial format (YYYY-MM). Use null if no progression. This is for continuous progression events.",
                            "last_relapse_date": "The date when relapse/recurrence was detected or documented in ISO format (YYYY-MM-DD) or partial format (YYYY-MM). Use null if no relapse/recurrence occurred. CRITICAL: Only populate this if the patient had achieved remission/complete response/NED and then the cancer RETURNED. Look for explicit mentions of 'recurrence', 'relapse', 'disease returned after remission', 'recurrent disease'."
                        }
                    }

    GEMINI_PROMPT = f"""
You are a deterministic clinical data extraction engine for oncology medical records.

{extraction_instruction}

OUTPUT SCHEMA (STRICT):
{json.dumps(description, indent=2)}

FINAL VALIDATION:
- Ensure all fields in the schema are present in the output
- Use null for fields not explicitly documented
- Express durations in human-readable format

OUTPUT FORMAT:
Return VALID JSON ONLY.
No explanations.
No markdown code blocks.
No commentary.
Just the JSON object following the schema above.
"""

    logger.info("🤖 Generating diagnosis footer extraction with Vertex AI Gemini...")

    model = GenerativeModel("gemini-2.5-flash")
    doc_part = Part.from_data(data=pdf_bytes, mime_type="application/pdf")

    try:
        response = model.generate_content(
            [doc_part, GEMINI_PROMPT],
            generation_config={
                "temperature": 0,
                "top_p": 1
            }
        )
        logger.info("✅ Gemini diagnosis footer extraction complete")
    except Exception as e:
        logger.error(f"❌ API request failed: {e}")
        raise

    try:
        response_text = response.text.strip()
        logger.info(f"📄 Extracted response text ({len(response_text)} chars)")

        json_pattern = r'```(?:json)?\s*([\s\S]*?)\s*```'
        match = re.search(json_pattern, response_text)

        if match:
            response_text = match.group(1).strip()
            logger.info("🧹 Cleaned markdown code blocks from response using regex")
        else:
            response_text = response_text.strip()
            logger.info("ℹ️  No markdown code blocks found, using response as is")

        extracted_data = json.loads(response_text)
        logger.info("✅ JSON parsed successfully")

        # Recalculate durations based on actual dates and today's date
        extracted_data = recalculate_durations(extracted_data)

        return extracted_data

    except (json.JSONDecodeError, AttributeError) as e:
        logger.error(f"❌ Failed to parse Gemini response: {e}")
        logger.error(f"Raw response text (first 500 chars): {response_text[:500] if 'response_text' in locals() else 'N/A'}")
        raise


def diagnosis_extraction(pdf_input, use_gemini=True):
    """
    Extract diagnosis information from a PDF document.

    Args:
        pdf_input: Either bytes (PDF content), URL, or file path
        use_gemini: Whether to use Gemini pipeline (default: True)

    Returns:
        Tuple of (diagnosis_header, diagnosis_evolution_timeline, diagnosis_footer)
    """

    extraction_instruction_header =  ("Extract comprehensive clinical summary data for the patient's primary cancer diagnosis from the medical records."
                            "1. CANCER IDENTIFICATION: Identify the primary cancer type (e.g., Non-Small Cell Lung Cancer), specific histology (e.g., Adenocarcinoma), and the initial diagnosis date. Use proper medical terminology with correct spacing (e.g., 'Non-Small Cell Lung Cancer' NOT 'Nonsmall cell lung cancer')."
                            "2. INITIAL STAGING: Find the staging information documented at the time of INITIAL/FIRST diagnosis. This is the baseline staging when the cancer was first identified. Look for terms like 'at diagnosis', 'initial presentation', or the earliest mentioned staging in the timeline."
                            "3. CURRENT STAGING: Find the MOST RECENT or CURRENT staging information. This reflects the latest disease status. Look for terms like 'current', 'most recent', 'latest', 'now shows', 'restaging', 'progression', or dates closest to the document date. "
                            "IMPORTANT: If no recent staging is explicitly mentioned (no restaging, no progression noted, no new TNM documented), this likely means the staging has NOT changed from initial diagnosis. In this case, use the same values from initial_staging for current_staging."
                            "4. STAGING FORMAT: For both initial and current staging, extract:"
                            "   - TNM: The complete TNM classification (e.g., 'T2a N1 M0' or 'T2aN1M0'). Include all components (T, N, M) with their modifiers (prefixes like c/p/y and suffixes like letters/numbers). NEVER use the word 'Stage' in this field."
                            "   - AJCC Stage: The full AJCC stage designation (e.g., 'Stage IIB', 'Stage IVA', 'Pathologic Stage IIIA', 'Clinical Stage IB'). Include stage type prefix if mentioned. MUST contain the word 'Stage'."
                            "5. DISEASE STATUS: Extract metastatic status (whether cancer has spread), specific metastatic sites (organs/locations), and recurrence/disease progression status. CRITICAL: Do NOT list the primary organ as a metastatic site (e.g., for lung cancer, do NOT include 'Lung' as a metastatic site unless it's 'Contralateral lung')."
                            "6. KEY RULES:"
                            "   - If only one staging is documented in the record, use it for both initial_staging and current_staging."
                            "   - If no recent/current staging is mentioned and there's no documentation of progression or restaging, assume no change occurred and copy initial_staging to current_staging."
                            "   - If the document mentions 'upstaging', 'downstaging', 'progression', or 'restaging', ensure these changes are reflected in current_staging with the new TNM/stage values."
                            "   - Return null for any field not explicitly stated in the document."
                            "   - Do not infer or calculate values."
                            "Return as a JSON object matching the schema below.")

    description_header = {
                "primary_diagnosis": "The formal clinical name of the primary cancer. Use proper medical terminology with correct spacing and capitalization (e.g., 'Non-Small Cell Lung Cancer' NOT 'Nonsmall cell lung cancer', 'Small Cell Lung Cancer', 'Breast Carcinoma'). This should be the main cancer type being treated.",
                "histologic_type": "The specific microscopic cell type from pathology report (e.g., 'Adenocarcinoma', 'Squamous cell carcinoma', 'Ductal carcinoma'). This describes the cellular characteristics of the cancer.",
                "diagnosis_date": "The exact date when the cancer was first diagnosed in ISO format YYYY-MM-DD (e.g., '2023-03-15'). Look for phrases like 'diagnosed on', 'initial diagnosis date', or earliest mention of cancer detection.",
                "initial_staging": {
                    "tnm": "CRITICAL: TNM classification ONLY - NEVER EVER include 'Stage'. This is the T-N-M tumor staging classification at initial/first diagnosis. Format examples: 'T2a N1 M0', 'T2aN1M0', 'pT1c pN2 cM0', 'cT3 cN2 cM1a', 'T4 N3 M1c'. Include prefixes (c=clinical, p=pathologic, y=post-therapy) and all modifiers. The TNM field describes Tumor size (T), Node involvement (N), and Metastasis status (M). ABSOLUTELY DO NOT put stage groups like 'Stage IV' or 'Stage IIB' here - those go in ajcc_stage field. If staging evolved from initial diagnosis, this should capture the EARLIEST TNM mentioned. Return null if no TNM is documented.",
                    "ajcc_stage": "CRITICAL: AJCC stage group ONLY - MUST ALWAYS start with 'Stage'. Format examples: 'Stage IIB', 'Stage IIIA', 'Stage IB', 'Stage IVA', 'Stage IV', 'Stage 4'. Include stage type prefix if documented (e.g., 'Pathologic Stage IB', 'Clinical Stage IVA'). This is the baseline stage when cancer was first found. ABSOLUTELY DO NOT put TNM classifications like 'T2 N1 M0' here - those go in the tnm field."
                },
                "current_staging": {
                    "tnm": "CRITICAL: TNM classification ONLY - NEVER EVER include 'Stage'. This is the MOST RECENT T-N-M tumor staging classification. Format examples: 'T4 N3 M1c', 'cT2 cN1 cM1b', 'ypT0 ypN0 cM0', 'T2a N1 M0'. This should reflect the latest disease extent documented in the record with Tumor size (T), Node involvement (N), and Metastasis status (M). Look for most recent imaging, pathology, or clinical assessment. ABSOLUTELY DO NOT put stage groups like 'Stage IV' or 'Stage IIA' here - those go in ajcc_stage field. Return null if no TNM is documented.",
                    "ajcc_stage": "CRITICAL: AJCC stage group ONLY - MUST ALWAYS start with 'Stage'. This is the MOST RECENT stage group. Format examples: 'Stage IVB', 'Stage IIA', 'Stage IVA', 'Stage IIIB', 'Stage IV', 'Stage 4'. Include stage type prefix if documented (e.g., 'Clinical Stage IVA', 'Pathologic Stage IIIB'). This is the current or latest stage reflecting current disease status. If disease progressed or responded to treatment, this should show the updated stage. ABSOLUTELY DO NOT put TNM classifications like 'T4 N3 M1c' here - those go in the tnm field."
                },
                "metastatic_status": "Clear statement of metastatic spread. Examples: 'Yes - Active metastases', 'No metastatic disease', 'Metastatic', 'Limited stage', 'Extensive stage', 'M0 - No distant metastasis'. This indicates if cancer has spread beyond the primary site.",
                "metastatic_sites": "Array of specific anatomical sites where metastases are present. CRITICAL RULES: (1) If metastatic_status indicates metastasis but NO specific sites are documented, return ['Sites not specified in report']. (2) If specific metastatic sites are documented, list ALL sites mentioned (e.g., ['Brain', 'Liver', 'Bone'], ['Bone', 'Lymph nodes']). (3) If NO metastasis (M0 or 'No metastatic disease'), return empty array []. (4) CRITICAL: DO NOT list the primary organ as a metastatic site. For lung cancer, do NOT include 'Lung' unless it's 'Contralateral lung'. For breast cancer, do NOT list 'Breast'. Metastatic sites are where cancer has SPREAD TO, not the primary origin. Never return null.",
                "recurrence_status": "Current disease behavior or progression state. Examples: 'Initial diagnosis - no prior cancer history', 'Progressive disease', 'Stable disease', 'Recurrent disease', 'Complete response', 'Partial response', 'Local recurrence', 'Distant recurrence'. This describes the disease trajectory."
                }

    extraction_instruction_evolution_timeline = (
            "Extract a comprehensive chronological timeline of the patient's cancer diagnosis, staging changes, treatment history, and disease evolution."
            "OBJECTIVE: Create a complete timeline showing how the patient's cancer has progressed or responded over time, including all staging changes, treatments administered, and clinical findings."
            ""
            "FOR EACH DISTINCT TIME POINT in the patient's journey, extract the following:"
            ""
            "1. DATE/TIMEFRAME:"
            "   - Capture the specific date, month/year, or timeframe (e.g., 'March 2023', 'June 15, 2024', '2022-11', 'Current Status')."
            "   - If this is the most recent entry, label it as 'Current Status' or use the most recent date mentioned."
            "   - Ensure dates are in chronological order from earliest to most recent."
            ""
            "2. STAGE INFORMATION:"
            "   - timeline_stage_group: The AJCC stage at this time point (e.g., 'Stage IIB', 'Stage IVA', 'Stage IB'). Include stage type if mentioned (e.g., 'Pathologic Stage IIIA', 'Clinical Stage IVB')."
            "   - timeline_tnm_status: The complete TNM classification at this time point (e.g., 'T2a N1 M0', 'T4 N3 M1c', 'pT1c pN0 cM0'). Include all components with prefixes and modifiers."
            "   - If staging hasn't changed from previous entry, still include the same staging information."
            "   - For pre-diagnosis timeline entries (e.g., initial nodule discovery), look ahead in the document to find the eventual stage when diagnosis was made and use that."
            "   - Attempt to provide stage information for all timeline entries by looking forward or backward in the document rather than leaving it null."
            ""
            "3. CLINICAL DESCRIPTION:"
            "   - timeline_description: Brief description of what happened at this time point. Examples: 'Initial diagnosis after biopsy', 'Disease progression detected on CT', 'Complete response to chemotherapy', 'Local recurrence identified', 'Metastatic disease progression', 'Stable disease on follow-up'."
            ""
            "4. TREATMENT INFORMATION:"
            "   - regimen: The ANTI-CANCER treatment regimen ONLY. Extract chemotherapy, immunotherapy, targeted therapy, surgery, or radiation therapy. Include drug names with doses if available."
            "     Examples: 'Right upper lobectomy', 'Carboplatin AUC 5 + Pemetrexed 500mg/m2', 'Osimertinib 80mg daily', 'Pembrolizumab 200mg Q3W', 'Radiation therapy 60 Gy', 'No treatment - surveillance'."
            "   - EXCLUDE: Pain medications, anti-nausea drugs, supportive care medications, symptom management, and all non-cancer treatments."
            "   - If no cancer treatment was given, explicitly state 'Surveillance' or 'No active treatment'."
            ""
            "5. TOXICITIES:"
            "   - Extract all treatment-related side effects with their severity grades."
            "   - Format: [{\"effect\": \"Neutropenia\", \"grade\": \"Grade 3\"}, {\"effect\": \"Fatigue\", \"grade\": \"Grade 2\"}]"
            "   - Include CTCAE grade if mentioned (Grade 1-5) or severity descriptors (Mild, Moderate, Severe)."
            "   - If no toxicities are documented, return an empty array."
            ""
            "6. DISEASE FINDINGS:"
            "   - Extract ALL clinical, pathology, imaging, and molecular findings documented at this time point."
            "   - Return as an array of distinct findings, each as a separate string."
            "   - CRITICAL EXCLUSIONS - Do NOT include:"
            "     * TNM staging information (already displayed separately)"
            "     * AJCC stage information (already displayed separately)"
            "     * Generic diagnosis statements"
            "   - Include:"
            "     * Imaging findings: tumor size, number of lesions, location, measurements (e.g., '3 brain metastases measuring 5-8mm on MRI', 'Primary tumor decreased from 4cm to 2.5cm')"
            "     * Pathology findings: biopsy results, histology, grade (e.g., 'Biopsy confirmed adenocarcinoma', 'Well-differentiated tumor grade')"
            "     * Molecular/genomic findings: mutations, biomarkers, test results (e.g., 'EGFR exon 19 deletion detected', 'PD-L1 TPS 85%', 'ALK fusion positive')"
            "     * Clinical findings: symptoms, physical exam, performance status (e.g., 'ECOG 1', 'New onset seizures', 'Weight loss 10 pounds')"
            "     * Disease progression/response markers: RECIST criteria, tumor markers (e.g., 'Progressive disease per RECIST 1.1', 'CEA increased from 5 to 45')"
            "   - Format example: [\"Primary tumor 4.2cm in RUL\", \"Mediastinal lymphadenopathy 2cm\", \"EGFR exon 19 deletion\", \"PD-L1 50%\"]"
            ""
            "KEY GUIDELINES:"
            "- Create timeline entries for: initial diagnosis, staging changes, treatment starts, disease progression/response events, and current status."
            "- Each time point should be a distinct entry in the array, ordered chronologically."
            "- Include at least: initial diagnosis entry and current status entry."
            "- If staging changed over time (e.g., upstaging from Stage II to Stage IV), ensure this is captured with separate timeline entries."
            "- If specific information is not documented for a time point, use null for that field rather than inferring."
            ""
            "Return all timeline events in chronological order in the 'stage_evolution_timeline' array."
        )

    description_evolution_timeline = {
        "stage_evolution_timeline": [
            {
                "timeline_event_date": "The date, month/year, or timeframe for this event. Format examples: 'March 2023', '2024-06-15', 'June 2024', 'Current Status'. Use 'Current Status' for the most recent entry. Ensure chronological ordering.",
                "timeline_stage_group": "The AJCC stage group at this time point - MUST start with 'Stage'. Format examples: 'Stage IIB', 'Stage IVA', 'Stage IIIA', 'Stage IB', 'Stage IVB', 'Stage 4'. If you extract 'IVA', format as 'Stage IVA'. Include stage type prefix if documented (e.g., 'Pathologic Stage IIIA', 'Clinical Stage IB'). The word 'Stage' is MANDATORY.",
                "timeline_tnm_status": "The complete TNM classification at this time point - MUST NOT include 'Stage'. Format examples: 'T2a N1 M0', 'T2aN1M0', 'cT4 cN3 cM1c', 'pT1c pN0 cM0', 'T3 N2 M1a'. Include ONLY T, N, M components with prefixes (c/p/y) and modifiers. Do NOT put the word 'Stage' here.",
                "timeline_description": "Brief clinical summary of what occurred at this time point. Examples: 'Initial diagnosis after CT-guided biopsy', 'Disease progression with new brain metastases', 'Partial response to chemotherapy', 'Surgical resection completed', 'Stable disease on maintenance therapy', 'Complete metabolic response on PET scan'.",
                "regimen": "The ANTI-CANCER treatment regimen ONLY administered at or after this time point. Include: chemotherapy (e.g., 'Carboplatin AUC 5 + Pemetrexed 500mg/m2 Q3W'), immunotherapy (e.g., 'Pembrolizumab 200mg IV Q3W'), targeted therapy (e.g., 'Osimertinib 80mg PO daily'), surgery (e.g., 'Right upper lobectomy with lymph node dissection'), or radiation (e.g., 'Radiation 60 Gy in 30 fractions'). EXCLUDE: pain medications, anti-nausea drugs, supportive care, and non-cancer treatments. Include drug names, doses, routes, and frequency when available. If no cancer treatment, state 'Surveillance - no active treatment'.",
                "toxicities": [
                    {
                        "effect": "The specific toxicity or adverse effect name. Examples: 'Neutropenia', 'Diarrhea', 'Fatigue', 'Rash', 'Neuropathy', 'Nausea', 'Anemia', 'Thrombocytopenia'.",
                        "grade": "The severity grade using CTCAE grading. Format examples: 'Grade 1', 'Grade 2', 'Grade 3', 'Grade 4', 'Mild', 'Moderate', 'Severe'. Must include 'Grade' prefix for numeric grades."
                    }
                ],
                "disease_findings": "Array of distinct clinical findings at this time point. Each finding should be a separate string. DO NOT include TNM staging or AJCC stage information here - they are displayed separately. Include imaging results (tumor size, location, measurements), pathology results (cell type, grade, margins), molecular findings (mutations, biomarkers), clinical observations (symptoms, exam findings), and progression/response indicators. Format example: ['Primary mass 4.2cm x 3.8cm in right upper lobe', 'Mediastinal lymphadenopathy largest 2cm', 'No distant metastases on PET-CT', 'EGFR exon 19 deletion detected', 'PD-L1 expression 60%', 'ECOG performance status 1']. Return empty array if no findings documented."
            }
        ]
    }

    extraction_instruction_footer = ("Extract temporal information about the patient's cancer diagnosis, disease progression, and relapse/recurrence. "
                                    "1. DIAGNOSIS DATE: Identify the date of the first cancer diagnosis and calculate the total duration from that date to the document signature date or current date mentioned in the document. "
                                    "2. PROGRESSION DATE: Identify the date of the most recent disease progression event (e.g., new metastases detected, disease advancement without prior remission, upstaging) and calculate the duration from that progression date to the document signature date. "
                                    "   If there is no documented progression, set duration_since_progression to 'N/A'. "
                                    "3. RELAPSE/RECURRENCE DATE (CRITICAL): Identify if there was a documented relapse or recurrence event. Relapse/recurrence means the cancer RETURNED after a period of remission, complete response, or disease-free status. "
                                    "   Look for phrases like: 'recurrence', 'relapse', 'disease returned', 'cancer came back', 'recurrent disease', 'after remission', 'disease-free interval', 'following complete response'. "
                                    "   IMPORTANT DISTINCTION: "
                                    "     - RELAPSE: Cancer returns AFTER achieving remission/complete response/NED (No Evidence of Disease). There was a disease-free period. "
                                    "     - PROGRESSION: Cancer worsens or spreads WITHOUT a prior remission period (continuous disease). "
                                    "   If a relapse/recurrence event is documented: "
                                    "     - Extract the date when the relapse was detected or documented "
                                    "     - Calculate the duration from that relapse date to the document signature date "
                                    "     - Store the date in reference_dates.last_relapse_date "
                                    "   If NO relapse/recurrence is documented (initial diagnosis, stable disease, or continuous progression without remission): "
                                    "     - Set duration_since_relapse to 'N/A' "
                                    "     - Set reference_dates.last_relapse_date to null "
                                    "Return the output strictly as a JSON object matching the schema described. "
                                    "Express durations in human-readable format (e.g., '14 months', '3 months', '2 years', '18 months'). "
                                    "Do not infer values; if a value is not explicitly stated, return null.")
    description_footer = {
                        "duration_since_diagnosis": "Total time from first ever diagnosis to the document signature date in human-readable format (e.g., '14 months', '2 years').",
                        "duration_since_progression": "Time elapsed from the most recent progression or new primary event to the document signature date in human-readable format (e.g., '3 months', '6 weeks'). Use 'N/A' if no progression is documented. NOTE: This is for continuous disease progression WITHOUT prior remission.",
                        "duration_since_relapse": "Time elapsed from the most recent relapse/recurrence event to the document signature date in human-readable format (e.g., '18 months', '6 months'). Use 'N/A' if no relapse/recurrence is documented. CRITICAL: This field is ONLY for cases where cancer RETURNED after a period of remission/complete response/NED. If the disease has been continuously present or progressively worsening without a remission period, use 'N/A'.",
                        "reference_dates": {
                            "initial_diagnosis_date": "The date of the first cancer diagnosis in ISO format (YYYY-MM-DD) or partial format (YYYY-MM).",
                            "last_progression_date": "The date of the most recent disease progression event in ISO format (YYYY-MM-DD) or partial format (YYYY-MM). Use null if no progression. This is for continuous progression events.",
                            "last_relapse_date": "The date when relapse/recurrence was detected or documented in ISO format (YYYY-MM-DD) or partial format (YYYY-MM). Use null if no relapse/recurrence occurred. CRITICAL: Only populate this if the patient had achieved remission/complete response/NED and then the cancer RETURNED. Look for explicit mentions of 'recurrence', 'relapse', 'disease returned after remission', 'recurrent disease'."
                        }
                    }

    log_extraction_start(logger, "Diagnosis Tab (3 components)", str(pdf_input)[:100] if isinstance(pdf_input, bytes) else pdf_input)

    # Convert URL/path to bytes once to avoid multiple downloads
    pdf_bytes = None
    if isinstance(pdf_input, bytes):
        logger.info(f"📤 Using provided PDF bytes ({len(pdf_input)} bytes)")
        pdf_bytes = pdf_input
    elif isinstance(pdf_input, str) and pdf_input.startswith("http"):
        # Download once for all three extractions
        logger.info(f"📥 Downloading PDF once from URL: {pdf_input}")
        if "drive.google.com" in pdf_input:
            match = re.search(r'/file/d/([^/]+)', pdf_input)
            if match:
                file_id = match.group(1)
                download_url = f"https://drive.google.com/uc?export=download&id={file_id}"
            else:
                raise ValueError("Could not extract file ID from Google Drive URL")
        else:
            download_url = pdf_input

        response = requests.get(download_url, allow_redirects=True)
        response.raise_for_status()
        pdf_bytes = response.content
        logger.info(f"✅ Downloaded {len(pdf_bytes)} bytes (will reuse for all 3 extractions)")
    elif isinstance(pdf_input, str):
        # Assume it's a file path
        logger.info(f"📤 Reading PDF once from path: {pdf_input}")
        with open(pdf_input, "rb") as f:
            pdf_bytes = f.read()
        logger.info(f"✅ Read {len(pdf_bytes)} bytes (will reuse for all 3 extractions)")
    else:
        raise ValueError("pdf_input must be bytes, URL string, or file path string")

    if use_gemini:
        # Gemini pipeline - pass bytes to avoid multiple downloads
        logger.info("🤖 Using Vertex AI Gemini pipeline")

        logger.info("🔄 Extracting patient diagnosis header data (1/3)...")
        diagnosis_header = extract_diagnosis_header_with_gemini(pdf_bytes)
        log_extraction_output(logger, "Diagnosis Header", diagnosis_header)
        log_extraction_complete(logger, "Diagnosis Header", diagnosis_header.keys() if isinstance(diagnosis_header, dict) else None)

        logger.info("🔄 Extracting patient diagnosis stage evolution data (2/3)...")
        diagnosis_evolution_timeline = extract_diagnosis_evolution_with_gemini(pdf_bytes)
        log_extraction_output(logger, "Diagnosis Evolution Timeline", diagnosis_evolution_timeline)
        log_extraction_complete(logger, "Diagnosis Evolution Timeline", diagnosis_evolution_timeline.keys() if isinstance(diagnosis_evolution_timeline, dict) else None)

        logger.info("🔄 Extracting patient diagnosis footer data (3/3)...")
        diagnosis_footer = extract_diagnosis_footer_with_gemini(pdf_bytes)
        log_extraction_output(logger, "Diagnosis Footer", diagnosis_footer)
        log_extraction_complete(logger, "Diagnosis Footer", diagnosis_footer.keys() if isinstance(diagnosis_footer, dict) else None)
    else:
        # Legacy pipeline using llmresponsedetailed
        logger.info("📝 Using legacy llmresponsedetailed pipeline")

        logger.info("🔄 Extracting patient diagnosis header data (1/3)...")
        diagnosis_header = llmresponsedetailed(pdf_url, extraction_instructions= extraction_instruction_header, description=description_header)
        log_extraction_output(logger, "Diagnosis Header", diagnosis_header)
        log_extraction_complete(logger, "Diagnosis Header", diagnosis_header.keys() if isinstance(diagnosis_header, dict) else None)

        logger.info("🔄 Extracting patient diagnosis stage evolution data (2/3)...")
        diagnosis_evolution_timeline = llmresponsedetailed(pdf_url, extraction_instructions=extraction_instruction_evolution_timeline, description=description_evolution_timeline)
        log_extraction_output(logger, "Diagnosis Evolution Timeline", diagnosis_evolution_timeline)
        log_extraction_complete(logger, "Diagnosis Evolution Timeline", diagnosis_evolution_timeline.keys() if isinstance(diagnosis_evolution_timeline, dict) else None)

        logger.info("🔄 Extracting patient diagnosis footer data (3/3)...")
        diagnosis_footer = llmresponsedetailed(pdf_url, extraction_instructions=extraction_instruction_footer, description=description_footer)
        # Recalculate durations based on actual dates and today's date
        diagnosis_footer = recalculate_durations(diagnosis_footer)
        log_extraction_output(logger, "Diagnosis Footer", diagnosis_footer)
        log_extraction_complete(logger, "Diagnosis Footer", diagnosis_footer.keys() if isinstance(diagnosis_footer, dict) else None)

    return diagnosis_header, diagnosis_evolution_timeline, diagnosis_footer


# diagnosis_info = diagnosis_extraction(pdf_input = "https://drive.google.com/file/d/1bO819Jfz_2cjIZan58zNFErpUCYmPOmn/view?usp=drive_link")
# print(json.dumps(diagnosis_info, indent=2))