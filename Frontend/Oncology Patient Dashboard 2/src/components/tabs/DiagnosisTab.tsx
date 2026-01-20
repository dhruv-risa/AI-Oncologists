import { DataField } from '../DataField';
import { TrendingUp, Calendar, ArrowDown, Eye, Download, ExternalLink } from 'lucide-react';
import { PatientData } from '../../services/api';
import { formatDate } from '../../utils/dateFormatter';

interface DiagnosisTabProps {
  patientData: PatientData | null;
}

export function DiagnosisTab({ patientData }: DiagnosisTabProps) {
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

  // Sort timeline by date (most recent first) and limit to 5 most recent
  const diagnosisTimeline = [...rawDiagnosisTimeline].sort((a, b) => {
    // Try to parse dates from date_label
    const parseDate = (dateStr: string) => {
      if (!dateStr) return new Date(0);

      // Handle "Current Status" or similar labels - should be most recent
      if (dateStr && dateStr.toLowerCase().includes('current')) {
        return new Date(); // Current date (highest priority)
      }

      // Try to parse date formats like "March 2023", "June 2024", "2023-03", "March 12, 2023"
      const monthNames = ['january', 'february', 'march', 'april', 'may', 'june',
                          'july', 'august', 'september', 'october', 'november', 'december'];

      const lowerStr = dateStr.toLowerCase().trim();

      // Check for "Month Year" format (e.g., "March 2023")
      for (let i = 0; i < monthNames.length; i++) {
        if (lowerStr.startsWith(monthNames[i])) {
          const yearMatch = dateStr.match(/\d{4}/);
          if (yearMatch) {
            return new Date(parseInt(yearMatch[0]), i, 1);
          }
        }
      }

      // Try standard date parsing
      const date = new Date(dateStr);
      if (!isNaN(date.getTime())) {
        return date;
      }

      // Fallback: return epoch if can't parse (lowest priority)
      return new Date(0);
    };

    const aDate = parseDate(a.date_label);
    const bDate = parseDate(b.date_label);
    return bDate.getTime() - aDate.getTime(); // Most recent first
  }).slice(0, 5); // Limit to 5 most recent stages

  // Derive initial and current staging from timeline (timeline is sorted most recent first)
  const initialStaging = diagnosisTimeline.length > 0
    ? {
        tnm: diagnosisTimeline[diagnosisTimeline.length - 1]?.tnm_status || 'NA',
        ajcc_stage: diagnosisTimeline[diagnosisTimeline.length - 1]?.stage_header || 'N/A'
      }
    : diagnosisHeader?.initial_staging || { tnm: 'NA', ajcc_stage: 'N/A' };

  const currentStaging = diagnosisTimeline.length > 0
    ? {
        tnm: diagnosisTimeline[0]?.tnm_status || 'NA',
        ajcc_stage: diagnosisTimeline[0]?.stage_header || 'N/A'
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
    if (tnm === 'NA' || !tnm) {
      return stage || 'N/A';
    }
    return `${tnm} (${stage})`;
  };

  // Parse key findings into bullet points
  const parseKeyFindings = (findings: string[]) => {
    if (!findings || !Array.isArray(findings)) return [];
    return findings.filter(item => item && item.trim().length > 0);
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
          value={diagnosisHeader?.histologic_type || 'N/A'}
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
              const borderColor = isFirst ? 'border-red-500' : index === 1 ? 'border-orange-500' : 'border-blue-500';
              const bgColor = isFirst ? 'bg-red-500' : index === 1 ? 'bg-orange-500' : 'bg-blue-500';
              const statusLabel = isFirst ? 'Current Status' : formatDate(event.date_label);

              // Helper function to get toxicity color
              const getToxicityColor = (grade: string) => {
                if (!grade) return 'bg-gray-100 text-gray-800';
                if (grade.includes('3') || grade.includes('4')) return 'bg-red-100 text-red-800';
                if (grade.includes('2')) return 'bg-amber-100 text-amber-800';
                return 'bg-yellow-100 text-yellow-800';
              };

              return (
                <div key={index} className="relative">
                  <div className={`bg-white rounded-lg p-5 shadow-md border-2 ${borderColor}`}>
                    <div className={`absolute -left-3 top-1/2 -translate-y-1/2 ${isFirst ? 'w-5 h-5' : 'w-4 h-4'} ${bgColor} rounded-full border-4 border-white shadow-lg ${isFirst ? 'animate-pulse' : ''} z-10`}></div>
                    <div className="flex items-stretch gap-6">
                      {/* Stage Info */}
                      <div className="flex-shrink-0 w-48">
                        <div className={`inline-block ${bgColor} text-white px-2 py-0.5 rounded-full text-xs mb-2`}>
                          {statusLabel}
                        </div>
                        <h4 className="text-sm font-semibold text-gray-900 mb-1">
                          {event.stage_header || 'N/A'}
                        </h4>
                        <p className="text-xs text-gray-700 mb-1">
                          {event.tnm_status !== 'NA' ? event.tnm_status : ''}
                        </p>
                        <p className="text-xs text-gray-500">
                          {event.disease_status || ''}
                        </p>
                      </div>

                      {/* Treatment Details */}
                      <div className="flex-1 space-y-3 border-r border-gray-200 pr-6 self-stretch">
                        <div>
                          <p className="text-xs text-gray-500 mb-1">Regimen</p>
                          <p className="text-sm text-gray-900">
                            {event.regimen || 'N/A'}
                          </p>
                        </div>
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
                            <ul className="text-xs text-gray-900 space-y-1 pl-4">
                              {parseKeyFindings(event.key_findings).map((finding, idx) => (
                                <li key={idx} className="list-disc ml-1">{finding}</li>
                              ))}
                            </ul>
                          ) : (
                            <p className="text-xs text-gray-900">No key findings recorded</p>
                          )}
                        </div>
                      </div>
                    </div>
                  </div>
                </div>
              );
            })
          )}
        </div>

        {/* Disease Course Duration */}
        {diagnosisFooter && (
          <div className="mt-6 pt-4 border-t border-slate-300">
            <p className="text-sm text-gray-800 text-center">
              <span className="font-semibold">Duration since diagnosis:</span> {diagnosisFooter.duration_since_diagnosis || 'N/A'}
              {diagnosisFooter.duration_since_progression && diagnosisFooter.duration_since_progression !== 'N/A' && (
                <> | <span className="font-semibold">Duration since progression:</span> {diagnosisFooter.duration_since_progression}</>
              )}
            </p>
          </div>
        )}
      </div>
    </div>
  );
}
