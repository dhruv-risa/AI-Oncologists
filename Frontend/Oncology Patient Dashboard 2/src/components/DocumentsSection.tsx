import { FileText, ExternalLink, Download, Eye } from 'lucide-react';
import { SectionCard } from './SectionCard';
import { useState } from 'react';

export function DocumentsSection() {
  const [selectedCategory, setSelectedCategory] = useState('Pathology Reports');

  const documents = [
    {
      category: 'Pathology Reports',
      items: [
        { name: 'Initial Biopsy - Right Upper Lobe', date: '03/18/2023', code: 'PATH-1001' },
        { name: 'Surgical Pathology - Lobectomy Specimen', date: '04/28/2023', code: 'PATH-1002' },
        { name: 'IHC Panel Results', date: '03/22/2023', code: 'PATH-1003' },
        { name: 'Molecular Pathology Addendum', date: '04/02/2023', code: 'PATH-1004' },
      ],
    },
    {
      category: 'Genomic Reports',
      items: [
        { name: 'FoundationOne CDx - Comprehensive Genomic Profile', date: '04/05/2023', code: 'GEN-2001' },
        { name: 'Guardant360 CDx - Liquid Biopsy ctDNA', date: '11/28/2024', code: 'GEN-2002' },
        { name: 'PD-L1 Testing Report (22C3 pharmDx)', date: '04/05/2023', code: 'GEN-2003' },
        { name: 'TMB and MSI Analysis Report', date: '04/10/2023', code: 'GEN-2004' },
      ],
    },
    {
      category: 'Radiology Reports',
      items: [
        { name: 'CT Chest with Contrast - Baseline', date: '03/10/2023', code: 'RAD-3001' },
        { name: 'PET/CT Whole Body', date: '11/15/2024', code: 'RAD-3002' },
        { name: 'CT Chest with Contrast - Latest', date: '12/08/2024', code: 'RAD-3003' },
        { name: 'Brain MRI with Contrast', date: '10/22/2024', code: 'RAD-3004' },
        { name: 'CT Abdomen/Pelvis with Contrast', date: '09/15/2024', code: 'RAD-3005' },
      ],
    },
    {
      category: 'Clinical Reports',
      items: [
        { name: 'Medical Oncology Initial Consult', date: '03/20/2023', code: 'CLIN-4001' },
        { name: 'Medical Oncology Follow-up', date: '12/10/2024', code: 'CLIN-4002' },
        { name: 'Surgical Oncology Consultation', date: '04/15/2023', code: 'CLIN-4003' },
        { name: 'Multidisciplinary Tumor Board Discussion', date: '03/25/2023', code: 'CLIN-4004' },
        { name: 'Radiation Oncology Consultation', date: '05/10/2023', code: 'CLIN-4005' },
      ],
    },
  ];

  const selectedDocuments = documents.find(doc => doc.category === selectedCategory);

  return (
    <SectionCard title="Source Documents" icon={FileText}>
      <div className="space-y-4">
        {/* Horizontal Navigation Tabs */}
        <div className="border-b border-gray-200">
          <div className="flex gap-1">
            {documents.map((category, idx) => (
              <button
                key={idx}
                onClick={() => setSelectedCategory(category.category)}
                className={`px-4 py-3 text-sm transition-all relative ${
                  selectedCategory === category.category
                    ? 'text-blue-600'
                    : 'text-gray-600 hover:text-gray-900 hover:bg-gray-50'
                }`}
              >
                {category.category}
                <span className={`ml-2 px-2 py-0.5 rounded-full text-xs ${
                  selectedCategory === category.category
                    ? 'bg-blue-100 text-blue-700'
                    : 'bg-gray-100 text-gray-600'
                }`}>
                  {category.items.length}
                </span>
                {selectedCategory === category.category && (
                  <div className="absolute bottom-0 left-0 right-0 h-0.5 bg-blue-600"></div>
                )}
              </button>
            ))}
          </div>
        </div>

        {/* Document List */}
        <div className="space-y-2">
          {selectedDocuments?.items.map((doc, docIdx) => (
            <div
              key={docIdx}
              className="flex items-center justify-between p-4 bg-white border border-gray-200 rounded-lg hover:border-blue-300 hover:shadow-sm transition-all group"
            >
              <div className="flex items-center gap-3 flex-1">
                <div className="w-10 h-10 bg-gray-50 rounded-lg flex items-center justify-center group-hover:bg-blue-50 transition-colors">
                  <FileText className="w-5 h-5 text-gray-500 group-hover:text-blue-600" />
                </div>
                <div className="flex-1">
                  <p className="text-sm text-gray-900">{doc.name}</p>
                  <div className="flex items-center gap-2 mt-1">
                    <span className="px-2 py-0.5 bg-gray-100 text-gray-700 rounded text-xs">
                      {doc.code}
                    </span>
                    <span className="text-gray-300">•</span>
                    <p className="text-xs text-gray-500">{doc.date}</p>
                  </div>
                </div>
              </div>
              <div className="flex items-center gap-1">
                <button
                  className="p-2 text-gray-400 hover:text-blue-600 hover:bg-blue-50 rounded-lg transition-colors"
                  title="View document"
                >
                  <Eye className="w-4 h-4" />
                </button>
                <button
                  className="p-2 text-gray-400 hover:text-blue-600 hover:bg-blue-50 rounded-lg transition-colors"
                  title="Download document"
                >
                  <Download className="w-4 h-4" />
                </button>
                <button
                  className="p-2 text-gray-400 hover:text-blue-600 hover:bg-blue-50 rounded-lg transition-colors"
                  title="Open in new tab"
                >
                  <ExternalLink className="w-4 h-4" />
                </button>
              </div>
            </div>
          ))}
        </div>

        {/* Summary Footer */}
        <div className="pt-3 border-t border-gray-200">
          <div className="flex items-center justify-between text-xs text-gray-600">
            <span>{selectedDocuments?.items.length || 0} documents in {selectedCategory}</span>
            <span>Total: {documents.reduce((acc, cat) => acc + cat.items.length, 0)} documents</span>
          </div>
        </div>
      </div>
    </SectionCard>
  );
}