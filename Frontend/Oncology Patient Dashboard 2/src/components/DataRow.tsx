interface DataRowProps {
  label: string;
  value: string;
  highlight?: boolean;
  actionable?: boolean;
}

export function DataRow({ label, value, highlight, actionable }: DataRowProps) {
  return (
    <div className={`${highlight ? 'bg-yellow-50 border border-yellow-200 rounded-lg p-3' : ''}`}>
      <dt className="text-sm text-gray-600 mb-1">{label}</dt>
      <dd className={`text-sm text-gray-900 ${actionable ? 'font-medium' : ''}`}>
        {value}
        {actionable && (
          <span className="ml-2 text-xs bg-green-100 text-green-800 px-2 py-1 rounded">
            Actionable
          </span>
        )}
      </dd>
    </div>
  );
}
