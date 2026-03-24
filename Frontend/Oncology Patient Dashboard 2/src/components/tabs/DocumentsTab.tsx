import { FileText } from 'lucide-react';
import { PatientData, resolveDocumentUrl } from '../../services/api';
import { formatDate } from '../../utils/dateFormatter';

interface DocumentsTabProps {
  patientData?: PatientData | null;
}

export function DocumentsTab({ patientData }: DocumentsTabProps) {
  // Build documents from actual patient data
  const documents = [];

  // Pathology Reports
  if (patientData?.pathology_reports && patientData.pathology_reports.length > 0) {
    documents.push({
      category: 'Pathology Reports',
      items: patientData.pathology_reports.map((report) => ({
        name: report.description || report.document_type || 'Pathology Report',
        date: formatDate(report.date),
        id: report.document_id || 'N/A',
        url: report.drive_url,
      })),
    });
  }

  // Lab Results
  if (patientData?.lab_reports && patientData.lab_reports.length > 0) {
    documents.push({
      category: 'Lab Results',
      items: patientData.lab_reports.map((report, idx) => ({
        name: report.description || report.type || 'Lab Results',
        date: formatDate(report.date),
        id: report.document_id || `LAB-${idx + 1}`,
        url: report.url,
      })),
    });
  }

  // Genomic Reports
  if (patientData?.genomics_reports && patientData.genomics_reports.length > 0) {
    documents.push({
      category: 'Genomic Reports',
      items: patientData.genomics_reports.map((report, idx) => ({
        name: report.type || report.description || 'Genomic Report',
        date: formatDate(report.date),
        id: `GEN-${idx + 1}`,
        url: report.url,
      })),
    });
  }

  // Radiology Reports
  if (patientData?.radiology_reports && patientData.radiology_reports.length > 0) {
    documents.push({
      category: 'Radiology Reports',
      items: patientData.radiology_reports.map((report) => ({
        name: report.description || report.document_type || 'Radiology Report',
        date: formatDate(report.date),
        id: report.document_id || 'N/A',
        url: report.drive_url,
      })),
    });
  }

  // If no documents, show a message
  if (documents.length === 0) {
    return (
      <div className="bg-white rounded-b-xl rounded-tr-xl border border-t-0 border-gray-200 p-6">
        <div className="text-center py-12 text-gray-500">
          <FileText className="w-12 h-12 mx-auto mb-3 text-gray-300" />
          <p>No documents available</p>
        </div>
      </div>
    );
  }

  return (
    <div className="bg-white rounded-b-xl rounded-tr-xl border border-t-0 border-gray-200 p-6">
      <div className="flex items-center gap-2 mb-6">
        <FileText className="w-4 h-4 text-gray-400" />
        <h3 className="text-gray-900">Source Documents</h3>
      </div>

      <div className="space-y-6">
        {documents.map((category, idx) => (
          <div key={idx}>
            <h4 className="text-sm text-gray-700 mb-3">{category.category}</h4>
            <div className="space-y-2">
              {category.items.map((doc, docIdx) => (
                <div
                  key={docIdx}
                  className="w-full flex items-center justify-between p-3 bg-gray-50 border border-gray-200 rounded-lg"
                >
                  <div className="flex items-center gap-3 flex-1">
                    <div className="p-2 bg-white rounded border border-gray-300">
                      <FileText className="w-4 h-4 text-gray-600" />
                    </div>
                    <div className="flex-1">
                      <p className="text-sm text-gray-900">
                        {doc.name}
                      </p>
                      <div className="flex items-center gap-3 mt-1">
                        <p className="text-xs text-gray-500">{doc.id}</p>
                        <span className="text-gray-300">•</span>
                        <p className="text-xs text-gray-500">{doc.date}</p>
                      </div>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
