import { CheckCircle, AlertTriangle, Calendar, Activity } from 'lucide-react';

export function RightSidebar() {
  return (
    <div className="w-80 flex-shrink-0 space-y-4">
      {/* Actionable Mutation */}
      <div className="bg-white rounded-xl p-5 border-2 border-emerald-200 shadow-lg">
        <div className="flex items-start gap-3">
          <div className="w-10 h-10 bg-emerald-500 rounded-lg flex items-center justify-center flex-shrink-0">
            <CheckCircle className="w-5 h-5 text-white" />
          </div>
          <div className="flex-1">
            <div className="flex items-center gap-2 mb-1">
              <p className="text-sm text-emerald-950">EGFR Exon 19 deletion</p>
            </div>
            <p className="text-xs text-emerald-700 mb-2">Actionable target identified</p>
            <div className="flex items-center gap-1.5">
              <div className="h-1.5 flex-1 bg-emerald-100 rounded-full overflow-hidden">
                <div className="h-full w-full bg-emerald-500 rounded-full"></div>
              </div>
              <span className="text-xs text-emerald-700">100%</span>
            </div>
          </div>
        </div>
      </div>

      {/* Current Treatment */}
      <div className="bg-white rounded-xl p-5 border border-blue-200 shadow-sm">
        <p className="text-xs text-blue-700 uppercase tracking-wider mb-2">Current Treatment</p>
        <p className="text-blue-950 mb-1">Osimertinib 80mg daily</p>
        <div className="flex items-center gap-2 text-xs text-blue-600">
          <div className="w-2 h-2 bg-blue-500 rounded-full animate-pulse"></div>
          <span>Active since Jul 10, 2024</span>
        </div>
      </div>

      {/* Clinical Alerts */}
      <div className="bg-white rounded-xl p-5 border border-amber-200 shadow-sm">
        <div className="flex items-center gap-2 mb-3">
          <AlertTriangle className="w-4 h-4 text-amber-600" />
          <p className="text-xs text-amber-800 uppercase tracking-wider">Clinical Alerts</p>
        </div>
        <div className="space-y-2">
          <div className="flex items-center gap-2">
            <div className="w-1.5 h-1.5 bg-amber-500 rounded-full"></div>
            <span className="text-sm text-amber-900">Liver dysfunction</span>
          </div>
          <div className="flex items-center gap-2">
            <div className="w-1.5 h-1.5 bg-amber-500 rounded-full"></div>
            <span className="text-sm text-amber-900">Mild anemia</span>
          </div>
        </div>
      </div>

      {/* Recent Activity */}
      <div className="bg-white rounded-xl p-5 border border-slate-200 shadow-sm">
        <div className="flex items-center gap-2 mb-3">
          <Activity className="w-4 h-4 text-slate-600" />
          <p className="text-xs text-slate-800 uppercase tracking-wider">Recent Activity</p>
        </div>
        <div className="space-y-3">
          <div>
            <p className="text-sm text-slate-900">CT Chest imaging</p>
            <p className="text-xs text-slate-500">Dec 12, 2024</p>
          </div>
          <div>
            <p className="text-sm text-slate-900">Lab work completed</p>
            <p className="text-xs text-slate-500">Dec 10, 2024</p>
          </div>
          <div>
            <p className="text-sm text-slate-900">Treatment cycle 4</p>
            <p className="text-xs text-slate-500">Dec 5, 2024</p>
          </div>
        </div>
      </div>

      {/* Next Appointment */}
      <div className="bg-gradient-to-br from-indigo-50 to-blue-50 rounded-xl p-5 border border-indigo-200 shadow-sm">
        <div className="flex items-center gap-2 mb-3">
          <Calendar className="w-4 h-4 text-indigo-600" />
          <p className="text-xs text-indigo-800 uppercase tracking-wider">Next Appointment</p>
        </div>
        <p className="text-indigo-950 mb-1">Follow-up consultation</p>
        <p className="text-sm text-indigo-700">Dec 22, 2024 at 2:30 PM</p>
        <p className="text-xs text-indigo-600 mt-2">Dr. Michael Roberts</p>
      </div>
    </div>
  );
}
