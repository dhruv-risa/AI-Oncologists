import { PatientData } from '../services/api';

interface DiseaseSummaryProps {
  patient: PatientData;
}

export function DiseaseSummary({ patient }: DiseaseSummaryProps) {
  // Use diagnosis_header for consistency with DiagnosisTab
  const cancerType = patient.diagnosis_header?.primary_diagnosis || 'Not specified';
  const histology = patient.diagnosis_header?.histologic_type || 'Not specified';
  const diagnosisDate = patient.diagnosis_header?.diagnosis_date || 'Unknown';

  // Derive current TNM and Stage from timeline (most recent entry) or fall back to header
  const timeline = patient.diagnosis_evolution_timeline?.timeline || [];
  const currentStaging = timeline.length > 0
    ? {
        tnm: timeline[0]?.tnm_status || 'N/A',
        ajcc_stage: timeline[0]?.stage_header || 'N/A'
      }
    : {
        tnm: patient.diagnosis_header?.current_staging?.tnm || 'N/A',
        ajcc_stage: patient.diagnosis_header?.current_staging?.ajcc_stage || 'N/A'
      };

  const tnmClassification = currentStaging.tnm;
  const ajccStage = currentStaging.ajcc_stage;

  // Line of therapy comes from treatment tab (current line)
  const currentTreatmentLine = patient.treatment_tab_info_LOT?.treatment_history?.find(
    (treatment: any) => treatment.header?.status_badge === 'Current'
  );
  const lineOfTherapy = currentTreatmentLine?.header?.line_number || 'N/A';

  // Use metastatic sites from diagnosis_header to match the diagnosis header display
  const metastaticSites = patient.diagnosis_header?.metastatic_sites || [];
  const ecogStatus = patient.diagnosis?.ecog_status || 'N/A';
  const diseaseStatus = patient.diagnosis?.disease_status || 'N/A';

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

      <div className="grid grid-cols-4 gap-4">
        <div className="bg-white/10 backdrop-blur-sm rounded-lg p-4 border border-white/20">
          <p className="text-xs text-slate-300 mb-1">TNM Classification</p>
          <p className="text-white">{tnmClassification}</p>
        </div>
        <div className="bg-white/10 backdrop-blur-sm rounded-lg p-4 border border-white/20">
          <p className="text-xs text-slate-300 mb-1">Metastatic Sites</p>
          <div className="flex gap-1.5 flex-wrap">
            {metastaticSites.length > 0 ? (
              metastaticSites.map((site, idx) => (
                <span key={idx} className="text-xs bg-red-500/30 border border-red-400/40 px-2 py-1 rounded text-red-100">
                  {site}
                </span>
              ))
            ) : (
              <span className="text-white text-sm">None</span>
            )}
          </div>
        </div>
        <div className="bg-white/10 backdrop-blur-sm rounded-lg p-4 border border-white/20">
          <p className="text-xs text-slate-300 mb-1">ECOG Status</p>
          <p className="text-white">{ecogStatus}</p>
        </div>
        <div className="bg-white/10 backdrop-blur-sm rounded-lg p-4 border border-white/20">
          <p className="text-xs text-slate-300 mb-1">Disease Status</p>
          <p className="text-white">{diseaseStatus}</p>
        </div>
      </div>
    </div>
  );
}
