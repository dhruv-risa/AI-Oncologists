"""
Clinical Trials Tab - Matching Engine

This module fetches clinical trials from ClinicalTrials.gov API v2 and matches
each eligibility criterion against patient data using a combination of
programmatic checks and Gemini LLM analysis.
"""

import os
import re
import json
import requests
from typing import Dict, List, Optional, Tuple, Any
from concurrent.futures import ThreadPoolExecutor
import vertexai
from vertexai.generative_models import GenerativeModel, Part

# Initialize Vertex AI
BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../"))
vertexai.init(project="prior-auth-portal-dev", location="us-central1")

# ClinicalTrials.gov API v2 base URL
CLINICALTRIALS_API_BASE = "https://clinicaltrials.gov/api/v2"


def fetch_trials_from_api(
    condition: str = "cancer",
    max_results: int = 250,
    status: str = "RECRUITING",
    age: str = None,
    gender: str = None,
    max_pages: int = 2
) -> List[Dict]:
    """
    Fetch clinical trials from ClinicalTrials.gov API v2 with pagination support.

    Strategy: Search broadly to get more trials, let eligibility matching filter.
    Now fetches multiple pages to get more comprehensive results.

    Args:
        condition: Cancer type or broad term (default: "cancer" for broad search)
        max_results: Maximum number of trials per page (default: 250)
        status: Trial status filter (RECRUITING, ACTIVE_NOT_RECRUITING, etc.)
        age: Patient age for filtering (e.g., "65 years")
        gender: Patient gender (MALE, FEMALE, ALL)
        max_pages: Maximum number of pages to fetch (default: 2)

    Returns:
        List of trial dictionaries with structured data
    """
    url = f"{CLINICALTRIALS_API_BASE}/studies"

    # Build base query params
    base_params = {
        "query.cond": condition,
        "filter.overallStatus": status,
        "pageSize": max_results,
        "fields": ",".join([
            "protocolSection.identificationModule",
            "protocolSection.statusModule",
            "protocolSection.designModule",
            "protocolSection.eligibilityModule",
            "protocolSection.contactsLocationsModule",
            "protocolSection.descriptionModule"
        ])
    }

    # Add age filter if provided
    if age:
        # ClinicalTrials.gov API supports age filtering
        base_params["filter.advanced"] = f"AREA[MinimumAge]RANGE[MIN, {age}] AND AREA[MaximumAge]RANGE[{age}, MAX]"

    # Add gender filter if provided
    if gender and gender.upper() in ["MALE", "FEMALE"]:
        # Filter for trials accepting this gender or ALL
        if "filter.advanced" in base_params:
            base_params["filter.advanced"] += f" AND (AREA[Sex]{gender.upper()} OR AREA[Sex]ALL)"
        else:
            base_params["filter.advanced"] = f"AREA[Sex]{gender.upper()} OR AREA[Sex]ALL"

    all_trials = []
    page_token = None

    # Fetch multiple pages
    for page_num in range(max_pages):
        try:
            params = base_params.copy()
            if page_token:
                params["pageToken"] = page_token

            response = requests.get(url, params=params, timeout=30)
            response.raise_for_status()
            data = response.json()

            studies = data.get("studies", [])
            if not studies:
                # No more results
                break

            for study in studies:
                protocol = study.get("protocolSection", {})
                identification = protocol.get("identificationModule", {})
                status_module = protocol.get("statusModule", {})
                design = protocol.get("designModule", {})
                eligibility = protocol.get("eligibilityModule", {})
                contacts = protocol.get("contactsLocationsModule", {})
                description = protocol.get("descriptionModule", {})

                # Extract locations
                locations = []
                for loc in contacts.get("locations", [])[:3]:  # Limit to 3 locations
                    locations.append({
                        "facility": loc.get("facility", ""),
                        "city": loc.get("city", ""),
                        "state": loc.get("state", ""),
                        "country": loc.get("country", ""),
                        "status": loc.get("status", "")
                    })

                # Extract primary contact
                central_contacts = contacts.get("centralContacts", [])
                primary_contact = {}
                if central_contacts:
                    contact = central_contacts[0]
                    primary_contact = {
                        "name": contact.get("name", ""),
                        "phone": contact.get("phone", ""),
                        "email": contact.get("email", "")
                    }

                all_trials.append({
                    "nct_id": identification.get("nctId", ""),
                    "title": identification.get("briefTitle", ""),
                    "official_title": identification.get("officialTitle", ""),
                    "status": status_module.get("overallStatus", ""),
                    "phase": ", ".join(design.get("phases", ["N/A"])),
                    "study_type": design.get("studyType", ""),
                    "brief_summary": description.get("briefSummary", ""),
                    "eligibility_criteria_text": eligibility.get("eligibilityCriteria", ""),
                    "sex": eligibility.get("sex", "ALL"),
                    "minimum_age": eligibility.get("minimumAge", ""),
                    "maximum_age": eligibility.get("maximumAge", ""),
                    "healthy_volunteers": eligibility.get("healthyVolunteers", False),
                    "locations": locations,
                    "contact": primary_contact
                })

            # Get next page token if available
            page_token = data.get("nextPageToken")
            if not page_token:
                # No more pages
                break

        except requests.RequestException as e:
            print(f"Error fetching trials (page {page_num + 1}): {e}")
            break

    return all_trials


def parse_eligibility_criteria(criteria_text: str) -> Dict[str, List[str]]:
    """
    Parse the eligibility criteria text into separate inclusion and exclusion criteria.
    
    Args:
        criteria_text: Raw eligibility criteria text from API
    
    Returns:
        Dictionary with 'inclusion' and 'exclusion' lists
    """
    result = {
        "inclusion": [],
        "exclusion": []
    }
    
    if not criteria_text:
        return result
    
    # Split into inclusion and exclusion sections
    text = criteria_text.strip()
    
    # Find the split point between inclusion and exclusion
    exclusion_markers = [
        "Exclusion Criteria:",
        "Exclusion criteria:",
        "EXCLUSION CRITERIA:",
        "Exclusion Criteria",
        "Key Exclusion Criteria:"
    ]
    
    inclusion_text = text
    exclusion_text = ""
    
    for marker in exclusion_markers:
        if marker in text:
            parts = text.split(marker, 1)
            inclusion_text = parts[0]
            exclusion_text = parts[1] if len(parts) > 1 else ""
            break
    
    # Parse inclusion criteria
    inclusion_text = re.sub(r'^.*?(Inclusion Criteria[:\s]*|Key Inclusion Criteria[:\s]*)', '', 
                            inclusion_text, flags=re.IGNORECASE | re.DOTALL)
    
    # Split by bullet points or numbered items
    inclusion_items = re.split(r'\n\s*[\*\-•]\s*|\n\s*\d+[\.\)]\s*', inclusion_text)
    result["inclusion"] = [item.strip() for item in inclusion_items if item.strip() and len(item.strip()) > 10]
    
    # Parse exclusion criteria
    exclusion_items = re.split(r'\n\s*[\*\-•]\s*|\n\s*\d+[\.\)]\s*', exclusion_text)
    result["exclusion"] = [item.strip() for item in exclusion_items if item.strip() and len(item.strip()) > 10]
    
    return result


