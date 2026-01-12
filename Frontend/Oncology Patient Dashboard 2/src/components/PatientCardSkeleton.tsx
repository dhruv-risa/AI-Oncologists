export function PatientCardSkeleton() {
  return (
    <div className="bg-white rounded-lg shadow-sm border-2 border-gray-200 p-5 animate-pulse">
      {/* Patient Header */}
      <div className="flex items-start justify-between mb-4">
        <div className="flex-1">
          <div className="flex items-center gap-2 mb-1">
            <div className="h-5 bg-gray-200 rounded w-32"></div>
            <div className="h-5 bg-gray-200 rounded-full w-16"></div>
          </div>
          <div className="h-3 bg-gray-200 rounded w-24 mb-1"></div>
          <div className="h-3 bg-gray-200 rounded w-28"></div>
        </div>
        <div className="w-5 h-5 bg-gray-200 rounded flex-shrink-0 mt-1"></div>
      </div>

      {/* Diagnosis Info */}
      <div className="space-y-3 mb-4 pb-4 border-b border-gray-200">
        <div>
          <div className="h-3 bg-gray-200 rounded w-16 mb-1"></div>
          <div className="h-4 bg-gray-200 rounded w-full"></div>
        </div>
        <div className="grid grid-cols-2 gap-3">
          <div>
            <div className="h-3 bg-gray-200 rounded w-12 mb-1"></div>
            <div className="h-4 bg-gray-200 rounded w-20"></div>
          </div>
          <div>
            <div className="h-3 bg-gray-200 rounded w-16 mb-1"></div>
            <div className="h-4 bg-gray-200 rounded w-24"></div>
          </div>
        </div>
      </div>

      {/* Treatment & Appointment */}
      <div className="space-y-2">
        <div>
          <div className="h-3 bg-gray-200 rounded w-28 mb-1"></div>
          <div className="h-4 bg-gray-200 rounded w-full"></div>
        </div>
        <div className="bg-blue-50 rounded-lg px-3 py-2 border border-blue-200">
          <div className="h-4 bg-gray-200 rounded w-full"></div>
        </div>
      </div>
    </div>
  );
}

export function PatientListSkeleton() {
  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 xl:grid-cols-3 gap-5">
      {[...Array(6)].map((_, index) => (
        <PatientCardSkeleton key={index} />
      ))}
    </div>
  );
}
