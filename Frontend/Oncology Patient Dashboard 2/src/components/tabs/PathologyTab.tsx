import { useState, useRef } from 'react';
import { FileText, ExternalLink, Eye, Download, Plus, X, Microscope, Loader2 } from 'lucide-react';
import { DataField } from '../DataField';
import { PatientData, PathologyReportDetail } from '../../services/api';

interface PathologyTabProps {
  patientData: PatientData | null;
}

export function PathologyTab({ patientData }: PathologyTabProps) {
  const [selectedReport, setSelectedReport] = useState(0);
  const [showMoreModal, setShowMoreModal] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);

  // Get pathology reports directly from patient data (already extracted during initial load)
  const reports: PathologyReportDetail[] = patientData?.pathology_reports || [];

  const visibleReports = reports.slice(0, 4);
  const hiddenReports = reports.slice(4);
  const hasMore = reports.length > 4;

  const handleSelectFromModal = (reportIndex: number) => {
    setSelectedReport(reportIndex);
    setShowMoreModal(false);
  };

  // Format date for display
  const formatDate = (dateString: string) => {
    try {
      const date = new Date(dateString);
      return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
    } catch {
      return dateString;
    }
  };

  // Get current report data
  const currentReport = reports[selectedReport];

  // Loading state - patient data not yet loaded
  if (!patientData) {
    return (
      <div className="flex items-center justify-center h-64">
        <Loader2 className="w-8 h-8 animate-spin text-blue-500" />
        <span className="ml-2 text-gray-600">Loading patient data...</span>
      </div>
    );
  }

  // No reports found
  if (!reports || reports.length === 0) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-center">
          <FileText className="w-12 h-12 text-gray-400 mx-auto mb-2" />
          <p className="text-gray-600">No pathology reports found</p>
        </div>
      </div>
    );
  }

  return (
    <div className="flex gap-4">
      {/* Vertical Reports Navigation */}
      <div className="w-56 flex-shrink-0">
        <div className="bg-white rounded-lg shadow-sm border border-gray-200 sticky top-6">
          <div className="px-4 py-3 border-b border-gray-200 bg-gray-50">
            <div className="flex items-center gap-2">
              <FileText className="w-4 h-4 text-gray-600" />
              <h4 className="text-sm text-gray-900">Reports</h4>
              <span className="text-xs text-gray-500">({reports.length})</span>
            </div>
          </div>
          <nav className="p-2 max-h-[calc(100vh-300px)] overflow-y-auto">
            {visibleReports.map((report, index) => (
              <button
                key={report.document_id}
                onClick={() => setSelectedReport(index)}
                className={`w-full p-3 mb-2 text-left transition-all rounded-lg border ${
                  selectedReport === index
                    ? 'border-blue-500 bg-blue-50'
                    : 'border-gray-200 bg-white hover:border-gray-300 hover:bg-gray-50'
                }`}
              >
                <p className={`text-sm mb-1 ${selectedReport === index ? 'text-blue-900' : 'text-gray-900'}`}>
                  {report.pathology_summary?.pathology_report?.header?.report_id || report.document_id}
                </p>
                <p className="text-xs text-gray-600 mb-1.5">{report.description || report.document_type}</p>
                <p className="text-xs text-gray-500">{formatDate(report.date)}</p>

                {/* Action buttons */}
                <div className="flex items-center gap-1 mt-2">
                  <button
                    className="p-1 text-gray-400 hover:text-blue-600 hover:bg-blue-100 rounded transition-colors"
                    title="View document"
                    onClick={(e) => {
                      e.stopPropagation();
                      window.open(report.drive_url, '_blank');
                    }}
                  >
                    <Eye className="w-3 h-3" />
                  </button>
                  <button
                    className="p-1 text-gray-400 hover:text-blue-600 hover:bg-blue-100 rounded transition-colors"
                    title="Download document"
                    onClick={(e) => {
                      e.stopPropagation();
                      window.open(report.drive_url, '_blank');
                    }}
                  >
                    <Download className="w-3 h-3" />
                  </button>
                  <button
                    className="p-1 text-gray-400 hover:text-blue-600 hover:bg-blue-100 rounded transition-colors"
                    title="Open in new tab"
                    onClick={(e) => {
                      e.stopPropagation();
                      window.open(report.drive_url, '_blank');
                    }}
                  >
                    <ExternalLink className="w-3 h-3" />
                  </button>
                </div>
              </button>
            ))}
            
            {/* More button */}
            {hasMore && (
              <button
                onClick={() => setShowMoreModal(true)}
                className="w-full flex items-center justify-center gap-2 px-3 py-2.5 text-sm text-gray-600 hover:text-gray-900 hover:bg-gray-50 border border-gray-200 rounded-lg transition-all"
              >
                <Plus className="w-4 h-4" />
                <span>More</span>
              </button>
            )}
          </nav>
        </div>
      </div>

      {/* Main Content */}
      <div className="flex-1 bg-white rounded-lg border border-gray-200 p-6">
        {!currentReport?.pathology_summary?.pathology_report || !currentReport?.pathology_markers ? (
          <div className="text-center py-12">
            <p className="text-red-600 mb-2">Failed to extract pathology details</p>
            <p className="text-gray-500 text-sm">
              {currentReport?.extraction_error || 'Pathology data not available'}
            </p>
          </div>
        ) : (
          /* Report details */
          <div>
            <div className="flex items-center justify-between mb-4">
              <div className="flex items-center gap-2">
                <FileText className="w-4 h-4 text-gray-400" />
                <h3 className="text-gray-900">Selected report</h3>
                <span className="text-xs text-gray-500">
                  {currentReport.pathology_summary.pathology_report.header?.report_id}
                </span>
              </div>
              <button
                className="flex items-center gap-2 px-4 py-2 bg-white hover:bg-gray-50 text-gray-700 border border-gray-300 rounded-lg text-sm transition-colors"
                onClick={() => window.open(currentReport.drive_url, '_blank')}
              >
                <ExternalLink className="w-4 h-4" />
                View Source
              </button>
            </div>

            <div className="space-y-4">
              {/* Alert banner */}
              {currentReport.pathology_summary.pathology_report.header?.alert_banner && (
                <div className="flex items-start gap-2 p-3 bg-amber-50 border border-amber-200 rounded-lg">
                  <div className="w-1 h-1 bg-amber-500 rounded-full mt-1.5"></div>
                  <div>
                    <p className="text-sm text-amber-900">
                      {currentReport.pathology_summary.pathology_report.header.alert_banner.headline}
                    </p>
                    <p className="text-xs text-amber-700 mt-1">
                      {currentReport.pathology_summary.pathology_report.header.alert_banner.subtext}
                    </p>
                  </div>
                </div>
              )}

              <div className="grid grid-cols-2 gap-4">
                <div className="col-span-2">
                  <DataField
                    label="Biopsy site"
                    value={currentReport.pathology_summary.pathology_report.details?.biopsy_site}
                  />
                </div>
                <DataField
                  label="Biopsy date"
                  value={currentReport.pathology_summary.pathology_report.details?.biopsy_date}
                />
                <DataField
                  label="Surgery date"
                  value={currentReport.pathology_summary.pathology_report.details?.surgery_date}
                />
                <DataField
                  label="Tumor grade"
                  value={currentReport.pathology_summary.pathology_report.details?.tumor_grade}
                />
                <DataField
                  label="Margin status"
                  value={currentReport.pathology_summary.pathology_report.details?.margin_status}
                />
              </div>

              <div className="pt-4 border-t border-gray-200">
                <h4 className="text-sm text-gray-700 mb-2">Diagnosis</h4>
                <div className="text-sm text-gray-600 bg-gray-50 p-3 rounded-lg border border-gray-200 leading-relaxed space-y-1">
                  {(() => {
                    const diagnosis = currentReport.pathology_summary.pathology_report.diagnosis_section?.full_diagnosis;

                    // Handle different types of diagnosis data
                    if (typeof diagnosis === 'string') {
                      return diagnosis.split('\n').map((line: string, idx: number) => (
                        <p key={idx}>{line}</p>
                      ));
                    } else if (Array.isArray(diagnosis)) {
                      return diagnosis.map((line: string, idx: number) => (
                        <p key={idx}>{line}</p>
                      ));
                    } else if (diagnosis && typeof diagnosis === 'object') {
                      return <p>{JSON.stringify(diagnosis)}</p>;
                    } else {
                      return <p className="text-gray-400 italic">No diagnosis information available</p>;
                    }
                  })()}
                </div>
              </div>

              <div className="pt-4 border-t border-gray-200">
                <h4 className="text-sm text-gray-700 mb-3">
                  {currentReport.pathology_markers.pathology_combined?.morphology_column?.title} &
                  Immunohistochemistry
                </h4>
                <div className="grid grid-cols-2 gap-x-8 gap-y-2">
                  {/* Left Column - Morphology */}
                  <div className="space-y-2">
                    <p className="text-xs text-gray-500 mb-2">
                      {currentReport.pathology_markers.pathology_combined?.morphology_column?.title}
                    </p>
                    {currentReport.pathology_markers.pathology_combined?.morphology_column?.items?.map(
                      (item: string, idx: number) => (
                        <div key={idx} className="flex items-start gap-2">
                          <div className="w-1.5 h-1.5 bg-gray-400 rounded-full mt-1.5 flex-shrink-0"></div>
                          <p className="text-sm text-gray-600">{item}</p>
                        </div>
                      )
                    )}
                  </div>

                  {/* Right Column - IHC Markers */}
                  <div className="space-y-2">
                    <p className="text-xs text-gray-500 mb-2">
                      {currentReport.pathology_markers.pathology_combined?.ihc_column?.title}
                    </p>
                    {currentReport.pathology_markers.pathology_combined?.ihc_column?.markers?.map(
                      (marker: any, idx: number) => (
                        <div key={idx} className="flex items-start gap-2">
                          <div
                            className={`w-1.5 h-1.5 rounded-full mt-1.5 flex-shrink-0 ${
                              marker.status_label?.toLowerCase().includes('positive')
                                ? 'bg-green-500'
                                : 'bg-red-500'
                            }`}
                          ></div>
                          <p className="text-sm text-gray-600">
                            <span className="font-medium text-gray-900">{marker.name}:</span>{' '}
                            {marker.status_label} {marker.details && `(${marker.details})`}
                          </p>
                        </div>
                      )
                    )}
                  </div>
                </div>
              </div>

              <div className="pt-4 border-t border-gray-200">
                <h4 className="text-sm text-gray-700 mb-3">Pathology interpretation keywords</h4>
                <div className="flex flex-wrap gap-2">
                  {currentReport.pathology_markers.pathology_combined?.keywords?.map(
                    (keyword: string, idx: number) => (
                      <span
                        key={idx}
                        className="px-2 py-1 bg-blue-100 text-blue-700 rounded text-xs border border-blue-200"
                      >
                        {keyword}
                      </span>
                    )
                  )}
                </div>
              </div>
            </div>
          </div>
        )}

      </div>

      {/* More reports modal */}
      {showMoreModal && (
        <div className="fixed inset-0 bg-white/30 backdrop-blur-sm flex items-center justify-center z-50">
          <div className="bg-white rounded-lg shadow-xl p-6 w-[500px] max-h-[600px] overflow-y-auto">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-gray-900">More Reports</h3>
              <button
                className="p-1 text-gray-400 hover:text-gray-900 hover:bg-gray-100 rounded transition-colors"
                onClick={() => setShowMoreModal(false)}
              >
                <X className="w-5 h-5" />
              </button>
            </div>
            <div className="space-y-2">
              {hiddenReports.map((report, index) => (
                <button
                  key={report.document_id}
                  onClick={() => handleSelectFromModal(index + 4)}
                  className="w-full flex items-start justify-between gap-3 p-3 bg-white hover:bg-blue-50 border border-gray-200 hover:border-blue-300 rounded-lg transition-all text-left"
                >
                  <div className="flex-1">
                    <p className="text-sm text-gray-900 mb-1">
                      {report.pathology_summary?.pathology_report?.header?.report_id || report.document_id}
                    </p>
                    <p className="text-xs text-gray-600">{report.description || report.document_type}</p>
                    <p className="text-xs text-gray-500 mt-1">{formatDate(report.date)}</p>
                  </div>
                </button>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}