def build_patient_context(patient_data: Dict) -> str:
    """
    Build a COMPREHENSIVE patient context string for LLM analysis.
    Includes ALL available data from all pipelines to maximize eligibility matching.
    
    Args:
        patient_data: Complete patient data from data pool
    
    Returns:
        Formatted string with ALL relevant patient information
    """
    context_parts = []
    
    # =========================================================================
    # DEMOGRAPHICS
    # =========================================================================
    demographics = patient_data.get("demographics", {})
    if demographics:
        context_parts.append(f"""
=== PATIENT DEMOGRAPHICS ===
- Patient Name: {demographics.get('Patient Name', 'Unknown')}
- Age: {demographics.get('Age', 'Unknown')}
- Gender/Sex: {demographics.get('Gender', demographics.get('Sex', 'Unknown'))}
- Date of Birth: {demographics.get('Date of Birth', 'Unknown')}
- Height: {demographics.get('Height', 'Unknown')}
- Weight: {demographics.get('Weight', 'Unknown')}
- BMI: {demographics.get('BMI', 'Unknown')}
- Race: {demographics.get('Race', 'Unknown')}
- Ethnicity: {demographics.get('Ethnicity', 'Unknown')}
- Primary Oncologist: {demographics.get('Primary Oncologist', 'Unknown')}
- Last Visit: {demographics.get('Last Visit', 'Unknown')}
""")
    
    # =========================================================================
    # DIAGNOSIS
    # =========================================================================
    diagnosis = patient_data.get("diagnosis", {})
    if diagnosis:
        metastatic_sites = diagnosis.get('metastatic_sites', [])
        if isinstance(metastatic_sites, list):
            metastatic_sites = ", ".join(metastatic_sites) if metastatic_sites else "None documented"
        context_parts.append(f"""
=== DIAGNOSIS ===
- Primary Cancer Type: {diagnosis.get('cancer_type', 'Unknown')}
- Histology/Histologic Type: {diagnosis.get('histology', diagnosis.get('histologic_type', 'Unknown'))}
- Primary Diagnosis: {diagnosis.get('primary_diagnosis', 'Unknown')}
- Diagnosis Date: {diagnosis.get('diagnosis_date', 'Unknown')}
- Initial TNM Classification: {diagnosis.get('tnm_classification', 'Unknown')}
- Initial AJCC Stage: {diagnosis.get('ajcc_stage', 'Unknown')}
- Current Stage: {diagnosis.get('current_stage', diagnosis.get('ajcc_stage', 'Unknown'))}
- Current Line of Therapy: {diagnosis.get('line_of_therapy', 'Unknown')}
- Metastatic Status: {diagnosis.get('metastatic_status', 'Unknown')}
- Metastatic Sites: {metastatic_sites}
- Disease Status: {diagnosis.get('disease_status', 'Unknown')}
- Recurrence Status: {diagnosis.get('recurrence_status', 'Unknown')}
""")
    
    # =========================================================================
    # PERFORMANCE STATUS (ECOG) - Critical for eligibility
    # =========================================================================
    comorbidities = patient_data.get("comorbidities", {})
    ecog = comorbidities.get("ecog_performance_status", {})
    ecog_score = ecog.get('score', 'Unknown') if ecog else 'Unknown'
    
    # Clinical interpretation of ECOG
    ecog_interpretation = "Unknown"
    if ecog_score in [0, '0']:
        ecog_interpretation = "Fully active, able to carry on all pre-disease activities without restriction. Life expectancy typically > 6 months."
    elif ecog_score in [1, '1']:
        ecog_interpretation = "Restricted in strenuous activity but ambulatory. Able to carry out light work. Life expectancy typically > 6 months."
    elif ecog_score in [2, '2']:
        ecog_interpretation = "Ambulatory and capable of self-care but unable to work. Up > 50% of waking hours. Life expectancy typically 3-6 months."
    elif ecog_score in [3, '3']:
        ecog_interpretation = "Capable of only limited self-care. Confined to bed/chair > 50% of waking hours. Life expectancy typically < 3 months."
    elif ecog_score in [4, '4']:
        ecog_interpretation = "Completely disabled. Cannot carry on any self-care. Totally confined to bed/chair."
    
    context_parts.append(f"""
=== PERFORMANCE STATUS ===
- ECOG Performance Status Score: {ecog_score}
- ECOG Description: {ecog.get('description', 'Unknown') if ecog else 'Unknown'}
- Clinical Interpretation: {ecog_interpretation}
""")
    
    # =========================================================================
    # COMORBIDITIES
    # =========================================================================
    comorbidity_list = comorbidities.get("comorbidities", [])
    if comorbidity_list:
        conditions = []
        for c in comorbidity_list:
            if isinstance(c, dict):
                name = c.get("condition_name", "")
                if name:
                    conditions.append(f"- {name}")
            elif isinstance(c, str):
                conditions.append(f"- {c}")
        if conditions:
            context_parts.append(f"""
=== COMORBIDITIES & MEDICAL HISTORY ===
{chr(10).join(conditions)}
""")
    
    # =========================================================================
    # BIOMARKERS / PATHOLOGY MARKERS (IHC)
    # =========================================================================
    pathology_markers = patient_data.get("pathology_markers", {})
    if pathology_markers:
        combined = pathology_markers.get("pathology_combined", {})
        ihc = combined.get("ihc_column", {})
        markers = ihc.get("markers", [])
        if markers:
            marker_lines = []
            for m in markers:
                name = m.get("name", "")
                status = m.get("status_label", "")
                details = m.get("details", "")
                marker_lines.append(f"- {name}: {status} ({details})")
            context_parts.append(f"""
=== BIOMARKERS / IHC RESULTS ===
{chr(10).join(marker_lines)}
""")
    
    # =========================================================================
    # PATHOLOGY SUMMARY
    # =========================================================================
    pathology_summary = patient_data.get("pathology_summary", {})
    if pathology_summary:
        context_parts.append(f"""
=== PATHOLOGY SUMMARY ===
{json.dumps(pathology_summary, indent=2) if isinstance(pathology_summary, dict) else str(pathology_summary)}
""")
    
    # =========================================================================
    # GENOMIC INFORMATION
    # =========================================================================
    genomic_info = patient_data.get("genomic_info", {})
    if genomic_info:
        # Driver mutations
        mutations = genomic_info.get("detected_driver_mutations", [])
        if mutations:
            mutation_lines = []
            for m in mutations:
                gene = m.get("gene", "")
                status = m.get("status", "")
                details = m.get("details", "")
                mutation_lines.append(f"- {gene}: {status} - {details}")
            context_parts.append(f"""
=== GENOMIC MUTATIONS / ALTERATIONS ===
{chr(10).join(mutation_lines)}
""")
        
        # Immunotherapy markers
        immuno = genomic_info.get("immunotherapy_markers", {})
        if immuno:
            pd_l1 = immuno.get('pd_l1', {})
            tmb = immuno.get('tmb', {})
            msi = immuno.get('msi_status', {})
            context_parts.append(f"""
=== IMMUNOTHERAPY MARKERS ===
- PD-L1 Expression: {pd_l1.get('value', 'Unknown')} {pd_l1.get('interpretation', '')}
- Tumor Mutational Burden (TMB): {tmb.get('value', 'Unknown')} {tmb.get('interpretation', '')}
- Microsatellite Instability (MSI) Status: {msi.get('status', 'Unknown')} - {msi.get('interpretation', '')}
- MMR Status: {genomic_info.get('mmr_status', 'Unknown')}
""")
    
    # =========================================================================
    # TREATMENT HISTORY - ALL lines
    # =========================================================================
    treatment_info = patient_data.get("treatment_tab_info_LOT", {})
    treatment_history = treatment_info.get("treatment_history", [])
    if treatment_history:
        treatment_lines = []
        for t in treatment_history:
            header = t.get("header", {})
            regimen = t.get("regimen_details", {})
            dates = t.get("dates", {})
            cycles = t.get("cycles_data", {})
            line_num = header.get("line_number", "?")
            drug_name = regimen.get("display_name", "Unknown")
            status = header.get("status_badge", "")
            date_range = dates.get("display_text", "")
            cycle_info = cycles.get("display_text", "")
            treatment_lines.append(f"- Line {line_num}: {drug_name} ({status}) - {date_range} - Cycles: {cycle_info}")
        context_parts.append(f"""
=== TREATMENT HISTORY (PRIOR THERAPIES) ===
Total Prior Lines of Therapy: {len(treatment_history)}
{chr(10).join(treatment_lines)}
""")
    else:
        context_parts.append("""
=== TREATMENT HISTORY ===
No prior systemic therapy documented.
""")
    
    # =========================================================================
    # LABORATORY VALUES - ALL available
    # =========================================================================
    lab_info = patient_data.get("lab_info", {})
    if lab_info:
        # Clinical interpretation
        interpretation = lab_info.get("clinical_interpretation", [])
        if interpretation:
            context_parts.append(f"""
=== LABORATORY VALUES - CLINICAL INTERPRETATION ===
{chr(10).join(f'- {i}' for i in interpretation)}
""")
        
        # All lab categories
        lab_categories = lab_info.get("lab_categories", {})
        if lab_categories:
            for category, labs in lab_categories.items():
                if labs and isinstance(labs, list):
                    lab_lines = []
                    for lab in labs:
                        if isinstance(lab, dict):
                            name = lab.get("name", lab.get("test_name", ""))
                            value = lab.get("value", lab.get("result", ""))
                            unit = lab.get("unit", "")
                            ref_range = lab.get("reference_range", lab.get("normal_range", ""))
                            flag = lab.get("flag", lab.get("status", ""))
                            lab_lines.append(f"  - {name}: {value} {unit} (Ref: {ref_range}) {flag}")
                    if lab_lines:
                        context_parts.append(f"""
=== LAB VALUES - {category.upper()} ===
{chr(10).join(lab_lines)}
""")
        
        # Summary labs if available
        summary = lab_info.get("summary", {})
        if summary:
            context_parts.append(f"""
=== LAB SUMMARY ===
{json.dumps(summary, indent=2) if isinstance(summary, dict) else str(summary)}
""")
    
    # =========================================================================
    # RADIOLOGY / IMAGING REPORTS
    # =========================================================================
    radiology_reports = patient_data.get("radiology_reports", [])
    if radiology_reports:
        radiology_lines = []
        for r in radiology_reports[:10]:  # Limit to 10 most recent
            if isinstance(r, dict):
                date = r.get("date", "Unknown date")
                doc_type = r.get("document_type", "Imaging")
                summary = r.get("radiology_summary", {})
                recist = r.get("radiology_imp_RECIST", {})
                
                summary_text = ""
                if isinstance(summary, dict):
                    findings = summary.get("findings", summary.get("key_findings", []))
                    impression = summary.get("impression", "")
                    if findings:
                        summary_text = "; ".join(findings[:3]) if isinstance(findings, list) else str(findings)
                    if impression:
                        summary_text += f" Impression: {impression}"
                elif summary:
                    summary_text = str(summary)[:200]
                
                recist_text = ""
                if isinstance(recist, dict):
                    response = recist.get("response", recist.get("overall_response", ""))
                    if response:
                        recist_text = f" [RECIST: {response}]"
                
                radiology_lines.append(f"- {date} ({doc_type}): {summary_text}{recist_text}")
        
        context_parts.append(f"""
=== RADIOLOGY / IMAGING ===
{chr(10).join(radiology_lines)}
""")
    
    # =========================================================================
    # PATHOLOGY REPORTS (if detailed reports available)
    # =========================================================================
    pathology_reports = patient_data.get("pathology_reports", [])
    if pathology_reports:
        path_lines = []
        for p in pathology_reports[:5]:  # Limit to 5
            if isinstance(p, dict):
                date = p.get("date", "Unknown")
                summary = p.get("pathology_summary", {})
                if isinstance(summary, dict):
                    diagnosis = summary.get("diagnosis", summary.get("findings", ""))
                    path_lines.append(f"- {date}: {diagnosis[:150] if diagnosis else 'Report available'}")
        if path_lines:
            context_parts.append(f"""
=== PATHOLOGY REPORTS ===
{chr(10).join(path_lines)}
""")
    
    # =========================================================================
    # DIAGNOSIS TAB INFO (if available)
    # =========================================================================
    diagnosis_header = patient_data.get("diagnosis_tab_info_header", {})
    if diagnosis_header:
        context_parts.append(f"""
=== ADDITIONAL DIAGNOSIS DETAILS ===
{json.dumps(diagnosis_header, indent=2) if isinstance(diagnosis_header, dict) else str(diagnosis_header)}
""")
    
    # =========================================================================
    # ANY OTHER DATA (catch-all for data we might have missed)
    # =========================================================================
    known_keys = {
        'demographics', 'diagnosis', 'comorbidities', 'pathology_markers',
        'pathology_summary', 'genomic_info', 'treatment_tab_info_LOT',
        'lab_info', 'radiology_reports', 'pathology_reports',
        'diagnosis_tab_info_header', 'diagnosis_tab_info_evolution',
        'diagnosis_tab_info_footer', 'treatment_tab_info_timeline',
        'genomic_alterations_reports', 'no_test_performed_reports'
    }
    
    additional_data = []
    for key, value in patient_data.items():
        if key not in known_keys and value:
            if isinstance(value, dict) and value:
                additional_data.append(f"- {key}: {list(value.keys())[:5]}")
            elif isinstance(value, list) and value:
                additional_data.append(f"- {key}: {len(value)} items")
    
    if additional_data:
        context_parts.append(f"""
=== ADDITIONAL AVAILABLE DATA ===
{chr(10).join(additional_data)}
""")
    
    return "\n".join(context_parts)


