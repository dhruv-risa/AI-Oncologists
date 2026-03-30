#!/bin/bash

# Update Cloud Run timeout for existing service
# This updates the running service without requiring a new deployment

set -e

PROJECT_ID="rapids-platform"
REGION="us-central1"
SERVICE="ai-oncologist-backend"
TIMEOUT="1800"  # 30 minutes (max for gen2 is 3600)

echo "Updating Cloud Run service timeout..."
echo "Project: $PROJECT_ID"
echo "Region: $REGION"
echo "Service: $SERVICE"
echo "New timeout: ${TIMEOUT}s ($(($TIMEOUT / 60)) minutes)"
echo ""

gcloud run services update $SERVICE \
  --region=$REGION \
  --project=$PROJECT_ID \
  --timeout=$TIMEOUT

echo ""
echo "✓ Cloud Run timeout updated successfully!"
echo ""
echo "To verify, run:"
echo "gcloud run services describe $SERVICE --region=$REGION --project=$PROJECT_ID --format='value(spec.template.spec.timeoutSeconds)'"
