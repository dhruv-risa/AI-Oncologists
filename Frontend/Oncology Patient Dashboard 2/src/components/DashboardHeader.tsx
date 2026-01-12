import { Activity } from 'lucide-react';

export function DashboardHeader() {
  return (
    <header className="bg-white border-b border-gray-200">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
        <div className="flex items-center gap-3">
          <div className="bg-blue-600 p-2 rounded-lg">
            <Activity className="w-6 h-6 text-white" />
          </div>
          <div>
            <h1 className="text-gray-900">Oncology Patient Characterizations</h1>
            <p className="text-gray-500 text-sm mt-1">
              Comprehensive patient analytics and insights
            </p>
          </div>
        </div>
      </div>
    </header>
  );
}
