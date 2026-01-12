import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend } from 'recharts';

const data = [
  { month: 'Jan', remission: 45, stable: 120, progressive: 23 },
  { month: 'Feb', remission: 52, stable: 118, progressive: 21 },
  { month: 'Mar', remission: 61, stable: 115, progressive: 19 },
  { month: 'Apr', remission: 68, stable: 122, progressive: 17 },
  { month: 'May', remission: 75, stable: 119, progressive: 15 },
  { month: 'Jun', remission: 83, stable: 117, progressive: 14 },
];

export function OutcomesChart() {
  return (
    <div className="bg-white rounded-lg p-6 shadow-sm border border-gray-200">
      <h3 className="text-gray-900 mb-4">Treatment Outcomes (6-Month Trend)</h3>
      <ResponsiveContainer width="100%" height={300}>
        <LineChart data={data}>
          <CartesianGrid strokeDasharray="3 3" />
          <XAxis dataKey="month" />
          <YAxis />
          <Tooltip />
          <Legend />
          <Line type="monotone" dataKey="remission" stroke="#10b981" strokeWidth={2} name="Remission" />
          <Line type="monotone" dataKey="stable" stroke="#3b82f6" strokeWidth={2} name="Stable" />
          <Line type="monotone" dataKey="progressive" stroke="#ef4444" strokeWidth={2} name="Progressive" />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
