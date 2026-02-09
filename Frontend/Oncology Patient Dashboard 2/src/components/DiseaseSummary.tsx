import { PatientData } from '../services/api';

interface DiseaseSummaryProps {
  patient: PatientData;
}

export function DiseaseSummary({ patient }: DiseaseSummaryProps) {
  // Use diagnosis_header for consistency with DiagnosisTab
  const cancerType = patient.diagnosis_header?.primary_diagnosis || 'Not specified';
  const rawHistology = patient.diagnosis_header?.histologic_type;
  const histology = (rawHistology && rawHistology !== 'N/A' && rawHistology !== 'NA') ? rawHistology : 'Not specified';
  const diagnosisDate = patient.diagnosis_header?.diagnosis_date || 'Unknown';

  // Derive current TNM and Stage from timeline (most recent entry) or fall back to header
  const timeline = patient.diagnosis_evolution_timeline?.timeline || [];

  // Sort timeline by date (most recent first) and find first entry with valid staging data
  const sortedTimeline = [...timeline].sort((a, b) => {
    const parseDate = (dateStr: string) => {
      if (!dateStr) return new Date(0);
      if (dateStr.toLowerCase().includes('current')) return new Date();

      const monthNames = ['january', 'february', 'march', 'april', 'may', 'june',
                          'july', 'august', 'september', 'october', 'november', 'december'];
      const lowerStr = dateStr.toLowerCase().trim();

      for (let i = 0; i < monthNames.length; i++) {
        if (lowerStr.startsWith(monthNames[i])) {
          const yearMatch = dateStr.match(/\d{4}/);
          if (yearMatch) return new Date(parseInt(yearMatch[0]), i, 1);
        }
      }

      const date = new Date(dateStr);
      return !isNaN(date.getTime()) ? date : new Date(0);
    };

    return parseDate(b.date_label).getTime() - parseDate(a.date_label).getTime();
  });

  // Find first timeline entry with valid staging data
  const currentTimelineEntry = sortedTimeline.find(entry =>
    entry.tnm_status && entry.tnm_status !== 'NA' && entry.tnm_status !== 'N/A'
  );

  const currentStaging = currentTimelineEntry
    ? {
        tnm: currentTimelineEntry.tnm_status || 'N/A',
        ajcc_stage: currentTimelineEntry.stage_header || 'N/A'
      }
    : {
        tnm: patient.diagnosis_header?.current_staging?.tnm || 'N/A',
        ajcc_stage: patient.diagnosis_header?.current_staging?.ajcc_stage || 'N/A'
      };

  // Format TNM and Stage for display with better messaging
  const formatStageDisplay = (stage: string) => {
    if (stage === 'Pre-diagnosis finding') return 'Pre-diagnosis';
    if (stage === 'Staging not performed') return 'Not staged';
    if (stage === 'N/A' || !stage) return 'Not documented';
    return stage;
  };

  const formatTNMDisplay = (tnm: string, stage: string) => {
    // If stage indicates no staging was done, don't show TNM
    if (stage === 'Pre-diagnosis finding' || stage === 'Staging not performed') return 'Not applicable';
    if (tnm === 'N/A' || !tnm || tnm === 'NA') return 'TNM not documented';
    return tnm;
  };

  const tnmClassification = formatTNMDisplay(currentStaging.tnm, currentStaging.ajcc_stage);
  const ajccStage = formatStageDisplay(currentStaging.ajcc_stage);

  // Line of therapy comes from treatment tab (current line)
  const currentTreatmentLine = patient.treatment_tab_info_LOT?.treatment_history?.find(
    (treatment: any) => treatment.header?.status_badge === 'Current'
  );

  // Fallback strategy for line of therapy:
  // 1. Use current treatment line from treatment history
  // 2. Fall back to diagnosis.line_of_therapy if available
  // 3. Fall back to highest line number in treatment history
  // 4. Finally show N/A
  let lineOfTherapy: number | string = 'N/A';

  if (currentTreatmentLine?.header?.line_number) {
    lineOfTherapy = currentTreatmentLine.header.line_number;
  } else if (patient.diagnosis?.line_of_therapy &&
             patient.diagnosis.line_of_therapy !== 'NA' &&
             patient.diagnosis.line_of_therapy !== 'N/A') {
    lineOfTherapy = patient.diagnosis.line_of_therapy;
  } else if (patient.treatment_tab_info_LOT?.treatment_history?.length > 0) {
    // Find the highest line number from treatment history
    const treatmentHistory = patient.treatment_tab_info_LOT.treatment_history;
    const numericLines = treatmentHistory
      .filter((t: any) => typeof t.header?.line_number === 'number')
      .map((t: any) => t.header.line_number);
    if (numericLines.length > 0) {
      lineOfTherapy = Math.max(...numericLines);
    }
  }

  // Use metastatic sites from diagnosis_header to match the diagnosis header display
  const metastaticSites = patient.diagnosis_header?.metastatic_sites || [];
  const rawEcogStatus = patient.diagnosis?.ecog_status || 'N/A';
  const rawDiseaseStatus = patient.diagnosis?.disease_status || 'N/A';

  // Check if ECOG status is available (not NA/N/A/Not applicable)
  const hasEcogStatus = rawEcogStatus !== 'NA' && rawEcogStatus !== 'N/A' && rawEcogStatus !== 'Not applicable';

  // Format NA/N/A values to be more user-friendly
  const formatStatus = (status: string) => {
    if (status === 'NA' || status === 'N/A' || status === 'Not applicable') {
      return 'Not assessed';
    }
    return status;
  };

  const ecogStatus = rawEcogStatus;
  const diseaseStatus = formatStatus(rawDiseaseStatus);

  return (
    <div className="bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900 rounded-2xl p-6 text-white shadow-xl">
      <div className="flex items-start justify-between mb-6">
        <div>
          <div className="flex items-center gap-3 mb-2">
            <h1 className="text-white text-2xl">{cancerType}</h1>
          </div>
          <p className="text-slate-300 text-sm">{histology} · Diagnosed {diagnosisDate}</p>
        </div>
        <div className="flex gap-2">
          <div className="px-4 py-2 bg-red-500/20 border border-red-400/30 rounded-lg backdrop-blur-sm">
            <p className="text-xs text-red-200">Stage</p>
            <p className="text-red-100">{ajccStage}</p>
          </div>
          {lineOfTherapy !== 'NA' && (
            <div className="px-4 py-2 bg-blue-500/20 border border-blue-400/30 rounded-lg backdrop-blur-sm">
              <p className="text-xs text-blue-200">Line</p>
              <p className="text-blue-100">{lineOfTherapy}</p>
            </div>
          )}
        </div>
      </div>

      <div className={`grid gap-4 ${hasEcogStatus ? 'grid-cols-4' : 'grid-cols-3'}`}>
        <div className="bg-white/10 backdrop-blur-sm rounded-lg p-4 border border-white/20">
          <p className="text-xs text-slate-300 mb-1">TNM Classification</p>
          <p className="text-white">{tnmClassification}</p>
        </div>
        <div className="bg-white/10 backdrop-blur-sm rounded-lg p-4 border border-white/20">
          <p className="text-xs text-slate-300 mb-1">Metastatic Sites</p>
          <div className="flex gap-1.5 flex-wrap">
            {metastaticSites.length > 0 ? (
              metastaticSites.map((site, idx) => {
                const isUnspecified = site === "Sites not specified in report";
                return (
                  <span
                    key={idx}
                    className={`text-xs px-2 py-1 rounded ${
                      isUnspecified
                        ? 'bg-slate-500/40 text-slate-200'
                        : 'bg-red-500/30 border border-red-400/40 text-red-100'
                    }`}
                  >
                    {site}
                  </span>
                );
              })
            ) : (
              <span className="text-white text-sm">None</span>
            )}
          </div>
        </div>
        {hasEcogStatus && (
          <div className="bg-white/10 backdrop-blur-sm rounded-lg p-4 border border-white/20">
            <p className="text-xs text-slate-300 mb-1">ECOG Status</p>
            <p className="text-white">{ecogStatus}</p>
          </div>
        )}
        <div className="bg-white/10 backdrop-blur-sm rounded-lg p-4 border border-white/20">
          <p className="text-xs text-slate-300 mb-1">Disease Status</p>
          <p className="text-white">{diseaseStatus}</p>
        </div>
      </div>
    </div>
  );
}
