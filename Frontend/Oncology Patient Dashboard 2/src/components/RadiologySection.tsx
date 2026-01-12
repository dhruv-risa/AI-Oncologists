import { Scan } from 'lucide-react';
import { SectionCard } from './SectionCard';
import { DataRow } from './DataRow';
import { AIInterpretation } from './AIInterpretation';

export function RadiologySection() {
  return (
    <SectionCard title="Radiology Findings" icon={Scan}>
      <div className="space-y-4">
        <AIInterpretation
          title="AI Radiology Interpretation"
          content="Excellent radiographic response to EGFR-targeted therapy. The 28% reduction in target lesions meets RECIST 1.1 criteria for Partial Response (PR). The primary RUL mass showing 34% reduction is particularly encouraging, with sustained response over 3 consecutive imaging studies indicating durable disease control. Absence of new lesions and improvement in mediastinal lymphadenopathy suggest systemic disease control. Recommend continuing current therapy with interval imaging every 6-8 weeks to monitor for acquired resistance patterns."
          variant="success"
        />

        <div>
          <h4 className="text-sm text-gray-700 mb-3">Latest Imaging Studies</h4>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-x-8 gap-y-4">
            <DataRow label="Latest CT Chest" value="December 8, 2024" />
            <DataRow label="Latest PET/CT" value="November 15, 2024" />
            <DataRow label="Latest Brain MRI" value="October 22, 2024 - No metastases" />
          </div>
        </div>

        <div>
          <h4 className="text-sm text-gray-700 mb-2">Radiology Impression (CT Chest - Dec 8, 2024)</h4>
          <p className="text-sm text-gray-600 bg-gray-50 p-3 rounded-lg border border-gray-200">
            Partial response to therapy. Right upper lobe mass decreased from 3.2 cm to 2.1 cm. Contralateral lung nodules stable. Small pleural effusion decreased. No new lesions. Mediastinal lymphadenopathy improved.
          </p>
        </div>

        <div>
          <h4 className="text-sm text-gray-700 mb-3">RECIST Measurements</h4>
          <div className="bg-white border border-gray-200 rounded-lg overflow-hidden">
            <table className="w-full text-sm">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-4 py-2 text-left text-gray-600">Lesion</th>
                  <th className="px-4 py-2 text-left text-gray-600">Baseline</th>
                  <th className="px-4 py-2 text-left text-gray-600">Current</th>
                  <th className="px-4 py-2 text-left text-gray-600">Change</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-200">
                <tr>
                  <td className="px-4 py-2 text-gray-900">RUL primary mass</td>
                  <td className="px-4 py-2 text-gray-600">3.2 cm</td>
                  <td className="px-4 py-2 text-gray-600">2.1 cm</td>
                  <td className="px-4 py-2 text-green-600">-34%</td>
                </tr>
                <tr>
                  <td className="px-4 py-2 text-gray-900">LUL nodule</td>
                  <td className="px-4 py-2 text-gray-600">1.8 cm</td>
                  <td className="px-4 py-2 text-gray-600">1.7 cm</td>
                  <td className="px-4 py-2 text-green-600">-6%</td>
                </tr>
                <tr>
                  <td className="px-4 py-2 text-gray-900">Mediastinal LN</td>
                  <td className="px-4 py-2 text-gray-600">2.4 cm</td>
                  <td className="px-4 py-2 text-gray-600">1.5 cm</td>
                  <td className="px-4 py-2 text-green-600">-38%</td>
                </tr>
                <tr className="bg-blue-50">
                  <td className="px-4 py-2 text-gray-900">Sum of diameters</td>
                  <td className="px-4 py-2 text-gray-900">7.4 cm</td>
                  <td className="px-4 py-2 text-gray-900">5.3 cm</td>
                  <td className="px-4 py-2 text-green-700">-28%</td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-x-8 gap-y-4">
          <DataRow label="Target Lesion Count" value="3 lesions" />
          <DataRow label="New Lesions" value="None" />
          <DataRow label="Overall Response" value="Partial Response (PR)" highlight />
        </div>

        <div className="bg-green-50 border border-green-200 rounded-lg p-4">
          <h4 className="text-sm text-green-900 mb-2">Radiology Trend</h4>
          <p className="text-sm text-green-800">
            <strong>Improving:</strong> 28% reduction in target lesions. No new lesions. Partial response maintained over 3 scans.
          </p>
        </div>
      </div>
    </SectionCard>
  );
}