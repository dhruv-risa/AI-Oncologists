import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, ReferenceLine } from 'recharts';
import React, { useMemo } from 'react';
import { calculateLabStatus, getNormalLimitForChart, PREDEFINED_NORMAL_LIMITS } from '../utils/labNormalRanges';

interface TrendDataPoint {
  date: string;
  value: number;
  status?: string;
  source_context?: string;
}

interface BiomarkerData {
  current: {
    value: any;
    unit: string;
    date: string;
    status: string;
    reference_range: string;
    is_abnormal?: boolean;
  };
  trend: TrendDataPoint[];
  trend_direction?: string;
  has_data?: boolean;
}

interface TreatmentStage {
  start_date: string;
  end_date: string;
  label: string;
  color: string;
  borderColor: string;
  textColor: string;
}

interface LabTrendChartProps {
  labName: string;
  biomarkerData: BiomarkerData | null;
  treatmentStages?: TreatmentStage[];
}

// Helper to format date from YYYY-MM-DD to short display format
const formatDateForDisplay = (dateStr: string): string => {
  if (!dateStr) return '';
  try {
    const date = new Date(dateStr);
    const month = date.toLocaleString('en-US', { month: 'short' });
    const year = date.getFullYear().toString().slice(-2);
    return `${month} ${year}`;
  } catch {
    return dateStr;
  }
};

// Helper to convert Tailwind color classes to actual hex colors
// Using DARKER, MORE VIBRANT colors for better visibility
const getTailwindColor = (colorClass: string): string => {
  const colorMap: Record<string, string> = {
    'bg-purple-200': '#d8b4fe',  // Darker purple
    'bg-blue-200': '#93c5fd',     // Darker blue
    'bg-emerald-200': '#6ee7b7',  // Darker emerald
    'bg-amber-200': '#fcd34d',    // Darker amber
    'bg-rose-200': '#fda4af',     // Darker rose
    'border-purple-400': '#a855f7',  // Vibrant purple
    'border-blue-400': '#3b82f6',    // Vibrant blue
    'border-emerald-400': '#10b981', // Vibrant emerald
    'border-amber-400': '#f59e0b',   // Vibrant amber
    'border-rose-400': '#f43f5e',    // Vibrant rose
    'text-purple-700': '#7e22ce',
    'text-blue-700': '#1d4ed8',
    'text-emerald-700': '#047857',
    'text-amber-700': '#b45309',
    'text-rose-700': '#be123c',
  };

  return colorMap[colorClass] || '#cccccc';
};

// Helper function to recalculate status based on predefined normal ranges
const recalculateStatus = (value: number, labName: string): string => {
  const status = calculateLabStatus(labName, value);
  return status || 'Normal';
};