def check_disease_match(trial: Dict, patient_data: Dict) -> Tuple[bool, str]:
    """
    Check if the patient's disease matches the trial's target condition.
    This is a critical pre-filter to avoid showing irrelevant trials.

    Args:
        trial: Trial data dictionary
        patient_data: Patient data dictionary

    Returns:
        Tuple of (matches: bool, reason: str)
    """
    # Get patient's cancer/disease type
    diagnosis = patient_data.get("diagnosis", {})
    patient_cancer = diagnosis.get("cancer_type", "").lower()
    patient_histology = diagnosis.get("histology", "").lower()

    if not patient_cancer and not patient_histology:
        return True, "No patient diagnosis available for comparison"

    # Get trial's target conditions
    trial_conditions = trial.get("conditions", trial.get("cancer_types", []))
    trial_title = trial.get("title", "").lower()
    trial_summary = trial.get("brief_summary", "").lower()

    # Combine all trial condition text for matching
    trial_text = " ".join([
        " ".join(trial_conditions) if trial_conditions else "",
        trial_title,
        trial_summary
    ]).lower()

    # List of non-cancer/oncology conditions that should NOT match cancer patients
    non_oncology_conditions = [
        "nmda", "nmdare", "encephalitis", "autoimmune encephalitis",
        "castleman", "mcd", "multicentric castleman",
        "hiv", "aids",
        "covid", "coronavirus", "sars-cov",
        "diabetes", "diabetic",
        "alzheimer", "parkinson", "dementia",
        "arthritis", "rheumatoid",
        "lupus", "sle",
        "crohn", "colitis", "ibd",
        "asthma", "copd",
        "heart failure", "cardiomyopathy",
        "healthy volunteer"
    ]

    # Check if trial is for a non-oncology condition
    for non_onc in non_oncology_conditions:
        if non_onc in trial_text:
            # Check if patient has this specific condition
            patient_has_condition = (
                non_onc in patient_cancer or
                non_onc in patient_histology
            )
            if not patient_has_condition:
                return False, f"Trial targets '{non_onc}' but patient has '{patient_cancer}'"

    # Check for cancer type match
    # Extract key cancer terms from patient diagnosis
    patient_cancer_terms = []
    cancer_keywords = [
        "lung", "breast", "colon", "colorectal", "rectal", "prostate",
        "ovarian", "pancreatic", "liver", "hepatocellular", "kidney", "renal",
        "bladder", "melanoma", "lymphoma", "leukemia", "myeloma",
        "sarcoma", "mesothelioma", "glioblastoma", "brain", "thyroid",
        "gastric", "stomach", "esophageal", "head and neck", "cervical",
        "endometrial", "uterine", "testicular"
    ]

    for keyword in cancer_keywords:
        if keyword in patient_cancer or keyword in patient_histology:
            patient_cancer_terms.append(keyword)

    # If trial mentions specific cancer types, check for match
    trial_cancer_types = []
    for keyword in cancer_keywords:
        if keyword in trial_text:
            trial_cancer_types.append(keyword)

    # If trial targets specific cancers, patient should have one of them
    # Exception: "solid tumor", "advanced cancer", "cancer" are broad/basket trials
    basket_terms = ["solid tumor", "advanced cancer", "metastatic cancer", "refractory", "cancer"]
    is_basket_trial = any(term in trial_text for term in basket_terms)

    if trial_cancer_types and not is_basket_trial:
        # Trial targets specific cancer types
        has_matching_cancer = any(
            patient_term in trial_cancer_types or
            any(trial_term in patient_cancer or trial_term in patient_histology
                for trial_term in trial_cancer_types)
            for patient_term in patient_cancer_terms
        )
        if not has_matching_cancer and patient_cancer_terms:
            return False, f"Trial targets {trial_cancer_types} but patient has {patient_cancer_terms}"

    return True, "Disease type is compatible"


