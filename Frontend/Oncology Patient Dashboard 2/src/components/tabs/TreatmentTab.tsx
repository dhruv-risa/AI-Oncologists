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
    return treatment.header.line_number.toString().toLowerCase().includes('adjuvant');
  };

  // Helper function to get discontinuation reason or ongoing status
  const getDiscontinuationReason = (treatment: any) => {
    const isOngoing = treatment.dates?.end_date === 'Ongoing' ||
                      treatment.header?.status_badge?.toLowerCase().includes('current') ||
                      treatment.header?.status_badge?.toLowerCase().includes('ongoing');

    if (isOngoing) {
      return 'Ongoing treatment';
    }

    return treatment.reason_for_discontinuation || null;
  };

  // Function to nest adjuvant therapies inside their corresponding lines based on dates
  const nestAdjuvantTherapies = (treatments: any[]) => {
    const adjuvantTherapies: any[] = [];
    const mainLines: any[] = [];

    // Separate adjuvant and non-adjuvant therapies
    treatments.forEach(treatment => {
      if (isAdjuvant(treatment)) {
        adjuvantTherapies.push(treatment);
      } else {
        mainLines.push({ ...treatment, adjuvant_therapies: [] });
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

    return mainLines;
  };

  // Process and nest adjuvant therapies
  const processedTreatments = nestAdjuvantTherapies([...rawTreatmentHistory]);

  // Sort treatment history: Current first, then by start date (most recent first)
  const treatmentHistory = processedTreatments.sort((a, b) => {
    // Current treatments always come first
    const aIsCurrent = a.header.status_badge.toLowerCase().includes('current');
    const bIsCurrent = b.header.status_badge.toLowerCase().includes('current');

    if (aIsCurrent && !bIsCurrent) return -1;
    if (!aIsCurrent && bIsCurrent) return 1;

    // Otherwise sort by start date (most recent first)
    const aDate = new Date(a.dates.start_date);
    const bDate = new Date(b.dates.start_date);
    return bDate.getTime() - aDate.getTime();
  });

  // Helper function to get response tag color
  const getResponseColor = (responseTag: string) => {
    if (!responseTag) return 'bg-gray-100 border-gray-200 text-gray-700';
    const tag = responseTag.toLowerCase();
    if (tag.includes('complete response') || tag.includes('cr')) {
      return 'bg-emerald-100 border-emerald-200 text-emerald-700';
    }
    if (tag.includes('partial response') || tag.includes('pr')) {
      return 'bg-green-100 border-green-200 text-green-700';
    }
    if (tag.includes('stable disease') || tag.includes('sd')) {
      return 'bg-blue-100 border-blue-200 text-blue-700';
    }
    if (tag.includes('progressive disease') || tag.includes('pd')) {
      return 'bg-red-100 border-red-200 text-red-700';
    }
    return 'bg-gray-100 border-gray-200 text-gray-700';
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
              treatmentHistory.map((treatment, index) => {
                const hasAdjuvants = treatment.adjuvant_therapies && treatment.adjuvant_therapies.length > 0;

                return (
                  <div
                    key={index}
                    className="bg-white border border-gray-300 rounded-lg p-5 shadow-sm"
                  >
                    {/* Main line of therapy */}
                    <div className={hasAdjuvants ? 'pb-4' : ''}>
                      <div className="flex items-center justify-between mb-3">
                        <div className="flex items-center gap-3">
                          <p className="text-gray-900 font-medium">
                            Line {treatment.header.line_number} - {treatment.header.primary_drug_name}
                          </p>
                          <span className={`px-2 py-1 rounded text-xs ${getStatusBadgeStyle(treatment.header.status_badge)}`}>
                            {treatment.header.status_badge}
                          </span>
                          {hasAdjuvants && (
                            <span className="px-2 py-1 bg-purple-600 text-white rounded text-xs font-medium">
                              {treatment.adjuvant_therapies.length} Adjuvant{treatment.adjuvant_therapies.length > 1 ? 's' : ''}
                            </span>
                          )}
                        </div>
                        <span className={`px-2 py-1 border rounded text-xs ${getResponseColor(treatment.outcome?.response_tag || '')}`}>
                          {treatment.outcome?.response_tag || 'N/A'}
                        </span>
                      </div>

                      <p className="text-sm text-gray-600 mb-3">
                        {treatment.dates?.display_text || 'Date not available'}
                      </p>

                      <div className="grid grid-cols-2 gap-4 mb-3">
                        <div>
                          <p className="text-xs text-gray-500 mb-1">Regimen</p>
                          <p className="text-sm text-gray-900">
                            {treatment.regimen_details?.display_name || 'N/A'}
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

                      {treatment.outcome?.details && (
                        <div className="mb-3">
                          <p className="text-xs text-gray-500 mb-1">Response Details</p>
                          <p className="text-sm text-gray-900">{treatment.outcome.details}</p>
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
                    </div>

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

                            <p className="text-sm text-gray-600 mb-3">
                              {adjuvant.dates?.display_text || 'Date not available'}
                            </p>

                            <div className="grid grid-cols-2 gap-4 mb-3">
                              <div>
                                <p className="text-xs text-gray-500 mb-1">Regimen</p>
                                <p className="text-sm text-gray-900">
                                  {adjuvant.regimen_details?.display_name || 'N/A'}
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

                            {adjuvant.outcome?.details && (
                              <div className="mb-3">
                                <p className="text-xs text-gray-500 mb-1">Response Details</p>
                                <p className="text-sm text-gray-900">{adjuvant.outcome.details}</p>
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
              })
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
            timelineEvents.map((event, index) => (
              <div key={index} className="flex items-start gap-4">
                <div className="w-24 flex-shrink-0 text-xs text-gray-600">
                  {event.date_display}
                </div>
                <div className="flex-1">
                  <div className="bg-gray-50 border-l-2 border-gray-900 p-3 rounded-r-lg">
                    <div className="flex items-center gap-2 mb-1">
                      <p className="text-sm text-gray-900 font-medium">{event.title}</p>
                      {event.event_type && (
                        <span className="px-2 py-0.5 bg-blue-100 text-blue-700 rounded text-xs">
                          {event.event_type}
                        </span>
                      )}
                    </div>
                    <p className="text-xs text-gray-600">{event.subtitle}</p>
                  </div>
                </div>
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  );
}
