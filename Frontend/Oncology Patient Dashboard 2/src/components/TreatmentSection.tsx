import { Activity } from 'lucide-react';
import { SectionCard } from './SectionCard';
import { DataRow } from './DataRow';

export function TreatmentSection() {
  return (
    <SectionCard title="Treatment History" icon={Activity}>
      <div className="space-y-4">
        <div>
          <h4 className="text-sm text-gray-700 mb-3">Treatment Plan Summary</h4>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-x-8 gap-y-4">
            <DataRow label="Current Line of Therapy" value="Second-line" highlight />
            <DataRow label="Treatment Status" value="Active - Ongoing" highlight />
          </div>
        </div>

        <div className="space-y-3">
          <div className="bg-blue-50 border-l-4 border-blue-600 p-4 rounded-r-lg">
            <div className="flex items-start justify-between mb-2">
              <h4 className="text-blue-900">Current: Osimertinib (Tagrisso)</h4>
              <span className="px-2 py-1 bg-blue-200 text-blue-900 rounded text-xs">Active</span>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-x-6 gap-y-2 text-sm">
              <div>
                <span className="text-blue-700">Line of Therapy:</span>
                <span className="text-blue-900 ml-2">Second-line</span>
              </div>
              <div>
                <span className="text-blue-700">Start Date:</span>
                <span className="text-blue-900 ml-2">July 10, 2024</span>
              </div>
              <div>
                <span className="text-blue-700">Regimen:</span>
                <span className="text-blue-900 ml-2">Osimertinib 80mg PO daily</span>
              </div>
              <div>
                <span className="text-blue-700">Response:</span>
                <span className="text-blue-900 ml-2">Partial Response (PR)</span>
              </div>
              <div className="md:col-span-2">
                <span className="text-blue-700">Toxicities:</span>
                <span className="text-blue-900 ml-2">Grade 1 diarrhea, Grade 1 rash (managed)</span>
              </div>
            </div>
          </div>

          <div className="bg-gray-50 border-l-4 border-gray-400 p-4 rounded-r-lg">
            <div className="flex items-start justify-between mb-2">
              <h4 className="text-gray-900">Prior: Carboplatin + Pemetrexed</h4>
              <span className="px-2 py-1 bg-gray-300 text-gray-900 rounded text-xs">Completed</span>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-x-6 gap-y-2 text-sm">
              <div>
                <span className="text-gray-700">Line of Therapy:</span>
                <span className="text-gray-900 ml-2">First-line</span>
              </div>
              <div>
                <span className="text-gray-700">Dates:</span>
                <span className="text-gray-900 ml-2">April 5, 2023 - June 20, 2024</span>
              </div>
              <div>
                <span className="text-gray-700">Regimen:</span>
                <span className="text-gray-900 ml-2">Carbo AUC 5 + Pem 500mg/m² q3w × 4, then Pem maintenance</span>
              </div>
              <div>
                <span className="text-gray-700">Best Response:</span>
                <span className="text-gray-900 ml-2">Stable Disease (SD)</span>
              </div>
              <div className="md:col-span-2">
                <span className="text-gray-700">Reason for Change:</span>
                <span className="text-gray-900 ml-2">Disease progression after 15 months; new contralateral nodule detected</span>
              </div>
              <div className="md:col-span-2">
                <span className="text-gray-700">Toxicities:</span>
                <span className="text-gray-900 ml-2">Grade 2 neutropenia, Grade 2 fatigue, Grade 1 nausea</span>
              </div>
            </div>
          </div>
        </div>

        <div>
          <h4 className="text-sm text-gray-700 mb-3">Other Treatment Modalities</h4>
          <div className="space-y-3">
            <div className="bg-white border border-gray-200 rounded-lg p-4">
              <div className="flex items-center justify-between mb-2">
                <h5 className="text-gray-900">Surgery</h5>
                <span className="text-xs text-gray-600">April 28, 2023</span>
              </div>
              <p className="text-sm text-gray-600">
                Right upper lobectomy with mediastinal lymph node dissection. R1 resection (positive bronchial margin).
              </p>
            </div>

            <div className="bg-white border border-gray-200 rounded-lg p-4">
              <div className="flex items-center justify-between mb-2">
                <h5 className="text-gray-900">Radiation</h5>
                <span className="text-xs text-gray-600">Not applicable</span>
              </div>
              <p className="text-sm text-gray-600">
                No radiation therapy administered to date.
              </p>
            </div>
          </div>
        </div>
      </div>
    </SectionCard>
  );
}
