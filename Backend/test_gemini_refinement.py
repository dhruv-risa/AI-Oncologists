"""
Standalone test script to verify Gemini API clinical interpretation refinement.

This script replicates the exact API call pattern from lab_postprocessor.py
to help diagnose why the API returns empty responses.

Uses REAL patient data from MRN 4125731.
"""

import vertexai
from vertexai.generative_models import GenerativeModel
import json
import time
import os

# Initialize Vertex AI (same config as lab_postprocessor.py)
print("="*70)
print("GEMINI API CLINICAL REFINEMENT TEST - PATIENT 4125731")
print("="*70)

print("\n🔧 Step 1: Load patient data...")
results_file = 'patient_4125731_lab_results_20260210_162354.json'

if not os.path.exists(results_file):
    print(f"❌ Error: Patient data file not found: {results_file}")
    print("Please run extract_patient_labs.py 4125731 first")
    exit(1)

with open(results_file, 'r') as f:
    patient_data = json.load(f)

print(f"✅ Loaded patient data: MRN {patient_data['patient_mrn']}")
print(f"   - Reports processed: {patient_data['reports_processed']}")
print(f"   - Unique markers: {len(patient_data['markers_timeline'])}")

# Extract raw clinical interpretations (filter out boilerplate)
raw_interpretations = []

for idx, raw_extraction in enumerate(patient_data['all_raw_extractions'], 1):
    extraction_data = raw_extraction['extraction_data']

    if 'clinical_interpretation' in extraction_data:
        clinical_interp = extraction_data['clinical_interpretation']

        if isinstance(clinical_interp, list):
            for item in clinical_interp:
                item_str = str(item).strip()
                # Filter out boilerplate lines
                if (item_str and
                    not item_str.startswith('Rules applied') and
                    not item_str.startswith('- Anemia:') and
                    not item_str.startswith('- Hepatic') and
                    not item_str.startswith('- Neutropenia') and
                    not item_str.startswith('- Include') and
                    item_str != '-'):
                    raw_interpretations.append(item_str)

print(f"   - Raw interpretations extracted: {len(raw_interpretations)}")

# Build lab summary from patient data
lab_summary = {}

for marker_name, marker_data in patient_data['markers_timeline'].items():
    if marker_data['measurements']:
        latest = marker_data['measurements'][-1]
        category = marker_data['category']

        if category not in lab_summary:
            lab_summary[category] = {}

        lab_summary[category][marker_name] = {
            "current_value": latest['value'],
            "current_unit": latest['unit'],
            "current_status": latest['status'],
            "has_data": True
        }

print(f"   - Lab categories in summary: {list(lab_summary.keys())}")

print("\n🔧 Step 2: Initialize Vertex AI...")
try:
    vertexai.init(project="prior-auth-portal-dev", location="us-central1")
    print("✅ Vertex AI initialized successfully")
except Exception as e:
    print(f"❌ Failed to initialize Vertex AI: {e}")
    exit(1)

# Build the exact prompt used in postprocessor
prompt = f"""You are a clinical oncology expert reviewing laboratory results for a cancer patient.

I have extracted raw clinical interpretations from multiple lab reports. Your task is to refine these into a concise, well-organized clinical summary.

RAW INTERPRETATIONS:
{chr(10).join(f"- {interp}" for interp in raw_interpretations)}

CURRENT LAB VALUES SUMMARY:
{json.dumps(lab_summary, indent=2)}

INSTRUCTIONS:
1. Synthesize the raw interpretations into a coherent clinical summary
2. Organize by clinical significance (most important findings first)
3. Remove redundancies and contradictions
4. Use precise medical terminology
5. Focus on actionable findings relevant to cancer treatment
6. Include trend information where relevant
7. Keep each point concise (1-2 sentences maximum)
8. Return MAXIMUM 5 most important clinical points (prioritize critical findings)

PRIORITIZATION RULES:
- Critical abnormalities (e.g., severe anemia, neutropenia requiring intervention) = Highest priority
- Treatment-limiting toxicities (e.g., hepatotoxicity, renal dysfunction) = High priority
- Tumor markers and disease monitoring = Medium-high priority
- Stable or normal findings with clinical context = Include only if space permits

OUTPUT FORMAT:
Return a JSON array of maximum 5 strings, each string being one refined clinical interpretation.
Example:
["Mild anemia (Hgb 10.2 g/dL) with stable trend over 3 measurements, consider transfusion if symptomatic", "Hepatic transaminases mildly elevated (ALT 58 U/L, AST 52 U/L) consistent with drug-induced liver injury, recommend monitoring", "Preserved bone marrow function (WBC 6.8 K/uL, ANC 3.8 K/uL, Platelets 185 K/uL) - safe to continue chemotherapy", "Renal function normal (Creatinine 0.9 mg/dL) - no dose adjustments required"]

Return ONLY the JSON array, no other text."""

