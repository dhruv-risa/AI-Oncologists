from pypdf import PdfReader, PdfWriter

pdf_files = [
    "/Users/dhruvsaraswat/Desktop/AI Oncologist/Onco_EMR_Files/443449/MD_Notes/MD_notes_1.pdf",
    "/Users/dhruvsaraswat/Desktop/AI Oncologist/Onco_EMR_Files/443449/Lab Results/Lab_result_1.pdf",
    "/Users/dhruvsaraswat/Desktop/AI Oncologist/Onco_EMR_Files/443449/Lab Results/Lab_results_2.pdf",
    "/Users/dhruvsaraswat/Desktop/AI Oncologist/Onco_EMR_Files/443449/Lab Results/Lab_results_3.pdf",
    "/Users/dhruvsaraswat/Desktop/AI Oncologist/Onco_EMR_Files/443449/Lab Results/Lab_results_4.pdf",
    "/Users/dhruvsaraswat/Desktop/AI Oncologist/Onco_EMR_Files/443449/Lab Results/Lab_results_5.pdf",
    "/Users/dhruvsaraswat/Desktop/AI Oncologist/Onco_EMR_Files/443449/Lab Results/Lab_results_6.pdf",
    "/Users/dhruvsaraswat/Desktop/AI Oncologist/Onco_EMR_Files/443449/Lab Results/Lab_results_7.pdf"
]

writer = PdfWriter()

for pdf in pdf_files:
    reader = PdfReader(pdf)
    for page in reader.pages:
        writer.add_page(page)

with open("merged.pdf", "wb") as f:
    writer.write(f)
