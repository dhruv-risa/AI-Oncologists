import { 
  Stethoscope, 
  Microscope, 
  Dna, 
  Scan, 
  FlaskConical, 
  Pill, 
  HeartPulse, 
  FileText,
} from 'lucide-react';

interface TabNavigationProps {
  activeTab: string;
  onTabChange: (tab: string) => void;
}

const tabs = [
  { id: 'diagnosis', label: 'Diagnosis', icon: Stethoscope },
  { id: 'pathology', label: 'Pathology', icon: Microscope },
  { id: 'genomics', label: 'Genomics', icon: Dna },
  { id: 'radiology', label: 'Radiology', icon: Scan },
  { id: 'labs', label: 'Labs', icon: FlaskConical },
  { id: 'treatment', label: 'Treatment', icon: Pill },
  { id: 'comorbidities', label: 'Comorbidities', icon: HeartPulse },
  { id: 'documents', label: 'Documents', icon: FileText },
];

export function TabNavigation({ activeTab, onTabChange }: TabNavigationProps) {
  return (
    <div className="bg-white rounded-lg shadow-sm border border-gray-200 overflow-x-auto">
      {/* Horizontal Navigation */}
      <nav className="flex items-center px-2 py-2 gap-1">
        {tabs.map((tab) => {
          const Icon = tab.icon;
          return (
            <button
              key={tab.id}
              onClick={() => onTabChange(tab.id)}
              className={`flex items-center gap-2 px-4 py-2.5 text-sm transition-all rounded-lg whitespace-nowrap ${
                activeTab === tab.id
                  ? 'text-blue-700 bg-blue-50 border-b-2 border-blue-600 font-medium shadow-sm'
                  : 'text-gray-600 border-b-2 border-transparent hover:text-gray-900 hover:bg-gray-50'
              }`}
            >
              <Icon className={`w-4 h-4 flex-shrink-0 ${
                activeTab === tab.id ? 'text-blue-600' : 'text-gray-400'
              }`} />
              <span>{tab.label}</span>
            </button>
          );
        })}
      </nav>
    </div>
  );
}