def pre_filter_trial(trial: Dict, patient_data: Dict) -> Tuple[bool, str]:
    """
    Quick programmatic pre-filter to exclude trials based on hard criteria.
    This runs BEFORE LLM analysis to save time and API calls.

    Checks:
    - Age: Patient must be within trial's age range
    - Gender: Patient must match trial's sex requirement
    - ECOG: Patient must meet trial's ECOG requirement (if specified)

    Args:
        trial: Trial data dictionary
        patient_data: Patient data dictionary

    Returns:
        Tuple of (passes: bool, reason: str)
    """
    demographics = patient_data.get("demographics", {})
    comorbidities = patient_data.get("comorbidities", {})

    # === AGE CHECK ===
    patient_age_str = demographics.get("Age", "")
    patient_age = None
    if patient_age_str:
        # Extract numeric age
        age_match = re.search(r'(\d+)', str(patient_age_str))
        if age_match:
            patient_age = int(age_match.group(1))

    if patient_age:
        # Check minimum age
        min_age_str = trial.get("minimum_age", "")
        if min_age_str:
            min_age_match = re.search(r'(\d+)', str(min_age_str))
            if min_age_match:
                min_age = int(min_age_match.group(1))
                if patient_age < min_age:
                    return False, f"Patient age ({patient_age}) below minimum ({min_age})"

        # Check maximum age
        max_age_str = trial.get("maximum_age", "")
        if max_age_str:
            max_age_match = re.search(r'(\d+)', str(max_age_str))
            if max_age_match:
                max_age = int(max_age_match.group(1))
                if patient_age > max_age:
                    return False, f"Patient age ({patient_age}) above maximum ({max_age})"

    # === GENDER CHECK ===
    patient_gender = demographics.get("Gender", demographics.get("Sex", "")).upper()
    trial_sex = trial.get("sex", "ALL").upper()

    if trial_sex and trial_sex != "ALL":
        if patient_gender:
            # Normalize gender values
            patient_is_male = "MALE" in patient_gender and "FEMALE" not in patient_gender
            patient_is_female = "FEMALE" in patient_gender

            if trial_sex == "MALE" and not patient_is_male:
                return False, f"Trial requires Male, patient is {patient_gender}"
            if trial_sex == "FEMALE" and not patient_is_female:
                return False, f"Trial requires Female, patient is {patient_gender}"

    # === ECOG CHECK ===
    ecog_data = comorbidities.get("ecog_performance_status", {})
    patient_ecog_str = ecog_data.get("score", "") if ecog_data else ""
    patient_ecog = None

    if patient_ecog_str:
        ecog_match = re.search(r'(\d)', str(patient_ecog_str))
        if ecog_match:
            patient_ecog = int(ecog_match.group(1))

    if patient_ecog is not None:
        # Check eligibility criteria for ECOG requirements
        criteria_text = trial.get("eligibility_criteria_text", "").lower()

        # Common patterns: "ECOG 0-1", "ECOG ≤ 2", "ECOG performance status 0, 1, or 2"
        ecog_patterns = [
            (r'ecog[:\s]*(?:performance[:\s]*status)?[:\s]*[≤<=]\s*(\d)', 'max'),  # ECOG ≤ 2
            (r'ecog[:\s]*(?:performance[:\s]*status)?[:\s]*(\d)\s*[-–]\s*(\d)', 'range'),  # ECOG 0-1
            (r'ecog[:\s]*(?:performance[:\s]*status)?[:\s]*(\d)\s*or\s*less', 'max'),  # ECOG 2 or less
        ]

        for pattern, pattern_type in ecog_patterns:
            match = re.search(pattern, criteria_text)
            if match:
                if pattern_type == 'max':
                    max_ecog = int(match.group(1))
                    if patient_ecog > max_ecog:
                        return False, f"Patient ECOG ({patient_ecog}) exceeds trial max ({max_ecog})"
                    break
                elif pattern_type == 'range':
                    min_ecog = int(match.group(1))
                    max_ecog = int(match.group(2))
                    if patient_ecog < min_ecog or patient_ecog > max_ecog:
                        return False, f"Patient ECOG ({patient_ecog}) outside trial range ({min_ecog}-{max_ecog})"
                    break

    return True, "Passes pre-filter checks"


