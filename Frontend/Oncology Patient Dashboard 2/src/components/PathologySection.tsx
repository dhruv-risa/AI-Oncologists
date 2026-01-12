import { Microscope } from 'lucide-react';
import { SectionCard } from './SectionCard';
import { DataRow } from './DataRow';
import { AIInterpretation } from './AIInterpretation';

export function PathologySection() {
  return (
    <SectionCard title="Pathology" icon={Microscope}>
      <div className="space-y-4">
        <div>
          <h4 className="text-sm text-gray-700 mb-2">Pathology Diagnosis Text</h4>
          <p className="text-sm text-gray-600 bg-gray-50 p-3 rounded-lg border border-gray-200">
            Lung biopsy, right upper lobe: Adenocarcinoma, moderately differentiated, with lepidic and acinar growth patterns. Tumor measures 3.2 cm in greatest dimension. Lymphovascular invasion present. Pleural surface involvement noted.
          </p>
        </div>

        <AIInterpretation
          title="AI Pathology Interpretation"
          content="The pathology findings confirm moderately differentiated adenocarcinoma with mixed growth patterns (predominantly acinar 60%, lepidic 30%). The presence of lymphovascular invasion and positive margins suggests higher risk for recurrence. TTF-1 and Napsin A positivity confirms primary lung origin. The tumor's lepidic component may correlate with the EGFR mutation status, as lepidic-predominant adenocarcinomas frequently harbor EGFR mutations. Recommend close monitoring and consideration of adjuvant targeted therapy."
          variant="info"
        />
        
        <div className="grid grid-cols-1 md:grid-cols-2 gap-x-8 gap-y-4">
          <DataRow label="Tumor Grade" value="Grade 2 (Moderately differentiated)" />
          <DataRow label="Biopsy Site" value="Right upper lobe, lung" />
          <DataRow label="Biopsy Date" value="March 18, 2023" />
          <DataRow label="Margin Status" value="Positive margins on bronchial resection" highlight />
          <DataRow 
            label="Histopathologic Features" 
            value="Lepidic pattern (30%), Acinar pattern (60%), Solid pattern (10%)" 
          />
          <DataRow 
            label="Pathology Keywords" 
            value="Adenocarcinoma, Lepidic, Acinar, LVI+" 
          />
        </div>

        <div>
          <h4 className="text-sm text-gray-700 mb-3">IHC Markers</h4>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            <div className="bg-green-50 border border-green-200 rounded-lg p-3">
              <p className="text-xs text-gray-600">TTF-1</p>
              <p className="text-green-800">Positive</p>
            </div>
            <div className="bg-green-50 border border-green-200 rounded-lg p-3">
              <p className="text-xs text-gray-600">Napsin A</p>
              <p className="text-green-800">Positive</p>
            </div>
            <div className="bg-red-50 border border-red-200 rounded-lg p-3">
              <p className="text-xs text-gray-600">CK7</p>
              <p className="text-red-800">Negative</p>
            </div>
            <div className="bg-red-50 border border-red-200 rounded-lg p-3">
              <p className="text-xs text-gray-600">CK20</p>
              <p className="text-red-800">Negative</p>
            </div>
          </div>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-x-8 gap-y-4">
          <DataRow label="Number of Reports" value="3 pathology reports" />
          <DataRow label="Ambiguous Diagnosis" value="None" />
        </div>
      </div>
    </SectionCard>
  );
}