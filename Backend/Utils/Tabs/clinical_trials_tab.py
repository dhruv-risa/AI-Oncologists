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
vertexai.init(project=os.environ.get("VERTEX_PROJECT", "rapids-platform"), location="us-central1")

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
            "protocolSection.conditionsModule",
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
                protocol = study.get("protocolSection", {}) or {}
                identification = protocol.get("identificationModule", {}) or {}
                status_module = protocol.get("statusModule", {}) or {}
                design = protocol.get("designModule", {}) or {}
                eligibility = protocol.get("eligibilityModule", {}) or {}
                conditions_module = protocol.get("conditionsModule", {}) or {}
                contacts = protocol.get("contactsLocationsModule", {}) or {}
                description = protocol.get("descriptionModule", {}) or {}

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
                    "conditions": conditions_module.get("conditions", []),
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


def normalize_tnm(tnm: str) -> str:
    """Normalize TNM notation to use proper lowercase prefixes (cT, cN, cM, pT, pN, pM)."""
    if not tnm or tnm in ('Unknown', 'NA', 'N/A', None):
        return tnm or 'Unknown'
    import re as _re
    result = _re.sub(r'\b([CP])([TNM])', lambda m: m.group(1).lower() + m.group(2), tnm)
    result = ' '.join(result.split())
    return result


def validate_ajcc_stage(tnm: str, ajcc_stage: str) -> str:
    """Validate and correct AJCC stage based on TNM M-subcategory (8th edition).
    Key rules: M1a → Stage IVA, M1b → Stage IVB, M1c → Stage IVB"""
    if not tnm or not ajcc_stage or ajcc_stage in ('Unknown', 'NA', 'N/A'):
        return ajcc_stage or 'Unknown'
    import re as _re
    tnm_upper = tnm.upper()
    m1a_match = _re.search(r'M1A', tnm_upper)
    m1b_match = _re.search(r'M1B', tnm_upper)
    m1c_match = _re.search(r'M1C', tnm_upper)
    if m1a_match:
        if 'IVB' in ajcc_stage.upper() or 'IVC' in ajcc_stage.upper():
            return 'Stage IVA'
    elif m1b_match or m1c_match:
        if 'IVA' in ajcc_stage.upper() and 'IVB' not in ajcc_stage.upper():
            return 'Stage IVB'
    return ajcc_stage


def standardize_lab_value(biomarker_name: str, value, unit: str):
    """Standardize lab value to common US clinical units.
    Conversions: Hemoglobin g/L→g/dL, WBC/ANC/Platelets raw→10^3/μL,
    Creatinine μmol/L→mg/dL, Bilirubin μmol/L→mg/dL"""
    try:
        val = float(value)
    except (ValueError, TypeError):
        return value, unit or ""
    unit = unit or ""
    unit_lower = unit.lower().strip()
    name_lower = biomarker_name.lower()

    # Hemoglobin: g/L → g/dL
    if 'hemoglobin' in name_lower or 'hgb' in name_lower or 'hb' in name_lower:
        if 'g/l' in unit_lower and val > 30:
            return round(val / 10.0, 1), "g/dL"

    # WBC, ANC, Platelets: raw counts → 10^3/μL
    if any(k in name_lower for k in ('wbc', 'white blood', 'anc', 'neutrophil', 'platelet')):
        if val > 500:
            return round(val / 1000.0, 2), "10^3/μL"

    # Creatinine: μmol/L → mg/dL
    if 'creatinine' in name_lower:
        if 'mol' in unit_lower or val > 20:
            return round(val / 88.4, 2), "mg/dL"

    # Bilirubin: μmol/L → mg/dL
    if 'bilirubin' in name_lower:
        if 'mol' in unit_lower or val > 5:
            return round(val / 17.1, 2), "mg/dL"

    return val, unit


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
- Race: {demographics.get('Race', 'Unknown')}
- Ethnicity: {demographics.get('Ethnicity', 'Unknown')}
- Address: {demographics.get('Address', 'Unknown')}
- City: {demographics.get('City', 'Unknown')}
- State: {demographics.get('State', 'Unknown')}
- Zip: {demographics.get('Zip', 'Unknown')}
- Primary Oncologist: {demographics.get('Primary Oncologist', 'Unknown')}
- Last Visit: {demographics.get('Last Visit', 'Unknown')}
""")

    # =========================================================================
    # ALLERGIES (from demographics extraction)
    # =========================================================================
    allergies = demographics.get("Allergies", {}) if demographics else {}
    if allergies:
        allergy_status = allergies.get("allergy_status", "Unknown")
        has_allergies = allergies.get("has_allergies", None)
        allergy_list = allergies.get("allergy_list", [])

        if has_allergies is False or allergy_status in ('NKDA', 'NKA', 'No Known Allergies', 'No Known Drug Allergies'):
            context_parts.append("""
=== ALLERGIES ===
- Allergy Status: NO KNOWN DRUG ALLERGIES (NKDA)
- The patient has NO documented allergies to any medications.
NOTE: When a trial criterion asks about allergy to a specific drug, and the patient has NKDA documented,
the patient is ELIGIBLE (not allergic) unless there is specific documentation of a reaction to that exact drug.
""")
        elif allergy_list:
            allergy_lines = [f"- {a}" for a in allergy_list]
            context_parts.append(f"""
=== ALLERGIES ===
- Allergy Status: Allergies Present
{chr(10).join(allergy_lines)}
""")
        else:
            context_parts.append(f"""
=== ALLERGIES ===
- Allergy Status: {allergy_status}
""")
    else:
        context_parts.append("""
=== ALLERGIES ===
- Allergy Status: Not documented in available records
""")

    # =========================================================================
    # VITAL SIGNS (from demographics extraction)
    # =========================================================================
    vitals = demographics.get("Vital Signs", {}) if demographics else {}
    if vitals and any(v is not None for v in vitals.values()):
        bp_sys = vitals.get("blood_pressure_systolic")
        bp_dia = vitals.get("blood_pressure_diastolic")
        hr = vitals.get("heart_rate")
        rr = vitals.get("respiratory_rate")
        temp = vitals.get("temperature")
        temp_unit = vitals.get("temperature_unit", "F")
        o2 = vitals.get("oxygen_saturation")
        pain = vitals.get("pain_score")

        vital_lines = []
        if bp_sys and bp_dia:
            vital_lines.append(f"- Blood Pressure: {bp_sys}/{bp_dia} mmHg")
        if hr:
            vital_lines.append(f"- Heart Rate: {hr} bpm")
        if rr:
            vital_lines.append(f"- Respiratory Rate: {rr} /min")
        if temp:
            vital_lines.append(f"- Temperature: {temp} {temp_unit}")
        if o2:
            vital_lines.append(f"- Oxygen Saturation (SpO2): {o2}%")
        if pain is not None:
            vital_lines.append(f"- Pain Score: {pain}/10")

        if vital_lines:
            context_parts.append(f"""
=== VITAL SIGNS ===
{chr(10).join(vital_lines)}
""")

    # =========================================================================
    # SOCIAL HISTORY (from demographics extraction)
    # =========================================================================
    social = demographics.get("Social History", {}) if demographics else {}
    if social and any(v is not None for v in social.values()):
        social_lines = []
        smoking = social.get("smoking_status")
        smoking_details = social.get("smoking_details")
        alcohol = social.get("alcohol_use")
        drugs = social.get("drug_use")
        occupation = social.get("occupation")

        if smoking:
            line = f"- Smoking Status: {smoking}"
            if smoking_details:
                line += f" ({smoking_details})"
            social_lines.append(line)
        if alcohol:
            social_lines.append(f"- Alcohol Use: {alcohol}")
        if drugs:
            social_lines.append(f"- Drug/Substance Use: {drugs}")
        if occupation:
            social_lines.append(f"- Occupation: {occupation}")

        if social_lines:
            context_parts.append(f"""
=== SOCIAL HISTORY ===
{chr(10).join(social_lines)}
""")

    # =========================================================================
    # PHQ-9 DEPRESSION SCREENING (from demographics extraction)
    # =========================================================================
    phq9 = demographics.get("PHQ9", {}) if demographics else {}
    if phq9 and phq9.get("score") is not None:
        context_parts.append(f"""
=== PHQ-9 DEPRESSION SCREENING ===
- PHQ-9 Score: {phq9.get('score')}
- Interpretation: {phq9.get('interpretation', 'Not specified')}
""")

    # =========================================================================
    # VACCINATION STATUS (from demographics extraction)
    # =========================================================================
    vaccination = demographics.get("Vaccination", {}) if demographics else {}
    if vaccination and any(v is not None for v in vaccination.values()):
        vax_lines = []
        for vax_name, vax_status in vaccination.items():
            if vax_status:
                vax_lines.append(f"- {vax_name.replace('_', ' ').title()}: {vax_status}")
        if vax_lines:
            context_parts.append(f"""
=== VACCINATION STATUS ===
{chr(10).join(vax_lines)}
""")

    # =========================================================================
    # DIAGNOSIS
    # =========================================================================
    diagnosis = patient_data.get("diagnosis", {})
    # diagnosis_header often has richer data (metastatic_status, recurrence_status)
    diagnosis_header = patient_data.get("diagnosis_header", patient_data.get("diagnosis_tab_info_header", {})) or {}
    if diagnosis:
        metastatic_sites = diagnosis.get('metastatic_sites', [])
        if isinstance(metastatic_sites, list):
            metastatic_sites = ", ".join(metastatic_sites) if metastatic_sites else "None documented"

        # Extract staging from nested dicts (actual data structure)
        initial_staging = diagnosis.get('initial_staging', {}) or {}
        current_staging = diagnosis.get('current_staging', {}) or {}
        initial_tnm = initial_staging.get('tnm') or diagnosis.get('tnm_classification') or 'Unknown'
        initial_ajcc = initial_staging.get('ajcc_stage') or diagnosis.get('ajcc_stage') or 'Unknown'
        current_tnm = current_staging.get('tnm') or initial_tnm
        current_ajcc = current_staging.get('ajcc_stage') or diagnosis.get('current_stage') or initial_ajcc

        # Compensate: normalize TNM notation and validate AJCC staging
        initial_tnm = normalize_tnm(initial_tnm)
        current_tnm = normalize_tnm(current_tnm)
        initial_ajcc = validate_ajcc_stage(initial_tnm, initial_ajcc)
        current_ajcc = validate_ajcc_stage(current_tnm, current_ajcc)

        # Pull metastatic/recurrence from diagnosis_header if not in diagnosis
        metastatic_status = diagnosis.get('metastatic_status') or diagnosis_header.get('metastatic_status') or 'Unknown'
        recurrence_status = diagnosis.get('recurrence_status') or diagnosis_header.get('recurrence_status') or 'Unknown'

        context_parts.append(f"""
=== DIAGNOSIS ===
- Primary Cancer Type: {diagnosis.get('cancer_type') or 'Unknown'}
- Histology/Histologic Type: {diagnosis.get('histology') or diagnosis.get('histologic_type') or 'Unknown'}
- Primary Diagnosis: {diagnosis.get('primary_diagnosis') or diagnosis_header.get('primary_diagnosis') or 'Unknown'}
- Diagnosis Date: {diagnosis.get('diagnosis_date') or 'Unknown'}
- Initial TNM Classification: {initial_tnm}
- Initial AJCC Stage: {initial_ajcc}
- Current TNM: {current_tnm}
- Current AJCC Stage: {current_ajcc}
- Current Line of Therapy: {diagnosis.get('line_of_therapy') or 'Unknown'}
- Metastatic Status: {metastatic_status}
- Metastatic Sites: {metastatic_sites}
- Disease Status: {diagnosis.get('disease_status') or 'Unknown'}
- Recurrence Status: {recurrence_status}
""")
    
    # =========================================================================
    # PERFORMANCE STATUS (ECOG) - Critical for eligibility
    # =========================================================================
    comorbidities = patient_data.get("comorbidities", {}) or {}
    ecog = comorbidities.get("ecog_performance_status", {}) or {}
    ecog_score = ecog.get('score') if ecog else None
    # "NA" means not available — treat same as Unknown
    if ecog_score in (None, '', 'NA', 'N/A', 'Unknown'):
        # Fallback: check diagnosis.ecog_status (e.g. "ECOG 1")
        diag_ecog = (diagnosis.get('ecog_status') or '')
        ecog_match = re.search(r'(\d)', str(diag_ecog))
        ecog_score = ecog_match.group(1) if ecog_match else 'Unknown'
    
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
    
    # KPS equivalent based on published conversion (Verger et al. 2023, n=5844; Buccheri et al. 1996, n=536)
    kps_equivalent = "Unknown"
    if ecog_score in [0, '0']:
        kps_equivalent = "KPS 90-100"
    elif ecog_score in [1, '1']:
        kps_equivalent = "KPS 70-80"
    elif ecog_score in [2, '2']:
        kps_equivalent = "KPS 50-70"
    elif ecog_score in [3, '3']:
        kps_equivalent = "KPS 40-50"
    elif ecog_score in [4, '4']:
        kps_equivalent = "KPS 10-30"

    context_parts.append(f"""
