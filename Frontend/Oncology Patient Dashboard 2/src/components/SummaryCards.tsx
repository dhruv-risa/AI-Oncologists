export function SummaryCards() {
  return (
    <div className="bg-white rounded-xl border border-gray-200 p-6 mb-6">
      <div className="flex items-start justify-between gap-6">
        {/* Current TNM */}
        <div className="flex-1">
          <p className="text-xs text-gray-500 uppercase tracking-wider mb-2">Current TNM</p>
          <p className="text-gray-900 mb-1">T2a N2 M1b (AJCC 8)</p>
          <p className="text-xs text-gray-600">As of 20 Nov 2025</p>
        </div>

        {/* Metastatic sites */}
        <div className="flex-1">
          <p className="text-xs text-gray-500 uppercase tracking-wider mb-2">Metastatic sites</p>
          <div className="flex gap-2">
            <span className="px-2 py-1 bg-gray-900 text-white rounded text-xs">brain</span>
            <span className="px-2 py-1 bg-gray-900 text-white rounded text-xs">bone</span>
          </div>
        </div>

        {/* Actionable summary */}
        <div className="flex-1">
          <p className="text-xs text-gray-500 uppercase tracking-wider mb-2">Actionable summary</p>
          <p className="text-gray-900 mb-1">EGFR L858R</p>
          <p className="text-xs text-gray-600">Candidate for EGFR TKI</p>
        </div>

        {/* Stage and Line */}
        <div className="flex gap-2">
          <span className="px-3 py-1.5 bg-gray-900 text-white rounded-lg text-sm">Stage IVA</span>
          <span className="px-3 py-1.5 bg-red-600 text-white rounded-lg text-sm">metastatic</span>
          <span className="px-3 py-1.5 bg-blue-600 text-white rounded-lg text-sm">Line 2</span>
        </div>
      </div>

      {/* Flags */}
      <div className="mt-4 pt-4 border-t border-gray-200">
        <p className="text-xs text-gray-500 uppercase tracking-wider mb-2">Flags</p>
        <div className="flex gap-2">
          <span className="px-3 py-1.5 bg-red-600 text-white rounded-full text-xs">Liver dysfunction</span>
          <span className="px-3 py-1.5 bg-red-600 text-white rounded-full text-xs">New lesions</span>
          <span className="px-3 py-1.5 bg-orange-500 text-white rounded-full text-xs">Actionable mutation</span>
        </div>
      </div>

      {/* Disease course summary */}
      <div className="mt-4 pt-4 border-t border-gray-200">
        <p className="text-xs text-gray-500 uppercase tracking-wider mb-2">Disease course</p>
        <p className="text-sm text-gray-700 leading-relaxed">
          Stage progressed to IVB with imaging progression; actionable EGFR mutation present; rising CEA; liver dysfunction flag new in Oct 2025.
        </p>
      </div>
    </div>
  );
}
