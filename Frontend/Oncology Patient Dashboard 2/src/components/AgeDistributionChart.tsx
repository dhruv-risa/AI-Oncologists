import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend } from 'recharts';

const data = [
  { ageGroup: '0-20', male: 12, female: 15 },
  { ageGroup: '21-30', male: 34, female: 42 },
  { ageGroup: '31-40', male: 89, female: 102 },
  { ageGroup: '41-50', male: 156, female: 178 },
  { ageGroup: '51-60', male: 234, female: 201 },
  { ageGroup: '61-70', male: 198, female: 165 },
  { ageGroup: '71+', male: 87, female: 74 },
];

export function AgeDistributionChart() {
  return (
    <div className="bg-white rounded-lg p-6 shadow-sm border border-gray-200">
      <h3 className="text-gray-900 mb-4">Age Distribution by Gender</h3>
      <ResponsiveContainer width="100%" height={300}>
        <BarChart data={data}>
          <CartesianGrid strokeDasharray="3 3" />
          <XAxis dataKey="ageGroup" />
          <YAxis />
          <Tooltip />
          <Legend />
          <Bar dataKey="male" fill="#3b82f6" name="Male" />
          <Bar dataKey="female" fill="#ec4899" name="Female" />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
