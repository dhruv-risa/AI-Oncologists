import { TestTube } from 'lucide-react';
import { SectionCard } from './SectionCard';
import { DataRow } from './DataRow';
import { LabTrendChart } from './LabTrendChart';
import { AIInterpretation } from './AIInterpretation';

export function LabSection() {
  return (
    <SectionCard title="Laboratory Values" icon={TestTube}>
      <div className="space-y-4">
        <AIInterpretation
          title="AI Laboratory Interpretation"
          content="Laboratory values show excellent disease control with tumor markers (CEA, CA19-9) within normal limits and demonstrating a declining trend. Mild anemia (Hgb 10.2 g/dL) is common in cancer patients on active treatment and may benefit from supportive care. Elevated transaminases (ALT 58, AST 52) are likely treatment-related hepatotoxicity from EGFR TKI therapy - Grade 1 toxicity requiring monitoring but not dose modification per CTCAE v5.0. Normal renal function (eGFR >90) supports continued full-dose therapy. Recommend trending liver enzymes bi-weekly and consider hepatoprotective measures if elevations progress."
          variant="warning"
        />

        <div>
          <h4 className="text-sm text-gray-700 mb-3">Tumor Markers (Latest: Dec 10, 2024)</h4>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
            <div className="bg-white border border-gray-200 rounded-lg p-3">
              <p className="text-xs text-gray-600">CEA</p>
              <p className="text-gray-900">4.2 ng/mL</p>
              <p className="text-xs text-green-600">↓ Normal (ref: &lt;5.0)</p>
            </div>
            <div className="bg-white border border-gray-200 rounded-lg p-3">
              <p className="text-xs text-gray-600">CA19-9</p>
              <p className="text-gray-900">18 U/mL</p>
              <p className="text-xs text-green-600">Normal (ref: &lt;37)</p>
            </div>
            <div className="bg-white border border-gray-200 rounded-lg p-3">
              <p className="text-xs text-gray-600">CA-125</p>
              <p className="text-gray-900">22 U/mL</p>
              <p className="text-xs text-green-600">Normal (ref: &lt;35)</p>
            </div>
          </div>
        </div>

        <div>
          <h4 className="text-sm text-gray-700 mb-3">Complete Blood Count</h4>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            <div className="bg-white border border-gray-200 rounded-lg p-3">
              <p className="text-xs text-gray-600">WBC</p>
              <p className="text-gray-900">6.8 K/μL</p>
              <p className="text-xs text-green-600">Normal</p>
            </div>
            <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-3">
              <p className="text-xs text-gray-600">Hemoglobin</p>
              <p className="text-gray-900">10.2 g/dL</p>
              <p className="text-xs text-yellow-700">↓ Low</p>
            </div>
            <div className="bg-white border border-gray-200 rounded-lg p-3">
              <p className="text-xs text-gray-600">Platelets</p>
              <p className="text-gray-900">185 K/μL</p>
              <p className="text-xs text-green-600">Normal</p>
            </div>
            <div className="bg-white border border-gray-200 rounded-lg p-3">
              <p className="text-xs text-gray-600">ANC</p>
              <p className="text-gray-900">3.8 K/μL</p>
              <p className="text-xs text-green-600">Normal</p>
            </div>
          </div>
        </div>

        <div>
          <h4 className="text-sm text-gray-700 mb-3">Comprehensive Metabolic Panel</h4>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            <div className="bg-white border border-gray-200 rounded-lg p-3">
              <p className="text-xs text-gray-600">Creatinine</p>
              <p className="text-gray-900">0.9 mg/dL</p>
              <p className="text-xs text-green-600">Normal</p>
            </div>
            <div className="bg-white border border-gray-200 rounded-lg p-3">
              <p className="text-xs text-gray-600">eGFR</p>
              <p className="text-gray-900">&gt;90 mL/min</p>
              <p className="text-xs text-green-600">Normal</p>
            </div>
            <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-3">
              <p className="text-xs text-gray-600">ALT</p>
              <p className="text-gray-900">58 U/L</p>
              <p className="text-xs text-yellow-700">↑ Elevated</p>
            </div>
            <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-3">
              <p className="text-xs text-gray-600">AST</p>
              <p className="text-gray-900">52 U/L</p>
              <p className="text-xs text-yellow-700">↑ Elevated</p>
            </div>
            <div className="bg-white border border-gray-200 rounded-lg p-3">
              <p className="text-xs text-gray-600">Total Bilirubin</p>
              <p className="text-gray-900">0.8 mg/dL</p>
              <p className="text-xs text-green-600">Normal</p>
            </div>
            <div className="bg-white border border-gray-200 rounded-lg p-3">
              <p className="text-xs text-gray-600">Albumin</p>
              <p className="text-gray-900">3.9 g/dL</p>
              <p className="text-xs text-green-600">Normal</p>
            </div>
            <div className="bg-white border border-gray-200 rounded-lg p-3">
              <p className="text-xs text-gray-600">Sodium</p>
              <p className="text-gray-900">140 mEq/L</p>
              <p className="text-xs text-green-600">Normal</p>
            </div>
            <div className="bg-white border border-gray-200 rounded-lg p-3">
              <p className="text-xs text-gray-600">Potassium</p>
              <p className="text-gray-900">4.2 mEq/L</p>
              <p className="text-xs text-green-600">Normal</p>
            </div>
          </div>
        </div>

        <div>
          <h4 className="text-sm text-gray-700 mb-3">Clinical Flags</h4>
          <div className="flex flex-wrap gap-2">
            <span className="px-3 py-1 bg-yellow-100 text-yellow-800 rounded-full text-xs">
              Mild anemia
            </span>
            <span className="px-3 py-1 bg-yellow-100 text-yellow-800 rounded-full text-xs">
              Elevated transaminases (likely treatment-related)
            </span>
          </div>
        </div>

        <div>
          <h4 className="text-sm text-gray-700 mb-3">Longitudinal Biomarker Trends (CEA)</h4>
          <LabTrendChart />
        </div>
      </div>
    </SectionCard>
  );
}