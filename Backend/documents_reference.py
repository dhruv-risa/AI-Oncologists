"""
Data Ingestion Module for OncoEMR FHIR API

This module provides functions to authenticate and retrieve patient documents
from the OncoEMR FHIR API.

Usage:
    from dataingestion import get_document_url_by_type

    # Get most recent MD note URL
    url = get_document_url_by_type(
        mrn="A2451440",
        loinc_type="11506-3",
        description_patterns=[r'\bMD\b.*\bvisit\b']
    )
"""

import requests
import base64
from typing import Optional, List, Dict, Any # For data validation


# ============================================================================
# Authentication Functions
# ============================================================================


## Generating bearer tokens
def generate_bearer_token(
    url: str = "https://authentication.risalabs.ai/api/v1/user-auth/token",
    headers: Optional[Dict] = None
) -> str:
    """
    Generate bearer token for Risa Labs API authentication.

    Args:
        url: Authentication endpoint URL
        headers: Optional additional headers

    Returns:
        Bearer token string

    Raises:
        requests.RequestException: If authentication fails
    """
    if headers is None:
        headers = {}

    payload = "{\n    \"username\": \"risa_front_end_user\",\n    \"password\": \"e4Itc/E[df~z\"\n}"
    response = requests.post(url, headers=headers, data=payload)
    response.raise_for_status()

    data = response.json()
    return data['access_token']

## Generating the Onco_EMR_token
## The code for Marybird = 3GKbZtgpPru1vJGCkxwR
## The code for Astera = tPvNbDprUnrXIJlDXyxs
def generate_onco_emr_token(
    bearer_token: str,
    url: str = "https://apis.risalabs.ai/pa-order-creation/commons/emr/get-flatiron-token/3GKbZtgpPru1vJGCkxwR"
) -> str:
    """
    Generate OncoEMR token using bearer token.

    Args:
        bearer_token: Bearer token from Risa Labs authentication
        url: OncoEMR token endpoint URL

    Returns:
        OncoEMR access token string

    Raises:
        requests.RequestException: If token generation fails
    """
    headers = {
        'Authorization': f'Bearer {bearer_token}'
    }
    response = requests.get(url, headers=headers)
    response.raise_for_status()

    data = response.json()
    return data['access_token']


# ============================================================================
# Patient and Document Retrieval Functions
# ============================================================================

## Need to get the patient_id for calling the document reference id
def get_patient_id_from_mrn(
    mrn: str,
    onco_emr_token: str,
    url: str = "https://fhir.prod.flatiron.io/fhir/Patient"
) -> tuple[str, Dict[str, Any]]:
    """
    Get patient ID and details using MRN (Medical Record Number).

    Args:
        mrn: Patient's Medical Record Number
        onco_emr_token: OncoEMR access token
        url: FHIR Patient endpoint URL

    Returns:
        Tuple of (patient_id, patient_resource_dict)

    Raises:
        ValueError: If no patient found for given MRN
        requests.RequestException: If API request fails
    """
    params = {"identifier": mrn}
    headers = {
        "Authorization": f"Bearer {onco_emr_token}",
        "Accept": "application/fhir+json"
    }

    response = requests.get(url, headers=headers, params=params)
    response.raise_for_status()

    data = response.json()

    if "entry" not in data or len(data["entry"]) == 0:
        raise ValueError(f"No patient found for MRN: {mrn}")

    patient_resource = data["entry"][0]["resource"]
    patient_id = patient_resource["id"]

    return patient_id, patient_resource


## Need to get the document references for the patient type
## The documents are fetched basis the lonic code:- For MD notes lonic code = 11506-3
## The following function gives all the docs info as bundle
def get_document_references(
    patient_id: str,
    onco_emr_token: str,
    loinc_type: str = "",
    url: str = "https://fhir.prod.flatiron.io/fhir/DocumentReference"
) -> Dict[str, Any]:
    """
    Get document references for a patient filtered by LOINC type.

    Common LOINC types:
        - "11506-3": Progress notes (includes MD notes, nurse notes, etc.)
        - "18842-5": Discharge summary
        - "11488-4": Consultation note
        - "60568-3": Pathology report

    Args:
        patient_id: FHIR patient ID
        onco_emr_token: OncoEMR access token
        loinc_type: LOINC code for document type
        url: FHIR DocumentReference endpoint URL

    Returns:
        FHIR DocumentReference bundle (dict)

    Raises:
        requests.RequestException: If API request fails
    """
    params = {
        "patient": patient_id,
        "type": loinc_type,
        "_summary": "true"
    }
    headers = {
        "Authorization": f"Bearer {onco_emr_token}",
        "Accept": "application/fhir+json"
    }

    response = requests.get(url, headers=headers, params=params)
    response.raise_for_status()

    return response.json()




