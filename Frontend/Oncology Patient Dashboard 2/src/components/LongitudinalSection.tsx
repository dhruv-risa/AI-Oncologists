import { TrendingUp } from 'lucide-react';
import { SectionCard } from './SectionCard';
import { TimelineChart } from './TimelineChart';

export function LongitudinalSection() {
  return (
    <SectionCard title="Longitudinal Trends & Disease Course" icon={TrendingUp}>
      <div className="space-y-4">
        <div>
          <h4 className="text-sm text-gray-700 mb-3">Stage Evolution</h4>
          <div className="relative">
            <div className="flex items-center justify-between">
              <div className="text-center flex-1">
                <div className="bg-blue-100 text-blue-800 rounded-lg p-3 mb-2">
                  <p className="text-xs text-blue-600">March 2023</p>
                  <p className="text-blue-900">Stage IIB</p>
                </div>
              </div>
              <div className="flex-shrink-0 px-4">
                <div className="w-8 h-0.5 bg-gray-300"></div>
              </div>
              <div className="text-center flex-1">
                <div className="bg-yellow-100 text-yellow-800 rounded-lg p-3 mb-2">
                  <p className="text-xs text-yellow-600">June 2024</p>
                  <p className="text-yellow-900">Stage IVA</p>
                </div>
              </div>
            </div>
            <p className="text-xs text-gray-600 text-center mt-2">
              Progression to metastatic disease with contralateral lung nodules
            </p>
          </div>
        </div>

        <div>
          <h4 className="text-sm text-gray-700 mb-3">Treatment Response Timeline</h4>
          <TimelineChart />
        </div>

        <div>
          <h4 className="text-sm text-gray-700 mb-3">Key Disease Course Events</h4>
          <div className="space-y-2">
            <div className="flex items-start gap-3 pb-3 border-b border-gray-200">
              <div className="flex-shrink-0 w-24 text-xs text-gray-600">Dec 2024</div>
              <div className="flex-1">
                <p className="text-sm text-gray-900">Continued partial response on Osimertinib (5 months)</p>
                <p className="text-xs text-green-600 mt-1">↓ 28% tumor burden reduction</p>
              </div>
            </div>
            <div className="flex items-start gap-3 pb-3 border-b border-gray-200">
              <div className="flex-shrink-0 w-24 text-xs text-gray-600">July 2024</div>
              <div className="flex-1">
                <p className="text-sm text-gray-900">Started Osimertinib (2nd-line)</p>
                <p className="text-xs text-gray-600 mt-1">After disease progression on chemotherapy</p>
              </div>
            </div>
            <div className="flex items-start gap-3 pb-3 border-b border-gray-200">
              <div className="flex-shrink-0 w-24 text-xs text-gray-600">June 2024</div>
              <div className="flex-1">
                <p className="text-sm text-gray-900">Disease progression detected</p>
                <p className="text-xs text-red-600 mt-1">↑ New contralateral nodule, stage IVA</p>
              </div>
            </div>
            <div className="flex items-start gap-3 pb-3 border-b border-gray-200">
              <div className="flex-shrink-0 w-24 text-xs text-gray-600">Apr 2023</div>
              <div className="flex-1">
                <p className="text-sm text-gray-900">Started Carboplatin + Pemetrexed (1st-line)</p>
                <p className="text-xs text-gray-600 mt-1">Post-surgical adjuvant therapy</p>
              </div>
            </div>
            <div className="flex items-start gap-3 pb-3 border-b border-gray-200">
              <div className="flex-shrink-0 w-24 text-xs text-gray-600">Apr 2023</div>
              <div className="flex-1">
                <p className="text-sm text-gray-900">Right upper lobectomy performed</p>
                <p className="text-xs text-yellow-600 mt-1">R1 resection (positive margin)</p>
              </div>
            </div>
            <div className="flex items-start gap-3">
              <div className="flex-shrink-0 w-24 text-xs text-gray-600">Mar 2023</div>
              <div className="flex-1">
                <p className="text-sm text-gray-900">Initial diagnosis</p>
                <p className="text-xs text-gray-600 mt-1">NSCLC Adenocarcinoma, EGFR Ex19del, Stage IIB</p>
              </div>
            </div>
          </div>
        </div>

        <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
          <h4 className="text-sm text-blue-900 mb-2">Overall Disease Course Summary</h4>
          <p className="text-sm text-blue-800">
            58-year-old female with EGFR-mutated NSCLC adenocarcinoma initially diagnosed at Stage IIB. Underwent surgical resection with positive margins, followed by adjuvant chemotherapy. Disease progressed to Stage IVA after 15 months with contralateral lung metastases. Currently on second-line targeted therapy (Osimertinib) with partial response maintained for 5 months. Molecular profile shows EGFR exon 19 deletion with high PD-L1 expression (75%). Comorbidities include controlled diabetes, hypertension, and mild COPD.
          </p>
        </div>
      </div>
    </SectionCard>
  );
}
