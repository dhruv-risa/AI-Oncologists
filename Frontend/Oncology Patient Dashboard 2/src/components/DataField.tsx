interface DataFieldProps {
  label: string;
  value: string;
  highlight?: boolean;
}

export function DataField({ label, value, highlight }: DataFieldProps) {
  return (
    <div>
      <dt className="text-xs text-gray-500 mb-1">{label}</dt>
      <dd className="text-sm text-gray-900">{value}</dd>
    </div>
  );
}