=== PERFORMANCE STATUS ===
- ECOG Performance Status Score: {ecog_score}
- ECOG Description: {ecog.get('description') or diagnosis.get('ecog_status') or 'Unknown'}
- Clinical Interpretation: {ecog_interpretation}
- Karnofsky (KPS) Equivalent: {kps_equivalent}
- WHO/Zubrod Score: Same as ECOG (WHO/Zubrod scale is identical to ECOG)

NOTE: When a trial criterion uses KPS or Karnofsky, use this standard conversion
(Verger et al. 2023, 5844 paired assessments; Buccheri et al. 1996, 84% agreement):
  ECOG 0 = KPS 90-100 | ECOG 1 = KPS 70-80 | ECOG 2 = KPS 50-70 | ECOG 3 = KPS 40-50 | ECOG 4 = KPS 10-30
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
                    severity = c.get("severity", "")
                    details = c.get("clinical_details", "")
                    meds = c.get("associated_medications", [])
                    line = f"- {name}"
                    if severity and severity not in ('NA', 'N/A', 'Unknown', ''):
                        line += f" (Severity: {severity})"
                    if details and details not in ('NA', 'N/A', ''):
                        line += f" — {details[:150]}"
                    if meds:
                        med_names = [str(m) for m in meds[:3]]
                        line += f" [Medications: {', '.join(med_names)}]"
                    conditions.append(line)
            elif isinstance(c, str):
                conditions.append(f"- {c}")
        if conditions:
            context_parts.append(f"""
=== COMORBIDITIES & MEDICAL HISTORY ===
{chr(10).join(conditions)}
""")

    # =========================================================================
    # REVIEW OF SYSTEMS (ROS)
    # =========================================================================
    ros = comorbidities.get("review_of_systems", {}) or {}
    if ros and any(v is not None for v in ros.values()):
        ros_lines = []
        ros_system_names = {
            "constitutional": "Constitutional",
            "cardiovascular": "Cardiovascular",
            "respiratory": "Respiratory",
            "gastrointestinal": "Gastrointestinal",
            "neurological": "Neurological",
            "musculoskeletal": "Musculoskeletal",
            "endocrine": "Endocrine",
            "hematologic": "Hematologic/Lymphatic",
            "dermatologic": "Dermatologic",
            "psychiatric": "Psychiatric",
            "genitourinary": "Genitourinary",
            "other": "Other"
        }
        for key, display_name in ros_system_names.items():
            finding = ros.get(key)
            if finding and finding not in (None, '', 'null'):
                ros_lines.append(f"- {display_name}: {finding}")
        if ros_lines:
            context_parts.append(f"""
=== REVIEW OF SYSTEMS ===
{chr(10).join(ros_lines)}
NOTE: 'Negative' means the patient DENIES symptoms in that system.
When a trial criterion asks about a condition and the ROS is negative for that system,
the patient does NOT have that symptom/condition.
""")

    # =========================================================================
    # PHYSICAL EXAMINATION
    # =========================================================================
    physical_exam = comorbidities.get("physical_exam", {}) or {}
    if physical_exam and any(v is not None for v in physical_exam.values()):
        pe_lines = []
        pe_system_names = {
            "general_appearance": "General",
            "heent": "HEENT",
            "cardiovascular_exam": "Cardiovascular",
            "respiratory_exam": "Respiratory",
            "abdominal_exam": "Abdomen",
            "extremities": "Extremities",
            "neurological_exam": "Neurological",
            "skin_exam": "Skin",
            "lymph_nodes": "Lymph Nodes"
        }
        for key, display_name in pe_system_names.items():
            finding = physical_exam.get(key)
            if finding and finding not in (None, '', 'null'):
                pe_lines.append(f"- {display_name}: {finding}")
        if pe_lines:
            context_parts.append(f"""
=== PHYSICAL EXAMINATION ===
{chr(10).join(pe_lines)}
""")

    # =========================================================================
    # BIOMARKERS / PATHOLOGY MARKERS (IHC)
    # =========================================================================
    pathology_markers = patient_data.get("pathology_markers", {})
    if pathology_markers:
        combined = pathology_markers.get("pathology_combined", {}) or {}
        ihc = combined.get("ihc_column", {}) or {}
        markers = ihc.get("markers", []) or []
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
        immuno = genomic_info.get("immunotherapy_markers", {}) or {}
        if immuno:
            pd_l1 = immuno.get('pd_l1', {}) or {}
            tmb = immuno.get('tmb', {}) or {}
            msi = immuno.get('msi_status', {}) or {}
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
            header = t.get("header", {}) or {}
            regimen = t.get("regimen_details", {}) or {}
            dates = t.get("dates", {}) or {}
            cycles = t.get("cycles_data", {}) or {}
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
    # LABORATORY VALUES - ALL available (structured + interpretation)
    # =========================================================================
    lab_info = patient_data.get("lab_info", {})
    if lab_info:
        # Extract structured lab values from actual data keys
        # Data is stored under: complete_blood_count, metabolic_panel, tumor_markers
        lab_category_keys = [
            ("complete_blood_count", "COMPLETE BLOOD COUNT (CBC)"),
            ("metabolic_panel", "METABOLIC PANEL / CHEMISTRY"),
            ("tumor_markers", "TUMOR MARKERS"),
            ("liver_function", "LIVER FUNCTION"),
            ("renal_function", "RENAL FUNCTION"),
            ("coagulation", "COAGULATION"),
            ("thyroid", "THYROID FUNCTION"),
            ("diabetes", "DIABETES / GLYCEMIC CONTROL"),
            ("iron_studies", "IRON STUDIES"),
        ]

        all_lab_lines = []
        for data_key, display_name in lab_category_keys:
            category_data = lab_info.get(data_key, {})
            if not isinstance(category_data, dict):
                continue
            category_lines = []
            for lab_name, lab_data in category_data.items():
                if not isinstance(lab_data, dict) or not lab_data.get("has_data"):
                    continue
                current = lab_data.get("current", {}) or {}
                value = current.get("value")
                if value is None:
                    continue
                unit = current.get("unit", "") or ""
                # Compensate: standardize lab units for consistent eligibility matching
                value, unit = standardize_lab_value(lab_name, value, unit)
                ref = current.get("reference_range", "") or ""
                status = current.get("status", "") or ""
                date = current.get("date", "") or ""
                line = f"  - {lab_name}: {value} {unit}"
                if ref:
                    line += f" (Ref: {ref})"
                if status and status != "Normal":
                    line += f" [{status}]"
                if date:
                    line += f" (Date: {date})"
                category_lines.append(line)

            if category_lines:
                all_lab_lines.append(f"\n--- {display_name} ---")
                all_lab_lines.extend(category_lines)

        if all_lab_lines:
            context_parts.append(f"""
=== LABORATORY VALUES (MOST RECENT) ===
{chr(10).join(all_lab_lines)}
""")

        # Also try legacy lab_categories format (fallback)
        lab_categories = lab_info.get("lab_categories", {})
        if lab_categories and not all_lab_lines:
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

        # Clinical interpretation (AI-generated summary of abnormalities)
        interpretation = lab_info.get("clinical_interpretation", [])
        if interpretation:
            # Include meaningful clinical lines, skip rule definition boilerplate
            skip_phrases = ['rules applied:', 'no relevant biomarker data', 'no relevant lab results']
            meaningful = []
            for i in interpretation:
                if not isinstance(i, str):
                    continue
                stripped = i.strip().lstrip('- ')
                if not stripped or len(stripped) < 10:
                    continue
                if any(sp in stripped.lower() for sp in skip_phrases):
                    continue
                # Skip pure rule definitions like "Anemia: Hemoglobin <13.5 (M) or <12.0 (F)"
                if stripped.startswith(('Anemia:', 'Hepatic dysfunction:', 'Neutropenia:')) and '<' in stripped and '(' in stripped:
                    continue
                meaningful.append(stripped)
            if meaningful:
                context_parts.append(f"""
=== LAB CLINICAL INTERPRETATION ===
{chr(10).join(f'- {i}' for i in meaningful[:15])}
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
                # Clean ISO date format for readability
                if 'T' in str(date):
                    date = str(date).split('T')[0]
                doc_type = r.get("document_type", "Imaging")
                description = r.get("description", "")
                summary = r.get("radiology_summary", {}) or {}
                recist = r.get("radiology_imp_RECIST", {}) or {}

                # Extract from actual structure: summary.report_summary
                report_summary = summary.get("report_summary", {}) or {}
                study_type = report_summary.get("study_type", "")
                overall_response = report_summary.get("overall_response", "")

                # Also check flat keys as fallback
                if not study_type:
                    study_type = summary.get("study_type", "")
                if not overall_response:
                    overall_response = summary.get("overall_response", "")

                # Extract impression from recist (it's a list)
                impression_list = recist.get("impression", [])
                impression_text = "; ".join(impression_list[:3]) if isinstance(impression_list, list) else str(impression_list) if impression_list else ""

                # Extract additional findings
                additional = recist.get("additional_findings", [])
                additional_text = "; ".join(additional[:3]) if isinstance(additional, list) else ""

                # Build the line
                parts = []
                if study_type:
                    parts.append(study_type)
                if overall_response:
                    parts.append(f"[Response: {overall_response}]")
                if impression_text:
                    parts.append(f"Impression: {impression_text}")
                if additional_text and not impression_text:
                    parts.append(f"Findings: {additional_text}")

                summary_text = " | ".join(parts) if parts else description or "Report available"
                radiology_lines.append(f"- {date} ({doc_type}): {summary_text}")
        
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
                summary = p.get("pathology_summary", {}) or {}
                if isinstance(summary, dict):
                    diagnosis = summary.get("diagnosis", summary.get("findings", ""))
                    path_lines.append(f"- {date}: {diagnosis[:150] if diagnosis else 'Report available'}")
        if path_lines:
            context_parts.append(f"""
=== PATHOLOGY REPORTS ===
{chr(10).join(path_lines)}
""")
    
    # =========================================================================
    # DIAGNOSIS EVOLUTION / FOOTER (if available and not already covered)
    # =========================================================================
    diag_footer = patient_data.get("diagnosis_footer", patient_data.get("diagnosis_tab_info_footer", {})) or {}
    if diag_footer:
        footer_lines = []
        for k, v in diag_footer.items():
            if v and v not in (None, '', 'Unknown', 'NA', 'N/A'):
                footer_lines.append(f"- {k}: {v}")
        if footer_lines:
            context_parts.append(f"""
=== ADDITIONAL DIAGNOSIS DETAILS ===
{chr(10).join(footer_lines)}
""")

    # =========================================================================
    # DISEASE EVOLUTION TIMELINE — progression, remission, treatment responses
    # =========================================================================
    diag_evolution = patient_data.get("diagnosis_evolution_timeline", {}) or {}
    evolution_entries = diag_evolution.get("timeline", []) if isinstance(diag_evolution, dict) else []
    if evolution_entries:
        evo_lines = []
        for entry in evolution_entries:
            date_label = entry.get("date_label", "Unknown date")
            stage = entry.get("stage_header", "")
            status = entry.get("disease_status", "")
            regimen = entry.get("regimen", "")
            findings = entry.get("key_findings", [])
            toxicities = entry.get("toxicities", [])
            line = f"- {date_label}: {stage} — {status}"
            if regimen:
                line += f" | Regimen: {regimen}"
            evo_lines.append(line)
            for f in findings:
                evo_lines.append(f"    {f}")
            for tox in toxicities:
                if isinstance(tox, dict) and tox.get("effect"):
                    grade = f" (Grade {tox['grade']})" if tox.get("grade") else ""
                    evo_lines.append(f"    Toxicity: {tox['effect']}{grade}")
        context_parts.append(f"""
=== DISEASE EVOLUTION TIMELINE ===
{chr(10).join(evo_lines)}
""")

    # =========================================================================
    # TREATMENT TIMELINE — dated treatment events (systemic, radiation, surgery, imaging)
    # =========================================================================
    treatment_timeline = patient_data.get("treatment_tab_info_timeline", {}) or {}
    timeline_events = treatment_timeline.get("timeline_events", []) if isinstance(treatment_timeline, dict) else []
    if timeline_events:
        tt_lines = []
        for event in timeline_events:
            date_disp = event.get("date_display", "Unknown")
            event_type = event.get("event_type", "")
            title = event.get("title", "")
            subtitle = event.get("subtitle", "")
            tt_lines.append(f"- {date_disp} [{event_type}]: {title}")
            if subtitle:
                tt_lines.append(f"    {subtitle}")
        context_parts.append(f"""
=== TREATMENT TIMELINE ===
{chr(10).join(tt_lines)}
""")

    # =========================================================================
    # CURRENT MEDICATIONS (from medication_timeline pipeline)
    # =========================================================================
    current_medications = patient_data.get("current_medications", {})
    if current_medications:
        med_lines = []
        for med in (current_medications.get("current_medications", []) or []):
            if isinstance(med, dict):
                name = med.get("name", "")
                dose = med.get("dose", "")
                freq = med.get("frequency", "")
                route = med.get("route", "")
                if name:
                    med_lines.append(f"- {name} {dose} {freq} ({route})".strip())
        if med_lines:
            context_parts.append(f"""
=== CURRENT MEDICATIONS ===
{chr(10).join(med_lines)}
""")

        # Steroid status
        steroids = current_medications.get("steroids", {}) or {}
        if steroids.get("currently_on_steroids"):
            context_parts.append(f"- CURRENTLY ON STEROIDS: {steroids.get('steroid_name', 'Unknown')} {steroids.get('steroid_dose', '')}")
        elif steroids.get("last_steroid_date"):
            context_parts.append(f"- Last steroid use: {steroids.get('steroid_name', 'steroid')} on {steroids['last_steroid_date']}")

        # Immunosuppressant status
        immuno = current_medications.get("immunosuppressants", {}) or {}
        if immuno.get("currently_on_immunosuppressants"):
            context_parts.append(f"- CURRENTLY ON IMMUNOSUPPRESSANTS: {', '.join(immuno.get('medication_names', []))}")

        # Anticoagulant status
        anticoag = current_medications.get("anticoagulants", {}) or {}
        if anticoag.get("currently_on_anticoagulants"):
            context_parts.append(f"- CURRENTLY ON ANTICOAGULANTS: {', '.join(anticoag.get('medication_names', []))}")

    # =========================================================================
    # FAMILY HISTORY (from family_history pipeline)
    # =========================================================================
    family_history = patient_data.get("family_history", {})
    if family_history:
        fh_lines = []
        for fh in (family_history.get("family_cancer_history", []) or []):
            if isinstance(fh, dict):
                rel = fh.get("relationship", "")
                cond = fh.get("condition", "")
                if rel and cond:
                    age_dx = fh.get("age_at_diagnosis", "")
                    age_str = f" (age {age_dx})" if age_dx else ""
                    fh_lines.append(f"- {rel}: {cond}{age_str}")
        if fh_lines:
            context_parts.append(f"""
=== FAMILY HISTORY ===
{chr(10).join(fh_lines)}
""")
        syndromes = family_history.get("hereditary_syndromes", [])
        if syndromes:
            context_parts.append(f"- Hereditary syndromes: {', '.join(syndromes)}")
        summary = family_history.get("family_history_summary", "")
        if summary and not fh_lines:
            context_parts.append(f"""
=== FAMILY HISTORY ===
- {summary}
""")

    # =========================================================================
    # SURGICAL / PROCEDURE HISTORY (from surgical_history pipeline)
    # =========================================================================
    surgical_history = patient_data.get("surgical_history", {})
    if surgical_history:
        surg_lines = []
        for surg in (surgical_history.get("surgeries", []) or []):
            if isinstance(surg, dict):
                name = surg.get("procedure_name", "")
                date = surg.get("date", "")
                site = surg.get("site", "")
                if name:
                    surg_lines.append(f"- {name} ({date or 'date unknown'}) — {site or ''}")
        if surg_lines:
            context_parts.append(f"""
=== SURGICAL HISTORY ===
{chr(10).join(surg_lines)}
""")

        biopsy_lines = []
        for bx in (surgical_history.get("biopsies", []) or []):
            if isinstance(bx, dict):
                bx_type = bx.get("type", "")
                bx_date = bx.get("date", "")
                bx_site = bx.get("site", "")
                if bx_type:
                    biopsy_lines.append(f"- {bx_type} ({bx_date or 'date unknown'}) — {bx_site or ''}")
        if biopsy_lines:
            context_parts.append(f"""
=== BIOPSY HISTORY ===
{chr(10).join(biopsy_lines)}
""")

        tissue = surgical_history.get("tissue_available", {}) or {}
        if tissue.get("has_archived_tissue"):
            context_parts.append(f"- Archived tissue available: {tissue.get('tissue_type', 'type unknown')} — {tissue.get('details', '')}")

        transplant = surgical_history.get("transplant_history", {}) or {}
        if transplant.get("has_transplant"):
            context_parts.append(f"- TRANSPLANT HISTORY: {transplant.get('type', 'Unknown type')} ({transplant.get('date', 'date unknown')})")

        rad_lines = []
        for rad in (surgical_history.get("radiation_history", []) or []):
            if isinstance(rad, dict):
                rad_type = rad.get("type", "")
                rad_site = rad.get("site", "")
                rad_date = rad.get("date", "")
                if rad_type:
                    rad_lines.append(f"- {rad_type} to {rad_site or 'unknown site'} ({rad_date or 'date unknown'})")
        if rad_lines:
            context_parts.append(f"""
=== RADIATION HISTORY ===
{chr(10).join(rad_lines)}
""")

    # =========================================================================
    # ANY OTHER DATA (catch-all for data we might have missed)
    # =========================================================================
    known_keys = {
        'demographics', 'diagnosis', 'comorbidities', 'pathology_markers',
        'pathology_summary', 'genomic_info', 'treatment_tab_info_LOT',
        'lab_info', 'radiology_reports', 'pathology_reports',
        # Both naming conventions for diagnosis sub-tabs
        'diagnosis_header', 'diagnosis_tab_info_header',
        'diagnosis_footer', 'diagnosis_tab_info_footer',
        'diagnosis_evolution_timeline', 'diagnosis_tab_info_evolution',
        'treatment_tab_info_timeline',
        'genomic_alterations_reports', 'no_test_performed_reports',
        # New pipeline keys
        'current_medications', 'family_history', 'surgical_history',
        # Meta keys (not clinical data)
        'mrn', 'pdf_url', 'success', 'error', 'pool_updated_at',
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
    patient_cancer = (diagnosis.get("cancer_type") or "").lower()
    patient_histology = (diagnosis.get("histology") or "").lower()

    if not patient_cancer and not patient_histology:
        return True, "No patient diagnosis available for comparison"

    # Get trial's target conditions
    trial_conditions = trial.get("conditions", trial.get("cancer_types", [])) or []
    trial_title = (trial.get("title") or "").lower()
    trial_summary = (trial.get("brief_summary") or "").lower()

    # Combine all trial condition text for matching
    trial_text = " ".join([
        " ".join(str(c) for c in trial_conditions if c) if trial_conditions else "",
        trial_title,
        trial_summary
    ]).lower()

    # List of non-cancer/oncology conditions that should NOT match cancer patients
    non_oncology_conditions = [
        # Neurological / psychiatric (never oncology)
        "nmda", "nmdare", "encephalitis", "autoimmune encephalitis",
        "alzheimer", "parkinson", "dementia",
        "borderline personality", "schizophreni", "bipolar disorder",
        "major depressive disorder", "obsessive compulsive", "ptsd",
        "autism", "adhd", "eating disorder", "anorexia nervosa", "bulimia",
        "transcranial magnetic stimulation",
        # Infectious disease (not oncology unless cancer-related)
        "hiv", "aids",
        "covid", "coronavirus", "sars-cov",
        "malaria", "tuberculosis",
        # Autoimmune / inflammatory
        "castleman", "mcd", "multicentric castleman",
        "arthritis", "rheumatoid",
        "lupus", "sle",
        "crohn", "colitis", "ibd",
        "multiple sclerosis",
        # Metabolic
        "diabetes", "diabetic",
        # Cardiovascular (standalone, not as cancer comorbidity)
        "heart failure", "cardiomyopathy",
        # Respiratory
        "asthma", "copd",
        "cystic fibrosis", "pulmonary fibrosis",
        # Other clearly non-oncology
        "healthy volunteer",
        "dental", "periodontal",
        "osteoporosis", "osteoarthritis",
        "glaucoma", "macular degeneration",
        "chronic kidney disease", "dialysis",
        "sleep apnea",
        "erectile dysfunction",
        "migraine", "fibromyalgia",
    ]

    # Check if trial is for a non-oncology condition
    # Only filter if the trial has NO cancer/oncology terms (some trials study
    # non-oncology conditions IN cancer patients, e.g., "erectile function after radiotherapy")
    oncology_terms = [
        "cancer", "tumor", "tumour", "neoplasm", "oncolog", "carcinoma", "malignant",
        "chemotherapy", "immunotherapy", "radiotherapy", "radiation", "checkpoint inhibitor",
        "solid tumor", "metastatic", "lymphoma", "leukemia", "myeloma", "sarcoma", "melanoma",
    ]
    trial_has_oncology = any(term in trial_text for term in oncology_terms)

    for non_onc in non_oncology_conditions:
        if non_onc in trial_text:
            # If trial ALSO mentions cancer/oncology, it's likely studying the
            # non-oncology condition in a cancer context — allow it
            if trial_has_oncology:
                continue
            # Check if patient has this specific condition
            patient_has_condition = (
                non_onc in patient_cancer or
                non_onc in patient_histology
            )
            if not patient_has_condition:
                return False, f"Trial targets '{non_onc}' but patient has '{patient_cancer}'"

    # Check for cancer type match using STRUCTURED conditions field
    # This is more reliable than parsing free text from titles/summaries
    patient_cancer_terms = []
    cancer_keywords = [
        "lung", "breast", "colon", "colorectal", "rectal", "prostate",
        "ovarian", "pancreatic", "liver", "hepatocellular", "kidney", "renal",
        "bladder", "melanoma", "lymphoma", "leukemia", "myeloma",
        "sarcoma", "mesothelioma", "glioblastoma", "brain", "thyroid",
        "gastric", "stomach", "esophageal", "head and neck", "cervical",
        "endometrial", "uterine", "testicular", "cholangiocarcinoma",
        "bile duct", "gallbladder", "adrenal", "pleural", "peritoneal",
    ]

    for keyword in cancer_keywords:
        if keyword in patient_cancer or keyword in patient_histology:
            patient_cancer_terms.append(keyword)

    # Basket/pan-cancer terms — these trials accept any cancer type
    basket_terms = [
        "solid tumor", "solid tumour", "advanced solid tumor", "advanced solid tumour",
        "all solid tumor", "any solid tumor", "pan-cancer", "pan cancer",
        "tumor agnostic", "tumour agnostic", "all comers",
        "any advanced malignancy", "any malignant neoplasm",
        "malignant solid neoplasm", "advanced malignant solid neoplasm",
        "advanced malignant neoplasm",
    ]

    # Use CONDITIONS field (structured data from ClinicalTrials.gov) for matching
    trial_conditions_lower = [str(c).lower() for c in trial_conditions] if trial_conditions else []

    # Check if it's a basket trial (from conditions or title)
    is_basket_trial = any(
        any(bt in cond for bt in basket_terms)
        for cond in trial_conditions_lower
    )
    if not is_basket_trial:
        is_basket_trial = any(term in trial_title for term in basket_terms)

    # If trial has conditions, match against them (strict, structured matching)
    if trial_conditions_lower and not is_basket_trial and patient_cancer_terms:
        # Check if ANY patient cancer term appears in ANY trial condition
        has_matching_condition = any(
            any(patient_term in cond for patient_term in patient_cancer_terms)
            for cond in trial_conditions_lower
        )
        # Also check if any trial condition appears in patient's cancer type
        if not has_matching_condition:
            has_matching_condition = any(
                cond in patient_cancer or cond in patient_histology
                for cond in trial_conditions_lower
            )
        if not has_matching_condition:
            return False, f"Trial conditions {trial_conditions_lower[:3]} don't match patient cancer [{patient_cancer}]"

    # Fallback for trials without conditions: check title only (not summary)
    if not trial_conditions_lower and not is_basket_trial and patient_cancer_terms:
        trial_title_cancer = [kw for kw in cancer_keywords if kw in trial_title]
        if trial_title_cancer:
            has_matching_title = any(
                pt in trial_title_cancer for pt in patient_cancer_terms
            )
            if not has_matching_title:
                return False, f"Trial title targets {trial_title_cancer} but patient has {patient_cancer_terms}"

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
    patient_gender = (demographics.get("Gender") or demographics.get("Sex") or "").upper()
    trial_sex = (trial.get("sex") or "ALL").upper()

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
        criteria_text = (trial.get("eligibility_criteria_text") or "").lower()

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


def derive_clinical_facts(patient_data: Dict) -> str:
    """
    Compute clinically derived facts from patient data using rule-based logic.
    These are factual inferences that a clinician would make from available records,
    provided as additional context to the LLM to help resolve unknowns.

    Each fact MUST be directly supported by data — no assumptions or guesses.
    """
    facts = []
    demographics = patient_data.get("demographics", {}) or {}
    diagnosis = patient_data.get("diagnosis", {}) or {}
    comorbidities = patient_data.get("comorbidities", {}) or {}
    lab_info = patient_data.get("lab_info", {}) or {}
    treatment_info = patient_data.get("treatment_tab_info_LOT", {}) or {}

    # --- Age-based reproductive status ---
    age_str = demographics.get("Age", "")
    gender = (demographics.get("Gender", demographics.get("Sex", "")) or "").lower()
    age = None
    if age_str:
        age_match = re.search(r'(\d+)', str(age_str))
        if age_match:
            age = int(age_match.group(1))

    if age and gender in ("female", "f"):
        if age >= 55:
            facts.append(f"Patient is a {age}-year-old female — post-menopausal age (>=55). Not of childbearing potential. Pregnancy is not clinically possible.")
        elif age >= 50:
            facts.append(f"Patient is a {age}-year-old female — likely post-menopausal. Pregnancy is unlikely but not ruled out without confirmation.")
    elif age and gender in ("male", "m"):
        facts.append(f"Patient is a {age}-year-old male — pregnancy criteria are not applicable.")

    # --- Blood draw capability ---
    # If patient has recent lab results, blood was successfully collected
    has_recent_labs = False
    lab_date = None
    for category_key in ("complete_blood_count", "metabolic_panel", "tumor_markers"):
        category = lab_info.get(category_key, {}) or {}
        for lab_name, lab_data in category.items():
            if isinstance(lab_data, dict) and lab_data.get("has_data"):
                current = lab_data.get("current", {}) or {}
                d = current.get("date", "")
                if d:
                    has_recent_labs = True
                    if not lab_date or d > lab_date:
                        lab_date = d

    if has_recent_labs:
        facts.append(f"Patient had blood successfully drawn and processed (lab results available, most recent: {lab_date or 'date available'}). No contraindications to blood collection observed.")

    # --- Life expectancy from disease status + ECOG ---
    ecog_data = comorbidities.get("ecog_performance_status", {}) or {}
    ecog_score = ecog_data.get("score")
    if ecog_score in (None, '', 'NA', 'N/A', 'Unknown'):
        diag_ecog = diagnosis.get("ecog_status", "") or ""
        ecog_match = re.search(r'(\d)', str(diag_ecog))
        ecog_score = int(ecog_match.group(1)) if ecog_match else None
    else:
        try:
            ecog_score = int(ecog_score)
        except (ValueError, TypeError):
            ecog_score = None

    disease_status = (diagnosis.get("disease_status") or "").lower()

    if ecog_score is not None:
        if ecog_score <= 1:
            facts.append(f"ECOG {ecog_score}: Patient is ambulatory and functional. Life expectancy typically > 6 months.")
        elif ecog_score == 2:
            facts.append(f"ECOG {ecog_score}: Patient is ambulatory but unable to work. Life expectancy typically 3-6 months.")

    if "remission" in disease_status or "no evidence" in disease_status or "ned" in disease_status:
        facts.append(f"Disease status: '{diagnosis.get('disease_status')}' — patient is in remission/NED. Life expectancy is favorable.")

    # --- Treatment history summary ---
    treatment_history = treatment_info.get("treatment_history", []) or []
    if treatment_history:
        n_lines = len(treatment_history)
        facts.append(f"Patient has received {n_lines} prior line(s) of therapy (not treatment-naive).")
        # Check for specific therapy types
        therapies = []
        for t in treatment_history:
            regimen = t.get("regimen_details", {}) or {}
            drug_name = (regimen.get("display_name", "") or "").lower()
            if drug_name:
                therapies.append(drug_name)
        if therapies:
            facts.append(f"Prior therapies include: {', '.join(therapies[:5])}.")
    else:
        facts.append("No prior systemic therapy documented (treatment-naive).")

    # --- Ambulatory status from clinic visits ---
    last_visit = demographics.get("Last Visit", "")
    if last_visit and last_visit not in ("Unknown", "NA", "N/A"):
        facts.append(f"Patient is attending clinic visits (last visit: {last_visit}) — patient is ambulatory and able to travel to medical facilities.")

    # --- Organ function assessment from lab values ---
    def _get_lab_value(panel_name, biomarker_name):
        """Extract numeric value from lab_info for a given panel/biomarker."""
        panel = lab_info.get(panel_name, {}) or {}
        marker = panel.get(biomarker_name, {}) or {}
        if isinstance(marker, dict) and marker.get("has_data"):
            current = marker.get("current", {}) or {}
            raw_val = current.get("value")
            if raw_val is not None:
                try:
                    raw_unit = current.get("unit", "") or ""
                    # Compensate: standardize units for accurate clinical calculations
                    std_val, std_unit = standardize_lab_value(biomarker_name, raw_val, raw_unit)
                    return float(std_val), std_unit, current.get("date", "")
                except (ValueError, TypeError):
                    pass
        return None, None, None

    # Renal function
    creat_val, creat_unit, creat_date = _get_lab_value("metabolic_panel", "Creatinine")
    egfr_val, egfr_unit, egfr_date = _get_lab_value("metabolic_panel", "eGFR")
    bun_val, _, _ = _get_lab_value("metabolic_panel", "BUN")

    if egfr_val is not None:
        if egfr_val >= 60:
            facts.append(f"RENAL FUNCTION: ADEQUATE — eGFR={egfr_val} {egfr_unit} (≥60 mL/min = adequate). Creatinine clearance ≥60 mL/min. Date: {egfr_date}")
        elif egfr_val >= 30:
            facts.append(f"RENAL FUNCTION: MODERATE IMPAIRMENT — eGFR={egfr_val} {egfr_unit} (30-59 = moderate CKD). Date: {egfr_date}")
        else:
            facts.append(f"RENAL FUNCTION: SEVERE IMPAIRMENT — eGFR={egfr_val} {egfr_unit} (<30). Date: {egfr_date}")
    if creat_val is not None:
        uln = 1.2 if gender in ("female", "f") else 1.3
        ratio = round(creat_val / uln, 2)
        if creat_val <= 1.5 * uln:
            facts.append(f"CREATININE: {creat_val} {creat_unit} (≤1.5× ULN of {uln} = {round(1.5*uln,2)}). Ratio={ratio}× ULN. Date: {creat_date}")
        else:
            facts.append(f"CREATININE: ELEVATED — {creat_val} {creat_unit} (>{1.5*uln} = >1.5× ULN). Date: {creat_date}")
        # Calculate creatinine clearance (Cockcroft-Gault) if we have weight and age
        weight_str = demographics.get("Weight", "")
        weight = None
        if weight_str:
            w_match = re.search(r'([\d.]+)', str(weight_str))
            if w_match:
                weight = float(w_match.group(1))
                if "lb" in str(weight_str).lower():
                    weight = weight * 0.453592
        if age and weight and creat_val > 0:
            crcl = ((140 - age) * weight) / (72 * creat_val)
            if gender in ("female", "f"):
                crcl *= 0.85
            crcl = round(crcl, 1)
            facts.append(f"CALCULATED CREATININE CLEARANCE (Cockcroft-Gault): {crcl} mL/min")

    # Hepatic function
    alt_val, alt_unit, alt_date = _get_lab_value("liver_function", "ALT")
    ast_val, ast_unit, ast_date = _get_lab_value("liver_function", "AST")
    tbili_val, tbili_unit, tbili_date = _get_lab_value("liver_function", "Total_Bilirubin")
    alp_val, alp_unit, alp_date = _get_lab_value("liver_function", "Alkaline_Phosphatase")

    hepatic_ok = True
    hepatic_details = []
    if alt_val is not None:
        alt_uln = 35  # standard ULN
        ratio = round(alt_val / alt_uln, 2)
        hepatic_details.append(f"ALT={alt_val} {alt_unit} ({ratio}× ULN)")
        if alt_val > 2.5 * alt_uln:
            hepatic_ok = False
    if ast_val is not None:
        ast_uln = 35
        ratio = round(ast_val / ast_uln, 2)
        hepatic_details.append(f"AST={ast_val} {ast_unit} ({ratio}× ULN)")
        if ast_val > 2.5 * ast_uln:
            hepatic_ok = False
    if tbili_val is not None:
        tbili_uln = 1.2
        ratio = round(tbili_val / tbili_uln, 2)
        hepatic_details.append(f"Total Bilirubin={tbili_val} {tbili_unit} ({ratio}× ULN)")
        if tbili_val > 1.5 * tbili_uln:
            hepatic_ok = False
    if alp_val is not None:
        alp_uln = 120
        ratio = round(alp_val / alp_uln, 2)
        hepatic_details.append(f"ALP={alp_val} {alp_unit} ({ratio}× ULN)")

    if hepatic_details:
        status = "ADEQUATE" if hepatic_ok else "ABNORMAL"
        facts.append(f"HEPATIC FUNCTION: {status} — {'; '.join(hepatic_details)}. Date: {alt_date or ast_date or tbili_date}")

    # Hematologic / bone marrow function
    wbc_val, wbc_unit, wbc_date = _get_lab_value("complete_blood_count", "WBC")
    hgb_val, hgb_unit, hgb_date = _get_lab_value("complete_blood_count", "Hemoglobin")
    plt_val, plt_unit, plt_date = _get_lab_value("complete_blood_count", "Platelets")
    anc_val, anc_unit, anc_date = _get_lab_value("complete_blood_count", "ANC")

    heme_ok = True
    heme_details = []
    if wbc_val is not None:
        heme_details.append(f"WBC={wbc_val} {wbc_unit}")
        if wbc_val < 3.0:
            heme_ok = False
    if hgb_val is not None:
        heme_details.append(f"Hgb={hgb_val} {hgb_unit}")
        if hgb_val < 8.0:
            heme_ok = False
    if plt_val is not None:
        heme_details.append(f"Platelets={plt_val} {plt_unit}")
        if plt_val < 75:
            heme_ok = False
    if anc_val is not None:
        heme_details.append(f"ANC={anc_val} {anc_unit}")
        if anc_val < 1.0:
            heme_ok = False

    if heme_details:
        status = "ADEQUATE" if heme_ok else "ABNORMAL"
        facts.append(f"BONE MARROW / HEMATOLOGIC FUNCTION: {status} — {'; '.join(heme_details)}. Date: {wbc_date or hgb_date or plt_date}")

    # Coagulation
    inr_val, inr_unit, inr_date = _get_lab_value("coagulation", "INR")
    pt_val, pt_unit, pt_date = _get_lab_value("coagulation", "PT")
    aptt_val, aptt_unit, aptt_date = _get_lab_value("coagulation", "aPTT")

    coag_details = []
    coag_ok = True
    if inr_val is not None:
        coag_details.append(f"INR={inr_val}")
        if inr_val > 1.5:
            coag_ok = False
    if pt_val is not None:
        coag_details.append(f"PT={pt_val} {pt_unit}")
    if aptt_val is not None:
        coag_details.append(f"aPTT={aptt_val} {aptt_unit}")

    if coag_details:
        status = "WITHIN NORMAL LIMITS" if coag_ok else "ABNORMAL"
        facts.append(f"COAGULATION: {status} — {'; '.join(coag_details)}. Date: {inr_date or pt_date or aptt_date}")

    # Overall organ function summary
    if hepatic_details and heme_details and (creat_val is not None or egfr_val is not None):
        if hepatic_ok and heme_ok and (egfr_val is None or egfr_val >= 60) and (creat_val is None or creat_val <= 1.5 * (1.2 if gender in ("female", "f") else 1.3)):
            facts.append("OVERALL ORGAN FUNCTION: ADEQUATE — hepatic, renal, and hematologic function all within acceptable limits for clinical trial enrollment.")

    # --- Comorbidity-based facts ---
    comorbidity_list = comorbidities.get("comorbidities", []) or []
    condition_names = [c.get("condition_name", "").lower() for c in comorbidity_list if isinstance(c, dict)]

    # Check for specific conditions relevant to eligibility
    has_autoimmune = any(kw in name for name in condition_names for kw in ("autoimmune", "lupus", "rheumatoid", "psoriasis", "scleroderma", "myasthenia", "crohn", "ulcerative colitis"))
    has_cardiac = any(kw in name for name in condition_names for kw in ("cardiac", "heart failure", "cardiomyopathy", "arrhythmia", "atrial fibrillation", "coronary"))
    has_hepatitis = any(kw in name for name in condition_names for kw in ("hepatitis", "hbv", "hcv"))
    has_hiv = any(kw in name for name in condition_names for kw in ("hiv", "aids"))
    has_tb = any(kw in name for name in condition_names for kw in ("tuberculosis", "tb"))

    if has_autoimmune:
        auto_conditions = [n for n in condition_names if any(kw in n for kw in ("autoimmune", "lupus", "rheumatoid", "psoriasis", "scleroderma", "myasthenia", "crohn", "ulcerative colitis"))]
        facts.append(f"DOCUMENTED autoimmune condition(s): {', '.join(auto_conditions)}")
    else:
        facts.append("NO autoimmune disease documented in comorbidities list or medical history.")
    if has_cardiac:
        cardiac_conditions = [n for n in condition_names if any(kw in n for kw in ("cardiac", "heart failure", "cardiomyopathy", "arrhythmia", "atrial fibrillation", "coronary"))]
        facts.append(f"DOCUMENTED cardiac condition(s): {', '.join(cardiac_conditions)}")
    if has_hepatitis:
        facts.append("DOCUMENTED hepatitis in medical history.")
    else:
        facts.append("NO hepatitis B or C documented in comorbidities, medical history, or problem list.")
    if has_hiv:
        facts.append("DOCUMENTED HIV/AIDS in medical history.")
    else:
        facts.append("NO HIV/AIDS documented in comorbidities, medical history, or problem list.")
    if has_tb:
        facts.append("DOCUMENTED tuberculosis in medical history.")
    else:
        facts.append("NO tuberculosis documented in comorbidities or medical history.")

    # --- Dynamic rules from conversion_rules.json ---
    dynamic_facts = _apply_dynamic_rules(patient_data, demographics, comorbidities, lab_info, treatment_info)
    facts.extend(dynamic_facts)

    if not facts:
        return ""

    header = "\n=== CLINICALLY DERIVED FACTS (from patient records — cite these as evidence) ==="
    return header + "\n" + "\n".join(f"- {f}" for f in facts) + "\n"


def _load_conversion_rules() -> List[Dict]:
    """Load dynamic conversion rules from JSON config file."""
    rules_path = os.path.join(os.path.dirname(__file__), "..", "conversion_rules.json")
    try:
        with open(rules_path, "r") as f:
            data = json.load(f)
        return [r for r in data.get("rules", []) if r.get("active", False)]
    except (FileNotFoundError, json.JSONDecodeError) as e:
        print(f"Warning: Could not load conversion rules: {e}")
        return []


def _get_all_treatment_drugs(treatment_info: Dict) -> List[str]:
    """Extract all drug names from treatment history."""
    drugs = []
    treatment_history = treatment_info.get("treatment_history", []) or []
    for t in treatment_history:
        if isinstance(t, dict):
            regimen = t.get("regimen_details", {}) or {}
            display = (regimen.get("display_name", "") or "").lower()
            if display:
                drugs.append(display)
            # Also check individual drug names in the regimen
            drug_list = regimen.get("drugs", []) or []
            for d in drug_list:
                if isinstance(d, str):
                    drugs.append(d.lower())
                elif isinstance(d, dict):
                    drugs.append((d.get("name", "") or "").lower())
    return drugs


def _get_all_condition_names(comorbidities: Dict) -> List[str]:
    """Extract all condition names from comorbidities."""
    comorbidity_list = comorbidities.get("comorbidities", []) or []
    return [c.get("condition_name", "").lower() for c in comorbidity_list if isinstance(c, dict)]


def _get_all_medication_names(comorbidities: Dict) -> List[str]:
    """Extract all medication names from comorbidities."""
    meds = []
    comorbidity_list = comorbidities.get("comorbidities", []) or []
    for c in comorbidity_list:
        if isinstance(c, dict):
            assoc_meds = c.get("associated_medications", []) or []
            if isinstance(assoc_meds, list):
                meds.extend([m.lower() for m in assoc_meds if isinstance(m, str)])
            elif isinstance(assoc_meds, str):
                meds.append(assoc_meds.lower())
    return meds


def _apply_dynamic_rules(patient_data: Dict, demographics: Dict, comorbidities: Dict,
                          lab_info: Dict, treatment_info: Dict) -> List[str]:
    """Apply dynamic conversion rules from conversion_rules.json."""
    rules = _load_conversion_rules()
    if not rules:
        return []

    facts = []
    condition_names = _get_all_condition_names(comorbidities)
    treatment_drugs = _get_all_treatment_drugs(treatment_info)
    medication_names = _get_all_medication_names(comorbidities)
    all_searchable_terms = condition_names + treatment_drugs + medication_names

    # Get patient basics
    age_str = demographics.get("Age", "")
    gender = (demographics.get("Gender", demographics.get("Sex", "")) or "").lower()
    age = None
    if age_str:
        age_match = re.search(r'(\d+)', str(age_str))
        if age_match:
            age = int(age_match.group(1))

    # Get height/weight for formulas
    height_cm = None
    weight_kg = None
    height_str = str(demographics.get("Height", "") or "")
    weight_str = str(demographics.get("Weight", "") or "")
    if height_str:
        hs = height_str.lower()
        # Handle "5 feet 6 inches", "5'6\"", "5 ft 6 in" patterns
        ft_in_match = re.search(r'(\d+)\s*(?:feet|foot|ft|\')\s*(\d+)\s*(?:inches|inch|in|")?', hs)
        if ft_in_match:
            feet = float(ft_in_match.group(1))
            inches = float(ft_in_match.group(2))
            height_cm = (feet * 12 + inches) * 2.54
        else:
            h_match = re.search(r'([\d.]+)', hs)
            if h_match:
                height_cm = float(h_match.group(1))
                if "cm" in hs:
                    pass  # already cm
                elif "m" in hs and "ft" not in hs and "in" not in hs:
                    height_cm = height_cm * 100  # meters to cm
                elif "ft" in hs or "'" in hs:
                    height_cm = height_cm * 30.48  # feet only to cm
                elif "in" in hs or '"' in hs:
                    height_cm = height_cm * 2.54  # inches to cm
    if weight_str:
        w_match = re.search(r'([\d.]+)', weight_str)
        if w_match:
            weight_kg = float(w_match.group(1))
            if "lb" in weight_str.lower() or "pound" in weight_str.lower():
                weight_kg = weight_kg * 0.453592  # lbs to kg

    # Get ECOG score
    ecog_data = comorbidities.get("ecog_performance_status", {}) or {}
    ecog_score = ecog_data.get("score")
    if ecog_score in (None, '', 'NA', 'N/A', 'Unknown'):
        diag = patient_data.get("diagnosis", {}) or {}
        diag_ecog = diag.get("ecog_status", "") or ""
        ecog_match = re.search(r'(\d)', str(diag_ecog))
        ecog_score = int(ecog_match.group(1)) if ecog_match else None
    else:
        try:
            ecog_score = int(ecog_score)
        except (ValueError, TypeError):
            ecog_score = None

    # Get social history
    social_history = demographics.get("Social History", {}) or {}

    # Get ROS
    ros = comorbidities.get("review_of_systems", {}) or {}

    # Get radiology summaries
    radiology_info = patient_data.get("radiology_details", []) or []
    radiology_text = " ".join(
        (r.get("summary", "") or "").lower() for r in radiology_info if isinstance(r, dict)
    )

    for rule in rules:
        rule_type = rule.get("type", "")
        rule_id = rule.get("id", "unknown")

        try:
            if rule_type == "lookup":
                # KPS from ECOG, ECOG from KPS
                source = rule.get("source_field", "")
                lookup = rule.get("lookup_table", {})

                if source == "ecog_score" and ecog_score is not None:
                    key = str(ecog_score)
                    if key in lookup:
                        entry = lookup[key]
                        fact = rule["output_template"].format(
                            ecog=ecog_score,
                            kps_range=entry.get("kps_range", ""),
                            kps_min=entry.get("kps_min", ""),
                            description=entry.get("description", "")
                        )
                        facts.append(fact)

            elif rule_type == "formula":
                # BMI, BSA, etc.
                required = rule.get("required_fields", [])
                values = {}
                has_all = True
                for field in required:
                    if field == "height_cm" and height_cm:
                        values[field] = height_cm
                    elif field == "weight_kg" and weight_kg:
                        values[field] = weight_kg
                    elif field == "age" and age:
                        values[field] = age
                    else:
                        has_all = False
                        break

                if has_all and values:
                    # Safe eval of simple math formula
                    formula_str = rule.get("formula", "")
                    try:
                        result = eval(formula_str, {"__builtins__": {}}, values)
                        result = round(result, 2)
                        values["result"] = result
                        fact = rule["output_template"].format(**values)
                        facts.append(fact)
                    except Exception:
                        pass

            elif rule_type == "data_search":
                # Search treatment history for specific drugs
                search_terms = rule.get("search_terms", [])
                matches = []
                drugs_searched = treatment_drugs

                for term in search_terms:
                    for drug in treatment_drugs:
                        if term.lower() in drug:
                            matches.append(drug)

                if matches:
                    unique_matches = list(set(matches))
                    fact = rule["output_if_found"].format(matches=", ".join(unique_matches))
                else:
                    fact = rule["output_if_not_found"].format(drugs_searched=", ".join(treatment_drugs[:10]) if treatment_drugs else "none documented")
                facts.append(fact)

            elif rule_type == "cross_reference":
                # Search across multiple sections
                search_terms = rule.get("search_terms", [])
                search_sections = rule.get("search_sections", [])
                matches = []

                # Build searchable items from specified sections
                # Use condition_names and medication_names (structured data — no negation issues)
                structured_items = []
                if "comorbidities" in search_sections:
                    structured_items.extend(condition_names)
                    structured_items.extend(medication_names)
                if "treatment_history" in search_sections:
                    structured_items.extend(treatment_drugs)
                if "medications" in search_sections:
                    structured_items.extend(medication_names)
                if "surgical_history" in search_sections:
                    structured_items.extend(condition_names)

                # Search structured items (these are condition/drug names — no negation)
                for term in search_terms:
                    for item in structured_items:
                        if term.lower() in item:
                            matches.append(term)

                # For free-text sections (ROS, radiology), handle negation
                # "No seizures" should NOT match as positive for "seizure"
                negation_patterns = re.compile(
                    r'(?:no|not|negative|denies|deny|without|absent|none|never|no evidence of)\s+(?:\w+\s+){0,3}',
                    re.IGNORECASE
                )

                free_text_parts = []
                if "radiology" in search_sections:
                    free_text_parts.append(radiology_text)
                if "ros_respiratory" in search_sections:
                    resp_ros = (ros.get("respiratory", "") or "").lower()
                    free_text_parts.append(resp_ros)
                if "neurological" in search_sections:
                    neuro_ros = (ros.get("neurological", "") or "").lower()
                    free_text_parts.append(neuro_ros)

                for text in free_text_parts:
                    if not text:
                        continue
                    for term in search_terms:
                        if term.lower() in text:
                            # Check if this is a negated mention
                            term_idx = text.find(term.lower())
                            # Look at the 80 chars before the term for negation words
                            context_before = text[max(0, term_idx - 80):term_idx].lower()
                            if negation_patterns.search(context_before + " " + term.lower()):
                                # Negated — "no seizures" means ABSENCE, not presence
                                pass
                            else:
                                matches.append(term)

                if matches:
                    unique_matches = list(set(matches))
                    fact = rule["output_if_found"].format(matches=", ".join(unique_matches))
                else:
                    fact = rule["output_if_not_found"]
                facts.append(fact)

            elif rule_type == "logic":
                conditions = rule.get("conditions", {})
                check_field = conditions.get("check_field", "")
                logic_rules = conditions.get("logic", [])
                result = None

                if check_field == "social_history.smoking_status":
                    value = (social_history.get("smoking_status", "") or "").lower()
                    if value:
                        for lr in logic_rules:
                            if "if_contains" in lr:
                                if any(kw in value for kw in lr["if_contains"]):
                                    result = lr["result"]
                                    break
                            elif "default" in lr:
                                result = lr["default"].format(value=value)
                    if result:
                        fact = rule["output_template"].format(result=result)
                        facts.append(fact)

                elif check_field == "treatment_history":
                    treatment_history = treatment_info.get("treatment_history", []) or []
                    count = len(treatment_history)
                    regimens = ", ".join(treatment_drugs[:5]) if treatment_drugs else "none"
                    for lr in logic_rules:
                        if "if" in lr:
                            if lr["if"] == "count=0" and count == 0:
                                result = lr["result"]
                                break
                            elif lr["if"] == "count>=1" and count >= 1:
                                result = lr["result"].format(count=count, regimens=regimens)
                                break
                    if result:
                        fact = rule["output_template"].format(result=result)
                        facts.append(fact)

                elif not check_field:
                    # Gender/age-based logic (reproductive status)
                    for lr in logic_rules:
                        if_cond = lr.get("if", "")
                        if "gender=male" in if_cond and gender in ("male", "m"):
                            result = lr["result"].format(age=age or "unknown")
                            break
                        elif "gender=female AND age>=55" in if_cond and gender in ("female", "f") and age and age >= 55:
                            result = lr["result"].format(age=age)
                            break
                        elif "gender=female AND age>=50" in if_cond and gender in ("female", "f") and age and age >= 50:
                            result = lr["result"].format(age=age)
                            break
                        elif "gender=female AND age<50" in if_cond and gender in ("female", "f") and age and age is not None and age < 50:
                            result = lr["result"].format(age=age)
                            break

                    if result:
                        fact = rule["output_template"].format(result=result)
                        facts.append(fact)

        except Exception as e:
            print(f"Warning: Error applying rule '{rule_id}': {e}")
            continue

    return facts


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

    # Clean criteria text: remove markdown escape sequences that break JSON parsing
    # ClinicalTrials.gov sometimes has \*, 1\., etc. in criteria text
    cleaned_criteria = []
    for c in criteria_list:
        cleaned = c.replace('\\*', '*').replace('\\.', '.')
        cleaned = re.sub(r'\\([^"\\/bfnrtu])', r'\1', cleaned)  # Remove invalid backslash escapes
        cleaned_criteria.append(cleaned)

    # Build the numbered criteria list
    criteria_numbered = "\n".join([f"{i+1}. {c}" for i, c in enumerate(cleaned_criteria)])

    # Compute derived clinical facts from patient data
    derived_facts = derive_clinical_facts(patient_data)

    # Construct the prompt - THIS IS THE KEY PART
    # Enable clinical reasoning to infer eligibility from related data
    prompt = f"""You are an expert oncology clinical trials eligibility analyst with deep knowledge of cancer medicine and clinical trial criteria.

## PATIENT INFORMATION
{patient_context}

{derived_facts}

## TRIAL {criteria_type.upper()} CRITERIA TO EVALUATE
{criteria_numbered}

## YOUR TASK
For EACH criterion above, determine whether the patient meets it using:
1. Direct evidence from patient data
2. The CLINICALLY DERIVED FACTS section above (these are pre-verified inferences — you may cite them directly)
3. Clinical reasoning ONLY when you can cite specific patient data as evidence

## EVIDENCE-BASED INFERENCE RULES
You MUST cite specific patient data or derived facts for every determination.

**ALLOWED inferences (cite the specific data):**
- **Organ function FROM lab values**: Use the CLINICALLY DERIVED FACTS section — it pre-computes renal, hepatic, hematologic, and coagulation assessments from actual lab values. CITE THESE DIRECTLY. For "adequate organ function" criteria → if derived facts say "ADEQUATE" for renal + hepatic + hematologic → met=true.
- **Lab threshold criteria**: ALT ≤2.5× ULN, bilirubin ≤1.5× ULN, creatinine ≤1.5× ULN, etc. → The derived facts include ×ULN ratios. USE THEM. Do NOT mark unknown if the value is in derived facts.
- **Creatinine clearance**: If derived facts include "CALCULATED CREATININE CLEARANCE" → use that value directly for CrCl criteria.
- **Life expectancy**: From ECOG score or disease status (NED/remission = favorable prognosis)
- **Prior therapy**: From treatment history (line count, drug names, dates)
- **Blood/specimen collection**: Recent lab results prove blood was successfully drawn
- **Reproductive status**: From age + gender (e.g., female >=55 = post-menopausal, male = pregnancy N/A)
- **Ambulatory status**: From clinic visits or ECOG score
- **Disease characteristics**: From staging, imaging, pathology data
- **No active treatment toxicity**: If labs are normal and treatment ended months ago
- **HIV/Hepatitis/TB from medical records**: If derived facts state "NO HIV/AIDS documented" AND "NO hepatitis documented" → the patient's comprehensive medical record does NOT list these conditions. For EXCLUSION criteria asking "no HIV" or "no hepatitis" → met=false (patient does NOT have it) with confidence="medium".
- **Autoimmune disease**: If derived facts state "NO autoimmune disease documented" → met=false for "active autoimmune disease" exclusion with confidence="medium".

**USING DOCUMENTED CLINICAL DATA (use these sections when available):**
- ALLERGIES section says "NKDA" or "No Known Drug Allergies" → patient is NOT allergic to any drug (met=true for "no allergy to X" criteria)
- REVIEW OF SYSTEMS says "Negative" for a system → patient DENIES symptoms in that system (e.g., ROS cardiovascular=Negative → no chest pain, no palpitations, no syncope)
- PHYSICAL EXAM documents normal findings → those body systems are clinically normal
- SOCIAL HISTORY documents "Never smoker" → patient has no smoking history
- VITAL SIGNS are documented → use them for criteria about BP, heart rate, O2 saturation, etc.
- VACCINATION section documents status → use for immunization criteria
- LAB VALUES section has actual numeric values → use for ANY lab-based threshold criterion (hemoglobin ≥X, platelets ≥X, creatinine ≤X, etc.)
- CLINICALLY DERIVED FACTS has pre-computed organ function assessments → use for "adequate organ/hepatic/renal/hematologic function" criteria

**CALCULATE IF DATA EXISTS (critical — do NOT say UNKNOWN if you can compute the answer):**
- If a criterion requires a score/value that can be calculated from available patient data using a standard medical formula, YOU MUST CALCULATE IT and use the result. Show your math.
- Common formulas you MUST apply when data is available:
  - **BMI** = weight(kg) / height(m)² — if height and weight are available
  - **BSA** (Du Bois) = 0.007184 × height(cm)^0.725 × weight(kg)^0.425
  - **Creatinine Clearance** (Cockcroft-Gault) = ((140-age) × weight) / (72 × creatinine) [×0.85 if female]
  - **MELD Score** = 10 × (0.957×ln(creatinine) + 0.378×ln(bilirubin) + 1.120×ln(INR) + 0.643)
  - **Child-Pugh Score** = from albumin + bilirubin + INR + ascites + encephalopathy
  - **KPS from ECOG**: ECOG 0=KPS 90-100, ECOG 1=KPS 70-80, ECOG 2=KPS 50-60, ECOG 3=KPS 30-40
  - **Any lab threshold × ULN**: Compare lab value to standard ULN and compute the ratio
- If a criterion asks about a prior drug/therapy → SEARCH the treatment history for that drug name
- If a criterion asks "no history of X" → SEARCH comorbidities, treatment history, and medical records for X. If NOT found anywhere → the patient does NOT have it

**FORBIDDEN inferences (mark as UNKNOWN ONLY for these):**
- No echocardiogram/EKG data → UNKNOWN for ejection fraction (LVEF), QTc interval, cardiac function tests
- No ECOG score documented AND no KPS documented → UNKNOWN (do NOT assume functional)
- No specific imaging or procedural test → UNKNOWN for findings from that test
- Lab value for a SPECIFIC test not present AND not calculable from other values → UNKNOWN

## IMPORTANT RULES
1. **INCLUSION criteria**: Patient SHOULD meet these to be eligible
2. **EXCLUSION criteria**: Patient should NOT have these conditions to be eligible
3. **Cite evidence**: Every met=true or met=false MUST cite specific data (lab value, date, fact)
4. **ALWAYS CHECK DERIVED FACTS FIRST**: Before marking anything unknown, check if the CLINICALLY DERIVED FACTS section already answers it (organ function, lab thresholds, infection status, creatinine clearance, KPS score, BMI, BSA, treatment searches, cross-references)
5. **Lab-based criteria are NEVER unknown if lab values are present**: If the patient context includes the relevant lab value, USE IT to determine met/not met — do NOT mark unknown
6. **Calculable criteria are NEVER unknown**: If you have the raw data to compute a required value (BMI, BSA, CrCl, MELD, KPS, etc.), CALCULATE IT — do NOT mark unknown
7. **History-based exclusions**: If a criterion says "no history of X" and X is NOT found anywhere in comorbidities, treatment history, or medical records → met=false (patient does NOT have it) with confidence="medium"
8. **Infection exclusions**: If derived facts say "NO HIV documented", "NO hepatitis documented", "NO tuberculosis documented" → the patient's medical record was reviewed and these conditions are absent → met=false (not excluded)
9. **Explain your reasoning**: Show exactly what data you used and any calculations performed

## BE DECISIVE — met=null IS A LAST RESORT
You are being too cautious if you mark met=null when you already have enough data to decide.
met=null means "I have NO IDEA" — not "I'm not 100% certain." Use these rules:

**RULE A: Absence of a condition in records = condition absent.**
For EXCLUSION criteria asking about diseases, infections, or conditions:
If you searched the records and found NO evidence of the condition → met=false (patient does NOT have it).
Do NOT say "cannot confirm without comprehensive testing." Medical records ARE the source of truth.
Examples:
- "Active infection" + no infection documented → met=false
- "Severe cardiac disease" + no cardiac issues documented → met=false
- "Concurrent infectious diseases" + no infections documented → met=false
- "Metallic implants or MRI contraindications" + none documented → met=false
- "Received radionuclide drugs" + none found in treatment history → met=false
- "Participation in another clinical trial" + none documented → met=false

**RULE B: Gender/demographic mismatch = resolved.**
If a criterion is clearly not applicable due to patient demographics, RESOLVE IT:
- Male patient + pregnancy/childbearing/birth control criterion → met=true for inclusion (not applicable = met), met=false for exclusion
- Patient age clearly meets/doesn't meet age criterion → resolve it

**RULE C: Data clearly matches = commit to the answer.**
If your extracted patient_value directly answers the criterion, commit:
- "≥3 prior lines of therapy" + patient has 5 prior lines → met=true
- "Prior radiation to spine" + radiation to lumbar spine documented → met=true

**RULE D: Only use met=null when:**
- A specific TEST result is required but was never performed (LVEF needs echo, QTc needs EKG, mutation status needs genomic profiling)
- The criterion requires SUBJECTIVE clinical judgment you truly cannot make ("severe," "clinically significant," "interferes with study")
- The criterion text is too vague or incomplete to evaluate ("as specified in protocol")
- Critical information is genuinely missing from all records

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
        response = model.generate_content(
            prompt, generation_config=generation_config
        )
        response_text = response.text.strip()

        # Clean up response - remove markdown code blocks if present
        if response_text.startswith("```"):
            response_text = re.sub(r'^```(?:json)?\s*', '', response_text)
            response_text = re.sub(r'\s*```$', '', response_text)
        
        # Fix common JSON escape issues from LLM responses
        # Replace unescaped backslashes that aren't valid escape sequences
        response_text = re.sub(r'\\(?!["\\/bfnrtu])', r'\\\\', response_text)

        # Try to parse JSON with multiple fallback strategies
        results = None
        for attempt in range(3):
            try:
                if attempt == 0:
                    results = json.loads(response_text)
                elif attempt == 1:
                    # Try extracting just the array portion
                    match = re.search(r'\[[\s\S]*\]', response_text)
                    if match:
                        results = json.loads(match.group())
                elif attempt == 2:
                    # Last resort: aggressively strip all backslashes except valid JSON escapes
                    cleaned = re.sub(r'\\(?!["\\/bfnrtu])', '', response_text)
                    results = json.loads(cleaned)
                if results is not None:
                    break
            except json.JSONDecodeError:
                if attempt == 2:
                    raise
                continue

        if results is None:
            raise json.JSONDecodeError("Failed all parse attempts", response_text, 0)
        
        # Add criterion type and original text to each result
        for i, r in enumerate(results):
            r["criterion_type"] = criteria_type
            # Store original (full) criterion text for consent detection
            # LLM may truncate criterion_text to 50 chars
            if i < len(cleaned_criteria):
                r["original_criterion_text"] = cleaned_criteria[i]

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


CONSENT_KEYWORDS = [
    # Consent & agreement
    'consent', 'willing to', 'agree to', 'agreement to provide',
    'comply with', 'able to comply', 'willing to comply', 'willingness to',
    'cooperate with', 'commit to', 'adhere to protocol',
    'capable of giving', 'voluntarily', 'assent', 'refusal',
    # Understanding & signing
    'ability to understand', 'able to understand', 'sign consent',
    'provide consent', 'informed consent', 'written consent', 'oral consent',
    'sign icf', 'understand, sign', 'read, understand',
    # Legal & administrative
    'legally authorized', 'decision-making capacity',
    'court protection', 'legal protection', 'under guardianship',
    'medical insurance', 'covered by insurance',
    # Language requirements (administrative, not clinical)
    'fluent in', 'speak english', 'read english', 'understand english',
    'speak french', 'speak, read', 'read and understand english',
    'fluent english', 'comprehend english',
    # Study compliance
    'follow study', 'available for follow',
]

# Location/relocation criteria — only the patient can decide these
LOCATION_KEYWORDS = [
    'reside in', 'reside within', 'reside near',
    'live in', 'live within', 'live near',
    'located in', 'located within', 'located near',
    'travel to', 'able to travel', 'willing to travel',
    'commuting distance', 'driving distance',
    'relocate', 'move to', 'able to move',
    'within driving', 'within commuting',
    'surrounding area', 'metropolitan area',
    'access to the study site', 'access to study site',
    'proximity to', 'close to the site',
]

# Investigator/compliance criteria — subjective judgment calls, never answerable from data
INVESTIGATOR_KEYWORDS = [
    'investigator deem', 'investigator considers',
    'deemed unsuitable', 'deems unsuitable',
    'unsuitable for inclusion', 'unsuitable for this study',
    'unsuitable by investigator', 'unsuitable by treating',
    'unsuitable by the investigator', 'unsuitable by the treating',
    'other unsuitable', 'other abnormal findings unsuitable',
    'other risks making subject unsuitable',
    'other diseases making patient unsuitable',
    'protocol non-compliance', 'non-compliance to medical',
    'medical condition decreasing data reliability',
    'serious adverse effects/unsafe', 'serious adverse effects/other unsuitable',
]


def is_investigator_criterion(criterion_text: str) -> bool:
    """Check if a criterion is an investigator/compliance judgment call."""
    text = (criterion_text or "").lower()
    return any(kw in text for kw in INVESTIGATOR_KEYWORDS)


def is_consent_criterion(criterion_text: str) -> bool:
    """Check if a criterion is consent/administrative rather than clinical."""
    text = (criterion_text or "").lower()
    return any(kw in text for kw in CONSENT_KEYWORDS)


CLINICAL_INDICATORS = [
    'contraception', 'contraceptive', 'pregnancy test', 'pregnant',
    'breastfeeding', 'childbearing', 'measurable', 'lesion', 'tumor',
    'metasta', 'cancer', 'lymphoma', 'carcinoma', 'disease',
    'chemotherapy', 'systemic', 'autoimmune', 'hepatitis',
]


def is_location_criterion(criterion_text: str) -> bool:
    """Check if a criterion is about location/relocation/travel."""
    text = (criterion_text or "").lower()
    return any(kw in text for kw in LOCATION_KEYWORDS)


def mark_consent_criteria(criteria_results: List[Dict]) -> List[Dict]:
    """
    Post-process criteria results: mark consent/administrative, location,
    and investigator-judgment criteria with consent_needed flag
    (displayed as 'Patient Review Needed').
    Uses the LLM's short summary (criterion_text) to avoid false positives.
    """
    for r in criteria_results:
        short_text = (r.get("criterion_text", "") or "").lower()
        has_consent = is_consent_criterion(short_text)
        has_location = is_location_criterion(short_text)
        has_investigator = is_investigator_criterion(short_text)
        has_clinical = any(ci in short_text for ci in CLINICAL_INDICATORS)
        if (has_consent and not has_clinical) or has_location or has_investigator:
            r["met"] = True
            r["consent_needed"] = True
            r["confidence"] = "patient_review"
            if has_location:
                r["explanation"] = (
                    "Location/travel requirement — only the patient can confirm. "
                    "Counted as met for eligibility scoring."
                )
            elif has_investigator:
                r["explanation"] = (
                    "Investigator/compliance judgment — only the treating physician can assess at screening. "
                    "Counted as met for eligibility scoring."
                )
            else:
                r["explanation"] = (
                    "Patient consent/agreement required — not a clinical data criterion. "
                    "Counted as met for eligibility scoring."
                )
    return criteria_results


# ── Bucket 2 & 3: Unknown criteria classification (Stage 2 LLM) ─────────────
# After Stage 1 matching produces met=null unknowns, a SECOND LLM pass
# classifies each unknown criterion into the correct review bucket:
#
#   1. consent_needed → "patient"  (already flagged by mark_consent_criteria)
#   2. LLM Stage 2 → "patient"    (patient can answer: willingness, lifestyle, demographics)
#   3. LLM Stage 2 → "clinician"  (has data but needs clinical judgment + clinician_action)
#   4. LLM Stage 2 → "testing"    (no data, needs a specific test + suggested_test)
#
# We do NOT derive review_type from patient_value heuristics because
# "Unknown" doesn't always mean "needs a test" (e.g. "Patients referred to
# the centres" has pv=Unknown but doesn't need a lab test — the patient knows).


def _pre_classify_unknown(r: Dict) -> Optional[str]:
    """
    Pre-classify an unknown criterion using keyword patterns.
    Returns review_type ("patient", "clinician", "testing") if high-confidence,
    or None if ambiguous (needs LLM).
    Also sets suggested_test or clinician_action when possible.
    """
    text = (r.get("criterion_text", "") or "").lower()
    # Only use criterion_text — original_criterion_text can bleed across criteria
    pv = (r.get("patient_value", "") or "").strip().lower()
    has_data = pv and pv not in ("unknown", "n/a", "none", "not available",
                                  "not found", "not documented", "not provided",
                                  "not recorded", "error analyzing")

    # ── PATIENT patterns (high confidence) ──
    PATIENT_KEYWORDS = [
        # Legal / administrative
        "dpa", "power of attorney", "legal representative", "legally authorized",
        "social security", "insurance", "health coverage", "health plan",
        "guardian", "guardianship", "court protection",
        # Consent-adjacent
        "willing", "willingness", "agree to", "consent", "assent",
        "able to comply", "comply with", "adhere to",
        "able to understand", "understand and sign", "read and understand",
        # Personal / lifestyle
        "contraception", "contraceptive", "birth control",
        "substance use", "alcohol", "smoking", "tobacco",
        "breastfeeding", "nursing", "pregnant", "pregnancy",
        "sexually active", "sexual abstinence",
        # Enrollment / logistics
        "other study", "another trial", "another study", "concurrent study",
        "enrolled in", "participating in",
        "travel", "reside", "live within", "located within",
        "available for follow", "attend visit",
        # Language / communication
        "speak english", "read english", "fluent", "language",
        # Identity / demographics
        "affiliated with", "affiliation", "nationality", "citizen",
    ]
    if any(kw in text for kw in PATIENT_KEYWORDS):
        return "patient"

    # ── TESTING patterns (specific orderable tests) ──
    TESTING_MAP = {
        "echocardiogram": "Echocardiogram (ECHO)",
        "echo ": "Echocardiogram (ECHO)",
        "lvef": "Echocardiogram (ECHO)",
        "ejection fraction": "Echocardiogram (ECHO)",
        "cardiac function": "Echocardiogram (ECHO)",
        "qtc": "12-lead ECG",
        "qt interval": "12-lead ECG",
        "electrocardiogram": "12-lead ECG",
        "ekg": "12-lead ECG",
        "ecg": "12-lead ECG",
        "hepatitis b": "Hepatitis B Panel (HBsAg, anti-HBc, HBV DNA)",
        "hepatitis c": "Hepatitis C Panel (anti-HCV, HCV RNA)",
        "hbsag": "Hepatitis B Panel (HBsAg, anti-HBc, HBV DNA)",
        "hiv": "HIV-1/2 Antigen/Antibody Test",
        "pulmonary function": "Pulmonary Function Test (PFT)",
        "fev1": "Pulmonary Function Test (PFT)",
        "dlco": "Pulmonary Function Test (PFT)",
        "spirometry": "Pulmonary Function Test (PFT)",
        "bone marrow": "Bone Marrow Biopsy",
        "ngs": "Next-Generation Sequencing (NGS Panel)",
        "genomic profiling": "Next-Generation Sequencing (NGS Panel)",
        "mutation status": "Next-Generation Sequencing (NGS Panel)",
        "molecular profiling": "Next-Generation Sequencing (NGS Panel)",
        "pd-l1": "PD-L1 IHC Assay",
        "msi": "Microsatellite Instability (MSI) Testing",
        "microsatellite": "Microsatellite Instability (MSI) Testing",
        "mmr": "Mismatch Repair (MMR) IHC",
        "brain mri": "MRI Brain with Contrast",
        "brain metastas": "MRI Brain with Contrast",
        "cns metastas": "MRI Brain with Contrast",
        "urine protein": "Urinalysis with Protein/Creatinine Ratio",
        "proteinuria": "Urinalysis with Protein/Creatinine Ratio",
        "thyroid function": "Thyroid Function Panel (TSH, Free T4)",
        "tsh": "Thyroid Function Panel (TSH, Free T4)",
        "coagulation": "Coagulation Panel (PT, INR, aPTT)",
        "inr": "Coagulation Panel (PT, INR, aPTT)",
        "pt/inr": "Coagulation Panel (PT, INR, aPTT)",
    }
    if not has_data:
        for keyword, test_name in TESTING_MAP.items():
            if keyword in text:
                r["suggested_test"] = test_name
                return "testing"

    # ── CLINICIAN: has real data but couldn't decide ──
    if has_data:
        pv_display = r.get("patient_value", "Unknown")
        r["clinician_action"] = f"Patient has: {pv_display}. Review if this meets the criterion."
        return "clinician"

    # ── AMBIGUOUS: needs LLM ──
    return None


def classify_unknown_criteria_with_llm(criteria_results: List[Dict]) -> List[Dict]:
    """
    Stage 2: Classify unknown (met=null) criteria into review_type buckets.

    Uses a two-pass approach:
    1. Pre-classify obvious items with keyword patterns (no LLM needed)
    2. Send only ambiguous items to Stage 2 LLM

    This reduces LLM calls significantly — many trials need zero Stage 2 calls.
    """
    # Collect unknown criteria (skip consent — already classified)
    unknowns = []
    for i, r in enumerate(criteria_results):
        if r.get("consent_needed", False):
            r["review_type"] = "patient"
            continue
        if r.get("met") is not None:
            continue
        unknowns.append(r)

    if not unknowns:
        return criteria_results

    # Pass 1: Pre-classify with keywords
    needs_llm = []
    for r in unknowns:
        review_type = _pre_classify_unknown(r)
        if review_type:
            r["review_type"] = review_type
        else:
            needs_llm.append(r)

    pre_classified = len(unknowns) - len(needs_llm)
    print(f"  Stage 2 pre-filter: {pre_classified}/{len(unknowns)} classified by keywords, {len(needs_llm)} need LLM")

    # If all classified by keywords, skip LLM entirely
    if not needs_llm:
        return criteria_results

    # Pass 2: Send only ambiguous items to Stage 2 LLM
    criteria_block = ""
    for idx, r in enumerate(needs_llm):
        criteria_block += (
            f"{idx + 1}. criterion_text: \"{r.get('criterion_text', '')}\"\n"
            f"   patient_value: \"{r.get('patient_value', 'Unknown')}\"\n"
            f"   explanation: \"{r.get('explanation', '')}\"\n"
            f"   criterion_type: \"{r.get('criterion_type', 'inclusion')}\"\n\n"
        )

    prompt = f"""You are a clinical trial eligibility classifier. You are given criteria that could NOT be
resolved during eligibility matching (met=null). Your job is to classify WHO can resolve each one.

## THE THREE BUCKETS

**"patient"** — The patient themselves can answer this. No medical records or tests needed.
Examples: willingness to participate, consent, lifestyle choices, personal preferences,
enrollment in other studies, ability to travel, language ability, insurance status,
contraception willingness, substance use, dietary habits, technology access,
legal documents (DPA, power of attorney), social security, affiliation, nationality,
breastfeeding/pregnancy status, device access, caregiver availability.
Key signal: The criterion asks about something only the patient would know or provide.

**"clinician"** — A clinician needs to review records or make a clinical judgment call.
Two sub-cases:
1. patient_value has real data but the matching LLM couldn't make the final call →
   clinician reviews and decides (severity grading, "clinically significant", staging ambiguity).
2. The criterion requires clinical assessment or physician evaluation — NOT a specific
   orderable test, but a doctor looking at the patient or their records and making a judgment.
   Examples: performance status assessment, disease severity evaluation, treatment planning,
   "adequate organ function" when some but not all labs are available, medication review.
Key signal: If you find yourself wanting to write "Clinical Assessment" as a test → it's clinician, NOT testing.
For each clinician item, provide clinician_action: a short note (max 2 sentences) describing
what the clinician should check or decide.

**"testing"** — A specific, orderable medical test that has NOT been done yet.
You must be able to name the EXACT test. If you cannot name a specific test, it is NOT testing.
Examples: "Echocardiogram (ECHO)" for LVEF, "12-lead ECG" for QTc interval,
"Hepatitis B/C Panel" for viral status, "NGS Panel" for mutation profiling,
"CT scan of chest/abdomen" for tumor measurements, "Pulmonary Function Test (PFT)".
Key signal: patient_value is "Unknown" AND you can name a specific lab/imaging/procedure.
NEVER use generic terms like "Clinical Assessment", "Testing Needed", "General Assessment",
or "Medical Evaluation" as suggested_test. If you cannot name a specific orderable test,
classify as "clinician" instead.

## DECISION RULES (follow in order)
1. Is it about patient willingness, consent, lifestyle, legal docs, personal circumstances,
   enrollment, logistics, or demographics? → "patient"
2. Does patient_value contain real clinical data (not Unknown)? → "clinician"
3. Can you name a SPECIFIC orderable test (lab, imaging, procedure)? → "testing"
4. Does it need a doctor's evaluation or clinical judgment? → "clinician"
5. Everything else → "clinician" (safer default than testing)

## CRITERIA TO CLASSIFY
{criteria_block}

## RESPONSE FORMAT
Return a JSON array with one object per criterion (in the same order):
[
    {{
        "index": <1-based index matching the list above>,
        "review_type": "<patient|clinician|testing>",
        "suggested_test": "<SPECIFIC orderable test name if review_type is testing, else null>",
        "clinician_action": "<action note if review_type is clinician, else null>"
    }}
]

Return ONLY the JSON array, no other text.
"""

    try:
        model = GenerativeModel("gemini-2.0-flash")
        generation_config = {"response_mime_type": "application/json"}
        response = model.generate_content(
            prompt, generation_config=generation_config
        )
        response_text = response.text.strip()

        # Clean up response
        if response_text.startswith("```"):
            response_text = re.sub(r'^```(?:json)?\s*', '', response_text)
            response_text = re.sub(r'\s*```$', '', response_text)

        classifications = json.loads(response_text)

        # Apply classifications back to the original criteria
        for cls in classifications:
            idx = cls.get("index", 0) - 1  # Convert to 0-based
            if 0 <= idx < len(needs_llm):
                r = needs_llm[idx]
                review_type = cls.get("review_type", "testing")
                if review_type not in ("patient", "clinician", "testing"):
                    review_type = "testing"
                r["review_type"] = review_type

                # Set actionable fields
                if review_type == "clinician":
                    ca = cls.get("clinician_action")
                    if ca and ca not in ("null", "None", "N/A"):
                        r["clinician_action"] = ca
                    else:
                        pv = r.get("patient_value", "Unknown")
                        r["clinician_action"] = f"Patient has: {pv}. Needs clinical assessment."
                    r["suggested_test"] = None
                elif review_type == "testing":
                    st = cls.get("suggested_test")
                    if st and st not in ("null", "None", "N/A", "Clinical Assessment"):
                        r["suggested_test"] = st
                    else:
                        r["suggested_test"] = None
                    r["clinician_action"] = None
                else:  # patient
                    r["suggested_test"] = None
                    r["clinician_action"] = None

    except Exception as e:
        print(f"Stage 2 classification LLM error: {e}")
        # Fallback: simple heuristic if LLM fails
        for r in needs_llm:
            pv = (r.get("patient_value", "") or "").strip().lower()
            if not pv or pv in ("unknown", "n/a", "none", "not available", "not found"):
                r["review_type"] = "testing"
            else:
                r["review_type"] = "clinician"
            r.setdefault("suggested_test", None)
            r.setdefault("clinician_action", None)

    return criteria_results


def classify_unknown_criteria(criteria_results: List[Dict]) -> List[Dict]:
    """
    Lightweight fallback for on-the-fly classification of OLD precomputed data
    that was stored before Stage 2 existed. For new data, Stage 2 LLM runs
    at compute time via classify_unknown_criteria_with_llm().

    Logic: consent → patient, administrative/personal → patient,
           has data → clinician, no data + medical measurement → testing.
    """
    # Administrative/personal criteria the PATIENT can resolve (no test needed)
    PATIENT_PATTERNS = [
        # Legal / administrative
        "dpa", "power of attorney", "legal representative", "legally authorized",
        "social security", "insurance", "health coverage", "health plan",
        "guardian", "guardianship", "court protection",
        # Consent-adjacent
        "willing", "willingness", "agree to", "consent", "assent",
        "able to comply", "comply with", "adhere to",
        "able to understand", "understand and sign", "read and understand",
        # Personal / lifestyle
        "contraception", "contraceptive", "birth control",
        "substance use", "alcohol", "smoking", "tobacco", "drug use",
        "breastfeeding", "nursing", "pregnant", "pregnancy",
        "sexually active", "sexual abstinence",
        # Enrollment / logistics
        "other study", "another trial", "another study", "concurrent study",
        "enrolled in", "participating in",
        "travel", "reside", "live within", "located within",
        "available for follow", "attend visit",
        # Language / communication
        "speak english", "read english", "fluent", "language",
        # Identity / demographics
        "affiliated with", "affiliation", "nationality", "citizen",
    ]

    for r in criteria_results:
        is_consent = r.get("consent_needed", False)
        is_unknown = r.get("met") is None
        if not is_unknown and not is_consent:
            continue
        if is_consent:
            r["review_type"] = "patient"
            continue

        text = (r.get("criterion_text", "") or "").lower()

        pv = (r.get("patient_value", "") or "").strip().lower()
        has_data = pv and pv not in ("unknown", "n/a", "none", "not available",
                                     "not found", "not documented", "not provided",
                                     "not recorded", "error analyzing")

        # Patient keywords always win (even if previously classified as clinician/testing)
        # Only match on criterion_text — original_criterion_text can bleed across criteria
        if any(pat in text for pat in PATIENT_PATTERNS):
            r["review_type"] = "patient"
        elif r.get("review_type"):
            continue  # Already classified by Stage 2 — don't override
        elif has_data:
            r["review_type"] = "clinician"
        else:
            r["review_type"] = "testing"
    return criteria_results


def add_suggested_tests(criteria_results: List[Dict]) -> List[Dict]:
    """Normalize suggested_test and clinician_action values from old data.
    Also reclassifies testing items that have no valid suggested_test —
    if we can't name a specific test, it's not really a testing item."""
    BAD_VALUES = ("null", "None", "N/A", "Clinical Assessment", "Testing Needed",
                  "clinical assessment", "testing needed", "General Assessment")
    for r in criteria_results:
        # Clean suggested_test on all items (old data had it on clinician items too)
        st = r.get("suggested_test")
        if not st or st in BAD_VALUES:
            r["suggested_test"] = None
        # Clean clinician_action
        ca = r.get("clinician_action")
        if not ca or ca in BAD_VALUES:
            r["clinician_action"] = None

        # Reclassify: if testing but no valid suggested_test → not a real testing item
        # Logic: if we can't name a specific orderable test, it belongs in clinician
        if r.get("review_type") == "testing" and r.get("suggested_test") is None:
            r["review_type"] = "clinician"
    return criteria_results


def calculate_eligibility_score(criteria_results: List[Dict]) -> Dict:
    """
    Calculate overall eligibility score based on criteria matching results.
    Consent-needed criteria (met=True, consent_needed=True) count as fully met.

    Args:
        criteria_results: List of all criterion match results

    Returns:
        Dictionary with eligibility status and percentage
    """
    inclusion_results = [r for r in criteria_results if r.get("criterion_type") == "inclusion"]
    exclusion_results = [r for r in criteria_results if r.get("criterion_type") == "exclusion"]

    # Count inclusion criteria (consent_needed items already have met=True)
    inclusion_met = sum(1 for r in inclusion_results if r.get("met") is True)
    inclusion_not_met = sum(1 for r in inclusion_results if r.get("met") is False)
    inclusion_unknown = sum(1 for r in inclusion_results if r.get("met") is None)
    inclusion_consent = sum(1 for r in inclusion_results if r.get("consent_needed") is True)
    inclusion_total = len(inclusion_results)

    # Count exclusion criteria (for exclusion, met=False is GOOD, met=True is BAD)
    # Consent-needed exclusion criteria are marked met=True meaning "clear" (not violated)
    exclusion_clear = sum(1 for r in exclusion_results if r.get("met") is False)
    exclusion_consent = sum(1 for r in exclusion_results if r.get("consent_needed") is True)
    # Consent items in exclusion count as clear (patient can agree to avoid them)
    exclusion_clear += exclusion_consent
    exclusion_violated = sum(1 for r in exclusion_results if r.get("met") is True and not r.get("consent_needed"))
    exclusion_unknown = sum(1 for r in exclusion_results if r.get("met") is None)
    exclusion_total = len(exclusion_results)

    total_consent = inclusion_consent + exclusion_consent

    # Determine eligibility status FIRST (before calculating percentage)
    if exclusion_violated > 0:
        status = "NOT_ELIGIBLE"
        status_reason = f"Patient fails {exclusion_violated} exclusion criteria - INELIGIBLE"
        percentage = 0
    elif inclusion_not_met > 0:
        status = "NOT_ELIGIBLE"
        status_reason = f"Patient does not meet {inclusion_not_met} required inclusion criteria"
        percentage = 0
    elif inclusion_unknown > 0 or exclusion_unknown > 0:
        status = "POTENTIALLY_ELIGIBLE"
        consent_note = f" ({total_consent} consent-only)" if total_consent > 0 else ""
        status_reason = f"Review needed: {inclusion_unknown + exclusion_unknown} criteria could not be verified{consent_note}"
        # Calculate percentage: consent criteria count as fully met, unknowns get 50% credit
        total_criteria = inclusion_total + exclusion_total
        criteria_met = inclusion_met + exclusion_clear
        criteria_partial = (inclusion_unknown + exclusion_unknown) * 0.5
        if total_criteria > 0:
            percentage = round(((criteria_met + criteria_partial) / total_criteria * 100), 1)
        else:
            percentage = 0
    else:
        status = "LIKELY_ELIGIBLE"
        consent_note = f" ({total_consent} pending patient consent)" if total_consent > 0 else ""
        status_reason = f"Patient appears to meet all eligibility criteria{consent_note}"
        percentage = 100

    return {
        "status": status,
        "status_reason": status_reason,
        "percentage": percentage,
        "inclusion": {
            "met": inclusion_met,
            "not_met": inclusion_not_met,
            "unknown": inclusion_unknown,
            "consent_needed": inclusion_consent,
            "total": inclusion_total
        },
        "exclusion": {
            "clear": exclusion_clear,
            "violated": exclusion_violated,
            "unknown": exclusion_unknown,
            "consent_needed": exclusion_consent,
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

        # Mark consent/administrative criteria as met (not clinical data gaps)
        all_criteria = mark_consent_criteria(all_criteria)

        # Stage 2: LLM classifies remaining unknowns into patient/clinician/testing
        all_criteria = classify_unknown_criteria_with_llm(all_criteria)

        # Calculate eligibility
        eligibility = calculate_eligibility_score(all_criteria)
        
        brief = trial.get("brief_summary", "") or ""
        return {
            "nct_id": trial.get("nct_id", ""),
            "title": trial.get("title", ""),
            "phase": trial.get("phase", ""),
            "status": trial.get("status", ""),
            "study_type": trial.get("study_type", ""),
            "brief_summary": brief[:300] + "..." if len(brief) > 300 else brief,
            "eligibility": eligibility,
            "criteria_results": {
                "inclusion": inclusion_results,
                "exclusion": exclusion_results
            },
            "contact": trial.get("contact", {}),
            "locations": trial.get("locations", [])
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

    # Extract stage from nested diagnosis structure
    # Priority: current_staging > initial_staging > flat ajcc_stage
    current_stage = ""
    if diagnosis:
        current_staging = diagnosis.get("current_staging", {})
        initial_staging = diagnosis.get("initial_staging", {})

        if current_staging and current_staging.get("ajcc_stage"):
            current_stage = current_staging.get("ajcc_stage", "")
        elif initial_staging and initial_staging.get("ajcc_stage"):
            current_stage = initial_staging.get("ajcc_stage", "")
        elif diagnosis.get("ajcc_stage"):
            # Backwards compatibility for flat structure
            current_stage = diagnosis.get("ajcc_stage", "")

    current_stage = current_stage.upper()
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