print(f"\n📝 Step 3: Prepare prompt...")
print(f"   - Prompt length: {len(prompt)} characters")
print(f"   - Raw interpretations: {len(raw_interpretations)}")
print(f"   - Lab summary keys: {list(lab_summary.keys())}")
print(f"\n📋 Raw interpretations being sent to API:")
for i, interp in enumerate(raw_interpretations[:5], 1):  # Show first 5
    print(f"   {i}. {interp}")
if len(raw_interpretations) > 5:
    print(f"   ... and {len(raw_interpretations) - 5} more")

# Test 1: WITHOUT response_mime_type (original approach)
print(f"\n🧪 Test 1: API call WITHOUT response_mime_type")
print("="*70)

try:
    model = GenerativeModel("gemini-2.5-pro")
    print("✅ Model loaded: gemini-2.5-pro")

    print("⏳ Calling Gemini API...")
    response = model.generate_content(
        prompt,
        generation_config={
            "temperature": 0.3,
            "top_p": 0.95,
            "max_output_tokens": 4096
        }
    )

    print(f"✅ API call completed")
    print(f"📝 Response type: {type(response)}")
    print(f"📝 Has 'text' attribute: {hasattr(response, 'text')}")

    # Check prompt feedback
    if hasattr(response, 'prompt_feedback'):
        print(f"📝 Prompt feedback: {response.prompt_feedback}")

    # Check candidates
    if hasattr(response, 'candidates'):
        print(f"📝 Candidates count: {len(response.candidates)}")
        for i, candidate in enumerate(response.candidates):
            if hasattr(candidate, 'finish_reason'):
                print(f"   - Candidate {i} finish_reason: {candidate.finish_reason}")
            if hasattr(candidate, 'safety_ratings'):
                print(f"   - Candidate {i} safety_ratings: {candidate.safety_ratings}")

    if hasattr(response, 'text') and response.text:
        response_text = response.text.strip()
        print(f"📝 Response text length: {len(response_text)}")
        print(f"📝 Response text (first 500 chars):\n{response_text[:500]}")

        # Try to parse JSON
        try:
            # Extract from markdown if needed
            import re
            json_pattern = r'```(?:json)?\s*([\s\S]*?)\s*```'
            match = re.search(json_pattern, response_text)
            if match:
                response_text = match.group(1).strip()
                print(f"📝 Extracted from markdown, new length: {len(response_text)}")

            parsed = json.loads(response_text)
            print(f"✅ TEST 1 PASSED: Valid JSON with {len(parsed)} items")
            print(f"📝 Parsed content: {json.dumps(parsed, indent=2)}")
        except json.JSONDecodeError as e:
            print(f"❌ TEST 1 FAILED: Invalid JSON - {e}")
            print(f"📝 Full response text:\n{response_text}")
    else:
        print(f"❌ TEST 1 FAILED: No response.text")
        if hasattr(response, 'text'):
            print(f"📝 response.text repr: {repr(response.text)}")

except Exception as e:
    print(f"❌ TEST 1 FAILED with exception: {e}")
    import traceback
    traceback.print_exc()

# Wait between tests
print("\n⏳ Waiting 3 seconds before Test 2...")
time.sleep(3)

# Test 2: WITH response_mime_type (new approach)
print(f"\n🧪 Test 2: API call WITH response_mime_type='application/json'")
print("="*70)

