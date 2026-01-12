import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, ReferenceLine, ReferenceArea } from 'recharts';

const labTrendData = {
  CEA: {
    data: [
      { date: 'Mar 23', value: 18.5 },
      { date: 'May 23', value: 15.2 },
      { date: 'Jul 23', value: 12.8 },
      { date: 'Sep 23', value: 9.6 },
      { date: 'Nov 23', value: 8.1 },
      { date: 'Jan 24', value: 7.4 },
      { date: 'Mar 24', value: 6.8 },
      { date: 'May 24', value: 9.2 },
      { date: 'Jul 24', value: 7.5 },
      { date: 'Sep 24', value: 5.8 },
      { date: 'Nov 24', value: 4.6 },
      { date: 'Dec 24', value: 4.2 },
    ],
    unit: 'ng/mL',
    normalLimit: 5,
    interpretation: 'CEA trending down from 18.5 to 4.2 ng/mL, now within normal range. Spike in May 2024 correlated with disease progression.',
  },
  'CA19-9': {
    data: [
      { date: 'Mar 23', value: 42 },
      { date: 'May 23', value: 38 },
      { date: 'Jul 23', value: 35 },
      { date: 'Sep 23', value: 28 },
      { date: 'Nov 23', value: 25 },
      { date: 'Jan 24', value: 22 },
      { date: 'Mar 24', value: 20 },
      { date: 'May 24', value: 19 },
      { date: 'Jul 24', value: 21 },
      { date: 'Sep 24', value: 19 },
      { date: 'Nov 24', value: 18 },
      { date: 'Dec 24', value: 18 },
    ],
    unit: 'U/mL',
    normalLimit: 37,
    interpretation: 'CA19-9 remains stable within normal range, trending from 42 to 18 U/mL over treatment course.',
  },
  'CA-125': {
    data: [
      { date: 'Mar 23', value: 45 },
      { date: 'May 23', value: 40 },
      { date: 'Jul 23', value: 35 },
      { date: 'Sep 23', value: 30 },
      { date: 'Nov 23', value: 28 },
      { date: 'Jan 24', value: 26 },
      { date: 'Mar 24', value: 24 },
      { date: 'May 24', value: 23 },
      { date: 'Jul 24', value: 22 },
      { date: 'Sep 24', value: 22 },
      { date: 'Nov 24', value: 22 },
      { date: 'Dec 24', value: 22 },
    ],
    unit: 'U/mL',
    normalLimit: 35,
    interpretation: 'CA-125 stable within normal range, consistent with current treatment response.',
  },
  WBC: {
    data: [
      { date: 'Mar 23', value: 7.2 },
      { date: 'May 23', value: 6.8 },
      { date: 'Jul 23', value: 7.0 },
      { date: 'Sep 23', value: 6.5 },
      { date: 'Nov 23', value: 6.9 },
      { date: 'Jan 24', value: 7.1 },
      { date: 'Mar 24', value: 6.7 },
      { date: 'May 24', value: 5.8 },
      { date: 'Jul 24', value: 6.4 },
      { date: 'Sep 24', value: 6.6 },
      { date: 'Nov 24', value: 6.8 },
      { date: 'Dec 24', value: 6.8 },
    ],
    unit: 'K/μL',
    normalLimit: null,
    interpretation: 'WBC count remains stable within normal range (4.5-11.0 K/μL), indicating good bone marrow function despite chemotherapy.',
  },
  Hemoglobin: {
    data: [
      { date: 'Mar 23', value: 13.2 },
      { date: 'May 23', value: 12.8 },
      { date: 'Jul 23', value: 12.5 },
      { date: 'Sep 23', value: 11.9 },
      { date: 'Nov 23', value: 11.2 },
      { date: 'Jan 24', value: 10.8 },
      { date: 'Mar 24', value: 10.5 },
      { date: 'May 24', value: 10.1 },
      { date: 'Jul 24', value: 10.3 },
      { date: 'Sep 24', value: 10.0 },
      { date: 'Nov 24', value: 10.2 },
      { date: 'Dec 24', value: 10.2 },
    ],
    unit: 'g/dL',
    normalLimit: 12,
    interpretation: 'Hemoglobin showing gradual decline, currently 10.2 g/dL (mild anemia). Consider erythropoietin support or transfusion if symptomatic.',
  },
  Platelets: {
    data: [
      { date: 'Mar 23', value: 220 },
      { date: 'May 23', value: 210 },
      { date: 'Jul 23', value: 205 },
      { date: 'Sep 23', value: 195 },
      { date: 'Nov 23', value: 190 },
      { date: 'Jan 24', value: 185 },
      { date: 'Mar 24', value: 180 },
      { date: 'May 24', value: 175 },
      { date: 'Jul 24', value: 180 },
      { date: 'Sep 24', value: 182 },
      { date: 'Nov 24', value: 185 },
      { date: 'Dec 24', value: 185 },
    ],
    unit: 'K/μL',
    normalLimit: 150,
    interpretation: 'Platelet count stable within normal range, adequate for continued therapy.',
  },
  ANC: {
    data: [
      { date: 'Mar 23', value: 4.2 },
      { date: 'May 23', value: 4.0 },
      { date: 'Jul 23', value: 4.1 },
      { date: 'Sep 23', value: 3.8 },
      { date: 'Nov 23', value: 3.9 },
      { date: 'Jan 24', value: 4.0 },
      { date: 'Mar 24', value: 3.7 },
      { date: 'May 24', value: 3.5 },
      { date: 'Jul 24', value: 3.6 },
      { date: 'Sep 24', value: 3.7 },
      { date: 'Nov 24', value: 3.8 },
      { date: 'Dec 24', value: 3.8 },
    ],
    unit: 'K/μL',
    normalLimit: 1.5,
    interpretation: 'ANC maintained above 1.5 K/μL, indicating preserved immune function. No need for growth factor support.',
  },
  Creatinine: {
    data: [
      { date: 'Mar 23', value: 0.9 },
      { date: 'May 23', value: 0.9 },
      { date: 'Jul 23', value: 0.8 },
      { date: 'Sep 23', value: 0.9 },
      { date: 'Nov 23', value: 0.9 },
      { date: 'Jan 24', value: 0.8 },
      { date: 'Mar 24', value: 0.9 },
      { date: 'May 24', value: 0.9 },
      { date: 'Jul 24', value: 0.9 },
      { date: 'Sep 24', value: 0.9 },
      { date: 'Nov 24', value: 0.9 },
      { date: 'Dec 24', value: 0.9 },
    ],
    unit: 'mg/dL',
    normalLimit: 1.2,
    interpretation: 'Creatinine stable at 0.9 mg/dL, indicating normal renal function. No dose adjustments needed.',
  },
  ALT: {
    data: [
      { date: 'Mar 23', value: 28 },
      { date: 'May 23', value: 32 },
      { date: 'Jul 23', value: 35 },
      { date: 'Sep 23', value: 38 },
      { date: 'Nov 23', value: 42 },
      { date: 'Jan 24', value: 45 },
      { date: 'Mar 24', value: 48 },
      { date: 'May 24', value: 52 },
      { date: 'Jul 24', value: 55 },
      { date: 'Sep 24', value: 56 },
      { date: 'Nov 24', value: 58 },
      { date: 'Dec 24', value: 58 },
    ],
    unit: 'U/L',
    normalLimit: 40,
    interpretation: 'ALT elevated at 58 U/L (Grade 1 hepatotoxicity). Monitor closely. Consider hepatoprotective agents or dose reduction if continues to rise.',
  },
  AST: {
    data: [
      { date: 'Mar 23', value: 26 },
      { date: 'May 23', value: 30 },
      { date: 'Jul 23', value: 33 },
      { date: 'Sep 23', value: 36 },
      { date: 'Nov 23', value: 40 },
      { date: 'Jan 24', value: 42 },
      { date: 'Mar 24', value: 45 },
      { date: 'May 24', value: 48 },
      { date: 'Jul 24', value: 50 },
      { date: 'Sep 24', value: 51 },
      { date: 'Nov 24', value: 52 },
      { date: 'Dec 24', value: 52 },
    ],
    unit: 'U/L',
    normalLimit: 40,
    interpretation: 'AST elevated at 52 U/L, paralleling ALT elevation. Pattern consistent with drug-induced liver injury.',
  },
  'Total Bilirubin': {
    data: [
      { date: 'Mar 23', value: 0.7 },
      { date: 'May 23', value: 0.7 },
      { date: 'Jul 23', value: 0.8 },
      { date: 'Sep 23', value: 0.8 },
      { date: 'Nov 23', value: 0.8 },
      { date: 'Jan 24', value: 0.7 },
      { date: 'Mar 24', value: 0.8 },
      { date: 'May 24', value: 0.8 },
      { date: 'Jul 24', value: 0.8 },
      { date: 'Sep 24', value: 0.8 },
      { date: 'Nov 24', value: 0.8 },
      { date: 'Dec 24', value: 0.8 },
    ],
    unit: 'mg/dL',
    normalLimit: 1.2,
    interpretation: 'Total bilirubin stable within normal range, indicating preserved hepatic synthetic function despite elevated transaminases.',
  },
};

