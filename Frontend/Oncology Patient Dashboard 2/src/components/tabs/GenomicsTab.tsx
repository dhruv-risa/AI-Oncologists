import { Dna, Sparkles } from 'lucide-react';
import { usePatient } from '../../contexts/PatientContext';

interface DetectedDriverMutation {
  gene: string;
  status: string;
  details: string | null;
  is_target: boolean;
}

interface ImmunotherapyMarker {
  pd_l1?: {
    value: string;
    metric: string;
    interpretation: string;
  };
  tmb?: {
    value: string;
    interpretation: string;
  };
  msi_status?: {
    status: string;
    interpretation: string;
  };
}

interface GenomicInfo {
  detected_driver_mutations?: DetectedDriverMutation[];
  immunotherapy_markers?: ImmunotherapyMarker;
  additional_genomic_alterations?: Array<{
    gene: string;
    alteration: string;
    type: string;
    significance: string;
  }>;
}

export function GenomicsTab() {
  const { currentPatient } = usePatient();

  // Get genomics data from patient context
  const genomicInfo: GenomicInfo = currentPatient?.genomic_info || {};

  // Define standard driver genes panel
  const standardDriverGenes = ['EGFR', 'ALK', 'ROS1', 'KRAS', 'BRAF', 'MET', 'RET', 'HER2', 'NTRK'];

  // Create a map of detected driver mutations
  const detectedDriverMutationsMap = new Map();
  (genomicInfo?.detected_driver_mutations || []).forEach(mutation => {
    detectedDriverMutationsMap.set(mutation.gene, {
      gene: mutation.gene,
      mutation: mutation.details || 'Detected',
      status: mutation.status,
      actionable: mutation.is_target,
      type: 'Driver Mutation'
    });
  });

  // Build comprehensive panel: all standard genes with their status
  const driverGenesPanel = standardDriverGenes.map(gene => {
    if (detectedDriverMutationsMap.has(gene)) {
      return detectedDriverMutationsMap.get(gene);
    } else {
      return {
        gene: gene,
        mutation: 'Not detected',
        status: 'Not detected',
        actionable: false,
        type: 'Driver Mutation'
      };
    }
  });

  // Additional alterations (always detected)
  const additionalAlterations = (genomicInfo?.additional_genomic_alterations || []).map(alteration => ({
    gene: alteration.gene,
    mutation: alteration.alteration,
    status: 'Detected',
    actionable: false,
    type: alteration.type,
    significance: alteration.significance
  }));

  // Combine all: driver panel + additional alterations
  const allGenomicAlterations = [...driverGenesPanel, ...additionalAlterations];

  // For actionable mutations summary, only include detected ones
  const allDetectedMutations = allGenomicAlterations.filter(m => m.status !== 'Not detected');

  // Map biomarkers from backend data - always show all three markers
  const biomarkers = [];

  // PD-L1 Expression
  if (genomicInfo?.immunotherapy_markers?.pd_l1 &&
      genomicInfo.immunotherapy_markers.pd_l1.value &&
      genomicInfo.immunotherapy_markers.pd_l1.value !== 'null' &&
      genomicInfo.immunotherapy_markers.pd_l1.metric &&
      genomicInfo.immunotherapy_markers.pd_l1.metric !== 'null') {
    const pdl1 = genomicInfo.immunotherapy_markers.pd_l1;
    biomarkers.push({
      name: 'PD-L1 Expression',
      value: `${pdl1.value} (${pdl1.metric})`,
      available: true,
      highlight: true,
      color: 'purple'
    });
  } else {
    biomarkers.push({
      name: 'PD-L1 Expression',
      value: 'Not mentioned in document',
      available: false,
      highlight: true,
      color: 'purple'
    });
  }

  // TMB
  if (genomicInfo?.immunotherapy_markers?.tmb &&
      genomicInfo.immunotherapy_markers.tmb.value &&
      genomicInfo.immunotherapy_markers.tmb.value !== 'null') {
    const tmb = genomicInfo.immunotherapy_markers.tmb;
    biomarkers.push({
      name: 'TMB',
      value: tmb.value,
      available: true,
      highlight: false,
      color: 'blue'
    });
  } else {
    biomarkers.push({
      name: 'TMB',
      value: 'Not mentioned in document',
      available: false,
      highlight: false,
      color: 'blue'
    });
  }

  // MSI Status
  if (genomicInfo?.immunotherapy_markers?.msi_status &&
      genomicInfo.immunotherapy_markers.msi_status.status &&
      genomicInfo.immunotherapy_markers.msi_status.status !== 'null' &&
      genomicInfo.immunotherapy_markers.msi_status.interpretation &&
      genomicInfo.immunotherapy_markers.msi_status.interpretation !== 'null') {
    const msi = genomicInfo.immunotherapy_markers.msi_status;
    biomarkers.push({
      name: 'MSI Status',
      value: `${msi.status} (${msi.interpretation})`,
      available: true,
      highlight: false,
      color: 'gray'
    });
  } else {
    biomarkers.push({
      name: 'MSI Status',
      value: 'Not mentioned in document',
      available: false,
      highlight: false,
      color: 'gray'
    });
  }

  // Show message if no patient data
  if (!currentPatient) {
    return (
      <div className="bg-white border border-t-0 border-gray-200 rounded-b-lg shadow-sm p-6">
        <div className="text-center text-gray-500 py-8">
          No patient data available
        </div>
      </div>
    );
  }

  // Show message if no genomics data
  if (!genomicInfo || Object.keys(genomicInfo).length === 0) {
    return (
      <div className="bg-white border border-t-0 border-gray-200 rounded-b-lg shadow-sm p-6">
        <div className="text-center text-gray-500 py-8">
          No genomics data available for this patient
        </div>
      </div>
    );
  }

  // Find actionable mutations for the summary
  const actionableMutations = allDetectedMutations.filter(m => m.actionable);

  return (
    <div className="bg-white border border-t-0 border-gray-200 rounded-b-lg shadow-sm p-6">
      {/* All Detected Mutations Section */}
      <div className="mb-8">
        <div className="flex items-center gap-2 mb-5">
          <Dna className="w-5 h-5 text-indigo-600" />
          <h3 className="text-gray-900">Detected Genomic Alterations</h3>
          <span className="text-xs text-gray-500">NGS Panel</span>
        </div>

        {allGenomicAlterations.length > 0 ? (
          <div className="grid grid-cols-3 gap-3">
            {allGenomicAlterations.map((item, idx) => {
              const isDetected = item.status !== 'Not detected';

              return (
                <div
                  key={idx}
                  className={`p-4 rounded-lg border-2 transition-all ${
                    item.actionable
                      ? 'border-emerald-400 bg-gradient-to-br from-emerald-50 to-green-50 shadow-sm'
                      : isDetected
                      ? 'border-blue-300 bg-gradient-to-br from-blue-50 to-cyan-50'
                      : 'border-gray-200 bg-white'
                  }`}
                >
                  <div className="flex items-start justify-between mb-2">
                    <div className="flex items-center gap-2">
                      <p className={
                        item.actionable
                          ? 'text-emerald-950 font-semibold'
                          : isDetected
                          ? 'text-blue-950 font-semibold'
                          : 'text-gray-900 font-semibold'
                      }>
                        {item.gene}
                      </p>
                      {item.type !== 'Driver Mutation' && (
                        <span className="px-1.5 py-0.5 bg-gray-200 text-gray-700 rounded text-xs">
                          {item.type}
                        </span>
                      )}
                    </div>
                    {item.actionable && (
                      <span className="px-2 py-0.5 bg-emerald-600 text-white rounded text-xs flex items-center gap-1">
                        <Sparkles className="w-3 h-3" />
                        Target
                      </span>
                    )}
                  </div>
                  <p className="text-xs text-gray-700 mb-2">{item.mutation}</p>
                  {item.significance && (
                    <p className="text-xs text-gray-600 mb-2 italic">{item.significance}</p>
                  )}
                  <div className="flex items-center gap-2">
                    <div className={`w-2 h-2 rounded-full ${
                      isDetected ? 'bg-red-500' : 'bg-emerald-500'
                    }`}></div>
                    <p className={`text-xs font-medium ${
                      isDetected ? 'text-red-700' : 'text-emerald-700'
                    }`}>
                      {item.status}
                    </p>
                  </div>
                </div>
              );
            })}
          </div>
        ) : (
          <div className="text-center py-6 bg-gray-50 rounded-lg border border-gray-200">
            <p className="text-gray-500">No genomic alterations data available</p>
          </div>
        )}
      </div>

      {biomarkers.length > 0 && (
        <div className="mb-8 pb-8 border-b border-gray-200">
          <h3 className="text-gray-900 mb-4">Biomarkers & Immunotherapy Markers</h3>
          <div className="grid grid-cols-3 gap-4">
            {biomarkers.map((item, idx) => (
              <div
                key={idx}
                className={`p-5 rounded-lg border-2 ${
                  item.available
                    ? item.color === 'purple'
                      ? 'border-purple-300 bg-gradient-to-br from-purple-50 to-indigo-50'
                      : item.color === 'blue'
                      ? 'border-blue-200 bg-gradient-to-br from-blue-50 to-cyan-50'
                      : 'border-gray-200 bg-white'
                    : 'border-gray-200 bg-gray-50'
                }`}
              >
                <p className={`text-xs mb-2 ${
                  item.available
                    ? item.color === 'purple' ? 'text-purple-700' :
                      item.color === 'blue' ? 'text-blue-700' : 'text-gray-600'
                    : 'text-gray-500'
                }`}>
                  {item.name}
                </p>
                <p className={`text-sm ${
                  item.available
                    ? item.color === 'purple' ? 'text-purple-950' : 'text-gray-900'
                    : 'text-gray-500 italic'
                }`}>
                  {item.value}
                </p>
              </div>
            ))}
          </div>
        </div>
      )}

      {actionableMutations.length > 0 && (
        <div className="bg-gradient-to-r from-emerald-50 to-teal-50 border-2 border-emerald-300 rounded-xl p-6">
          <div className="flex items-start gap-4">
            <div className="w-12 h-12 bg-emerald-600 rounded-xl flex items-center justify-center flex-shrink-0">
              <Sparkles className="w-6 h-6 text-white" />
            </div>
            <div className="flex-1">
              <h4 className="text-emerald-950 mb-2">Actionable Therapy Summary</h4>
              <div className="space-y-3">
                {actionableMutations.map((mutation, idx) => (
                  <div key={idx}>
                    <p className="text-sm text-emerald-800 leading-relaxed">
                      <strong>{mutation.gene} {mutation.mutation}</strong> - This is an actionable target.
                      {mutation.gene === 'EGFR' && ' FDA-approved targeted therapies available including Osimertinib (Tagrisso) as first-line therapy, with Erlotinib and Afatinib as alternative options.'}
                      {mutation.gene === 'ALK' && ' FDA-approved ALK inhibitors available including Alectinib, Brigatinib, and Ceritinib.'}
                      {mutation.gene === 'ROS1' && ' FDA-approved ROS1 inhibitors available including Crizotinib and Entrectinib.'}
                      {mutation.gene === 'BRAF' && mutation.mutation.includes('V600E') && ' FDA-approved BRAF inhibitors available including Dabrafenib + Trametinib combination.'}
                      {mutation.gene === 'MET' && ' MET inhibitors such as Capmatinib or Tepotinib may be considered.'}
                      {mutation.gene === 'RET' && ' FDA-approved RET inhibitors available including Selpercatinib (Retevmo) and Pralsetinib.'}
                      {mutation.gene === 'HER2' && ' HER2-targeted therapies available including Trastuzumab Deruxtecan.'}
                      {mutation.gene === 'NTRK' && ' FDA-approved TRK inhibitors available including Larotrectinib and Entrectinib.'}
                    </p>
                  </div>
                ))}
                {genomicInfo?.immunotherapy_markers?.pd_l1 &&
                 genomicInfo.immunotherapy_markers.pd_l1.value &&
                 genomicInfo.immunotherapy_markers.pd_l1.value !== 'null' ? (
                  <p className="text-sm text-emerald-800 leading-relaxed mt-2">
                    PD-L1 expression ({genomicInfo.immunotherapy_markers.pd_l1.value}) supports potential for immunotherapy strategies.
                  </p>
                ) : (
                  <p className="text-sm text-emerald-800 leading-relaxed mt-2">
                    PD-L1 expression status not mentioned in available documents. Consider immunotherapy evaluation based on clinical context.
                  </p>
                )}
              </div>
            </div>
          </div>
        </div>
      )}

      {actionableMutations.length === 0 && (
        <div className="bg-gradient-to-r from-gray-50 to-slate-50 border-2 border-gray-300 rounded-xl p-6">
          <div className="flex items-start gap-4">
            <div className="w-12 h-12 bg-gray-400 rounded-xl flex items-center justify-center flex-shrink-0">
              <Dna className="w-6 h-6 text-white" />
            </div>
            <div className="flex-1">
              <h4 className="text-gray-950 mb-2">Genomic Profile Summary</h4>
              <p className="text-sm text-gray-700 leading-relaxed">
                No actionable driver mutations detected in the standard panel. Consider additional genomic testing or enrollment in clinical trials based on clinical context.
                {genomicInfo?.immunotherapy_markers?.pd_l1 &&
                 genomicInfo.immunotherapy_markers.pd_l1.value &&
                 genomicInfo.immunotherapy_markers.pd_l1.value !== 'null'
                  ? ` PD-L1 expression (${genomicInfo.immunotherapy_markers.pd_l1.value}) may support immunotherapy strategies.`
                  : ` PD-L1 expression status not mentioned in available documents.`
                }
              </p>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
