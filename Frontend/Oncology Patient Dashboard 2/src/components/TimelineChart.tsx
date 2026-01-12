import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, ReferenceLine, Cell } from 'recharts';

const data = [
  { date: 'Mar 23', tumorBurden: 100, treatment: 'Baseline' },
  { date: 'May 23', tumorBurden: 92, treatment: 'Surgery + Chemo' },
  { date: 'Aug 23', tumorBurden: 78, treatment: 'Chemo' },
  { date: 'Nov 23', tumorBurden: 75, treatment: 'Chemo' },
  { date: 'Feb 24', tumorBurden: 73, treatment: 'Maintenance' },
  { date: 'May 24', tumorBurden: 82, treatment: 'Maintenance' },
  { date: 'Jun 24', tumorBurden: 95, treatment: 'Progression' },
  { date: 'Aug 24', tumorBurden: 78, treatment: 'Osimertinib' },
  { date: 'Oct 24', tumorBurden: 68, treatment: 'Osimertinib' },
  { date: 'Dec 24', tumorBurden: 58, treatment: 'Osimertinib' },
];

export function TimelineChart() {
  return (
    <div className="bg-white border border-gray-200 rounded-lg p-4">
      <ResponsiveContainer width="100%" height={250}>
        <BarChart data={data}>
          <CartesianGrid strokeDasharray="3 3" />
          <XAxis dataKey="date" tick={{ fontSize: 12 }} />
          <YAxis tick={{ fontSize: 12 }} label={{ value: 'Tumor Burden (%)', angle: -90, position: 'insideLeft', fontSize: 12 }} />
          <Tooltip 
            content={({ active, payload }) => {
              if (active && payload && payload.length) {
                return (
                  <div className="bg-white p-3 border border-gray-300 rounded shadow-lg">
                    <p className="text-sm text-gray-900">{payload[0].payload.date}</p>
                    <p className="text-sm text-blue-600">Burden: {payload[0].value}%</p>
                    <p className="text-xs text-gray-600">{payload[0].payload.treatment}</p>
                  </div>
                );
              }
              return null;
            }}
          />
          <ReferenceLine y={100} stroke="#6b7280" strokeDasharray="3 3" />
          <Bar dataKey="tumorBurden" radius={[4, 4, 0, 0]}>
            {data.map((entry, index) => (
              <Cell 
                key={`cell-${index}`} 
                fill={entry.tumorBurden > 90 ? '#ef4444' : entry.tumorBurden > 70 ? '#f59e0b' : '#10b981'} 
              />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
      <div className="flex items-center gap-4 mt-3 text-xs">
        <div className="flex items-center gap-2">
          <div className="w-3 h-3 bg-green-500 rounded"></div>
          <span className="text-gray-600">Good response (&lt;70%)</span>
        </div>
        <div className="flex items-center gap-2">
          <div className="w-3 h-3 bg-yellow-500 rounded"></div>
          <span className="text-gray-600">Stable (70-90%)</span>
        </div>
        <div className="flex items-center gap-2">
          <div className="w-3 h-3 bg-red-500 rounded"></div>
          <span className="text-gray-600">Progression (&gt;90%)</span>
        </div>
      </div>
    </div>
  );
}
