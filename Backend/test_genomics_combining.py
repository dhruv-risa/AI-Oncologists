"""
Test script for genomics combining logic.

This script tests the logic for combining multiple genomics PDFs
and extracting information from them.
"""

import json
import sys
import os

# Add Backend directory and parent directory to Python path
BACKEND_DIR = os.path.abspath(os.path.dirname(__file__))
PARENT_DIR = os.path.abspath(os.path.join(BACKEND_DIR, ".."))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)
if PARENT_DIR not in sys.path:
    sys.path.insert(0, PARENT_DIR)

from Backend.Utils.Tabs.genomics_tab import extract_genomic_info_with_gemini
from Backend.Utils.pdf_url_handler import get_pdf_bytes_from_url
from Backend.bytes_extractor import combine_pdf_bytes_and_upload
from Backend.Utils.logger_config import setup_logger

# Setup logger
logger = setup_logger(__name__)


def test_genomics_combining(genomics_urls, patient_id="test_patient"):
    """
    Test the genomics combining logic for multiple PDFs.

    Args:
        genomics_urls (list): List of Google Drive URLs for genomics reports
        patient_id (str): Patient identifier for output file naming

    Returns:
        dict: Extracted genomic information
    """
    logger.info("="*80)
    logger.info(f"🧬 TESTING GENOMICS COMBINING LOGIC")
    logger.info(f"   Patient ID: {patient_id}")
    logger.info(f"   Number of genomics URLs: {len(genomics_urls)}")
    logger.info("="*80)

    if not genomics_urls:
        logger.warning("⚠️  No genomics URLs provided")
        return None

    # Display URLs
    logger.info("\n📋 Genomics URLs to process:")
    for idx, url in enumerate(genomics_urls, 1):
        logger.info(f"   {idx}. {url}")

    try:
        # Step 1: Download PDFs
        logger.info("\n" + "="*80)
        logger.info("STEP 1: Downloading PDFs")
        logger.info("="*80)

        pdf_bytes_list = []
        for idx, url in enumerate(genomics_urls, 1):
            try:
                logger.info(f"\n📥 [{idx}/{len(genomics_urls)}] Downloading from URL:")
                logger.info(f"   {url[:80]}...")

                pdf_bytes = get_pdf_bytes_from_url(url)
                pdf_bytes_list.append(pdf_bytes)

                logger.info(f"   ✅ Downloaded successfully ({len(pdf_bytes):,} bytes)")

            except Exception as e:
                logger.error(f"   ❌ Failed to download: {str(e)}")
                continue

        if not pdf_bytes_list:
            raise ValueError("Failed to download any genomics reports")

        logger.info(f"\n✅ Successfully downloaded {len(pdf_bytes_list)}/{len(genomics_urls)} PDFs")
        total_bytes = sum(len(pdf) for pdf in pdf_bytes_list)
        logger.info(f"   Total size: {total_bytes:,} bytes")

        # Step 2: Combine PDFs
        logger.info("\n" + "="*80)
        logger.info("STEP 2: Combining PDFs")
        logger.info("="*80)

        logger.info(f"\n🔄 Combining {len(pdf_bytes_list)} PDFs into single document...")

        combine_result = combine_pdf_bytes_and_upload(
            pdf_bytes_list=pdf_bytes_list,
            output_file_name=f"{patient_id}_genomics_combined.pdf",
            folder_id=None
        )

        combined_bytes = combine_result['combined_pdf_bytes']
        logger.info(f"   ✅ PDFs combined successfully!")
        logger.info(f"   Combined size: {len(combined_bytes):,} bytes")
        logger.info(f"   Uploaded to Drive: {combine_result['shareable_url']}")

        # Step 3: Extract genomic information
        logger.info("\n" + "="*80)
        logger.info("STEP 3: Extracting Genomic Information")
        logger.info("="*80)

        logger.info(f"\n🤖 Extracting genomic information using Gemini API...")

        extraction = extract_genomic_info_with_gemini(pdf_input=combined_bytes)

        logger.info(f"   ✅ Extraction complete!")

        # Step 4: Transform to frontend format
        logger.info("\n" + "="*80)
        logger.info("STEP 4: Transforming to Frontend Format")
        logger.info("="*80)

        if extraction and 'driver_mutations' in extraction:
            # Convert driver_mutations dict to list
            detected_driver_mutations = []

            for gene, data in extraction['driver_mutations'].items():
                status = data.get('status', 'Not detected')
                # Only include detected mutations
                if status and status not in ["Not detected", "NA", None]:
                    detected_driver_mutations.append({
                        'gene': gene,
                        'status': status,
                        'details': data.get('details'),
                        'is_target': data.get('is_target', False)
                    })

            genomic_info = {
                'detected_driver_mutations': detected_driver_mutations,
                'immunotherapy_markers': extraction.get('immunotherapy_markers', {}),
                'additional_genomic_alterations': extraction.get('additional_genomic_alterations', [])
            }

            # Display results
            logger.info("\n" + "="*80)
            logger.info("RESULTS")
            logger.info("="*80)

            logger.info(f"\n✅ Genomics extraction complete!")
            logger.info(f"   - Detected driver mutations: {len(detected_driver_mutations)}")
            logger.info(f"   - Additional alterations: {len(genomic_info['additional_genomic_alterations'])}")
            logger.info(f"   - Immunotherapy markers present: {bool(genomic_info['immunotherapy_markers'])}")

            # Display detailed results
            if detected_driver_mutations:
                logger.info(f"\n📊 Detected Driver Mutations:")
                for mutation in detected_driver_mutations:
                    target_flag = " [TARGET]" if mutation.get('is_target') else ""
                    logger.info(f"   • {mutation['gene']}: {mutation['status']}{target_flag}")
                    if mutation.get('details'):
                        logger.info(f"     Details: {mutation['details']}")

            if genomic_info['additional_genomic_alterations']:
                logger.info(f"\n🧬 Additional Genomic Alterations:")
                for alt in genomic_info['additional_genomic_alterations'][:5]:  # Show first 5
                    logger.info(f"   • {alt['gene']}: {alt.get('alteration')} ({alt.get('type')})")
                if len(genomic_info['additional_genomic_alterations']) > 5:
                    logger.info(f"   ... and {len(genomic_info['additional_genomic_alterations']) - 5} more")

            if genomic_info['immunotherapy_markers']:
                logger.info(f"\n💉 Immunotherapy Markers:")
                markers = genomic_info['immunotherapy_markers']
                if 'pd_l1' in markers:
                    pd_l1 = markers['pd_l1']
                    logger.info(f"   • PD-L1: {pd_l1.get('value')} ({pd_l1.get('metric')})")
                if 'tmb' in markers:
                    tmb = markers['tmb']
                    logger.info(f"   • TMB: {tmb.get('value')} - {tmb.get('interpretation')}")
                if 'msi_status' in markers:
                    msi = markers['msi_status']
                    logger.info(f"   • MSI: {msi.get('status')} - {msi.get('interpretation')}")

            # Save to JSON file
            output_file = f"{patient_id}_genomics_result.json"
            with open(output_file, 'w') as f:
                json.dump(genomic_info, f, indent=2)
            logger.info(f"\n💾 Full results saved to: {output_file}")

            logger.info("\n" + "="*80)
            logger.info("TEST COMPLETED SUCCESSFULLY ✅")
            logger.info("="*80 + "\n")

            return genomic_info

        else:
            logger.warning("⚠️  No genomics data extracted")
            return None

    except Exception as e:
        logger.error(f"\n❌ ERROR during genomics combining test:")
        logger.error(f"   {str(e)}")
        import traceback
        logger.error("\n" + traceback.format_exc())
        return None


if __name__ == "__main__":
    # Load demo data
    demo_data_path = os.path.join(BACKEND_DIR, "demo_data.json")

    with open(demo_data_path, 'r') as f:
        demo_data = json.load(f)

    # Test with patient 4028657 (has 3 genomics URLs)
    patient_id = "4028657"

    if patient_id not in demo_data:
        logger.error(f"Patient {patient_id} not found in demo_data.json")
        sys.exit(1)

    genomics_urls = demo_data[patient_id].get('genomics', [])

    if not genomics_urls:
        logger.error(f"No genomics URLs found for patient {patient_id}")
        sys.exit(1)

    logger.info(f"\n🔬 Testing genomics combining logic for patient {patient_id}")
    logger.info(f"Found {len(genomics_urls)} genomics URLs\n")

    # Run the test
    result = test_genomics_combining(genomics_urls, patient_id)

    if result:
        print("\n" + "="*80)
        print("✅ Test completed successfully!")
        print(f"Results saved to {patient_id}_genomics_result.json")
        print("="*80)
    else:
        print("\n" + "="*80)
        print("❌ Test failed - check logs above for details")
        print("="*80)
        sys.exit(1)
