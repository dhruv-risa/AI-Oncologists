import { Heart } from 'lucide-react';
import { SectionCard } from './SectionCard';
import { usePatient } from '../contexts/PatientContext';

export function ComorbiditiesSection() {
  const { currentPatient } = usePatient();

  // Get comorbidities data from patient context
  const comorbiditiesList = currentPatient?.comorbidities?.comorbidities || [];

  // Filter out the primary cancer diagnosis from comorbidities
  const filteredComorbidities = comorbiditiesList.filter(
    item => !item.condition_name.toLowerCase().includes('nsclc') &&
            !item.condition_name.toLowerCase().includes('adenocarcinoma') &&
            !item.condition_name.toLowerCase().includes('lung cancer')
  );

  // Helper function to determine severity badge style
  const getSeverityStyle = (severity: string) => {
    const severityLower = severity?.toLowerCase() || 'mild';

    if (severityLower.includes('severe') || severityLower.includes('stage iii') || severityLower.includes('stage iv')) {
      return 'bg-red-100 text-red-800';
    }
    if (severityLower.includes('moderate') || severityLower.includes('stage ii')) {
      return 'bg-yellow-100 text-yellow-800';
    }
    return 'bg-green-100 text-green-800';
  };

  // Helper function to determine border color based on severity
  const getBorderColor = (severity: string) => {
    const severityLower = severity?.toLowerCase() || 'mild';

    if (severityLower.includes('severe') || severityLower.includes('stage iii') || severityLower.includes('stage iv')) {
      return 'border-red-300 border-l-4';
    }
    if (severityLower.includes('moderate') || severityLower.includes('stage ii')) {
      return 'border-yellow-300 border-l-4';
    }
    return 'border-green-300 border-l-4';
  };

  // Helper function to check if medications exist
  const hasMedications = (item: any) => {
    return item.associated_medications &&
           item.associated_medications.length > 0 &&
           !item.associated_medications.some((med: string) =>
             med.toLowerCase() === 'na' ||
             med.toLowerCase() === 'n/a' ||
             med.trim() === ''
           );
  };

  // Show message if no data is available
  if (!currentPatient) {
    return (
      <SectionCard title="Comorbidities" icon={Heart}>
        <div className="text-center text-gray-500 py-4">
          No patient data available
        </div>
      </SectionCard>
    );
  }

  return (
    <SectionCard title="Comorbidities" icon={Heart}>
      {filteredComorbidities.length === 0 ? (
        <div className="text-center text-gray-500 py-4">
          No comorbidities recorded
        </div>
      ) : (
        <div className="space-y-3">
          {filteredComorbidities.map((item, index) => (
            <div key={index} className={`bg-white border rounded-lg p-4 ${getBorderColor(item.severity)}`}>
              <div className="flex items-start justify-between mb-2">
                <h5 className="text-gray-900 font-medium">{item.condition_name}</h5>
                <span className={`text-xs px-2 py-1 rounded ${getSeverityStyle(item.severity)}`}>
                  {item.severity || 'Mild'}
                </span>
              </div>

              {item.clinical_details && (
                <p className="text-sm text-gray-600 mb-3">{item.clinical_details}</p>
              )}

              <div className="mt-2 pt-2 border-t border-gray-100">
                <p className="text-xs font-medium text-gray-500 mb-1">Medications:</p>
                {hasMedications(item) ? (
                  <div className="flex flex-wrap gap-1">
                    {item.associated_medications.map((med: string, medIdx: number) => (
                      <span
                        key={medIdx}
                        className="px-2 py-1 bg-blue-50 text-blue-700 border border-blue-200 rounded text-xs"
                      >
                        {med}
                      </span>
                    ))}
                  </div>
                ) : (
                  <p className="text-xs text-gray-500 italic">
                    No medication currently prescribed for this comorbidity
                  </p>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </SectionCard>
  );
}
