import { FileText, ExternalLink, Download, Eye } from 'lucide-react';
import { SectionCard } from './SectionCard';
import { useState, useMemo } from 'react';
import { PatientData } from '../services/api';
import { formatDate } from '../utils/dateFormatter';

interface DocumentsSectionProps {
  patientData?: PatientData | null;
}

export function DocumentsSection({ patientData }: DocumentsSectionProps) {
  const [selectedCategory, setSelectedCategory] = useState('Pathology Reports');

  // Build documents from actual patient data
  const documents = useMemo(() => {
    const categories = [];

    // Pathology Reports
    if (patientData?.pathology_reports && patientData.pathology_reports.length > 0) {
      categories.push({
        category: 'Pathology Reports',
        items: patientData.pathology_reports.map((report) => ({
          name: report.description || report.document_type || 'Pathology Report',
          date: formatDate(report.date),
          code: report.document_id || 'N/A',
          url: report.drive_url,
          file_id: report.drive_file_id,
        })),
      });
    }

    // Genomic Reports
    if (patientData?.genomics_reports && patientData.genomics_reports.length > 0) {
      categories.push({
        category: 'Genomic Reports',
        items: patientData.genomics_reports.map((report, idx) => ({
          name: report.type || 'Genomic Report',
          date: formatDate(report.date),
          code: `GEN-${idx + 1}`,
          url: report.url,
          file_id: report.file_id,
        })),
      });
    }

    // Radiology Reports
    if (patientData?.radiology_reports && patientData.radiology_reports.length > 0) {
      categories.push({
        category: 'Radiology Reports',
        items: patientData.radiology_reports.map((report) => ({
          name: report.description || report.document_type || 'Radiology Report',
          date: formatDate(report.date),
          code: report.document_id || 'N/A',
          url: report.drive_url,
          file_id: report.drive_file_id,
        })),
      });
    }

    return categories;
  }, [patientData]);

  const selectedDocuments = documents.find(doc => doc.category === selectedCategory);

  // If no documents, show a message
  if (!documents || documents.length === 0) {
    return (
      <SectionCard title="Source Documents" icon={FileText}>
        <div className="text-center py-12 text-gray-500">
          <FileText className="w-12 h-12 mx-auto mb-3 text-gray-300" />
          <p>No documents available</p>
        </div>
      </SectionCard>
    );
  }

  return (
    <SectionCard title="Source Documents" icon={FileText}>
      <div className="space-y-4">
        {/* Horizontal Navigation Tabs */}
        <div className="border-b border-gray-200">
          <div className="flex gap-1">
            {documents.map((category, idx) => (
              <button
                key={idx}
                onClick={() => setSelectedCategory(category.category)}
                className={`px-4 py-3 text-sm transition-all relative ${
                  selectedCategory === category.category
                    ? 'text-blue-600'
                    : 'text-gray-600 hover:text-gray-900 hover:bg-gray-50'
                }`}
              >
                {category.category}
                <span className={`ml-2 px-2 py-0.5 rounded-full text-xs ${
                  selectedCategory === category.category
                    ? 'bg-blue-100 text-blue-700'
                    : 'bg-gray-100 text-gray-600'
                }`}>
                  {category.items.length}
                </span>
                {selectedCategory === category.category && (
                  <div className="absolute bottom-0 left-0 right-0 h-0.5 bg-blue-600"></div>
                )}
              </button>
            ))}
          </div>
        </div>

        {/* Document List */}
        <div className="space-y-2">
          {selectedDocuments?.items.map((doc, docIdx) => (
            <div
              key={docIdx}
              className="flex items-center justify-between p-4 bg-white border border-gray-200 rounded-lg hover:border-blue-300 hover:shadow-sm transition-all group"
            >
              <div className="flex items-center gap-3 flex-1">
                <div className="w-10 h-10 bg-gray-50 rounded-lg flex items-center justify-center group-hover:bg-blue-50 transition-colors">
                  <FileText className="w-5 h-5 text-gray-500 group-hover:text-blue-600" />
                </div>
                <div className="flex-1">
                  <p className="text-sm text-gray-900">{doc.name}</p>
                  <div className="flex items-center gap-2 mt-1">
                    <span className="px-2 py-0.5 bg-gray-100 text-gray-700 rounded text-xs">
                      {doc.code}
                    </span>
                    <span className="text-gray-300">•</span>
                    <p className="text-xs text-gray-500">{doc.date}</p>
                  </div>
                </div>
              </div>
              <div className="flex items-center gap-1">
                <button
                  onClick={() => doc.url && window.open(doc.url, '_blank')}
                  className="p-2 text-gray-400 hover:text-blue-600 hover:bg-blue-50 rounded-lg transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                  title="View document"
                  disabled={!doc.url}
                >
                  <Eye className="w-4 h-4" />
                </button>
                <button
                  onClick={() => doc.url && window.open(doc.url, '_blank')}
                  className="p-2 text-gray-400 hover:text-blue-600 hover:bg-blue-50 rounded-lg transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                  title="Download document"
                  disabled={!doc.url}
                >
                  <Download className="w-4 h-4" />
                </button>
                <button
                  onClick={() => doc.url && window.open(doc.url, '_blank')}
                  className="p-2 text-gray-400 hover:text-blue-600 hover:bg-blue-50 rounded-lg transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                  title="Open in new tab"
                  disabled={!doc.url}
                >
                  <ExternalLink className="w-4 h-4" />
                </button>
              </div>
            </div>
          ))}
        </div>

        {/* Summary Footer */}
        <div className="pt-3 border-t border-gray-200">
          <div className="flex items-center justify-between text-xs text-gray-600">
            <span>{selectedDocuments?.items.length || 0} documents in {selectedCategory}</span>
            <span>Total: {documents.reduce((acc, cat) => acc + cat.items.length, 0)} documents</span>
          </div>
        </div>
      </div>
    </SectionCard>
  );
}