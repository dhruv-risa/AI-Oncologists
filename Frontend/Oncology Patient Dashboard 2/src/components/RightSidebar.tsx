import { CheckCircle, AlertTriangle, Activity } from 'lucide-react';
import { PatientData } from '../services/api';

interface RightSidebarProps {
  patientData: PatientData | null;
}

export function RightSidebar({ patientData }: RightSidebarProps) {
  // Extract current treatment from treatment history based on current line of therapy
  const getCurrentTreatment = () => {
    if (!patientData?.treatment_tab_info_LOT?.treatment_history) return null;

    const treatmentHistory = patientData.treatment_tab_info_LOT.treatment_history;

    // Strategy 1: Use diagnosis.line_of_therapy if available, but only if the treatment is actually current
    const currentLineOfTherapy = patientData?.diagnosis?.line_of_therapy;
    if (currentLineOfTherapy && currentLineOfTherapy !== 'NA' && currentLineOfTherapy !== null) {
      const treatmentByLine = treatmentHistory.find(
        (treatment) => String(treatment.header.line_number) === String(currentLineOfTherapy)
      );
      // Only return this treatment if it's marked as Current or Ongoing
      if (treatmentByLine) {
        const status = treatmentByLine.header?.status_badge?.toLowerCase() || '';
        if (status.includes('current') || status.includes('ongoing')) {
          return treatmentByLine;
        }
        // If the treatment is not current, fall through to other strategies
      }
    }

    // Strategy 2: Find treatment with status_badge === 'Current'
    const currentTreatment = treatmentHistory.find(
      (treatment) => treatment.header.status_badge === 'Current'
    );
    if (currentTreatment) return currentTreatment;

    // Strategy 3: Find the most recent ongoing treatment (end_date is 'Ongoing')
    const ongoingTreatments = treatmentHistory.filter(
      (treatment) => treatment.dates.end_date === 'Ongoing' || treatment.dates.end_date === 'ongoing'
    );
    if (ongoingTreatments.length > 0) {
      // Return the one with highest numeric line number, or most recent start date
      return ongoingTreatments.reduce((latest, current) => {
        const latestLine = typeof latest.header.line_number === 'number' ? latest.header.line_number : 0;
        const currentLine = typeof current.header.line_number === 'number' ? current.header.line_number : 0;
        return currentLine > latestLine ? current : latest;
      });
    }

    // Strategy 4: Return the most recent treatment (highest line number among numeric lines)
    const numericLineTreatments = treatmentHistory.filter(
      (treatment) => typeof treatment.header.line_number === 'number'
    );
    if (numericLineTreatments.length > 0) {
      return numericLineTreatments.reduce((latest, current) => {
        return (current.header.line_number as number) > (latest.header.line_number as number) ? current : latest;
      });
    }

    return null;
  };

  // Extract target mutations from genomic data
  const getTargetMutation = () => {
    if (!patientData?.genomic_info?.detected_driver_mutations) return null;

    const targetMutation = patientData.genomic_info.detected_driver_mutations.find(
      (mutation: any) => mutation.is_target === true
    );

    return targetMutation;
  };

  // Extract clinical alerts from lab data and comorbidities
  const getClinicalAlerts = () => {
    const alerts: Array<{ severity: string; message: string }> = [];
    const seenMessages = new Set<string>(); // Track unique alert messages

    // Check comorbidities for significant conditions
    if (patientData?.comorbidities?.comorbidities) {
      patientData.comorbidities.comorbidities.forEach((comorbidity) => {
        const conditionLower = comorbidity.condition_name?.toLowerCase() || '';
        const severityLower = comorbidity.severity?.toLowerCase() || '';

        let alertMessage = '';
        let severity = 'warning';

        // High-risk cardiac conditions
        if (conditionLower.includes('heart') || conditionLower.includes('cardiac') ||
            conditionLower.includes('myocardial') || conditionLower.includes('coronary')) {
          alertMessage = `Cardiac condition: ${comorbidity.condition_name}`;
          severity = 'danger';
        }
        // Renal conditions
        else if (conditionLower.includes('renal') || conditionLower.includes('kidney')) {
          alertMessage = `Renal condition: ${comorbidity.condition_name}`;
          severity = 'warning';
        }
        // Hepatic conditions
        else if (conditionLower.includes('hepatic') || conditionLower.includes('liver') ||
                 conditionLower.includes('cirrhosis')) {
          alertMessage = `Hepatic condition: ${comorbidity.condition_name}`;
          severity = 'warning';
        }
        // Diabetes
        else if (conditionLower.includes('diabetes')) {
          alertMessage = `Diabetes: ${comorbidity.condition_name}`;
          severity = 'warning';
        }
        // Severe conditions based on severity level
        else if (severityLower.includes('severe') || severityLower.includes('critical')) {
          alertMessage = `${comorbidity.condition_name} (${comorbidity.severity})`;
          severity = 'danger';
        }

        // Add alert only if we haven't seen this message before
        if (alertMessage && !seenMessages.has(alertMessage.toLowerCase())) {
          seenMessages.add(alertMessage.toLowerCase());
          alerts.push({ severity, message: alertMessage });
        }
      });
    }

    // Check for clinical interpretations from labs
    if (patientData?.lab_info?.clinical_interpretation) {
      patientData.lab_info.clinical_interpretation.forEach((interpretation: string) => {
        const interpretationLower = interpretation.toLowerCase();

        // Parse alerts from clinical interpretation - only add once per type
        if (interpretationLower.includes('anemia') && !seenMessages.has('anemia detected')) {
          seenMessages.add('anemia detected');
          alerts.push({ severity: 'warning', message: 'Anemia detected' });
        }
        if (interpretationLower.includes('hepatic dysfunction') &&
            !interpretationLower.includes('no hepatic dysfunction') &&
            !seenMessages.has('liver dysfunction')) {
          seenMessages.add('liver dysfunction');
          alerts.push({ severity: 'warning', message: 'Liver dysfunction' });
        }
        if (interpretationLower.includes('neutropenia') &&
            !interpretationLower.includes('no neutropenia') &&
            !seenMessages.has('neutropenia')) {
          seenMessages.add('neutropenia');
          alerts.push({ severity: 'danger', message: 'Neutropenia' });
        }
        if (interpretationLower.includes('hyperglycemia') && !seenMessages.has('elevated glucose')) {
          seenMessages.add('elevated glucose');
          alerts.push({ severity: 'warning', message: 'Elevated glucose' });
        }
      });
    }

    return alerts.slice(0, 3); // Limit to top 3 alerts
  };

  // Extract recent activity from timeline
  const getRecentActivity = () => {
    if (!patientData?.treatment_tab_info_timeline?.timeline_events) return [];

    return patientData.treatment_tab_info_timeline.timeline_events.slice(0, 3);
  };

  const currentTreatment = getCurrentTreatment();
  const targetMutation = getTargetMutation();
  const clinicalAlerts = getClinicalAlerts();
  const recentActivity = getRecentActivity();

  return (
    <div className="w-80 flex-shrink-0 space-y-4">
      {/* Actionable Mutation */}
      <div className={`bg-white rounded-xl p-5 border-2 shadow-lg ${targetMutation ? 'border-emerald-200' : 'border-gray-200'}`}>
        <div className="flex items-start gap-3">
          <div className={`w-10 h-10 rounded-lg flex items-center justify-center flex-shrink-0 ${targetMutation ? 'bg-emerald-500' : 'bg-gray-300'}`}>
            <CheckCircle className="w-5 h-5 text-white" />
          </div>
          <div className="flex-1">
            {targetMutation ? (
              <>
                <p className="text-xs text-emerald-700 font-semibold uppercase tracking-wider mb-1">Target Mutation</p>
                <p className="text-base text-emerald-950 font-bold mb-1">{targetMutation.gene}</p>
                <p className="text-xs text-emerald-600">{targetMutation.details || 'Actionable target identified'}</p>
              </>
            ) : (
              <>
                <p className="text-sm text-gray-950 font-semibold">Target Mutation</p>
                <p className="text-xs text-gray-500 mt-1">No actionable target identified</p>
              </>
            )}
          </div>
        </div>
      </div>

      {/* Current Treatment */}
      <div className="bg-white rounded-xl p-5 border border-blue-200 shadow-sm">
        <p className="text-xs text-blue-700 uppercase tracking-wider mb-2">Current Treatment</p>
        {currentTreatment ? (
          <>
            <p className="text-blue-950 mb-1 font-medium">
              {(currentTreatment as any).systemic_regimen || currentTreatment.regimen_details?.display_name || 'N/A'}
            </p>
            {currentTreatment.dates?.start_date &&
             currentTreatment.dates.start_date !== 'NA' &&
             currentTreatment.dates.start_date !== 'N/A' &&
             currentTreatment.dates.start_date !== 'Not applicable' && (
              <div className="flex items-center gap-2 text-xs text-blue-600">
                <div className="w-2 h-2 bg-blue-500 rounded-full animate-pulse"></div>
                <span>Active since {currentTreatment.dates.start_date}</span>
              </div>
            )}
            {currentTreatment.cycles_data?.display_text && (
              <p className="text-xs text-blue-600 mt-2">{currentTreatment.cycles_data.display_text}</p>
            )}
          </>
        ) : (
          <p className="text-gray-500 text-sm">No active treatment</p>
        )}
      </div>

      {/* Clinical Alerts */}
      <div className="bg-white rounded-xl p-5 border border-amber-200 shadow-sm">
        <div className="flex items-center gap-2 mb-3">
          <AlertTriangle className="w-4 h-4 text-amber-600" />
          <p className="text-xs text-amber-800 uppercase tracking-wider">Clinical Alerts</p>
        </div>
        <div className="space-y-2">
          {clinicalAlerts.length > 0 ? (
            clinicalAlerts.map((alert, index) => (
              <div key={index} className="flex items-center gap-2">
                <div className={`w-1.5 h-1.5 rounded-full ${alert.severity === 'danger' ? 'bg-red-500' : 'bg-amber-500'}`}></div>
                <span className="text-sm text-amber-900">{alert.message}</span>
              </div>
            ))
          ) : (
            <p className="text-gray-500 text-sm">No clinical alerts</p>
          )}
        </div>
      </div>

      {/* Recent Activity */}
      <div className="bg-white rounded-xl p-5 border border-slate-200 shadow-sm">
        <div className="flex items-center gap-2 mb-3">
          <Activity className="w-4 h-4 text-slate-600" />
          <p className="text-xs text-slate-800 uppercase tracking-wider">Recent Activity</p>
        </div>
        <div className="space-y-3">
          {recentActivity.length > 0 ? (
            recentActivity.map((event, index) => (
              <div key={index}>
                <p className="text-sm text-slate-900 font-medium">
                  {event.systemic_regimen || event.local_therapy || event.title || 'Treatment Update'}
                </p>
                <p className="text-xs text-slate-600">
                  {event.details || event.subtitle || 'No details available'}
                </p>
                <p className="text-xs text-slate-500 mt-0.5">{event.date_display || 'Date not available'}</p>
              </div>
            ))
          ) : (
            <p className="text-gray-500 text-sm">No recent activity</p>
          )}
        </div>
      </div>
    </div>
  );
}
