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

  // Helper functions
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

  // Get the study date from radiology report (use extracted study_date > file date)
  const getReportDate = (report: RadiologyReportDetail) => {
    // Try to get study_date from extracted radiology data
    if (report.radiology_summary?.report_summary?.study_date) {
      return report.radiology_summary.report_summary.study_date;
    }

    // Fall back to file date
    return report.date;
  };

  // Sort reports by date (most recent first) - use study date from extraction
  const sortedReports = [...radiologyReports].sort((a, b) =>
    new Date(getReportDate(b)).getTime() - new Date(getReportDate(a)).getTime()
  );

  const visibleReports = sortedReports.slice(0, 4);
  const hiddenReports = sortedReports.slice(4);
  const hasMore = sortedReports.length > 4;

  const selectedReport = sortedReports[selectedReportIndex];

  const handleSelectFromModal = (index: number) => {
    setSelectedReportIndex(index);
    setShowMoreModal(false);
  };

  const getResponseBadge = (response?: string) => {
    if (!response) return null;

    const normalized = response.toLowerCase().trim();

    // Check for progressive disease first to avoid matching "pr" in "progressive"
    if (normalized.includes('progressive disease') || normalized.includes('progressive') ||
        normalized.match(/\bpd\b/)) {
      return { text: 'PD', color: 'red' };
    }
    // Check for partial response (use word boundary to avoid matching in "progressive")
    if (normalized.includes('partial response') || normalized.match(/\bpr\b/)) {
      return { text: 'PR', color: 'green' };
    }
    // Check for complete response
    if (normalized.includes('complete response') || normalized.match(/\bcr\b/)) {
      return { text: 'CR', color: 'green' };
    }
    // Check for stable disease
    if (normalized.includes('stable disease') || normalized.includes('stable') ||
        normalized.match(/\bsd\b/)) {
      return { text: 'SD', color: 'gray' };
    }

    // If response doesn't match any standard RECIST category, don't show a badge
    return null;
  };

  const formatValue = (value: string | undefined) => {
    if (!value || value === 'NA' || value === 'N/A') {
      return 'Not measured';
    }
    return value;
  };

  // Check if current value is valid (not NA, not incomplete)
  const isValidCurrentValue = (value: string | undefined) => {
    if (!value || value === 'NA' || value === 'N/A') {
      return false;
    }

    const trimmedValue = value.trim();

    // Check for incomplete dimensions like "4.12 x" or "4.12 x " (ends with 'x' followed by optional whitespace)
    if (/x\s*$/i.test(trimmedValue)) {
      return false;
    }

    // If it contains an 'x', it should be a complete two-dimension measurement (e.g., "4.1 x 2.3 cm")
    if (trimmedValue.toLowerCase().includes('x')) {
      // Must have pattern: number x number unit (e.g., "4.1 x 2.3 cm")
      // Unit must be 2+ chars to avoid matching trailing 'x' as unit
      const completeTwoDimPattern = /^\d+\.?\d*\s*x\s*\d+\.?\d*\s*[a-zA-Z]{2,}$/i;
      if (!completeTwoDimPattern.test(trimmedValue)) {
        return false;
      }

      // Extra validation: the unit should not be just "x"
      const unitMatch = trimmedValue.match(/[a-zA-Z]+$/);
      if (unitMatch && unitMatch[0].toLowerCase() === 'x') {
        return false;
      }
    } else {
      // Single dimension - must have pattern: number unit (e.g., "10.37 cm")
      const singleDimPattern = /^\d+\.?\d*\s*[a-zA-Z]{2,}$/;
      if (!singleDimPattern.test(trimmedValue)) {
        return false;
      }
    }

    return true;
  };

  // Calculate current value from baseline and percentage change
  const calculateCurrentValue = (baseline: string, changePercentage: string) => {
    // Check if baseline and change are available
    if (!baseline || baseline === 'NA' || baseline === 'N/A' ||
        !changePercentage || changePercentage === 'NA' || changePercentage === 'N/A') {
      return 'Not measured';
    }

    const changeNum = parseFloat(changePercentage.replace('%', ''));
    if (isNaN(changeNum)) {
      return 'Not measured';
    }

    // Extract unit from the END of the string (not the first letter match)
    // This ensures we get "cm" not "x" for "4.1 x 2.3 cm"
    const unitMatch = baseline.match(/[a-zA-Z]+$/);
    const unit = unitMatch?.[0] || 'cm';

    // Check if baseline has two dimensions (e.g., "4.1 x 2.3 cm")
    const twoDimensionMatch = baseline.match(/(\d+\.?\d*)\s*x\s*(\d+\.?\d*)/i);

    if (twoDimensionMatch) {
      // Two dimensions found
      const dim1 = parseFloat(twoDimensionMatch[1]);
      const dim2 = parseFloat(twoDimensionMatch[2]);

      if (isNaN(dim1) || isNaN(dim2)) {
        return 'Not measured';
      }

      // Calculate both dimensions: current = baseline × (1 + change/100)
      const currentDim1 = dim1 * (1 + changeNum / 100);
      const currentDim2 = dim2 * (1 + changeNum / 100);

      return `${currentDim1.toFixed(2)} x ${currentDim2.toFixed(2)} ${unit}`;
    } else {
      // Single dimension (e.g., "12.2 cm")
      const singleDimMatch = baseline.match(/(\d+\.?\d*)/);
      if (!singleDimMatch) {
        return 'Not measured';
      }

      const baselineNum = parseFloat(singleDimMatch[1]);
      if (isNaN(baselineNum)) {
        return 'Not measured';
      }

      // Calculate: current = baseline × (1 + change/100)
      const currentValue = baselineNum * (1 + changeNum / 100);
      return `${currentValue.toFixed(2)} ${unit}`;
    }
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

  // Get treatment regimen name at the time of the radiology report
  const getTreatmentAtDate = (reportDate: string) => {
    const treatmentHistory = currentPatient?.treatment_tab_info_LOT?.treatment_history || [];

    if (!reportDate || reportDate === 'NA') {
      return 'Treatment info unavailable';
    }

    try {
      const reportDateObj = new Date(reportDate);

      // Sort treatments by start date to check from earliest to latest
      const sortedTreatments = [...treatmentHistory].sort((a, b) => {
        const dateA = a.dates?.start_date;
        const dateB = b.dates?.start_date;
        if (!dateA || dateA === 'NA') return 1;
        if (!dateB || dateB === 'NA') return -1;
        return new Date(dateA).getTime() - new Date(dateB).getTime();
      });

      // Find the treatment line that was active on the report date
      for (const treatment of sortedTreatments) {
        const startDate = treatment.dates?.start_date;
        const endDate = treatment.dates?.end_date;

        if (!startDate || startDate === 'NA') continue;

        const treatmentStart = new Date(startDate);

        // Check if report date is after treatment start
        if (reportDateObj >= treatmentStart) {
          // If treatment is ongoing or no end date, this is the active treatment
          if (!endDate || endDate === 'Ongoing' || endDate === 'NA') {
            return treatment.systemic_regimen || treatment.header?.primary_drug_name || 'Treatment name unavailable';
          }

          // If there's an end date, check if report is within range
          const treatmentEnd = new Date(endDate);
          if (reportDateObj <= treatmentEnd) {
            return treatment.systemic_regimen || treatment.header?.primary_drug_name || 'Treatment name unavailable';
          }
        }
      }

      // If no match found, return the most recent treatment
      if (sortedTreatments.length > 0) {
        const lastTreatment = sortedTreatments[sortedTreatments.length - 1];
        return lastTreatment.systemic_regimen || lastTreatment.header?.primary_drug_name || 'Treatment info unavailable';
      }

      return 'No treatment data';
    } catch (e) {
      console.error('Error matching treatment to date:', e);
      return 'Treatment info unavailable';
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
                  <p className="text-xs text-gray-500 mb-2">{formatDate(getReportDate(report))}</p>

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
                        handleDownloadDocument(report.drive_url, `${report.description}_${formatDate(getReportDate(report))}.pdf`);
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
                  {selectedReport.description} - {formatDate(getReportDate(selectedReport))}
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
                    value={formatDate(getReportDate(selectedReport))}
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

                // Check if this is a baseline study (no prior comparison OR all baseline values are "Not available")
                const priorComparison = selectedReport.radiology_summary?.report_summary?.prior_comparison;

                // Check if all baseline values are "Not available" or "NA"
                const allBaselinesNA = recistData.lesions.every(lesion => {
                  const baselineVal = lesion.current_treatment_data.baseline_val;
                  return !baselineVal ||
                         baselineVal === 'NA' ||
                         baselineVal === 'N/A' ||
                         baselineVal.toLowerCase() === 'not available';
                });

                const isBaselineStudy = !priorComparison ||
                                       priorComparison === 'NA' ||
                                       priorComparison.toLowerCase().includes('baseline') ||
                                       allBaselinesNA;

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
                            <th className="px-3 py-2 text-center text-xs text-gray-600 border-l border-gray-300" colSpan={isBaselineStudy ? 1 : 3}>
                              <div className="flex flex-col items-center">
                                <span className="font-semibold text-purple-700">
                                  Current Treatment ({getTreatmentAtDate(getReportDate(selectedReport))})
                                </span>
                                <span className="text-xs text-gray-500 font-normal">
                                  {formatDate(getReportDate(selectedReport))}
                                </span>
                              </div>
                            </th>
                          </tr>
                          <tr className="border-t border-gray-300">
                            <th className="px-3 py-2 text-left text-xs text-gray-600"></th>
                            {!isBaselineStudy && (
                              <th className="px-3 py-2 text-left text-xs text-gray-600 border-l border-gray-200">
                                <div className="flex flex-col">
                                  <span>Baseline</span>
                                  <span className="text-xs text-gray-500 font-normal">(First study)</span>
                                </div>
                              </th>
                            )}
                            <th className={`px-3 py-2 ${isBaselineStudy ? 'text-center border-l border-gray-200' : 'text-left'} text-xs text-gray-600`}>
                              <div className={`flex flex-col ${isBaselineStudy ? 'items-center' : ''}`}>
                                <span>Current</span>
                                <span className="text-xs text-gray-500 font-normal">(Current study)</span>
                              </div>
                            </th>
                            {!isBaselineStudy && (
                              <th className="px-3 py-2 text-left text-xs text-gray-600">Change</th>
                            )}
                          </tr>
                        </thead>
                        <tbody className="divide-y divide-gray-200">
                          {/* Lesion rows */}
                          {recistData.lesions.map((lesion, idx) => {
                            // Try to use current_val if valid, otherwise calculate it
                            const currentVal = lesion.current_treatment_data.current_val;
                            const displayCurrentVal = isValidCurrentValue(currentVal)
                              ? formatValue(currentVal)
                              : calculateCurrentValue(
                                  lesion.current_treatment_data.baseline_val,
                                  lesion.current_treatment_data.change_percentage
                                );

                            return (
                              <tr key={idx}>
                                <td className="px-3 py-2 text-gray-900">{lesion.lesion_name}</td>
                                {!isBaselineStudy && (
                                  <td className="px-3 py-2 text-gray-600 border-l border-gray-200">
                                    {formatValue(lesion.current_treatment_data.baseline_val)}
                                  </td>
                                )}
                                <td className={`px-3 py-2 text-gray-600 ${isBaselineStudy ? 'text-center border-l border-gray-200' : ''}`}>
                                  {displayCurrentVal}
                                </td>
                                {!isBaselineStudy && (
                                  <td className="px-3 py-2">
                                    <span className={getChangeColor(lesion.current_treatment_data.change_percentage)}>
                                      {formatValue(lesion.current_treatment_data.change_percentage)}
                                    </span>
                                  </td>
                                )}
                              </tr>
                            );
                          })}

                          {/* Sum row */}
                          {recistData.sum_row && (() => {
                            // Try to use current_val if valid, otherwise calculate it
                            const currentVal = recistData.sum_row.current_treatment_data.current_val;
                            const displayCurrentVal = isValidCurrentValue(currentVal)
                              ? formatValue(currentVal)
                              : calculateCurrentValue(
                                  recistData.sum_row.current_treatment_data.baseline_val,
                                  recistData.sum_row.current_treatment_data.change_percentage
                                );

                            // Check if all values are N/A or not quantifiable
                            const baselineVal = formatValue(recistData.sum_row.current_treatment_data.baseline_val);
                            const changeVal = formatValue(recistData.sum_row.current_treatment_data.change_percentage);

                            const isNA = (val: string) => {
                              const normalizedVal = val.toLowerCase().trim();
                              return normalizedVal === 'not measured' ||
                                     normalizedVal === 'n/a' ||
                                     normalizedVal === 'na' ||
                                     normalizedVal.includes('not quantifiable');
                            };

                            // Hide sum row if all values are N/A or not quantifiable
                            if (isNA(baselineVal) && isNA(displayCurrentVal) && isNA(changeVal)) {
                              return null;
                            }

                            return (
                              <tr className="bg-gray-50 font-semibold">
                                <td className="px-3 py-2 text-gray-900">
                                  {recistData.sum_row.lesion_name}
                                </td>
                                {!isBaselineStudy && (
                                  <td className="px-3 py-2 text-gray-900 border-l border-gray-200">
                                    {baselineVal}
                                  </td>
                                )}
                                <td className={`px-3 py-2 text-gray-900 ${isBaselineStudy ? 'text-center border-l border-gray-200' : ''}`}>
                                  {displayCurrentVal}
                                </td>
                                {!isBaselineStudy && (
                                  <td className="px-3 py-2">
                                    <span className={getChangeColor(recistData.sum_row.current_treatment_data.change_percentage)}>
                                      {changeVal}
                                    </span>
                                  </td>
                                )}
                              </tr>
                            );
                          })()}
                        </tbody>
                      </table>
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
                        <p className="text-xs text-gray-500">{formatDate(getReportDate(report))}</p>
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