interface LabTrendChartProps {
  labName: string;
}

export function LabTrendChart({ labName }: LabTrendChartProps) {
  const labData = labTrendData[labName as keyof typeof labTrendData];

  if (!labData) {
    return <div className="text-sm text-gray-500">No trend data available</div>;
  }

  return (
    <div className="bg-white border border-gray-200 rounded-lg p-4">
      {/* Stage Legend */}
      <div className="flex items-center gap-4 mb-3 text-xs">
        <div className="flex items-center gap-1.5">
          <div className="w-3 h-3 bg-purple-200 border border-purple-400 rounded"></div>
          <span className="text-gray-600">Post-Surgery (Mar-Jun 2023)</span>
        </div>
        <div className="flex items-center gap-1.5">
          <div className="w-3 h-3 bg-blue-200 border border-blue-400 rounded"></div>
          <span className="text-gray-600">1L Chemo (Jun 2023-Apr 2024)</span>
        </div>
        <div className="flex items-center gap-1.5">
          <div className="w-3 h-3 bg-amber-200 border border-amber-400 rounded"></div>
          <span className="text-gray-600">Progression (Apr-Jun 2024)</span>
        </div>
        <div className="flex items-center gap-1.5">
          <div className="w-3 h-3 bg-emerald-200 border border-emerald-400 rounded"></div>
          <span className="text-gray-600">2L Osimertinib (Jun 2024-Present)</span>
        </div>
      </div>

      <ResponsiveContainer width="100%" height={200}>
        <LineChart data={labData.data}>
          {/* Stage overlays - colored background regions */}
          <ReferenceArea x1="Mar 23" x2="May 23" fill="#e9d5ff" fillOpacity={0.3} stroke="#c084fc" strokeOpacity={0.5} label={{ value: 'Post-Surgery', position: 'top', fontSize: 10, fill: '#7e22ce' }} />
          <ReferenceArea x1="Jul 23" x2="Mar 24" fill="#bfdbfe" fillOpacity={0.3} stroke="#60a5fa" strokeOpacity={0.5} label={{ value: '1L Chemo', position: 'top', fontSize: 10, fill: '#1e40af' }} />
          <ReferenceArea x1="May 24" x2="Jul 24" fill="#fde68a" fillOpacity={0.3} stroke="#fbbf24" strokeOpacity={0.5} label={{ value: 'Progression', position: 'top', fontSize: 10, fill: '#b45309' }} />
          <ReferenceArea x1="Jul 24" x2="Dec 24" fill="#d1fae5" fillOpacity={0.3} stroke="#6ee7b7" strokeOpacity={0.5} label={{ value: '2L Osimertinib', position: 'top', fontSize: 10, fill: '#065f46' }} />
          
          <CartesianGrid strokeDasharray="3 3" />
          <XAxis dataKey="date" tick={{ fontSize: 12 }} />
          <YAxis tick={{ fontSize: 12 }} label={{ value: `${labName} (${labData.unit})`, angle: -90, position: 'insideLeft', fontSize: 12 }} />
          <Tooltip />
          {labData.normalLimit && (
            <ReferenceLine y={labData.normalLimit} stroke="#ef4444" strokeDasharray="3 3" label={{ value: 'Normal limit', fontSize: 10 }} />
          )}
          <Line type="monotone" dataKey="value" stroke="#3b82f6" strokeWidth={2} dot={{ r: 4 }} />
        </LineChart>
      </ResponsiveContainer>
      <p className="text-xs text-gray-600 mt-2">
        {labData.interpretation}
      </p>
    </div>
  );
}