def match_criteria_with_gemini(
    criteria_list: List[str],
    criteria_type: str,  # "inclusion" or "exclusion"
    patient_context: str,
    patient_data: Dict
) -> List[Dict]:
    """
    Use Gemini to match each criterion against patient data.

    This is the core matching function with a carefully crafted prompt
    to ensure accurate, explainable matching.

    Args:
        criteria_list: List of criterion strings to evaluate
        criteria_type: "inclusion" or "exclusion"
        patient_context: Formatted patient context string
        patient_data: Raw patient data for additional context

    Returns:
        List of criterion match results
    """
    if not criteria_list:
        return []

    # Build the numbered criteria list
    criteria_numbered = "\n".join([f"{i+1}. {c}" for i, c in enumerate(criteria_list)])

    # Construct the prompt - THIS IS THE KEY PART
    # Enable clinical reasoning to infer eligibility from related data
    prompt = f"""You are an expert oncology clinical trials eligibility analyst with deep knowledge of cancer medicine and clinical trial criteria.

## PATIENT INFORMATION
{patient_context}

## TRIAL {criteria_type.upper()} CRITERIA TO EVALUATE
{criteria_numbered}

## YOUR TASK
For EACH criterion above, determine whether the patient meets it using:
1. Direct evidence from patient data
2. Clinical reasoning and inference from related data

## CLINICAL REASONING GUIDELINES
Use your medical knowledge to make reasonable inferences:
- **Life expectancy**: ECOG 0-1 typically indicates life expectancy > 6 months; ECOG 2 indicates 3-6 months; ECOG 3+ indicates < 3 months
- **Organ function**: Use lab values to infer liver/kidney/cardiac function (e.g., normal creatinine implies adequate kidney function)
- **Prior therapy**: Count treatment lines to determine "received prior therapy" or "treatment-naive"
- **Disease stage**: Infer from imaging, metastatic sites, and pathology
- **Performance status**: ECOG score indicates functional capacity

## IMPORTANT RULES
1. **INCLUSION criteria**: Patient SHOULD meet these to be eligible
2. **EXCLUSION criteria**: Patient should NOT have these conditions to be eligible
3. **Use inference**: If exact data is missing but you can reasonably infer from related data, DO infer with medium/low confidence
4. **Mark unknown ONLY**: When there is NO relevant data to even make an inference
5. **Explain your reasoning**: Show what data you used to make your determination

## ADMINISTRATIVE/PROCEDURAL CRITERIA - USE PATIENT STATUS TO INFER
For criteria about consent, travel, communication, and compliance:

**IF patient is ACTIVE/STABLE (ECOG 0-2):**
- Ability to travel to study site → met=true (patient is ambulatory)
- Ability to sign consent/understand → met=true (patient is functional)
- Ability to comply with study visits → met=true (patient can manage activities)
- Willingness criteria → met=true with confidence="medium" (assume cooperative unless evidence otherwise)

**IF patient is CRITICAL/POOR STATUS (ECOG 3-4):**
- Ability to travel → met=null (patient may be bed-bound)
- Ability to consent → met=null (may have limited capacity)
- Compliance criteria → met=null (may not be physically able)

**IF ECOG status is UNKNOWN:**
- Mark these criteria as met=null with explanation "Patient functional status unknown"

This allows us to make reasonable inferences for stable patients while being cautious for critical patients.

## RESPONSE FORMAT
Return a JSON array with one object per criterion:
{{
    "criterion_number": <number>,
    "criterion_text": "<short summary of criterion - max 50 chars>",
    "patient_value": "<extracted or inferred patient value relevant to this criterion>",
    "met": <true/false/null>,
    "confidence": "<high/medium/low>",
    "explanation": "<reasoning: what data you used and how you determined eligibility>"
}}

For EXCLUSION criteria:
- "met": true = patient HAS this condition (INELIGIBLE)
- "met": false = patient does NOT have this condition (ELIGIBLE)
- "met": null = cannot determine even with inference

Return ONLY the JSON array, no other text.
"""

    try:
        model = GenerativeModel("gemini-2.0-flash")
        # Enforce JSON output to prevent parsing errors
        generation_config = {"response_mime_type": "application/json"}
        response = model.generate_content(prompt, generation_config=generation_config)
        response_text = response.text.strip()
        
        # Clean up response - remove markdown code blocks if present
        if response_text.startswith("```"):
            response_text = re.sub(r'^```(?:json)?\s*', '', response_text)
            response_text = re.sub(r'\s*```$', '', response_text)
        
        # Fix common JSON escape issues from LLM responses
        # Replace unescaped backslashes that aren't valid escape sequences
        response_text = re.sub(r'\\(?!["\\/bfnrtu])', r'\\\\', response_text)
        
        # Try to parse JSON
        try:
            results = json.loads(response_text)
        except json.JSONDecodeError:
            # If still failing, try to extract just the array portion
            match = re.search(r'\[[\s\S]*\]', response_text)
            if match:
                results = json.loads(match.group())
            else:
                raise
        
        # Add criterion type to each result
        for r in results:
            r["criterion_type"] = criteria_type
        
        return results
        
    except Exception as e:
        print(f"Error in Gemini matching: {e}")
        # Return basic results for each criterion on error
        return [
            {
                "criterion_number": i + 1,
                "criterion_text": c[:50] + "..." if len(c) > 50 else c,
                "patient_value": "Error analyzing",
                "met": None,
                "confidence": "low",
                "explanation": f"Error during analysis: {str(e)}",
                "criterion_type": criteria_type
            }
            for i, c in enumerate(criteria_list)
        ]


