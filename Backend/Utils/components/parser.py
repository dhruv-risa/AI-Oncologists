import requests
import json

def llmresponse(pdfurl, extraction_instructions):

  url = "https://api.risalabs.ai/medical-necessity/v1/pdf-extraction/send-prompt"

  payload = json.dumps({
    "pdf_url": pdfurl,
    "extraction_instructions": extraction_instructions
  })
  headers = {
    'Content-Type': 'application/json',
    'Authorization': 'Bearer {{bearerToken}}'
  }

  response = requests.request("POST", url, headers=headers, data=payload)

  return response
