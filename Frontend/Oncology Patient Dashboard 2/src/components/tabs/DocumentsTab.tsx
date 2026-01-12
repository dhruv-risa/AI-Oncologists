import { FileText, ExternalLink } from 'lucide-react';

export function DocumentsTab() {
  const documents = [
    {
      category: 'Pathology Reports',
      items: [
        { name: 'Initial Biopsy - Right Upper Lobe', date: '03/18/2023', id: 'PATH-1001' },
        { name: 'Surgical Pathology - Lobectomy Specimen', date: '04/28/2023', id: 'PATH-1002' },
        { name: 'IHC Panel Results', date: '03/22/2023', id: 'PATH-1003' },
      ],
    },
    {
      category: 'Genomic Reports',
      items: [
        { name: 'FoundationOne CDx - Comprehensive Genomic Profile', date: '04/05/2023', id: 'GEN-2001' },
        { name: 'Guardant360 CDx - Liquid Biopsy ctDNA', date: '11/28/2024', id: 'GEN-2002' },
        { name: 'PD-L1 Testing Report (22C3 pharmDx)', date: '04/05/2023', id: 'GEN-2003' },
      ],
    },
    {
      category: 'Radiology Reports',
      items: [
        { name: 'CT Chest with Contrast - Baseline', date: '03/10/2023', id: 'RAD-3001' },
        { name: 'PET/CT Whole Body', date: '11/15/2024', id: 'RAD-3002' },
        { name: 'CT Chest with Contrast - Latest', date: '12/08/2024', id: 'RAD-3003' },
        { name: 'Brain MRI with Contrast', date: '10/22/2024', id: 'RAD-3004' },
      ],
    },
    {
      category: 'Clinical Notes',
      items: [
        { name: 'Medical Oncology Initial Consult', date: '03/20/2023', id: 'NOTE-4001' },
        { name: 'Medical Oncology Follow-up', date: '12/10/2024', id: 'NOTE-4002' },
        { name: 'Multidisciplinary Tumor Board Discussion', date: '03/25/2023', id: 'NOTE-4003' },
      ],
    },
  ];

  return (
    <div className="bg-white rounded-b-xl rounded-tr-xl border border-t-0 border-gray-200 p-6">
      <div className="flex items-center gap-2 mb-6">
        <FileText className="w-4 h-4 text-gray-400" />
        <h3 className="text-gray-900">Source Documents</h3>
      </div>

      <div className="space-y-6">
        {documents.map((category, idx) => (
          <div key={idx}>
            <h4 className="text-sm text-gray-700 mb-3">{category.category}</h4>
            <div className="space-y-2">
              {category.items.map((doc, docIdx) => (
                <button
                  key={docIdx}
                  className="w-full flex items-center justify-between p-3 bg-gray-50 hover:bg-gray-100 border border-gray-200 rounded-lg transition-colors text-left group"
                >
                  <div className="flex items-center gap-3 flex-1">
                    <div className="p-2 bg-white rounded border border-gray-300">
                      <FileText className="w-4 h-4 text-gray-600" />
                    </div>
                    <div className="flex-1">
                      <p className="text-sm text-gray-900 group-hover:text-blue-600 transition-colors">
                        {doc.name}
                      </p>
                      <div className="flex items-center gap-3 mt-1">
                        <p className="text-xs text-gray-500">{doc.id}</p>
                        <span className="text-gray-300">•</span>
                        <p className="text-xs text-gray-500">{doc.date}</p>
                      </div>
                    </div>
                  </div>
                  <ExternalLink className="w-4 h-4 text-gray-400 group-hover:text-blue-600 transition-colors" />
                </button>
              ))}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