def calculate_eligibility_score(criteria_results: List[Dict]) -> Dict:
    """
    Calculate overall eligibility score based on criteria matching results.
    
    Args:
        criteria_results: List of all criterion match results
    
    Returns:
        Dictionary with eligibility status and percentage
    """
    inclusion_results = [r for r in criteria_results if r.get("criterion_type") == "inclusion"]
    exclusion_results = [r for r in criteria_results if r.get("criterion_type") == "exclusion"]
    
    # Count inclusion criteria
    inclusion_met = sum(1 for r in inclusion_results if r.get("met") is True)
    inclusion_not_met = sum(1 for r in inclusion_results if r.get("met") is False)
    inclusion_unknown = sum(1 for r in inclusion_results if r.get("met") is None)
    inclusion_total = len(inclusion_results)
    
    # Count exclusion criteria (for exclusion, met=False is GOOD, met=True is BAD)
    exclusion_clear = sum(1 for r in exclusion_results if r.get("met") is False)  # Good
    exclusion_violated = sum(1 for r in exclusion_results if r.get("met") is True)  # Bad
    exclusion_unknown = sum(1 for r in exclusion_results if r.get("met") is None)
    exclusion_total = len(exclusion_results)
    
    # Determine eligibility status FIRST (before calculating percentage)
    if exclusion_violated > 0:
        status = "NOT_ELIGIBLE"
        status_reason = f"Patient fails {exclusion_violated} exclusion criteria - INELIGIBLE"
        # For NOT_ELIGIBLE, show 0% - don't mislead with partial match
        percentage = 0
    elif inclusion_not_met > 0:
        status = "NOT_ELIGIBLE"
        status_reason = f"Patient does not meet {inclusion_not_met} required inclusion criteria"
        # For NOT_ELIGIBLE, show 0%
        percentage = 0
    elif inclusion_unknown > 0 or exclusion_unknown > 0:
        status = "POTENTIALLY_ELIGIBLE"
        status_reason = f"Review needed: {inclusion_unknown + exclusion_unknown} criteria could not be verified"
        # Calculate percentage based on ALL criteria (unknowns count as partial)
        # This prevents misleading 100% scores when many criteria are unknown
        total_criteria = inclusion_total + exclusion_total
        criteria_met = inclusion_met + exclusion_clear
        # Give unknowns 50% credit (they might be met)
        criteria_partial = (inclusion_unknown + exclusion_unknown) * 0.5
        if total_criteria > 0:
            percentage = round(((criteria_met + criteria_partial) / total_criteria * 100), 1)
        else:
            percentage = 0
    else:
        status = "LIKELY_ELIGIBLE"
        status_reason = "Patient appears to meet all eligibility criteria"
        percentage = 100  # All criteria met
    
    return {
        "status": status,
        "status_reason": status_reason,
        "percentage": percentage,
        "inclusion": {
            "met": inclusion_met,
            "not_met": inclusion_not_met,
            "unknown": inclusion_unknown,
            "total": inclusion_total
        },
        "exclusion": {
            "clear": exclusion_clear,
            "violated": exclusion_violated,
            "unknown": exclusion_unknown,
            "total": exclusion_total
        }
    }


def process_single_trial(trial: Dict, patient_context: str, patient_data: Dict) -> Dict:
    """
    Process a single trial for eligibility matching.
    Helper function for parallel execution.
    """
    try:
        # CRITICAL: First check if patient's disease matches trial's target condition
        disease_matches, disease_reason = check_disease_match(trial, patient_data)

        if not disease_matches:
            # Patient's disease doesn't match trial - return NOT_ELIGIBLE immediately
            # This avoids wasting LLM calls on irrelevant trials
            return {
                "nct_id": trial["nct_id"],
                "title": trial["title"],
                "phase": trial.get("phase", ""),
                "status": trial.get("status", ""),
                "study_type": trial.get("study_type", ""),
                "brief_summary": trial.get("brief_summary", "")[:300] + "..." if len(trial.get("brief_summary", "")) > 300 else trial.get("brief_summary", ""),
                "eligibility": {
                    "status": "NOT_ELIGIBLE",
                    "status_reason": disease_reason,
                    "percentage": 0,
                    "inclusion": {"met": 0, "not_met": 1, "unknown": 0, "total": 1},
                    "exclusion": {"clear": 0, "violated": 0, "unknown": 0, "total": 0}
                },
                "criteria_results": {
                    "inclusion": [{
                        "criterion_number": 1,
                        "criterion_text": "Disease type must match trial target",
                        "patient_value": patient_data.get("diagnosis", {}).get("cancer_type", "Unknown"),
                        "met": False,
                        "confidence": "high",
                        "explanation": disease_reason,
                        "criterion_type": "inclusion"
                    }],
                    "exclusion": []
                },
                "contact": trial.get("contact", {}),
                "locations": trial.get("locations", [])
            }

        # QUICK PRE-FILTER: Check age, gender, ECOG before expensive LLM calls
        passes_prefilter, prefilter_reason = pre_filter_trial(trial, patient_data)

        if not passes_prefilter:
            # Patient fails basic eligibility criteria - return NOT_ELIGIBLE immediately
            # This saves LLM API calls and speeds up processing significantly
            return {
                "nct_id": trial["nct_id"],
                "title": trial["title"],
                "phase": trial.get("phase", ""),
                "status": trial.get("status", ""),
                "study_type": trial.get("study_type", ""),
                "brief_summary": trial.get("brief_summary", "")[:300] + "..." if len(trial.get("brief_summary", "")) > 300 else trial.get("brief_summary", ""),
                "eligibility": {
                    "status": "NOT_ELIGIBLE",
                    "status_reason": prefilter_reason,
                    "percentage": 0,
                    "inclusion": {"met": 0, "not_met": 1, "unknown": 0, "total": 1},
                    "exclusion": {"clear": 0, "violated": 0, "unknown": 0, "total": 0}
                },
                "criteria_results": {
                    "inclusion": [{
                        "criterion_number": 1,
                        "criterion_text": prefilter_reason.split(",")[0] if "," in prefilter_reason else prefilter_reason,
                        "patient_value": prefilter_reason,
                        "met": False,
                        "confidence": "high",
                        "explanation": prefilter_reason,
                        "criterion_type": "inclusion"
                    }],
                    "exclusion": []
                },
                "contact": trial.get("contact", {}),
                "locations": trial.get("locations", [])
            }

        # Parse eligibility criteria
        criteria_text = trial.get("eligibility_criteria_text", "")
        parsed = parse_eligibility_criteria(criteria_text)
        
        # Add structured criteria from API fields
        structured_criteria = []
        if trial.get("minimum_age"):
            structured_criteria.append(f"Minimum age: {trial['minimum_age']}")
        if trial.get("maximum_age"):
            structured_criteria.append(f"Maximum age: {trial['maximum_age']}")
        if trial.get("sex") and trial["sex"] != "ALL":
            structured_criteria.append(f"Sex: {trial['sex']}")
        
        # Prepend structured criteria to inclusion list
        parsed["inclusion"] = structured_criteria + parsed["inclusion"]
        
        # Match inclusion criteria
        inclusion_results = match_criteria_with_gemini(
            parsed["inclusion"],
            "inclusion",
            patient_context,
            patient_data
        )
        
        # Match exclusion criteria
        exclusion_results = match_criteria_with_gemini(
            parsed["exclusion"],
            "exclusion",
            patient_context,
            patient_data
        )
        
        # Combine all criteria results
        all_criteria = inclusion_results + exclusion_results
        
        # Calculate eligibility
        eligibility = calculate_eligibility_score(all_criteria)
        
        return {
            "nct_id": trial["nct_id"],
            "title": trial["title"],
            "phase": trial["phase"],
            "status": trial["status"],
            "study_type": trial["study_type"],
            "brief_summary": trial["brief_summary"][:300] + "..." if len(trial.get("brief_summary", "")) > 300 else trial.get("brief_summary", ""),
            "eligibility": eligibility,
            "criteria_results": {
                "inclusion": inclusion_results,
                "exclusion": exclusion_results
            },
            "contact": trial["contact"],
            "locations": trial["locations"]
        }
    except Exception as e:
        print(f"Error processing trial {trial.get('nct_id')}: {e}")
        return None


