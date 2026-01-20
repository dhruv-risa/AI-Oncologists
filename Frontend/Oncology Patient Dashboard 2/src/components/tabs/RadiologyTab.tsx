import { useState, useRef, useEffect } from 'react';
import { Scan, FileText, ExternalLink, Eye, Download, Plus, X } from 'lucide-react';
import { DataField } from '../DataField';
import { usePatient } from '../../contexts/PatientContext';
import { RadiologyReportDetail } from '../../services/api';

export function RadiologyTab() {
  const { currentPatient } = usePatient();
  const [selectedReportIndex, setSelectedReportIndex] = useState(0);
  const [showMoreModal, setShowMoreModal] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);

  // Get radiology reports from patient data
  const radiologyReports = currentPatient?.radiology_reports || [];

  // Sort reports by date (most recent first)
  const sortedReports = [...radiologyReports].sort((a, b) =>
    new Date(b.date).getTime() - new Date(a.date).getTime()
  );

  const visibleReports = sortedReports.slice(0, 4);
  const hiddenReports = sortedReports.slice(4);
  const hasMore = sortedReports.length > 4;

  const selectedReport = sortedReports[selectedReportIndex];

  const handleSelectFromModal = (index: number) => {
    setSelectedReportIndex(index);
    setShowMoreModal(false);
  };

  const formatDate = (dateStr: string) => {
    try {
      const date = new Date(dateStr);
      return date.toLocaleDateString('en-US', {
        month: 'short',
        day: 'numeric',
        year: 'numeric'
      });
    } catch {
      return dateStr;
    }
  };

  const getResponseBadge = (response?: string) => {
    if (!response) return null;

    const normalized = response.toLowerCase();
    if (normalized.includes('partial response') || normalized.includes('pr')) {
      return { text: 'PR', color: 'green' };
    }
    if (normalized.includes('complete response') || normalized.includes('cr')) {
      return { text: 'CR', color: 'green' };
    }
    if (normalized.includes('progressive disease') || normalized.includes('pd')) {
      return { text: 'PD', color: 'red' };
    }
    if (normalized.includes('stable')) {
      return { text: 'SD', color: 'gray' };
    }
    return null;
  };

  const formatValue = (value: string) => {
    if (!value || value === 'NA' || value === 'N/A') {
      return 'Data not available';
    }
    return value;
  };

  const getChangeColor = (changeStr: string) => {
    if (!changeStr || changeStr === 'NA' || changeStr === 'N/A') return 'text-gray-600';

    const value = parseFloat(changeStr.replace('%', ''));
    if (isNaN(value)) return 'text-gray-600';

    return value < 0 ? 'text-green-600' : value > 0 ? 'text-red-600' : 'text-gray-600';
  };

  // Parse impression into bullet points (similar to disease findings)
  const parseImpression = (impression: string | string[]) => {
    if (!impression) return [];

    // If it's already an array, return it
    if (Array.isArray(impression)) {
      return impression.filter(item => item && item.trim().length > 0);
    }

    // If it's a string, try to split it intelligently
    // First check if it contains bullet points or list markers
    if (impression.includes('•') || impression.includes('-') || impression.includes('*')) {
      return impression
        .split(/[•\-*]/)
        .map(item => item.trim())
        .filter(item => item.length > 0);
    }

    // Check for newlines (multiline text)
    if (impression.includes('\n')) {
      return impression
        .split(/\n/)
        .map(item => item.trim())
        .filter(item => item.length > 0);
    }

    // If it's a single item or already formatted, return as is
    return [impression.trim()];
  };

  const handleViewDocument = (url: string) => {
    window.open(url, '_blank');
  };

  const handleDownloadDocument = (url: string, fileName: string) => {
    // Extract file ID from Google Drive URL
    const fileIdMatch = url.match(/\/d\/([^/]+)/);
    if (fileIdMatch) {
      const fileId = fileIdMatch[1];
      const downloadUrl = `https://drive.google.com/uc?export=download&id=${fileId}`;
      window.open(downloadUrl, '_blank');
    }
  };

  // Show loading state if no patient data
  if (!currentPatient) {
    return (
      <div className="flex items-center justify-center h-64">
        <p className="text-gray-500">No patient data loaded</p>
      </div>
    );
  }

  // Show empty state if no reports
  if (radiologyReports.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center h-64 bg-white rounded-lg border border-gray-200">
        <Scan className="w-12 h-12 text-gray-400 mb-3" />
        <p className="text-gray-600 mb-1">No radiology reports available</p>
        <p className="text-sm text-gray-500">Reports will appear here once they are extracted</p>
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
              <Scan className="w-4 h-4 text-gray-600" />
              <h4 className="text-sm text-gray-900">Reports</h4>
              <span className="text-xs text-gray-500">({sortedReports.length})</span>
            </div>
          </div>
          <nav className="p-2 max-h-[calc(100vh-300px)] overflow-y-auto">
            {visibleReports.map((report, index) => {
              const badge = getResponseBadge(report.radiology_summary?.report_summary?.overall_response);
              return (
                <button
                  key={report.document_id}
                  onClick={() => setSelectedReportIndex(index)}
                  className={`w-full p-3 mb-2 text-left transition-all rounded-lg border ${
                    selectedReportIndex === index
                      ? 'border-blue-500 bg-blue-50'
                      : 'border-gray-200 bg-white hover:border-gray-300 hover:bg-gray-50'
                  }`}
                >
                  <div className="flex items-start justify-between mb-1">
                    <p className={`text-sm ${selectedReportIndex === index ? 'text-blue-900' : 'text-gray-900'}`}>
                      {report.description || report.document_type}
                    </p>
                    {badge && (
                      <span className={`px-1.5 py-0.5 rounded text-xs ${
                        badge.color === 'green'
                          ? 'bg-green-100 text-green-700 border border-green-200'
                          : badge.color === 'red'
                          ? 'bg-red-100 text-red-700 border border-red-200'
                          : 'bg-gray-100 text-gray-700'
                      }`}>
                        {badge.text}
                      </span>
                    )}
                  </div>
                  <p className="text-xs text-gray-500 mb-2">{formatDate(report.date)}</p>

                  {/* Action buttons */}
                  <div className="flex items-center gap-1">
                    <button
                      className="p-1 text-gray-400 hover:text-blue-600 hover:bg-blue-100 rounded transition-colors"
                      title="View document"
                      onClick={(e) => {
                        e.stopPropagation();
                        handleViewDocument(report.drive_url);
                      }}
                    >
                      <Eye className="w-3 h-3" />
                    </button>
                    <button
                      className="p-1 text-gray-400 hover:text-blue-600 hover:bg-blue-100 rounded transition-colors"
                      title="Download document"
                      onClick={(e) => {
                        e.stopPropagation();
                        handleDownloadDocument(report.drive_url, `${report.description}_${formatDate(report.date)}.pdf`);
                      }}
                    >
                      <Download className="w-3 h-3" />
                    </button>
                    <button
                      className="p-1 text-gray-400 hover:text-blue-600 hover:bg-blue-100 rounded transition-colors"
                      title="Open in new tab"
                      onClick={(e) => {
                        e.stopPropagation();
                        handleViewDocument(report.drive_url);
                      }}
                    >
                      <ExternalLink className="w-3 h-3" />
                    </button>
                  </div>
                </button>
              );
            })}

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
        {selectedReport ? (
          <div>
            <div className="flex items-center justify-between mb-4">
              <div className="flex items-center gap-2">
                <FileText className="w-4 h-4 text-gray-400" />
                <h3 className="text-gray-900">Report summary</h3>
                <span className="text-xs text-gray-500">
                  {selectedReport.description} - {formatDate(selectedReport.date)}
                </span>
              </div>
              <button
                className="flex items-center gap-2 px-4 py-2 bg-white hover:bg-gray-50 text-gray-700 border border-gray-300 rounded-lg text-sm transition-colors"
                onClick={() => handleViewDocument(selectedReport.drive_url)}
              >
                <ExternalLink className="w-4 h-4" />
                View Source
              </button>
            </div>

            <div className="space-y-4">
              {/* Report Summary Fields */}
              {selectedReport.radiology_summary?.report_summary && (
                <div className="grid grid-cols-2 gap-4">
                  <DataField
                    label="Study type"
                    value={formatValue(selectedReport.radiology_summary.report_summary.study_type)}
                  />
                  <DataField
                    label="Study date"
                    value={formatValue(selectedReport.radiology_summary.report_summary.study_date) !== 'Data not available'
                      ? formatValue(selectedReport.radiology_summary.report_summary.study_date)
                      : formatDate(selectedReport.date)}
                  />
                  <DataField
                    label="Overall response"
                    value={formatValue(selectedReport.radiology_summary.report_summary.overall_response)}
                  />
                  <DataField
                    label="Prior comparison"
                    value={formatValue(selectedReport.radiology_summary.report_summary.prior_comparison)}
                  />
                </div>
              )}

              {/* Impression */}
              {selectedReport.radiology_imp_RECIST?.impression && (
                <div className="pt-4 border-t border-gray-200">
                  <h4 className="text-sm text-gray-700 mb-2">Impression</h4>
                  <div className="bg-gray-50 p-3 rounded-lg border border-gray-200">
                    <ul className="text-sm text-gray-600 space-y-1 pl-4">
                      {parseImpression(selectedReport.radiology_imp_RECIST.impression).map((finding, idx) => (
                        <li key={idx} className="list-disc ml-1 leading-relaxed">{finding}</li>
                      ))}
                    </ul>
                  </div>
                </div>
              )}

              {/* RECIST Measurements - Only show if there are lesions */}
              {(() => {
                const recistData = selectedReport.radiology_imp_RECIST?.recist_measurements;
                const hasLesions = recistData && recistData.lesions && recistData.lesions.length > 0;

                // Don't render section if no lesions data
                if (!hasLesions) {
                  return null;
                }

                return (
                  <div className="pt-4 border-t border-gray-200">
                    <div className="flex items-center justify-between mb-3">
                      <h4 className="text-sm text-gray-700">RECIST Measurements</h4>
                    </div>
                    <div className="overflow-hidden rounded-lg border border-gray-200">
                      <table className="w-full text-sm">
                        <thead className="bg-gray-50">
                          <tr>
                            <th className="px-3 py-2 text-left text-xs text-gray-600">Lesion</th>
                            <th className="px-3 py-2 text-center text-xs text-gray-600 border-l border-gray-300" colSpan={2}>
                              <div className="flex flex-col">
                                <span className="font-semibold text-blue-700">
                                  {recistData.column_headers.initial_diagnosis_label?.split(' ').slice(0, 2).join(' ') || 'Initial Diagnosis'}
                                </span>
                                <span className="text-xs text-gray-500 font-normal">
                                  {recistData.column_headers.initial_diagnosis_label?.split(' ').slice(-2).join(' ') || ''}
                                </span>
                              </div>
                            </th>
                            <th className="px-3 py-2 text-center text-xs text-gray-600 border-l border-gray-300" colSpan={2}>
                              <div className="flex flex-col">
                                <span className="font-semibold text-purple-700">
                                  {recistData.column_headers.current_treatment_label?.split(' ').slice(0, 2).join(' ') || 'Current Treatment'}
                                </span>
                                <span className="text-xs text-gray-500 font-normal">
                                  {recistData.column_headers.current_treatment_label?.split(' ').slice(-2).join(' ') || ''}
                                </span>
                              </div>
                            </th>
                          </tr>
                          <tr className="border-t border-gray-300">
                            <th className="px-3 py-2 text-left text-xs text-gray-600"></th>
                            <th className="px-3 py-2 text-left text-xs text-gray-600 border-l border-gray-200">Baseline</th>
                            <th className="px-3 py-2 text-left text-xs text-gray-600">Change</th>
                            <th className="px-3 py-2 text-left text-xs text-gray-600 border-l border-gray-200">Baseline</th>
                            <th className="px-3 py-2 text-left text-xs text-gray-600">Change</th>
                          </tr>
                        </thead>
                        <tbody className="divide-y divide-gray-200">
                          {/* Lesion rows */}
                          {recistData.lesions.map((lesion, idx) => (
                            <tr key={idx}>
                              <td className="px-3 py-2 text-gray-900">{lesion.lesion_name}</td>
                              <td className="px-3 py-2 text-gray-600 border-l border-gray-200">
                                {formatValue(lesion.initial_diagnosis_data.baseline_val)}
                              </td>
                              <td className="px-3 py-2">
                                <span className={getChangeColor(lesion.initial_diagnosis_data.change_percentage)}>
                                  {formatValue(lesion.initial_diagnosis_data.change_percentage)}
                                </span>
                              </td>
                              <td className="px-3 py-2 text-gray-600 border-l border-gray-200">
                                {formatValue(lesion.current_treatment_data.baseline_val)}
                              </td>
                              <td className="px-3 py-2">
                                <span className={getChangeColor(lesion.current_treatment_data.change_percentage)}>
                                  {formatValue(lesion.current_treatment_data.change_percentage)}
                                </span>
                              </td>
                            </tr>
                          ))}

                          {/* Sum row */}
                          {recistData.sum_row && (
                            <tr className="bg-gray-50 font-semibold">
                              <td className="px-3 py-2 text-gray-900">
                                {recistData.sum_row.lesion_name}
                              </td>
                              <td className="px-3 py-2 text-gray-900 border-l border-gray-200">
                                {formatValue(recistData.sum_row.initial_diagnosis_data.baseline_val)}
                              </td>
                              <td className="px-3 py-2">
                                <span className={getChangeColor(recistData.sum_row.initial_diagnosis_data.change_percentage)}>
                                  {formatValue(recistData.sum_row.initial_diagnosis_data.change_percentage)}
                                </span>
                              </td>
                              <td className="px-3 py-2 text-gray-900 border-l border-gray-200">
                                {formatValue(recistData.sum_row.current_treatment_data.baseline_val)}
                              </td>
                              <td className="px-3 py-2">
                                <span className={getChangeColor(recistData.sum_row.current_treatment_data.change_percentage)}>
                                  {formatValue(recistData.sum_row.current_treatment_data.change_percentage)}
                                </span>
                              </td>
                            </tr>
                          )}
                        </tbody>
                      </table>
                    </div>

                    {/* Legend */}
                    <div className="mt-3 flex items-center gap-4 text-xs text-gray-600">
                      <div className="flex items-center gap-2">
                        <div className="w-3 h-3 bg-blue-50 border border-blue-300 rounded"></div>
                        <span>Initial diagnosis baseline</span>
                      </div>
                      <div className="flex items-center gap-2">
                        <div className="w-3 h-3 bg-purple-50 border border-purple-300 rounded"></div>
                        <span>Current treatment baseline</span>
                      </div>
                    </div>
                  </div>
                );
              })()}

              {/* Additional Findings Section */}
              {selectedReport.radiology_imp_RECIST?.additional_findings && (
                <div className="pt-4 border-t border-gray-200">
                  <h4 className="text-sm text-gray-700 mb-2">Additional Findings</h4>
                  <div className="bg-gray-50 p-3 rounded-lg border border-gray-200">
                    <ul className="text-sm text-gray-600 space-y-1 pl-4">
                      {parseImpression(selectedReport.radiology_imp_RECIST.additional_findings).map((finding, idx) => (
                        <li key={idx} className="list-disc ml-1 leading-relaxed">{finding}</li>
                      ))}
                    </ul>
                  </div>
                </div>
              )}

              {/* Extraction error message */}
              {selectedReport.extraction_error && (
                <div className="pt-4 border-t border-gray-200">
                  <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-4">
                    <h4 className="text-sm text-yellow-900 mb-1">Extraction Note</h4>
                    <p className="text-sm text-yellow-800">
                      Some details could not be extracted from this report. Please view the source document for complete information.
                    </p>
                  </div>
                </div>
              )}
            </div>
          </div>
        ) : (
          <div className="flex items-center justify-center h-64">
            <p className="text-gray-500">Select a report to view details</p>
          </div>
        )}

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
                {hiddenReports.map((report, idx) => {
                  const actualIndex = idx + 4; // Since hidden reports start after the first 4
                  const badge = getResponseBadge(report.radiology_summary?.report_summary?.overall_response);
                  return (
                    <button
                      key={report.document_id}
                      onClick={() => handleSelectFromModal(actualIndex)}
                      className="w-full flex items-start justify-between gap-3 p-3 bg-white hover:bg-blue-50 border border-gray-200 hover:border-blue-300 rounded-lg transition-all text-left"
                    >
                      <div className="flex-1">
                        <div className="flex items-start justify-between mb-1">
                          <p className="text-sm text-gray-900">{report.description || report.document_type}</p>
                          {badge && (
                            <span className={`px-1.5 py-0.5 rounded text-xs ${
                              badge.color === 'green'
                                ? 'bg-green-100 text-green-700'
                                : badge.color === 'red'
                                ? 'bg-red-100 text-red-700'
                                : 'bg-gray-100 text-gray-700'
                            }`}>
                              {badge.text}
                            </span>
                          )}
                        </div>
                        <p className="text-xs text-gray-500">{formatDate(report.date)}</p>
                      </div>
                    </button>
                  );
                })}
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