export function LabTrendChart({ labName, biomarkerData, treatmentStages }: LabTrendChartProps) {
  // Check if we have valid data
  if (!biomarkerData || !biomarkerData.has_data || !biomarkerData.trend || biomarkerData.trend.length === 0) {
    return <div className="text-sm text-gray-500">No trend data available for {labName}</div>;
  }

  // Format trend data for the chart and recalculate status based on predefined normal ranges
  const chartData = useMemo(() => {
    const data = biomarkerData.trend
      .filter(point => point.value != null && !isNaN(Number(point.value)))
      .map(point => {
        const value = typeof point.value === 'number' ? point.value : parseFloat(point.value);
        return {
          date: formatDateForDisplay(point.date),
          fullDate: point.date,
          value: value,
          status: recalculateStatus(value, labName) // Recalculate status based on predefined limits
        };
      })
      .sort((a, b) => new Date(a.fullDate).getTime() - new Date(b.fullDate).getTime());

    return data;
  }, [biomarkerData.trend, labName]);

  // If no valid chart data after filtering, show no data message
  if (chartData.length === 0) {
    return <div className="text-sm text-gray-500">No trend data available for {labName}</div>;
  }

  const unit = biomarkerData.current.unit || '';

  // Recalculate current status based on predefined normal ranges
  const currentStatus = calculateLabStatus(labName, biomarkerData.current.value);
  const normalLimit = getNormalLimitForChart(labName, currentStatus);

  // Calculate tick interval based on number of data points
  const tickInterval = useMemo(() => {
    const dataCount = chartData.length;
    if (dataCount <= 4) return 0; // Show all ticks
    if (dataCount <= 8) return 1; // Show every other tick
    if (dataCount <= 12) return 2; // Show every 3rd tick
    return Math.floor(dataCount / 6); // Show ~6 ticks for larger datasets
  }, [chartData.length]);

  // Determine interpretation based on trend
  const interpretation = useMemo(() => {
    if (chartData.length < 2) return `Current value: ${biomarkerData.current.value} ${unit}`;

    const firstValue = chartData[0].value;
    const lastValue = chartData[chartData.length - 1].value;
    const change = lastValue - firstValue;
    const pctChange = ((change / firstValue) * 100).toFixed(1);

    const direction = biomarkerData.trend_direction === 'increasing' ? 'increasing' :
                     biomarkerData.trend_direction === 'decreasing' ? 'decreasing' : 'stable';

    return `${labName} trending ${direction} from ${firstValue} to ${lastValue} ${unit} (${change > 0 ? '+' : ''}${pctChange}% over ${chartData.length} measurements)`;
  }, [chartData, biomarkerData, labName, unit]);

  // Compute treatment overlays with proper date matching
  const treatmentOverlays = useMemo(() => {
    if (!treatmentStages || treatmentStages.length === 0 || chartData.length === 0) {
      console.log(`[${labName}] No treatment stages or chart data available`);
      return { overlays: [], tickMarks: [] };
    }

    console.log(`[${labName}] Computing overlays for ${treatmentStages.length} treatment stages`);
    console.log(`[${labName}] Lab data range: ${chartData[0].fullDate} to ${chartData[chartData.length - 1].fullDate}`);

    const overlays: Array<{
      x1: string;
      x2: string;
      fillColor: string;
      strokeColor: string;
      label: string;
    }> = [];

    const tickMarks: Array<{
      date: string;
      label: string;
      color: string;
    }> = [];

    treatmentStages.forEach((stage, idx) => {
      // Validate stage dates
      if (!stage.start_date || !stage.end_date) {
        console.log(`[${labName}] Stage ${idx} missing dates:`, stage);
        return;
      }

      const stageStart = new Date(stage.start_date).getTime();
      const stageEnd = new Date(stage.end_date).getTime();

      if (isNaN(stageStart) || isNaN(stageEnd)) {
        console.log(`[${labName}] Stage ${idx} invalid dates:`, stage.start_date, stage.end_date);
        return;
      }

      // Check if stage overlaps with lab data
      const labStart = new Date(chartData[0].fullDate).getTime();
      const labEnd = new Date(chartData[chartData.length - 1].fullDate).getTime();

      // No overlap if stage ends before lab starts, or stage starts after lab ends
      if (stageEnd < labStart || stageStart > labEnd) {
        console.log(`[${labName}] Stage ${idx} no overlap with lab data`);
        return;
      }

      // Find the best matching data points for x1 and x2
      // x1 should be the first data point that's on or after the stage start (or first available)
      let x1Idx = 0;
      for (let i = 0; i < chartData.length; i++) {
        const pointTime = new Date(chartData[i].fullDate).getTime();
        if (pointTime >= stageStart) {
          x1Idx = i;
          break;
        }
        // If we've gone past the stage start without finding a point, use the last checked point
        if (pointTime < stageStart && i === chartData.length - 1) {
          x1Idx = i;
        }
      }

      // x2 should be the last data point that's on or before the stage end (or last available)
      let x2Idx = chartData.length - 1;
      for (let i = chartData.length - 1; i >= 0; i--) {
        const pointTime = new Date(chartData[i].fullDate).getTime();
        if (pointTime <= stageEnd) {
          x2Idx = i;
          break;
        }
        // If we've gone before the stage end without finding a point, use the first checked point
        if (pointTime > stageEnd && i === 0) {
          x2Idx = i;
        }
      }

      // Ensure x1 comes before x2
      if (x1Idx > x2Idx) {
        [x1Idx, x2Idx] = [x2Idx, x1Idx];
      }

      // If they're the same and there's more data, expand
      if (x1Idx === x2Idx && chartData.length > 1) {
        if (x2Idx < chartData.length - 1) {
          x2Idx++;
        } else if (x1Idx > 0) {
          x1Idx--;
        }
      }

      const overlay = {
        x1: chartData[x1Idx].date,
        x2: chartData[x2Idx].date,
        fillColor: getTailwindColor(stage.color),
        strokeColor: getTailwindColor(stage.borderColor),
        label: stage.label
      };

      console.log(`[${labName}] Stage ${idx}: "${stage.label}" → Overlay from ${overlay.x1} to ${overlay.x2} (color: ${overlay.fillColor})`);
      overlays.push(overlay);

      // Add tick mark only for treatment start date
      tickMarks.push({
        date: chartData[x1Idx].date,
        label: `${stage.label} Start`,
        color: getTailwindColor(stage.borderColor)
      });
    });

    console.log(`[${labName}] Total overlays created: ${overlays.length}`);
    console.log(`[${labName}] Total tick marks created: ${tickMarks.length}`);
    return { overlays, tickMarks };
  }, [treatmentStages, chartData, labName]);

  if (!chartData || chartData.length === 0) {
    return <div className="text-sm text-gray-500">No trend data available</div>;
  }

  return (
    <div className="bg-white border border-gray-200 rounded-lg p-4">
      {/* Stage Legend - only show if treatment stages are provided */}
      {treatmentStages && treatmentStages.length > 0 && (
        <div className="mb-3 bg-gradient-to-r from-gray-50 to-slate-50 p-3 rounded-lg border border-gray-200">
          <div className="text-xs font-semibold text-gray-700 mb-2">Treatment Timeline:</div>
          <div className="flex flex-wrap items-center gap-4">
            {treatmentStages.map((stage, idx) => {
              const formatDateShort = (dateStr: string) => {
                // Check for invalid dates
                if (!dateStr || dateStr === 'NA' || dateStr === 'N/A' || dateStr === 'null') {
                  return null;
                }

                try {
                  // Format as "DD MMM YYYY" to match treatment tab display
                  const date = new Date(dateStr);

                  // Check if date is valid
                  if (isNaN(date.getTime())) {
                    return null;
                  }

                  const day = date.getDate();
                  const month = date.toLocaleDateString('en-US', { month: 'short' });
                  const year = date.getFullYear();
                  return `${day} ${month} ${year}`;
                } catch {
                  return null;
                }
              };

              // Format start and end dates
              const formattedStart = formatDateShort(stage.start_date);
              const formattedEnd = stage.end_date === new Date().toISOString().split('T')[0]
                ? 'Ongoing'
                : formatDateShort(stage.end_date);

              // Determine date range text
              let dateRangeText = '';
              const showDateRange = formattedStart !== null || formattedEnd !== null;

              if (showDateRange) {
                // If start and end dates are the same, only show one date
                if (formattedStart === formattedEnd && formattedStart !== null) {
                  dateRangeText = `(${formattedStart})`;
                } else {
                  // Show full range
                  dateRangeText = `(${formattedStart || ''} - ${formattedEnd || ''})`;
                }
              }

              return (
                <div key={idx} className="flex items-center gap-1.5 text-xs">
                  <div className={`w-3 h-3 ${stage.color} border-2 ${stage.borderColor} rounded flex-shrink-0`}></div>
                  <span className={`font-medium ${stage.textColor}`}>{stage.label}</span>
                  {showDateRange && (
                    <span className="text-gray-500 text-[10px]">{dateRangeText}</span>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      )}

      <ResponsiveContainer width="100%" height={280}>
        <LineChart data={chartData} margin={{ top: 45, right: 20, bottom: 20, left: 20 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />

          {/* Treatment start tick marks - vertical lines with enhanced visibility */}
          {treatmentOverlays.tickMarks.map((tick, idx) => (
            <ReferenceLine
              key={`tick-${idx}`}
              x={tick.date}
              stroke={tick.color}
              strokeWidth={4}
              strokeDasharray="8 4"
              label={{
                value: tick.label,
                position: 'top',
                fontSize: 12,
                fill: tick.color,
                fontWeight: 'bold',
                offset: 10
              }}
              isFront={true}
            />
          ))}
          <XAxis
            dataKey="date"
            tick={{ fontSize: 12 }}
            interval={tickInterval}
            angle={chartData.length > 8 ? -45 : 0}
            textAnchor={chartData.length > 8 ? "end" : "middle"}
            height={chartData.length > 8 ? 60 : 30}
          />
          <YAxis
            tick={{ fontSize: 12 }}
            label={{ value: `${labName} (${unit})`, angle: -90, position: 'insideLeft', fontSize: 12 }}
          />
          <Tooltip
            content={({ active, payload }) => {
              if (active && payload && payload.length) {
                const data = payload[0].payload;

                // Get normal range for this biomarker
                const normalRange = PREDEFINED_NORMAL_LIMITS[labName];

                // Get status color based on recalculated status
                const getStatusColor = (status: string) => {
                  if (status === 'High') return 'text-red-600';
                  if (status === 'Low') return 'text-amber-600';
                  return 'text-green-600';
                };

                // Get status explanation with normal range bounds
                const getStatusExplanation = (status: string) => {
                  if (!normalRange) return null;

                  if (status === 'High') {
                    return `Above upper limit (>${normalRange.upper} ${unit})`;
                  } else if (status === 'Low') {
                    return `Below lower limit (<${normalRange.lower} ${unit})`;
                  } else {
                    return `Within normal range (${normalRange.lower}-${normalRange.upper} ${unit})`;
                  }
                };

                return (
                  <div className="bg-white p-3 border-2 border-gray-300 rounded shadow-lg">
                    <p className="font-semibold text-gray-800 mb-2 text-sm">{data.fullDate}</p>
                    <p className="text-blue-600 font-semibold text-sm mb-1">
                      Value: {data.value} {unit}
                    </p>
                    {data.status && (
                      <>
                        <p className={`font-bold text-sm ${getStatusColor(data.status)}`}>
                          Status: {data.status}
                        </p>
                        <p className="text-gray-600 text-xs mt-1">
                          {getStatusExplanation(data.status)}
                        </p>
                      </>
                    )}
                  </div>
                );
              }
              return null;
            }}
          />

          {normalLimit !== null && (
            <ReferenceLine
              y={normalLimit}
              stroke="#ef4444"
              strokeDasharray="5 5"
              strokeWidth={2}
              label={{
                value: `Normal limit: ${normalLimit}`,
                fontSize: 10,
                fill: '#ef4444',
                fontWeight: 'bold',
                position: 'insideTopRight',
                offset: 10
              }}
            />
          )}
          <Line
            type="monotone"
            dataKey="value"
            stroke="#3b82f6"
            strokeWidth={2}
            dot={{ r: 4 }}
            activeDot={{ r: 6 }}
          />
        </LineChart>
      </ResponsiveContainer>
      <p className="text-xs text-gray-600 mt-2">
        {interpretation}
      </p>
    </div>
  );
}