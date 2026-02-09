import { useState, useEffect } from 'react';
import { DataField } from '../DataField';
import { TrendingUp, Calendar, ArrowDown, Eye, Download, ExternalLink, AlertTriangle, Target, GitCompare, Search, ChevronDown, ChevronUp } from 'lucide-react';
import { PatientData } from '../../services/api';
import { formatDate } from '../../utils/dateFormatter';

interface DiagnosisTabProps {
  patientData: PatientData | null;
}

export function DiagnosisTab({ patientData }: DiagnosisTabProps) {
  const [visibleTimelineCount, setVisibleTimelineCount] = useState(5);

  // Reset visible count when patient changes
  useEffect(() => {
    setVisibleTimelineCount(5);
  }, [patientData?.mrn]);

  if (!patientData) {
    return (
      <div className="bg-white border border-t-0 border-gray-200 rounded-b-lg shadow-sm p-6">
        <p className="text-gray-500 text-center">No patient data available</p>
      </div>
    );
  }

  const diagnosisHeader = patientData.diagnosis_header;
  const rawDiagnosisTimeline = patientData.diagnosis_evolution_timeline?.timeline || [];
  const diagnosisFooter = patientData.diagnosis_footer;

  // Sort timeline by date (most recent first)
  const sortedTimeline = [...rawDiagnosisTimeline].sort((a, b) => {
    // Try to parse dates from date_label
    const parseDate = (dateStr: string) => {
      if (!dateStr) return new Date(0);

      // Handle "Current Status" or similar labels - should be most recent
      if (dateStr && dateStr.toLowerCase().includes('current')) {
        return new Date(); // Current date (highest priority)
      }

      // Handle "Prior to" dates (e.g., "Prior to 8/11/2025")
      const priorToMatch = dateStr.match(/prior\s+to\s+(.+)/i);
      if (priorToMatch) {
        const extractedDate = priorToMatch[1].trim();
        const parsedDate = new Date(extractedDate);
        if (!isNaN(parsedDate.getTime())) {
          // Subtract one day to ensure it comes before the actual date
          return new Date(parsedDate.getTime() - 24 * 60 * 60 * 1000);
        }
      }

      // Try to parse date formats like "March 2023", "June 2024", "2023-03", "March 12, 2023"
      const monthNames = ['january', 'february', 'march', 'april', 'may', 'june',
                          'july', 'august', 'september', 'october', 'november', 'december'];

      const lowerStr = dateStr.toLowerCase().trim();

      // Check for "Month Year" format (e.g., "March 2023", "December 2025")
      for (let i = 0; i < monthNames.length; i++) {
        if (lowerStr.startsWith(monthNames[i])) {
          const yearMatch = dateStr.match(/\d{4}/);
          if (yearMatch) {
            return new Date(parseInt(yearMatch[0]), i, 1);
          }
        }
      }

      // Check for year-only format (e.g., "2023", "2024")
      const yearOnlyMatch = dateStr.match(/^(20\d{2})$/);
      if (yearOnlyMatch) {
        return new Date(parseInt(yearOnlyMatch[1]), 0, 1); // January 1st of that year
      }

      // Try standard date parsing (handles YYYY-MM-DD, M/D/YYYY, etc.)
      const date = new Date(dateStr);
      if (!isNaN(date.getTime())) {
        return date;
      }

      // Handle vague terms that might have slipped through (fallback)
      const yearMatch = dateStr.match(/\b(20\d{2})\b/);
      if (yearMatch) {
        const year = parseInt(yearMatch[0]);
        // Use middle of year as fallback
        return new Date(year, 5, 1); // June 1st
      }

      // Fallback: return epoch if can't parse (lowest priority)
      return new Date(0);
    };

    const aDate = parseDate(a.date_label);
    const bDate = parseDate(b.date_label);
    return bDate.getTime() - aDate.getTime(); // Most recent first
  });

  // Apply pagination - slice based on visible count
  const diagnosisTimeline = sortedTimeline.slice(0, visibleTimelineCount);
  const totalTimelineEntries = sortedTimeline.length;
  const hasMore = visibleTimelineCount < totalTimelineEntries;
  const canShowLess = visibleTimelineCount > 5;

  // Derive initial and current staging from timeline (timeline is sorted most recent first)
  // Find oldest timeline entry with valid staging data for initial staging
  const initialTimelineEntry = diagnosisTimeline.length > 0
    ? [...diagnosisTimeline].reverse().find(entry =>
        (entry.tnm_status && entry.tnm_status !== 'NA' && entry.tnm_status !== 'N/A') ||
        (entry.stage_header && entry.stage_header !== 'N/A')
      )
    : null;

  const initialStaging = initialTimelineEntry
    ? {
        tnm: initialTimelineEntry.tnm_status || 'NA',
        ajcc_stage: initialTimelineEntry.stage_header || 'N/A'
      }
    : diagnosisHeader?.initial_staging || { tnm: 'NA', ajcc_stage: 'N/A' };

  // Find most recent timeline entry with valid staging data for current staging
  const currentTimelineEntry = diagnosisTimeline.find(entry =>
    (entry.tnm_status && entry.tnm_status !== 'NA' && entry.tnm_status !== 'N/A') ||
    (entry.stage_header && entry.stage_header !== 'N/A')
  );

  const currentStaging = currentTimelineEntry
    ? {
        tnm: currentTimelineEntry.tnm_status || 'NA',
        ajcc_stage: currentTimelineEntry.stage_header || 'N/A'
      }
    : diagnosisHeader?.current_staging || { tnm: 'NA', ajcc_stage: 'N/A' };

  // Format metastatic sites for display
  const metastaticSitesDisplay = diagnosisHeader?.metastatic_sites?.length > 0
    ? diagnosisHeader.metastatic_sites.join(', ')
    : 'None';

  // Format dates
  const formatDate = (dateString: string) => {
    if (!dateString || dateString === 'NA') return 'N/A';
    const date = new Date(dateString);
    return date.toLocaleDateString('en-US', { year: 'numeric', month: 'long', day: 'numeric' });
  };

  // Format TNM with stage
  const formatTNMStage = (tnm: string, stage: string) => {
    // Handle special stage values that don't need TNM
    if (stage === 'Pre-diagnosis finding') {
      return 'Pre-diagnosis finding (stage assigned at diagnosis)';
    }
    if (stage === 'Staging not performed') {
      return 'Staging not performed at this time';
    }

    // Normal case: show TNM with stage, or indicate TNM not documented
    if (tnm === 'NA' || !tnm || tnm === 'N/A' || tnm === 'null') {
      if (stage && stage !== 'N/A' && stage !== 'NA') {
        return 'TNM not documented';
      }
      return 'Staging information not documented';
    }
    return `${tnm} (${stage})`;
  };

  // Parse key findings into bullet points
  const parseKeyFindings = (findings: string[]) => {
    if (!findings || !Array.isArray(findings)) return [];
    return findings.filter(item => item && item.trim().length > 0);
  };

  // Helper function to parse local therapy details
  const parseLocalTherapy = (localTherapyText: string) => {
    if (!localTherapyText) return { therapyType: 'N/A', site: 'N/A' };

    const text = localTherapyText.toLowerCase();
    let therapyType = 'N/A';
    let site = 'N/A';

    // Extract therapy type
    if (text.includes('wbrt') || text.includes('whole brain radiation')) {
      therapyType = 'WBRT (Whole Brain Radiation Therapy)';
      site = 'Brain';
    } else if (text.includes('sbrt')) {
      therapyType = 'SBRT (Stereotactic Body Radiation Therapy)';
    } else if (text.includes('srs') || text.includes('stereotactic radiosurgery')) {
      therapyType = 'SRS (Stereotactic Radiosurgery)';
    } else if (text.includes('radiation')) {
      therapyType = 'Radiation Therapy';
    } else if (text.includes('lobectomy')) {
      therapyType = 'Lobectomy';
      site = text.includes('right') ? 'Right lung' : text.includes('left') ? 'Left lung' : 'Lung';
    } else if (text.includes('resection')) {
      therapyType = 'Surgical Resection';
    } else if (text.includes('surgery')) {
      therapyType = 'Surgery';
    }

    // Extract site if not already set
    if (site === 'N/A') {
      if (text.includes('brain') || text.includes('hippocampal')) {
        site = 'Brain';
      } else if (text.includes('lung')) {
        site = 'Lung';
      } else if (text.includes('liver')) {
        site = 'Liver';
      } else if (text.includes('bone')) {
        site = 'Bone';
      } else if (text.includes('spine')) {
        site = 'Spine';
      } else {
        site = localTherapyText; // Use full text as fallback
      }
    }

    return { therapyType, site };
  };

  return (
    <div className="bg-white border border-t-0 border-gray-200 rounded-b-lg shadow-sm p-6">
      <div className="grid grid-cols-3 gap-x-8 gap-y-5 mb-8">
        <DataField
          label="Primary diagnosis"
          value={diagnosisHeader?.primary_diagnosis || 'N/A'}
        />
        <DataField
          label="Histologic type"
          value={(diagnosisHeader?.histologic_type && diagnosisHeader.histologic_type !== 'N/A' && diagnosisHeader.histologic_type !== 'NA') ? diagnosisHeader.histologic_type : 'Not specified'}
        />
        <DataField
          label="Diagnosis date"
          value={formatDate(diagnosisHeader?.diagnosis_date || '')}
        />
        <DataField
          label="Initial TNM stage"
          value={formatTNMStage(
            initialStaging.tnm,
            initialStaging.ajcc_stage
          )}
        />
        <DataField
          label="Current TNM stage"
          value={formatTNMStage(
            currentStaging.tnm,
            currentStaging.ajcc_stage
          )}
        />
        <DataField
          label="Metastatic status"
          value={diagnosisHeader?.metastatic_status || 'N/A'}
        />
        <DataField
          label="Metastatic sites"
          value={metastaticSitesDisplay}
        />
        <DataField
          label="RECIST status"
          value={diagnosisHeader?.recurrence_status || 'N/A'}
        />
      </div>

      <div className="bg-gradient-to-br from-slate-50 to-gray-50 rounded-xl p-6 border border-slate-200">
        {/* Title with horizontal line */}
        <div className="relative flex items-center justify-center mb-8">
          <div className="absolute inset-0 flex items-center">
            <div className="w-full border-t border-gray-300"></div>
          </div>
          <div className="relative bg-gradient-to-br from-slate-50 to-gray-50 px-4">
            <div className="flex items-center gap-2">
              <TrendingUp className="w-4 h-4 text-slate-600" />
              <h3 className="text-sm text-slate-900">Treatment & Stage Evolution Timeline</h3>
            </div>
          </div>
        </div>

        {/* Vertical Timeline */}
        <div className="max-w-5xl mx-auto space-y-4">
          {diagnosisTimeline.length === 0 ? (
            <div className="text-center text-gray-500 py-8">
              No timeline data available
            </div>
          ) : (
            diagnosisTimeline.map((event, index) => {
              const isFirst = index === 0;
              const isRelapse = event.relapse_info?.is_relapse === true;

              // Special styling for relapse cards - use amber/yellow for warning
              const borderColor = isRelapse
                ? 'border-amber-500'
                : isFirst
                  ? 'border-red-500'
                  : index === 1
                    ? 'border-orange-500'
                    : 'border-blue-500';

              const bgColor = isRelapse
                ? 'bg-amber-500'
                : isFirst
                  ? 'bg-red-500'
                  : index === 1
                    ? 'bg-orange-500'
                    : 'bg-blue-500';

              // For timeline dates, use the date_label directly (it's already formatted by backend)
              // Only format if it's a strict ISO date (YYYY-MM-DD)
              const formatTimelineDate = (dateStr: string) => {
                if (!dateStr) return 'Unknown Date';
                // If it's already in "Month YYYY" format, return as-is
                if (/^[A-Za-z]+ \d{4}$/.test(dateStr)) return dateStr;
                // If it's YYYY-MM-DD format, format it nicely
                if (/^\d{4}-\d{2}-\d{2}$/.test(dateStr)) {
                  const date = new Date(dateStr);
                  return date.toLocaleDateString('en-US', { year: 'numeric', month: 'long', day: 'numeric' });
                }
                // Otherwise return as-is
                return dateStr;
              };
              const statusLabel = isFirst ? 'Current Status' : formatTimelineDate(event.date_label);

              // Helper function to get toxicity color
              const getToxicityColor = (grade: string) => {
                if (!grade) return 'bg-gray-100 text-gray-800';
                if (grade.includes('3') || grade.includes('4')) return 'bg-red-100 text-red-800';
                if (grade.includes('2')) return 'bg-amber-100 text-amber-800';
                return 'bg-yellow-100 text-yellow-800';
              };

              return (
                <div key={index} className="relative">
                  {/* Different structure for Relapse cases */}
                  {isRelapse ? (
                    <div className="bg-white rounded-lg shadow-lg border-2 border-amber-400 overflow-hidden">
                      <div className={`absolute -left-3 top-6 w-5 h-5 ${bgColor} rounded-full border-4 border-white shadow-lg z-10`}></div>

                      {/* Top Banner: Relapse Flag */}
                      <div className="bg-amber-100 border-b-2 border-amber-300 px-5 py-3 flex items-center gap-2">
                        <AlertTriangle className="w-4 h-4 text-amber-700" strokeWidth={2.5} />
                        <span className="text-amber-900 font-semibold text-sm uppercase tracking-wide">Relapse</span>
                        {event.relapse_info?.remission_duration && (
                          <span className="text-amber-800 text-xs font-medium ml-2">
                            • After {event.relapse_info.remission_duration} remission
                          </span>
                        )}
                      </div>

                      {/* Card Content - Matching regular timeline card structure */}
                      <div className="p-5">
                        <div className="flex items-stretch gap-6">
                          {/* Stage Info */}
                          <div className="flex-shrink-0 w-48">
                            <div className={`inline-block ${bgColor} text-white px-2 py-0.5 rounded-full text-xs mb-2`}>
                              {statusLabel}
                            </div>
                            <h4 className="text-sm font-semibold text-gray-900 mb-1">
                              {event.stage_header || <span className="text-gray-500 italic">Stage not documented</span>}
                            </h4>
                            <p className="text-xs text-gray-700 mb-1">
                              {event.tnm_status !== 'NA' && event.tnm_status ? event.tnm_status : ''}
                            </p>
                            <p className="text-xs text-gray-500">
                              {event.disease_status || ''}
                            </p>
                          </div>

                          {/* Treatment Details */}
                          <div className="flex-1 space-y-3 border-r border-gray-200 pr-6 self-stretch">
                            {event.systemic_regimen || event.regimen ? (
                              <div>
                                <p className="text-xs text-gray-500 mb-1">Regimen</p>
                                <p className="text-sm text-gray-900">
                                  {event.systemic_regimen || event.regimen}
                                </p>
                              </div>
                            ) : event.local_therapy && (() => {
                              const therapyType = parseLocalTherapy(event.local_therapy).therapyType;
                              const isNAOrNone = therapyType === 'N/A' ||
                                                 therapyType.toLowerCase() === 'none' ||
                                                 therapyType.toLowerCase() === 'n/a';
                              return !isNAOrNone;
                            })() ? (
                              <div>
                                <p className="text-xs text-gray-500 mb-1">Therapy Type</p>
                                <p className="text-sm text-gray-900">
                                  {parseLocalTherapy(event.local_therapy).therapyType}
                                </p>
                              </div>
                            ) : null}

                            {event.toxicities && event.toxicities.length > 0 && (
                              <div>
                                <p className="text-xs text-gray-500 mb-1">Toxicities</p>
                                <div className="flex flex-wrap gap-2">
                                  {event.toxicities.map((toxicity, idx) => (
                                    <span
                                      key={idx}
                                      className={`px-2 py-1 rounded text-xs ${getToxicityColor(toxicity.grade)}`}
                                    >
                                      {toxicity.effect}
                                    </span>
                                  ))}
                                </div>
                              </div>
                            )}
                          </div>

                          {/* Relapse Details (instead of Disease Findings) */}
                          <div className="flex-1 space-y-2 self-stretch">
                            <p className="text-xs text-gray-500 mb-1">Relapse Details</p>
                            {event.relapse_info ? (
                              <div className="space-y-1">
                                {event.relapse_info.relapse_pattern && (
                                  <div className="flex gap-2 items-start">
                                    <span className="text-gray-400 flex-shrink-0 text-xs leading-none mt-[0.1rem]">•</span>
                                    <p className="text-xs text-gray-900 flex-1 leading-normal">{event.relapse_info.relapse_pattern}</p>
                                  </div>
                                )}
                                {event.relapse_info.comparison_to_initial && (
                                  <div className="flex gap-2 items-start">
                                    <span className="text-gray-400 flex-shrink-0 text-xs leading-none mt-[0.1rem]">•</span>
                                    <p className="text-xs text-gray-900 flex-1 leading-normal">{event.relapse_info.comparison_to_initial}</p>
                                  </div>
                                )}
                                {event.relapse_info.relapse_detected_by && (
                                  <div className="flex gap-2 items-start">
                                    <span className="text-gray-400 flex-shrink-0 text-xs leading-none mt-[0.1rem]">•</span>
                                    <p className="text-xs text-gray-900 flex-1 leading-normal">{event.relapse_info.relapse_detected_by}</p>
                                  </div>
                                )}
                              </div>
                            ) : (
                              <p className="text-xs text-gray-900">No relapse details available</p>
                            )}
                          </div>
                        </div>
                      </div>
                    </div>
                  ) : (
                    /* Regular timeline card structure */
                    <div className={`bg-white rounded-lg p-5 shadow-md border-2 ${borderColor}`}>
                      <div className={`absolute -left-3 top-1/2 -translate-y-1/2 ${isFirst ? 'w-5 h-5' : 'w-4 h-4'} ${bgColor} rounded-full border-4 border-white shadow-lg ${isFirst ? 'animate-pulse' : ''} z-10`}></div>
                      <div className="flex items-stretch gap-6">
                      {/* Stage Info */}
                      <div className="flex-shrink-0 w-48">
                        <div className={`inline-block ${bgColor} text-white px-2 py-0.5 rounded-full text-xs mb-2`}>
                          {statusLabel}
                        </div>
                        <h4 className="text-sm font-semibold text-gray-900 mb-1">
                          {event.stage_header === 'Pre-diagnosis finding' || event.stage_header === 'Staging not performed'
                            ? <span className="text-gray-600 italic">{event.stage_header}</span>
                            : event.stage_header || <span className="text-gray-500 italic">Stage not documented</span>
                          }
                        </h4>
                        <p className="text-xs text-gray-700 mb-1">
                          {event.tnm_status !== 'NA' && event.tnm_status ? event.tnm_status : ''}
                        </p>
                        <p className="text-xs text-gray-500">
                          {event.disease_status || ''}
                        </p>

                        {/* Relapse Badge */}
                        {isRelapse && (
                          <div className="mt-2">
                            <span className="inline-flex items-center gap-1 bg-amber-100 text-amber-800 px-2 py-1 rounded-full text-xs font-medium border border-amber-300">
                              ⚠️ Relapse
                            </span>
                            {event.relapse_info?.remission_duration && (
                              <p className="text-xs text-gray-600 mt-1 italic">
                                After {event.relapse_info.remission_duration} remission
                              </p>
                            )}
                          </div>
                        )}
                      </div>

                      {/* Treatment Details */}
                      <div className="flex-1 space-y-3 border-r border-gray-200 pr-6 self-stretch">
                        {(() => {
                          const isInitialDiagnosis = event.disease_status?.toLowerCase().includes('initial diagnosis') ||
                                                     event.disease_status?.toLowerCase().includes('newly diagnosed');

                          // Check if this is an initial diagnosis with no treatment
                          if (event.systemic_regimen || event.regimen) {
                            return (
                              <div>
                                <p className="text-xs text-gray-500 mb-1">Regimen</p>
                                <p className="text-sm text-gray-900">
                                  {event.systemic_regimen || event.regimen}
                                </p>
                              </div>
                            );
                          } else if (event.local_therapy) {
                            const therapyType = parseLocalTherapy(event.local_therapy).therapyType;
                            const isNAOrNone = therapyType === 'N/A' ||
                                               therapyType.toLowerCase() === 'none' ||
                                               therapyType.toLowerCase() === 'n/a';

                            if (!isNAOrNone) {
                              return (
                                <div>
                                  <p className="text-xs text-gray-500 mb-1">Therapy Type</p>
                                  <p className="text-sm text-gray-900">
                                    {therapyType}
                                  </p>
                                </div>
                              );
                            }
                          } else if (isInitialDiagnosis) {
                            // For initial diagnosis or pre-diagnosis, show status message
                            return (
                              <div>
                                <p className="text-xs text-gray-500 mb-1">Status</p>
                                <p className="text-sm text-gray-900 italic">
                                  {event.stage_header === 'Pre-diagnosis finding'
                                    ? 'Pre diagnosis - No treatment initiated'
                                    : 'Initial diagnosis - No treatment initiated'}
                                </p>
                              </div>
                            );
                          }
                          return null;
                        })()}

                        {event.toxicities && event.toxicities.length > 0 && (
                          <div>
                            <p className="text-xs text-gray-500 mb-1">Toxicities</p>
                            <div className="flex flex-wrap gap-2">
                              {event.toxicities.map((toxicity, idx) => (
                                <span
                                  key={idx}
                                  className={`px-2 py-1 rounded text-xs ${getToxicityColor(toxicity.grade)}`}
                                >
                                  {toxicity.effect}
                                </span>
                              ))}
                            </div>
                          </div>
                        )}
                      </div>

                      {/* Disease Findings */}
                      <div className="flex-1 space-y-2 self-stretch">
                        <div>
                          <p className="text-xs text-gray-500 mb-1">Key Findings</p>
                          {event.key_findings && event.key_findings.length > 0 ? (
                            <div className="space-y-1">
                              {parseKeyFindings(event.key_findings).map((finding, idx) => (
                                <div key={idx} className="flex gap-2 items-start">
                                  <span className="text-gray-400 flex-shrink-0 text-xs leading-none mt-[0.1rem]">•</span>
                                  <p className="text-xs text-gray-900 flex-1 leading-normal">{finding}</p>
                                </div>
                              ))}
                            </div>
                          ) : (
                            <p className="text-xs text-gray-900">No key findings recorded</p>
                          )}
                        </div>
                      </div>
                    </div>
                  </div>
                  )}
                </div>
              );
            })
          )}
        </div>

        {/* Pagination Controls */}
        {(hasMore || canShowLess) && (
          <div className="mt-8 pt-6 border-t border-slate-200">
            <div className="flex flex-col items-center gap-4">
              <div className="flex flex-row items-center gap-3">
                {hasMore && (
                  <button
                    onClick={() => setVisibleTimelineCount((prev: number) => Math.min(prev + 5, totalTimelineEntries))}
                    className="flex flex-row items-center gap-2 px-6 py-3 bg-gradient-to-r from-blue-600 to-blue-700 hover:from-blue-700 hover:to-blue-800 text-white text-sm font-semibold rounded-lg transition-all duration-200 shadow-md hover:shadow-lg transform hover:-translate-y-0.5 active:translate-y-0"
                  >
                    <span className="leading-none">Show More</span>
                    <ChevronDown className="w-4 h-4 flex-shrink-0" strokeWidth={2.5} />
                  </button>
                )}
                {canShowLess && (
                  <button
                    onClick={() => setVisibleTimelineCount(5)}
                    className="flex flex-row items-center gap-2 px-6 py-3 bg-gradient-to-r from-blue-600 to-blue-700 hover:from-blue-700 hover:to-blue-800 text-white text-sm font-semibold rounded-lg transition-all duration-200 shadow-md hover:shadow-lg transform hover:-translate-y-0.5 active:translate-y-0"
                  >
                    <ChevronUp className="w-4 h-4 flex-shrink-0" strokeWidth={2.5} />
                    <span className="leading-none">Show Less</span>
                  </button>
                )}
              </div>
              <div className="flex flex-row items-center gap-2 px-4 py-2 bg-slate-100 rounded-full">
                <span className="text-sm text-gray-600">Showing</span>
                <span className="text-sm font-bold text-blue-600">{visibleTimelineCount}</span>
                <span className="text-sm text-gray-500">of</span>
                <span className="text-sm font-bold text-gray-900">{totalTimelineEntries}</span>
                <span className="text-sm text-gray-600">entries</span>
              </div>
            </div>
          </div>
        )}

        {/* Disease Course Duration */}
        {diagnosisFooter && (
          <div className="mt-6 pt-4 border-t border-slate-300">
            <p className="text-sm text-gray-800 text-center">
              {/* Check if there's a relapse duration from backend */}
              {diagnosisFooter.duration_since_relapse && diagnosisFooter.duration_since_relapse !== 'N/A' ? (
                <>
                  <span className="font-semibold">Duration since relapse:</span> {diagnosisFooter.duration_since_relapse}
                  {diagnosisFooter.duration_since_progression && diagnosisFooter.duration_since_progression !== 'N/A' && (
                    <> | <span className="font-semibold">Duration since progression:</span> {diagnosisFooter.duration_since_progression}</>
                  )}
                </>
              ) : (
                <>
                  <span className="font-semibold">Duration since diagnosis:</span> {diagnosisFooter.duration_since_diagnosis || 'N/A'}
                  {diagnosisFooter.duration_since_progression && diagnosisFooter.duration_since_progression !== 'N/A' && (
                    <> | <span className="font-semibold">Duration since progression:</span> {diagnosisFooter.duration_since_progression}</>
                  )}
                </>
              )}
            </p>
          </div>
        )}
      </div>
    </div>
  );
}