try:
    model = GenerativeModel("gemini-2.5-pro")

    print("⏳ Calling Gemini API with JSON mode...")
    response = model.generate_content(
        prompt,
        generation_config={
            "temperature": 0.3,
            "top_p": 0.95,
            "max_output_tokens": 4096,
            "response_mime_type": "application/json"
        }
    )

    print(f"✅ API call completed")
    print(f"📝 Response type: {type(response)}")
    print(f"📝 Has 'text' attribute: {hasattr(response, 'text')}")

    # Check prompt feedback
    if hasattr(response, 'prompt_feedback'):
        print(f"📝 Prompt feedback: {response.prompt_feedback}")

    # Check candidates
    if hasattr(response, 'candidates'):
        print(f"📝 Candidates count: {len(response.candidates)}")
        for i, candidate in enumerate(response.candidates):
            if hasattr(candidate, 'finish_reason'):
                print(f"   - Candidate {i} finish_reason: {candidate.finish_reason}")
            if hasattr(candidate, 'safety_ratings'):
                print(f"   - Candidate {i} safety_ratings: {candidate.safety_ratings}")

    if hasattr(response, 'text') and response.text:
        response_text = response.text.strip()
        print(f"📝 Response text length: {len(response_text)}")
        print(f"📝 Response text (first 500 chars):\n{response_text[:500]}")

        # Try to parse JSON
        try:
            parsed = json.loads(response_text)
            print(f"✅ TEST 2 PASSED: Valid JSON with {len(parsed)} items")
            print(f"📝 Parsed content: {json.dumps(parsed, indent=2)}")
        except json.JSONDecodeError as e:
            print(f"❌ TEST 2 FAILED: Invalid JSON - {e}")
            print(f"📝 Full response text:\n{response_text}")
    else:
        print(f"❌ TEST 2 FAILED: No response.text")
        if hasattr(response, 'text'):
            print(f"📝 response.text repr: {repr(response.text)}")
            print(f"📝 response.text is None: {response.text is None}")
            print(f"📝 response.text == '': {response.text == ''}")

except Exception as e:
    print(f"❌ TEST 2 FAILED with exception: {e}")
    import traceback
    traceback.print_exc()

# Test 3: Simpler prompt to verify API works
print("\n⏳ Waiting 3 seconds before Test 3...")
time.sleep(3)

print(f"\n🧪 Test 3: Simple JSON test (verify API works at all)")
print("="*70)

simple_prompt = """Return a JSON array with exactly 3 clinical interpretation strings.

Example format:
["Finding 1 about labs", "Finding 2 about patient", "Finding 3 about treatment"]

Return ONLY the JSON array, no other text."""

try:
    model = GenerativeModel("gemini-2.5-pro")

    print("⏳ Calling Gemini API with simple prompt...")
    response = model.generate_content(
        simple_prompt,
        generation_config={
            "temperature": 0.3,
            "max_output_tokens": 200,
            "response_mime_type": "application/json"
        }
    )

    print(f"✅ API call completed")

    if hasattr(response, 'text') and response.text:
        response_text = response.text.strip()
        print(f"📝 Response text: {response_text}")

        try:
            parsed = json.loads(response_text)
            print(f"✅ TEST 3 PASSED: Valid JSON with {len(parsed)} items")
            print(f"📝 Content: {parsed}")
        except json.JSONDecodeError as e:
            print(f"❌ TEST 3 FAILED: Invalid JSON - {e}")
    else:
        print(f"❌ TEST 3 FAILED: No response.text")

except Exception as e:
    print(f"❌ TEST 3 FAILED: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "="*70)
print("SUMMARY")
print("="*70)
print("""
If all tests failed:
  → Check Vertex AI quotas: https://console.cloud.google.com/iam-admin/quotas
  → Verify gemini-2.5-pro is available in us-central1
  → Check authentication: gcloud auth application-default login

If Test 1 & 2 failed but Test 3 passed:
  → Prompt is too complex or contains content triggering safety filters
  → Try reducing the number of interpretations or simplifying the prompt

If Test 1 failed but Test 2 passed:
  → Use response_mime_type='application/json' (already added to your code)

If Test 2 failed with empty response.text:
  → Response is being generated but blocked/filtered before reaching you
  → Check safety_ratings and finish_reason in the output above
""")

print("\n✅ Test complete!")