def build_search_queries_from_patient(patient_data: Dict) -> List[str]:
    """
    Build targeted search queries from patient data to capture relevant trials.

    This generates multiple specific queries based on:
    - Cancer type and histology
    - Biomarkers (HER2, ER, PR, etc.)
    - Genomic alterations (EGFR, BRCA, KRAS, etc.)
    - Immunotherapy markers (MSI-H, TMB, PD-L1)
    - Basket trial terms (solid tumor, advanced cancer)

    Args:
        patient_data: Complete patient data from data pool

    Returns:
        List of search query strings
    """
    queries = []
    demographics = patient_data.get("demographics", {})
    diagnosis = patient_data.get("diagnosis", {})
    genomic_info = patient_data.get("genomic_info", {})
    pathology_markers = patient_data.get("pathology_markers", {})

    # 1. Cancer type - primary search
    cancer_type = diagnosis.get("cancer_type", "")
    if cancer_type and cancer_type.lower() != "unknown":
        # Normalize cancer type
        normalized = cancer_type.lower()
        # Remove verbose prefixes
        normalized = re.sub(r'malignant neoplasm of\s*', '', normalized, flags=re.IGNORECASE)
        normalized = re.sub(r'\bleft\b|\bright\b|\bprimary\b', '', normalized, flags=re.IGNORECASE)
        normalized = re.sub(r'stage\s+[ivx0-9]+', '', normalized, flags=re.IGNORECASE)
        normalized = normalized.strip()
        if normalized and len(normalized) > 3:
            queries.append(normalized)

    # 2. Histology/Histologic type
    histology = diagnosis.get("histology", diagnosis.get("histologic_type", ""))
    if histology and histology.lower() != "unknown":
        histology_clean = histology.lower().strip()
        if len(histology_clean) > 5 and histology_clean not in [q.lower() for q in queries]:
            queries.append(histology_clean)

    # 3. Biomarkers from pathology (HER2, ER, PR, etc.)
    combined = pathology_markers.get("pathology_combined", {}) if pathology_markers else {}
    ihc = combined.get("ihc_column", {}) if combined else {}
    markers = ihc.get("markers", []) if ihc else []
    biomarker_queries = []

    for marker in markers:
        name = marker.get("name", "").upper()
        status = marker.get("status_label", "").lower()

        if name in ["HER2", "HER-2"]:
            if "positive" in status:
                biomarker_queries.append("HER2 positive")
            elif "negative" in status:
                biomarker_queries.append("HER2 negative")
        elif name in ["ER", "ESTROGEN"]:
            if "positive" in status:
                biomarker_queries.append("estrogen receptor positive")
        elif name in ["PR", "PROGESTERONE"]:
            if "positive" in status:
                biomarker_queries.append("progesterone receptor positive")
        elif name == "PD-L1" or name == "PDL1":
            if "positive" in status or "expressed" in status:
                biomarker_queries.append("PD-L1 positive")

    # Check for triple negative breast cancer
    if cancer_type and "breast" in cancer_type.lower():
        er_neg = any(m.get("name", "").upper() in ["ER", "ESTROGEN"] and
                     "negative" in m.get("status_label", "").lower() for m in markers)
        pr_neg = any(m.get("name", "").upper() in ["PR", "PROGESTERONE"] and
                     "negative" in m.get("status_label", "").lower() for m in markers)
        her2_neg = any(m.get("name", "").upper() in ["HER2", "HER-2"] and
                       "negative" in m.get("status_label", "").lower() for m in markers)
        if er_neg and pr_neg and her2_neg:
            biomarker_queries.append("triple negative breast cancer")

    queries.extend(biomarker_queries)

    # 4. Genomic alterations (driver mutations)
    mutations = genomic_info.get("detected_driver_mutations", []) if genomic_info else []
    for mutation in mutations:
        gene = mutation.get("gene", "").upper()
        status = mutation.get("status", "").lower()

        if gene and ("detected" in status or "positive" in status or "mutation" in status):
            # Add gene-specific queries
            if gene in ["EGFR", "ALK", "ROS1", "BRAF", "KRAS", "NTRK", "RET", "MET"]:
                queries.append(f"{gene} mutation")
                queries.append(f"{gene} positive")
            elif gene in ["BRCA1", "BRCA2"]:
                queries.append(f"{gene} mutation")
            elif gene in ["PIK3CA", "ERBB2"]:
                queries.append(f"{gene}")

    # 5. Immunotherapy markers
    immuno = genomic_info.get("immunotherapy_markers", {}) if genomic_info else {}

    # MSI status
    msi = immuno.get("msi_status", {}) if immuno else {}
    msi_status = msi.get("status", "").upper() if msi else ""
    if "HIGH" in msi_status or "MSI-H" in msi_status:
        queries.append("MSI-H")
        queries.append("microsatellite instability high")

    # MMR status
    mmr_status = genomic_info.get("mmr_status", "").upper() if genomic_info else ""
    if "DEFICIENT" in mmr_status or "DMMR" in mmr_status:
        queries.append("dMMR")
        queries.append("mismatch repair deficient")

    # TMB
    tmb = immuno.get("tmb", {}) if immuno else {}
    tmb_value = str(tmb.get("value", "")).lower() if tmb else ""
    if "high" in tmb_value:
        queries.append("TMB-high")
        queries.append("tumor mutational burden high")

    # PD-L1
    pd_l1 = immuno.get("pd_l1", {}) if immuno else {}
    pd_l1_value = str(pd_l1.get("value", "")).lower() if pd_l1 else ""
    if pd_l1_value and ("positive" in pd_l1_value or "%" in pd_l1_value):
        queries.append("PD-L1 positive")

    # 6. Disease stage/status
    metastatic_status = diagnosis.get("metastatic_status", "").lower() if diagnosis else ""
    if "yes" in metastatic_status or "metastatic" in metastatic_status:
        queries.append("metastatic cancer")
        if cancer_type:
            queries.append(f"metastatic {cancer_type.lower()}")

    current_stage = diagnosis.get("current_stage", diagnosis.get("ajcc_stage", "")).upper() if diagnosis else ""
    if "IV" in current_stage or "4" in current_stage:
        queries.append("stage IV cancer")
        queries.append("advanced cancer")

    # 7. Basket trial terms (always include these)
    basket_queries = [
        "solid tumor",
        "advanced solid tumor",
        "refractory cancer"
    ]
    queries.extend(basket_queries)

    # 8. Add broad cancer search as fallback
    queries.append("cancer")

    # Deduplicate while preserving order
    seen = set()
    unique_queries = []
    for q in queries:
        q_lower = q.lower().strip()
        if q_lower and q_lower not in seen and len(q_lower) > 2:
            seen.add(q_lower)
            unique_queries.append(q)

    return unique_queries


