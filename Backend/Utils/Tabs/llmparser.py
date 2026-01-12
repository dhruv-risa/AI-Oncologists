import requests
import json


def llmresponsedetailed(
    pdf_url,
    extraction_instructions,
    description,
    config=None
):
    url = "https://apis-dev.risalabs.ai/ai-service/commons/pdf-extraction/extract"

    # ✅ Default config (used if not provided)
    default_config = {
        "model": "claude-sonnet-4-0",
        "batch_size": 1,
        "enable_batch_processing": False
    }

    # ✅ Merge user config over defaults (user wins)
    final_config = default_config.copy()
    if config:
        final_config.update(config)

    payload = {
        "pdf_url": pdf_url,
        "extraction_instructions": extraction_instructions,
        "metadata": {
            "description": description
        },
        "config": final_config,
        "response_type": "json"
    }

    headers = {
        "Content-Type": "application/json",
        "Authorization": "Bearer {{bearerToken}}"
    }

    response = requests.post(url, headers=headers, json=payload)

    try:
        response_data = response.json()
        extracted_data = response_data.get("extracted_data", response_data)

        # If backend returns JSON as string
        if isinstance(extracted_data, str):
            extracted_data = json.loads(extracted_data)

        return extracted_data

    except json.JSONDecodeError:
        raise Exception(f"Failed to parse response: {response.text}")
