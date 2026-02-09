import { Activity } from 'lucide-react';
import { PatientData } from '../../services/api';

interface TreatmentTabProps {
  patientData: PatientData | null;
}

export function TreatmentTab({ patientData }: TreatmentTabProps) {
  if (!patientData) {
    return (
      <div className="bg-white border border-t-0 border-gray-200 p-6">
        <p className="text-gray-500 text-center">No patient data available</p>
      </div>
    );
  }

  const rawTreatmentHistory = patientData.treatment_tab_info_LOT?.treatment_history || [];
  const timelineEvents = patientData.treatment_tab_info_timeline?.timeline_events || [];

  // Helper function to check if treatment is adjuvant
  const isAdjuvant = (treatment: any) => {
    return treatment.header?.line_number?.toString().toLowerCase().includes('adjuvant') || false;
  };

  // Helper function to check if treatment is local therapy only
  const isLocalTherapyOnly = (treatment: any) => {
    return treatment.local_therapy && !treatment.systemic_regimen && !treatment.regimen_details?.display_name;
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

  // Helper function to format date display (single date if start and end are the same)
  const formatDateDisplay = (treatment: any) => {
    const displayText = treatment.dates?.display_text;
    const startDate = treatment.dates?.start_date;
    const endDate = treatment.dates?.end_date;

    if (!displayText) return '';

    // Check if display text contains an arrow
    const arrowIndex = displayText.indexOf('->');
    if (arrowIndex > 0) {
      const firstPart = displayText.substring(0, arrowIndex).trim();
      const secondPart = displayText.substring(arrowIndex + 2).trim();

      // If both parts are identical (same date repeated), show only once
      if (firstPart === secondPart) {
        return firstPart;
      }

      // If backend dates are the same (and not Ongoing/NA), show only first date
      if (startDate && endDate &&
          startDate === endDate &&
          startDate !== 'Ongoing' &&
          startDate !== 'NA' &&
          endDate !== 'Ongoing' &&
          endDate !== 'NA') {
        return firstPart;
      }
    }

    return displayText;
  };

  // Helper function to check if dates should be displayed
  const shouldShowDates = (treatment: any) => {
    const displayText = treatment.dates?.display_text;
    const startDate = treatment.dates?.start_date;

    // Don't show dates if display_text is missing or invalid
    if (!displayText || displayText === 'NA' || displayText === 'Date not available') {
      return false;
    }

    // Don't show dates if they contain "NA ->" (e.g., "NA -> Ongoing", "NA -> NA")
    if (displayText.includes('NA ->') || displayText.includes('NA->')) {
      return false;
    }

    // Don't show dates if start_date is NA or missing
    if (!startDate || startDate === 'NA' || startDate === 'N/A') {
      return false;
    }

    return true;
  };

  // Helper function to check if clinical details should be displayed
  const shouldShowClinicalDetails = (treatment: any) => {
    const details = treatment.outcome?.details;
    if (!details || details === 'NA' || details.trim() === '' ||
        details.toLowerCase().includes('treatment planned but not yet started')) {
      return false;
    }
    return true;
  };

  // Helper function to check if response badge should be displayed
  const shouldShowResponseBadge = (treatment: any) => {
    const responseTag = treatment.outcome?.response_tag;
    if (!responseTag || responseTag === 'NA' || responseTag.trim() === '') {
      return false;
    }
    return true;
  };

  // Helper function to get discontinuation reason (only for discontinued treatments)
  const getDiscontinuationReason = (treatment: any) => {
    const status = treatment.header?.status_badge?.toLowerCase() || '';

    // Don't show discontinuation reason for ongoing, current, or planned treatments
    if (status.includes('current') ||
        status.includes('ongoing') ||
        status.includes('planned') ||
        treatment.dates?.end_date === 'Ongoing') {
      return null;
    }

    // Only return reason if it exists and is not "NA" or empty
    const reason = treatment.reason_for_discontinuation;
    if (reason && reason !== 'NA' && reason.trim() !== '') {
      return reason;
    }

    return null;
  };

  // Function to nest adjuvant therapies inside their corresponding lines based on dates
  const nestAdjuvantTherapies = (treatments: any[]) => {
    const adjuvantTherapies: any[] = [];
    const localTherapies: any[] = [];
    const mainLines: any[] = [];

    // Separate adjuvant, local therapy only, and regular therapies
    treatments.forEach(treatment => {
      if (isAdjuvant(treatment)) {
        adjuvantTherapies.push(treatment);
      } else if (isLocalTherapyOnly(treatment)) {
        localTherapies.push(treatment);
      } else {
        mainLines.push({ ...treatment, adjuvant_therapies: [], regimen_modifications: [] });
      }
    });

    // Match each adjuvant to its parent line based on dates
    adjuvantTherapies.forEach(adjuvant => {
      const adjuvantStart = adjuvant.dates?.start_date;

      if (!adjuvantStart || adjuvantStart === 'Ongoing') {
        // If no valid date, add to the most recent line
        if (mainLines.length > 0) {
          mainLines[0].adjuvant_therapies.push(adjuvant);
        }
        return;
      }

      try {
        const adjuvantDate = new Date(adjuvantStart);
        let matched = false;

        // Find the line whose date range contains this adjuvant's start date
        for (const line of mainLines) {
          const lineStart = line.dates?.start_date;
          const lineEnd = line.dates?.end_date;

          if (!lineStart) continue;

          try {
            const lineStartDate = new Date(lineStart);

            // If line is ongoing or end date is missing, check if adjuvant is after line start
            if (!lineEnd || lineEnd === 'Ongoing') {
              if (adjuvantDate >= lineStartDate) {
                line.adjuvant_therapies.push(adjuvant);
                matched = true;
                break;
              }
            } else {
              const lineEndDate = new Date(lineEnd);
              if (adjuvantDate >= lineStartDate && adjuvantDate <= lineEndDate) {
                line.adjuvant_therapies.push(adjuvant);
                matched = true;
                break;
              }
            }
          } catch (e) {
            continue;
          }
        }

        // If no match found, add to the closest line (by start date proximity)
        if (!matched && mainLines.length > 0) {
          let closestLine = null;
          let minDiff = Infinity;

          for (const line of mainLines) {
            const lineStart = line.dates?.start_date;
            if (lineStart) {
              try {
                const lineStartDate = new Date(lineStart);
                const diff = Math.abs(adjuvantDate.getTime() - lineStartDate.getTime());
                if (diff < minDiff) {
                  minDiff = diff;
                  closestLine = line;
                }
              } catch (e) {
                continue;
              }
            }
          }

          if (closestLine) {
            closestLine.adjuvant_therapies.push(adjuvant);
          }
        }
      } catch (e) {
        // If date parsing fails, add to the most recent line
        if (mainLines.length > 0) {
          mainLines[0].adjuvant_therapies.push(adjuvant);
        }
      }
    });

    // Group treatments by line number to handle regimen modifications
    const lineNumberGroups: { [key: string]: any[] } = {};
    mainLines.forEach(line => {
      const lineNum = line.header?.line_number?.toString() || 'unknown';
      if (!lineNumberGroups[lineNum]) {
        lineNumberGroups[lineNum] = [];
      }
      lineNumberGroups[lineNum].push(line);
    });

    // Process each group: first entry is main, rest are regimen modifications
    const consolidatedLines: any[] = [];
    Object.keys(lineNumberGroups).forEach(lineNum => {
      const group = lineNumberGroups[lineNum];

      if (group.length === 1) {
        // Single entry, just add it
        consolidatedLines.push(group[0]);
      } else {
        // Multiple entries with same line number - treat as regimen modifications
        // Sort by start date to get chronological order
        const sortedGroup = group.sort((a, b) => {
          const dateA = a.dates?.start_date;
          const dateB = b.dates?.start_date;
          if (!dateA || dateA === 'NA') return 1;
          if (!dateB || dateB === 'NA') return -1;
          try {
            return new Date(dateA).getTime() - new Date(dateB).getTime();
          } catch {
            return 0;
          }
        });

        // First entry is the main treatment
        const mainTreatment = sortedGroup[0];

        // Rest are regimen modifications
        mainTreatment.regimen_modifications = sortedGroup.slice(1);

        consolidatedLines.push(mainTreatment);
      }
    });

    return { mainLines: consolidatedLines, localTherapies };
  };

  // Process and nest adjuvant therapies
  const { mainLines: processedTreatments, localTherapies } = nestAdjuvantTherapies([...rawTreatmentHistory]);

  // Sort treatment history: Current first, then by line number (highest first)
  const treatmentHistory = processedTreatments.sort((a, b) => {
    // Current treatments always come first
    const aIsCurrent = a.header?.status_badge?.toLowerCase().includes('current') || false;
    const bIsCurrent = b.header?.status_badge?.toLowerCase().includes('current') || false;

    if (aIsCurrent && !bIsCurrent) return -1;
    if (!aIsCurrent && bIsCurrent) return 1;

    // Otherwise sort by line number (highest first)
    const aLineNum = parseInt(a.header?.line_number) || 0;
    const bLineNum = parseInt(b.header?.line_number) || 0;
    return bLineNum - aLineNum;
  });

  // Helper function to get response tag color
  const getResponseColor = (responseTag: string) => {
    if (!responseTag) return 'bg-gray-200 text-gray-800 font-medium';
    const tag = responseTag.toLowerCase();

    // Check for progressive disease FIRST (before partial response)
    // because "progressive" contains "pr" which would match partial response
    if (tag.includes('progressive disease') || tag.includes('progression') ||
        (tag.includes('pd') && !tag.includes('partial'))) {
      return 'bg-red-600 text-white font-medium';
    }
    if (tag.includes('excellent response')) {
      return 'bg-green-600 text-white font-medium';
    }
    if (tag.includes('complete response') || tag.includes('cr') || tag.includes('remission')) {
      return 'bg-emerald-500 text-white font-medium';
    }
    if (tag.includes('partial response') || tag.includes('pr')) {
      return 'bg-green-500 text-white font-medium';
    }
    if (tag.includes('stable disease') || tag.includes('sd')) {
      return 'bg-blue-500 text-white font-medium';
    }
    if (tag.includes('mixed response')) {
      return 'bg-yellow-500 text-white font-medium';
    }
    if (tag.includes('completed') || tag.includes('complete')) {
      return 'bg-gray-600 text-white font-medium';
    }
    return 'bg-gray-400 text-white font-medium';
  };

  // Helper function to get status badge color
  const getStatusBadgeStyle = (status: string) => {
    if (!status) return 'bg-gray-300 text-gray-700';
    const statusLower = status.toLowerCase();
    if (statusLower.includes('current') || statusLower.includes('ongoing')) {
      return 'bg-blue-600 text-white';
    }
    return 'bg-gray-300 text-gray-700';
  };

  // Helper function to get toxicity color
  const getToxicityColor = (grade: string) => {
    if (!grade) return 'bg-gray-100 text-gray-800';
    if (grade.includes('3') || grade.includes('4')) return 'bg-red-100 text-red-800';
    if (grade.includes('2')) return 'bg-amber-100 text-amber-800';
    return 'bg-yellow-100 text-yellow-800';
  };

  return (
    <div className="bg-white border border-t-0 border-gray-200 p-6">
      <div className="space-y-6 mb-6">
        {/* Lines of therapy */}
        <div>
          <div className="flex items-center gap-2 mb-4">
            <Activity className="w-4 h-4 text-gray-400" />
            <h3 className="text-gray-900">Lines of therapy</h3>
          </div>

          <div className="space-y-4">
            {treatmentHistory.length === 0 ? (
              <div className="text-center text-gray-500 py-8">
                No treatment history available
              </div>
            ) : (
              <>
                {treatmentHistory.map((treatment, index) => {
                  const hasAdjuvants = treatment.adjuvant_therapies && treatment.adjuvant_therapies.length > 0;
                  const hasRegimenModifications = treatment.regimen_modifications && treatment.regimen_modifications.length > 0;

                  return (
                    <div
                      key={index}
                      className="bg-white border border-gray-300 rounded-lg p-5 shadow-sm"
                    >
                      {/* Main line of therapy */}
                      <div className="flex items-center justify-between mb-3">
                        <div className="flex items-center gap-3">
                          <p className="text-gray-900 font-medium">
                            Line {treatment.header.line_number} - {treatment.header.primary_drug_name}
                          </p>
                          <span className={`px-2 py-1 rounded text-xs ${getStatusBadgeStyle(treatment.header.status_badge)}`}>
                            {treatment.header.status_badge}
                          </span>
                          {hasRegimenModifications && (
                            <span className="px-2 py-1 bg-amber-600 text-white rounded text-xs font-medium">
                              {treatment.regimen_modifications.length} Modification{treatment.regimen_modifications.length > 1 ? 's' : ''}
                            </span>
                          )}
                          {hasAdjuvants && (
                            <span className="px-2 py-1 bg-purple-600 text-white rounded text-xs font-medium">
                              {treatment.adjuvant_therapies.length} Adjuvant{treatment.adjuvant_therapies.length > 1 ? 's' : ''}
                            </span>
                          )}
                        </div>
                        {shouldShowResponseBadge(treatment) && (
                          <span className={`px-2.5 py-1 rounded-md text-xs ${getResponseColor(treatment.outcome?.response_tag || '')}`}>
                            {treatment.outcome?.response_tag}
                          </span>
                        )}
                      </div>

                      {shouldShowDates(treatment) && (
                        <p className="text-sm text-gray-600 mb-3">
                          {formatDateDisplay(treatment)}
                        </p>
                      )}

                      <div className="grid grid-cols-2 gap-4 mb-3">
                        <div>
                          <p className="text-xs text-gray-500 mb-1">Regimen</p>
                          <p className="text-sm text-gray-900">
                            {treatment.systemic_regimen || treatment.regimen_details?.display_name || 'N/A'}
                          </p>
                        </div>
                        <div>
                          <p className="text-xs text-gray-500 mb-1">Cycles completed</p>
                          <p className="text-sm text-gray-900">
                            {treatment.cycles_data?.display_text || 'N/A'}
                          </p>
                        </div>
                      </div>

                      {treatment.toxicities && treatment.toxicities.length > 0 && (
                        <div className="mb-3">
                          <p className="text-xs text-gray-500 mb-1">Toxicities</p>
                          <div className="flex flex-wrap gap-2">
                            {treatment.toxicities.map((toxicity: any, idx: number) => (
                              <span
                                key={idx}
                                className={`px-2 py-1 rounded text-xs ${getToxicityColor(toxicity.grade)}`}
                              >
                                {toxicity.display_tag}
                              </span>
                            ))}
                          </div>
                        </div>
                      )}

                      {shouldShowClinicalDetails(treatment) && (
                        <div className="mb-3">
                          <p className="text-xs text-gray-500 mb-1">Clinical Details</p>
                          <p className="text-sm text-gray-900 whitespace-pre-line">{treatment.outcome.details}</p>
                        </div>
                      )}

                      {(() => {
                        const reason = getDiscontinuationReason(treatment);
                        return reason ? (
                          <div>
                            <p className="text-xs text-gray-500 mb-1">Reason for discontinuation</p>
                            <p className="text-sm text-gray-900">{reason}</p>
                          </div>
                        ) : null;
                      })()}

                      {/* Regimen Modifications */}
                      {hasRegimenModifications && (
                        <div className="border-t-2 border-gray-200 pt-4 mt-4 space-y-3">
                          <div className="flex items-center gap-2 mb-3">
                            <div className="h-px flex-1 bg-gray-300"></div>
                            <span className="text-xs font-medium text-gray-600 uppercase tracking-wide">
                              Regimen Modifications ({treatment.regimen_modifications.length})
                            </span>
                            <div className="h-px flex-1 bg-gray-300"></div>
                          </div>

                          {treatment.regimen_modifications.map((modification: any, modIndex: number) => (
                            <div
                              key={modIndex}
                              className="bg-gradient-to-r from-amber-50 to-orange-50 border-l-4 border-amber-500 rounded-lg p-4 shadow-md"
                            >
                              <div className="flex items-center justify-between mb-3">
                                <div className="flex items-center gap-3">
                                  <span className="px-2 py-1 bg-amber-200 text-amber-800 rounded text-xs font-semibold">
                                    Modification {modIndex + 1}
                                  </span>
                                  <p className="text-amber-900 font-medium">
                                    {modification.header.primary_drug_name}
                                  </p>
                                  <span className={`px-2 py-1 rounded text-xs ${getStatusBadgeStyle(modification.header.status_badge)}`}>
                                    {modification.header.status_badge}
                                  </span>
                                </div>
                                {shouldShowResponseBadge(modification) && (
                                  <span className={`px-2.5 py-1 rounded-md text-xs ${getResponseColor(modification.outcome?.response_tag || '')}`}>
                                    {modification.outcome?.response_tag}
                                  </span>
                                )}
                              </div>

                              {shouldShowDates(modification) && (
                                <p className="text-sm text-gray-600 mb-3">
                                  {formatDateDisplay(modification)}
                                </p>
                              )}

                              <div className="grid grid-cols-2 gap-4 mb-3">
                                <div>
                                  <p className="text-xs text-gray-500 mb-1">Regimen</p>
                                  <p className="text-sm text-gray-900">
                                    {modification.systemic_regimen || modification.regimen_details?.display_name || 'N/A'}
                                  </p>
                                </div>
                                <div>
                                  <p className="text-xs text-gray-500 mb-1">Cycles completed</p>
                                  <p className="text-sm text-gray-900">
                                    {modification.cycles_data?.display_text || 'N/A'}
                                  </p>
                                </div>
                              </div>

                              {modification.toxicities && modification.toxicities.length > 0 && (
                                <div className="mb-3">
                                  <p className="text-xs text-gray-500 mb-1">Toxicities</p>
                                  <div className="flex flex-wrap gap-2">
                                    {modification.toxicities.map((toxicity: any, idx: number) => (
                                      <span
                                        key={idx}
                                        className={`px-2 py-1 rounded text-xs ${getToxicityColor(toxicity.grade)}`}
                                      >
                                        {toxicity.display_tag}
                                      </span>
                                    ))}
                                  </div>
                                </div>
                              )}

                              {shouldShowClinicalDetails(modification) && (
                                <div className="mb-3">
                                  <p className="text-xs text-gray-500 mb-1">Clinical Details</p>
                                  <p className="text-sm text-gray-900 whitespace-pre-line">{modification.outcome.details}</p>
                                </div>
                              )}

                              {(() => {
                                const reason = getDiscontinuationReason(modification);
                                return reason ? (
                                  <div>
                                    <p className="text-xs text-gray-500 mb-1">Reason for discontinuation</p>
                                    <p className="text-sm text-gray-900">{reason}</p>
                                  </div>
                                ) : null;
                              })()}
                            </div>
                          ))}
                        </div>
                      )}

                      {/* Nested adjuvant therapies */}
                      {hasAdjuvants && (
                      <div className="border-t-2 border-gray-200 pt-4 mt-4 space-y-3">
                        <div className="flex items-center gap-2 mb-3">
                          <div className="h-px flex-1 bg-gray-300"></div>
                          <span className="text-xs font-medium text-gray-600 uppercase tracking-wide">
                            Adjuvant Therapies ({treatment.adjuvant_therapies.length})
                          </span>
                          <div className="h-px flex-1 bg-gray-300"></div>
                        </div>

                        {treatment.adjuvant_therapies.map((adjuvant: any, adjIndex: number) => (
                          <div
                            key={adjIndex}
                            className="bg-gradient-to-r from-indigo-50 to-purple-50 border-l-4 border-indigo-500 rounded-lg p-4 shadow-md"
                          >
                            <div className="flex items-center justify-between mb-3">
                              <div className="flex items-center gap-3">
                                <span className="px-2 py-1 bg-purple-200 text-purple-800 rounded text-xs font-semibold">
                                  Adjuvant {adjIndex + 1}
                                </span>
                                <p className="text-purple-900 font-medium">
                                  {adjuvant.header.primary_drug_name}
                                </p>
                                <span className={`px-2 py-1 rounded text-xs ${getStatusBadgeStyle(adjuvant.header.status_badge)}`}>
                                  {adjuvant.header.status_badge}
                                </span>
                              </div>
                            </div>

                            {shouldShowDates(adjuvant) && (
                              <p className="text-sm text-gray-600 mb-3">
                                {formatDateDisplay(adjuvant)}
                              </p>
                            )}

                            <div className="grid grid-cols-2 gap-4 mb-3">
                              <div>
                                <p className="text-xs text-gray-500 mb-1">Regimen</p>
                                <p className="text-sm text-gray-900">
                                  {adjuvant.systemic_regimen || adjuvant.regimen_details?.display_name || 'N/A'}
                                </p>
                              </div>
                              <div>
                                <p className="text-xs text-gray-500 mb-1">Cycles completed</p>
                                <p className="text-sm text-gray-900">
                                  {adjuvant.cycles_data?.display_text || 'N/A'}
                                </p>
                              </div>
                            </div>

                            {adjuvant.toxicities && adjuvant.toxicities.length > 0 && (
                              <div className="mb-3">
                                <p className="text-xs text-gray-500 mb-1">Toxicities</p>
                                <div className="flex flex-wrap gap-2">
                                  {adjuvant.toxicities.map((toxicity: any, idx: number) => (
                                    <span
                                      key={idx}
                                      className={`px-2 py-1 rounded text-xs ${getToxicityColor(toxicity.grade)}`}
                                    >
                                      {toxicity.display_tag}
                                    </span>
                                  ))}
                                </div>
                              </div>
                            )}

                            {shouldShowClinicalDetails(adjuvant) && (
                              <div className="mb-3">
                                <p className="text-xs text-gray-500 mb-1">Clinical Details</p>
                                <p className="text-sm text-gray-900 whitespace-pre-line">{adjuvant.outcome.details}</p>
                              </div>
                            )}

                            {(() => {
                              const reason = getDiscontinuationReason(adjuvant);
                              return reason ? (
                                <div>
                                  <p className="text-xs text-gray-500 mb-1">Reason for discontinuation</p>
                                  <p className="text-sm text-gray-900">{reason}</p>
                                </div>
                              ) : null;
                            })()}
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                  );
                })}

                {/* Local Therapy Standalone Cards */}
                {localTherapies.map((therapy, index) => {
                  const { therapyType, site } = parseLocalTherapy(therapy.local_therapy);

                  return (
                    <div
                      key={`local-${index}`}
                      className="bg-white border border-purple-400 rounded-lg p-5 shadow-sm"
                    >
                      <div className="flex items-center justify-between mb-3">
                        <div className="flex items-center gap-3">
                          <p className="text-gray-900 font-medium">
                            {therapy.header.primary_drug_name || 'Local Therapy'}
                          </p>
                          <span className={`px-2 py-1 rounded text-xs ${getStatusBadgeStyle(therapy.header.status_badge)}`}>
                            {therapy.header.status_badge}
                          </span>
                          <span className="px-2 py-1 bg-purple-600 text-white rounded text-xs font-medium">
                            Local Therapy
                          </span>
                        </div>
                        {shouldShowResponseBadge(therapy) && (
                          <span className={`px-2.5 py-1 rounded-md text-xs ${getResponseColor(therapy.outcome?.response_tag || '')}`}>
                            {therapy.outcome?.response_tag}
                          </span>
                        )}
                      </div>

                      {shouldShowDates(therapy) && (
                        <p className="text-sm text-gray-600 mb-3">
                          {therapy.dates?.display_text}
                        </p>
                      )}

                      <div className="grid grid-cols-2 gap-4 mb-3">
                        <div>
                          <p className="text-xs text-gray-500 mb-1">Therapy Type</p>
                          <p className="text-sm text-gray-900">
                            {therapyType}
                          </p>
                        </div>
                        <div>
                          <p className="text-xs text-gray-500 mb-1">Site / Target Area</p>
                          <p className="text-sm text-gray-900">
                            {site}
                          </p>
                        </div>
                      </div>

                      {therapy.toxicities && therapy.toxicities.length > 0 && (
                        <div className="mb-3">
                          <p className="text-xs text-gray-500 mb-1">Toxicities</p>
                          <div className="flex flex-wrap gap-2">
                            {therapy.toxicities.map((toxicity: any, idx: number) => (
                              <span
                                key={idx}
                                className={`px-2 py-1 rounded text-xs ${getToxicityColor(toxicity.grade)}`}
                              >
                                {toxicity.display_tag}
                              </span>
                            ))}
                          </div>
                        </div>
                      )}

                      {shouldShowClinicalDetails(therapy) && (
                        <div className="mb-3">
                          <p className="text-xs text-gray-500 mb-1">Clinical Details</p>
                          <p className="text-sm text-gray-900 whitespace-pre-line">{therapy.outcome.details}</p>
                        </div>
                      )}

                      {(() => {
                        const reason = getDiscontinuationReason(therapy);
                        return reason ? (
                          <div>
                            <p className="text-xs text-gray-500 mb-1">Reason for discontinuation</p>
                            <p className="text-sm text-gray-900">{reason}</p>
                          </div>
                        ) : null;
                      })()}
                    </div>
                  );
                })}
              </>
            )}
          </div>
        </div>
      </div>

      <div className="pt-6 border-t border-gray-200">
        <h3 className="text-gray-900 mb-4">Treatment Timeline</h3>
        <div className="space-y-3">
          {timelineEvents.length === 0 ? (
            <div className="text-center text-gray-500 py-8">
              No timeline events available
            </div>
          ) : (
            timelineEvents.map((event, index) => {
              // Use the backend's data structure:
              // - systemic_regimen for drug treatments
              // - local_therapy for radiation/surgery
              // - details for description

              // Determine fallback based on event type
              const getFallbackTitle = (eventType?: string) => {
                const type = eventType?.toLowerCase() || '';
                if (type.includes('systemic')) return 'Systemic Therapy';
                if (type.includes('radiation')) return 'Radiation Therapy';
                if (type.includes('surgery')) return 'Surgical Procedure';
                if (type.includes('imaging')) return 'Diagnostic Imaging';
                return 'Clinical Event';
              };

              const eventTitle = event.systemic_regimen ||
                                event.local_therapy ||
                                event.title ||
                                getFallbackTitle(event.event_type);
              const eventDescription = event.details || event.subtitle || '';

              return (
                <div key={index} className="flex items-start gap-4">
                  <div className="w-24 flex-shrink-0 text-xs text-gray-600">
                    {event.date_display}
                  </div>
                  <div className="flex-1">
                    <div className="bg-gray-50 border-l-2 border-gray-900 p-3 rounded-r-lg">
                      <div className="flex items-center gap-2 mb-1">
                        <p className="text-sm text-gray-900 font-medium">
                          {eventTitle}
                        </p>
                        {event.event_type && (
                          <span className="px-2 py-0.5 bg-blue-100 text-blue-700 rounded text-xs">
                            {event.event_type}
                          </span>
                        )}
                      </div>

                      {eventDescription && (
                        <p className="text-xs text-gray-600">{eventDescription}</p>
                      )}
                    </div>
                  </div>
                </div>
              );
            })
          )}
        </div>
      </div>
    </div>
  );
}