def extract_clinical_trials(patient_data: Dict, max_trials_per_query: int = 250, max_pages: int = 2) -> Dict:
    """
    Main entry point: Extract and match clinical trials for a patient.

    NEW STRATEGY: Multi-query smart search approach
    - Build targeted queries from patient data (cancer type, biomarkers, genomics, etc.)
    - Fetch 250+ trials per query with pagination (2-3 pages)
    - Capture cancer-specific, biomarker-driven, and basket trials
    - Deduplicate by NCT ID
    - Check eligibility with LLM on all unique trials

    Args:
        patient_data: Complete patient data from data pool
        max_trials_per_query: Maximum trials per search query (default: 250)
        max_pages: Number of pages to fetch per query (default: 2)

    Returns:
        Dictionary with matched trials and eligibility information
    """
    # Get patient demographics for search filters
    demographics = patient_data.get("demographics", {})
    diagnosis = patient_data.get("diagnosis", {})

    # Extract age for filtering
    age_str = demographics.get("Age", "")
    patient_age = None
    if age_str:
        # Extract numeric age (e.g., "65 years" -> "65 years")
        age_match = re.search(r'(\d+)', str(age_str))
        if age_match:
            patient_age = f"{age_match.group(1)} years"

    # Extract gender for filtering
    gender = demographics.get("Gender", demographics.get("Sex", ""))
    patient_gender = None
    if gender:
        gender_upper = gender.upper()
        if "MALE" in gender_upper and "FEMALE" not in gender_upper:
            patient_gender = "MALE"
        elif "FEMALE" in gender_upper:
            patient_gender = "FEMALE"

    # Get cancer type for display/logging
    cancer_type = diagnosis.get("cancer_type", "cancer")

    # NEW: Build smart search queries from patient data
    search_queries = build_search_queries_from_patient(patient_data)

    print(f"=== SMART CLINICAL TRIALS SEARCH ===")
    print(f"Patient: {cancer_type}")
    print(f"Age filter: {patient_age or 'None'}")
    print(f"Gender filter: {patient_gender or 'All'}")
    print(f"Generated {len(search_queries)} targeted search queries:")
    for i, q in enumerate(search_queries[:10], 1):  # Show first 10
        print(f"  {i}. {q}")
    if len(search_queries) > 10:
        print(f"  ... and {len(search_queries) - 10} more")
    print(f"Fetching up to {max_trials_per_query} trials per query ({max_pages} pages)")

    # Fetch trials using smart multi-query search
    all_trials = []
    seen_nct_ids = set()

    for idx, query in enumerate(search_queries):
        print(f"Fetching trials for query {idx + 1}/{len(search_queries)}: '{query}'...")
        trials = fetch_trials_from_api(
            condition=query,
            max_results=max_trials_per_query,
            age=patient_age,
            gender=patient_gender,
            max_pages=max_pages
        )
        print(f"  Retrieved {len(trials)} trials")

        # Deduplicate by NCT ID
        new_count = 0
        for trial in trials:
            nct_id = trial.get("nct_id")
            if nct_id and nct_id not in seen_nct_ids:
                seen_nct_ids.add(nct_id)
                all_trials.append(trial)
                new_count += 1
        print(f"  Added {new_count} new unique trials (total: {len(all_trials)})")
    
    print(f"\n=== TRIAL FETCHING COMPLETE ===")
    print(f"Total unique trials collected: {len(all_trials)}")

    if not all_trials:
        return {
            "success": True,
            "message": f"No recruiting trials found matching patient criteria",
            "search_queries": search_queries,
            "total_queries": len(search_queries),
            "trials": []
        }

    # Build patient context for LLM
    patient_context = build_patient_context(patient_data)

    print(f"\n=== ELIGIBILITY ANALYSIS ===")
    print(f"Analyzing {len(all_trials)} unique trials with Gemini LLM...")
    print(f"Using parallel processing (10 workers)...")

    matched_trials = []
    # Use ThreadPoolExecutor for I/O bound tasks (Gemini API calls)
    with ThreadPoolExecutor(max_workers=10) as executor:
        # Map returns results in order
        results = list(executor.map(
            lambda t: process_single_trial(t, patient_context, patient_data),
            all_trials
        ))

        # Filter out failed trials (None results)
        matched_trials = [r for r in results if r is not None]

    print(f"Successfully analyzed {len(matched_trials)} trials")

    # Sort by eligibility percentage (highest first)
    matched_trials.sort(key=lambda x: x["eligibility"]["percentage"], reverse=True)

    # Count trials by eligibility status
    likely_eligible = sum(1 for t in matched_trials if t["eligibility"]["status"] == "LIKELY_ELIGIBLE")
    potentially_eligible = sum(1 for t in matched_trials if t["eligibility"]["status"] == "POTENTIALLY_ELIGIBLE")
    not_eligible = sum(1 for t in matched_trials if t["eligibility"]["status"] == "NOT_ELIGIBLE")

    print(f"\n=== RESULTS SUMMARY ===")
    print(f"Likely Eligible: {likely_eligible}")
    print(f"Potentially Eligible: {potentially_eligible}")
    print(f"Not Eligible: {not_eligible}")

    return {
        "success": True,
        "search_queries": search_queries,
        "total_queries": len(search_queries),
        "patient_cancer_type": cancer_type,
        "total_trials_fetched": len(all_trials),
        "total_trials_analyzed": len(matched_trials),
        "summary": {
            "likely_eligible": likely_eligible,
            "potentially_eligible": potentially_eligible,
            "not_eligible": not_eligible
        },
        "trials": matched_trials
    }


# Test function
if __name__ == "__main__":
    # Test with sample patient data
    sample_patient = {
        "demographics": {
            "Patient Name": "Jane Doe",
            "Age": "67",
            "Gender": "Female"
        },
        "diagnosis": {
            "cancer_type": "Breast Cancer",
            "histology": "Invasive Ductal Carcinoma",
            "ajcc_stage": "Stage IIA",
            "disease_status": "Stable"
        },
        "comorbidities": {
            "ecog_performance_status": {
                "score": "1",
                "description": "Restricted in strenuous activity"
            }
        },
        "pathology_markers": {
            "pathology_combined": {
                "ihc_column": {
                    "markers": [
                        {"name": "ER", "status_label": "Positive", "details": "95%"},
                        {"name": "PR", "status_label": "Positive", "details": "80%"},
                        {"name": "HER2", "status_label": "Negative", "details": "IHC 1+"}
                    ]
                }
            }
        }
    }
    
    result = extract_clinical_trials(sample_patient, max_trials=2)
    print(json.dumps(result, indent=2))
