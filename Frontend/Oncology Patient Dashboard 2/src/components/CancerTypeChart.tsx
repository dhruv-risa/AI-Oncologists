import { PieChart, Pie, Cell, ResponsiveContainer, Legend, Tooltip } from 'recharts';

const data = [
  { name: 'Breast Cancer', value: 312, color: '#3b82f6' },
  { name: 'Lung Cancer', value: 245, color: '#8b5cf6' },
  { name: 'Colorectal Cancer', value: 198, color: '#10b981' },
  { name: 'Prostate Cancer', value: 176, color: '#f59e0b' },
  { name: 'Leukemia', value: 142, color: '#ef4444' },
  { name: 'Other', value: 174, color: '#6b7280' },
];

export function CancerTypeChart() {
  return (
    <div className="bg-white rounded-lg p-6 shadow-sm border border-gray-200">
      <h3 className="text-gray-900 mb-4">Cancer Type Distribution</h3>
      <ResponsiveContainer width="100%" height={300}>
        <PieChart>
          <Pie
            data={data}
            cx="50%"
            cy="50%"
            labelLine={false}
            label={({ name, percent }) => `${name} ${(percent * 100).toFixed(0)}%`}
            outerRadius={80}
            fill="#8884d8"
            dataKey="value"
          >
            {data.map((entry, index) => (
              <Cell key={`cell-${index}`} fill={entry.color} />
            ))}
          </Pie>
          <Tooltip />
          <Legend />
        </PieChart>
      </ResponsiveContainer>
    </div>
  );
}
