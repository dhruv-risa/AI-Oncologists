import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend } from 'recharts';

const data = [
  { stage: 'Stage I', patients: 298 },
  { stage: 'Stage II', patients: 387 },
  { stage: 'Stage III', patients: 342 },
  { stage: 'Stage IV', patients: 220 },
];

export function TreatmentStageChart() {
  return (
    <div className="bg-white rounded-lg p-6 shadow-sm border border-gray-200">
      <h3 className="text-gray-900 mb-4">Treatment Stage Distribution</h3>
      <ResponsiveContainer width="100%" height={300}>
        <BarChart data={data}>
          <CartesianGrid strokeDasharray="3 3" />
          <XAxis dataKey="stage" />
          <YAxis />
          <Tooltip />
          <Legend />
          <Bar dataKey="patients" fill="#10b981" name="Patients" />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
