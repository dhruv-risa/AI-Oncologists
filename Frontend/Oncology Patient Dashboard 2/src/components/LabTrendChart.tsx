import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, ReferenceLine } from 'recharts';
import React, { useMemo, useState } from 'react';
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

interface RelevantStage extends TreatmentStage {
  isContextOnly?: boolean;
}

interface LabTrendChartProps {
  labName: string;
  biomarkerData: BiomarkerData | null;
  treatmentStages?: TreatmentStage[];
}

// Helper to format date from YYYY-MM-DD to DD/MM/YYYY format
const formatDateForDisplay = (dateStr: string): string => {
  if (!dateStr) return '';
  try {
    const date = new Date(dateStr);
    const day = date.getDate().toString().padStart(2, '0');
    const month = (date.getMonth() + 1).toString().padStart(2, '0');
    const year = date.getFullYear();
    return day + '/' + month + '/' + year;
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
          status: recalculateStatus(value, labName), // Recalculate status based on predefined limits
          isPhantom: false // This is a real data point
        };
      })
      .sort((a, b) => new Date(a.fullDate).getTime() - new Date(b.fullDate).getTime());

    // Add phantom data points for treatment start dates (so ReferenceLine can position correctly)
    // Add phantom points for: 1) most recent prior treatment, 2) treatments during/after lab data
    if (treatmentStages && treatmentStages.length > 0 && data.length > 0) {
      // Get the lab data start time to determine which treatments need phantom points
      const labStartTime = new Date(data[0].fullDate).getTime();

      // Find the most recent treatment that started before lab data
      let mostRecentPriorTreatment: TreatmentStage | null = null;
      let mostRecentPriorTime = -Infinity;

      treatmentStages.forEach(stage => {
        if (stage.start_date) {
          const startTime = new Date(stage.start_date).getTime();
          if (startTime < labStartTime && startTime > mostRecentPriorTime) {
            mostRecentPriorTreatment = stage;
            mostRecentPriorTime = startTime;
          }
        }
      });

      treatmentStages.forEach(stage => {
        if (stage.start_date) {
          const startTime = new Date(stage.start_date).getTime();

          // Add phantom point if:
          // 1. Treatment started during or after lab data range, OR
          // 2. This is the most recent prior treatment (for context)
          const shouldAddPhantom = startTime >= labStartTime || stage === mostRecentPriorTreatment;

          if (shouldAddPhantom) {
            const formattedDate = formatDateForDisplay(stage.start_date);

            // Check if this date already exists in data
            const existingPoint = data.find(d => d.date === formattedDate);
            if (!existingPoint) {
              // Find surrounding points to interpolate a value
              const beforePoints = data.filter(d => new Date(d.fullDate).getTime() < startTime);
              const afterPoints = data.filter(d => new Date(d.fullDate).getTime() > startTime);

              let interpolatedValue = null;
              if (beforePoints.length > 0 && afterPoints.length > 0) {
                // Linear interpolation between closest points
                const before = beforePoints[beforePoints.length - 1];
                const after = afterPoints[0];
                const beforeTime = new Date(before.fullDate).getTime();
                const afterTime = new Date(after.fullDate).getTime();
                const ratio = (startTime - beforeTime) / (afterTime - beforeTime);
                interpolatedValue = before.value + ratio * (after.value - before.value);
              } else if (beforePoints.length > 0) {
                interpolatedValue = beforePoints[beforePoints.length - 1].value;
              } else if (afterPoints.length > 0) {
                interpolatedValue = afterPoints[0].value;
              }

              if (interpolatedValue !== null) {
                data.push({
                  date: formattedDate,
                  fullDate: stage.start_date,
                  value: interpolatedValue,
                  status: recalculateStatus(interpolatedValue, labName),
                  isPhantom: true // This is a phantom point for treatment start positioning
                });
              }
            }
          }
        }
      });

      // Add an extra phantom point one day before the most recent prior treatment
      // This extends the X-axis for better visibility
      if (mostRecentPriorTreatment && mostRecentPriorTreatment.start_date) {
        const priorStartTime = new Date(mostRecentPriorTreatment.start_date).getTime();
        const oneDayBefore = new Date(priorStartTime - 24 * 60 * 60 * 1000); // 1 day = 24 hours * 60 min * 60 sec * 1000 ms
        const oneDayBeforeFormatted = formatDateForDisplay(oneDayBefore.toISOString().split('T')[0]);

        // Check if this date already exists
        const existingPoint = data.find(d => d.date === oneDayBeforeFormatted);
        if (!existingPoint) {
          // Use interpolation to find value
          const beforePoints = data.filter(d => new Date(d.fullDate).getTime() < oneDayBefore.getTime());
          const afterPoints = data.filter(d => new Date(d.fullDate).getTime() > oneDayBefore.getTime());

          let interpolatedValue = null;
          if (beforePoints.length > 0 && afterPoints.length > 0) {
            const before = beforePoints[beforePoints.length - 1];
            const after = afterPoints[0];
            const beforeTime = new Date(before.fullDate).getTime();
            const afterTime = new Date(after.fullDate).getTime();
            const ratio = (oneDayBefore.getTime() - beforeTime) / (afterTime - beforeTime);
            interpolatedValue = before.value + ratio * (after.value - before.value);
          } else if (beforePoints.length > 0) {
            interpolatedValue = beforePoints[beforePoints.length - 1].value;
          } else if (afterPoints.length > 0) {
            interpolatedValue = afterPoints[0].value;
          }

          if (interpolatedValue !== null) {
            data.push({
              date: oneDayBeforeFormatted,
              fullDate: oneDayBefore.toISOString().split('T')[0],
              value: interpolatedValue,
              status: recalculateStatus(interpolatedValue, labName),
              isPhantom: true // Phantom point for X-axis padding
            });
          }
        }
      }

      // Re-sort after adding phantom points
      data.sort((a, b) => new Date(a.fullDate).getTime() - new Date(b.fullDate).getTime());
    }

    return data;
  }, [biomarkerData.trend, labName, treatmentStages]);

  // If no valid chart data after filtering, show no data message
  if (chartData.length === 0) {
    return <div className="text-sm text-gray-500">No trend data available for {labName}</div>;
  }

  const unit = biomarkerData.current.unit || '';

  // Recalculate current status based on predefined normal ranges
  const currentStatus = calculateLabStatus(labName, biomarkerData.current.value);
  const normalLimit = getNormalLimitForChart(labName, currentStatus);

  // Show all ticks for every data point
  const tickInterval = 0; // 0 means show all ticks

  // State for current window index
  const [windowIndex, setWindowIndex] = useState(0);

  // Calculate 2-month time windows starting from the latest date
  const windows = useMemo(() => {
    // Get the date range of real data points
    const realDataPoints = chartData.filter(d => !d.isPhantom);
    if (realDataPoints.length === 0) return [chartData];

    // Sort by date to ensure correct ordering
    const sortedData = [...chartData].sort((a, b) =>
      new Date(a.fullDate).getTime() - new Date(b.fullDate).getTime()
    );

    const latestDate = new Date(sortedData[sortedData.length - 1].fullDate);
    const earliestDate = new Date(sortedData[0].fullDate);

    // Create 2-month windows starting from the latest date going backwards
    const windows: typeof chartData[] = [];
    let windowEndDate = new Date(latestDate);

    while (windowEndDate >= earliestDate) {
      // Calculate window start date (2 months before end date)
      const windowStartDate = new Date(windowEndDate);
      windowStartDate.setMonth(windowStartDate.getMonth() - 2);

      // Filter data points that fall within this window
      const windowData = sortedData.filter(point => {
        const pointDate = new Date(point.fullDate);
        return pointDate >= windowStartDate && pointDate <= windowEndDate;
      });

      if (windowData.length > 0) {
        windows.push(windowData);
      }

      // Move to next window (going backwards in time)
      windowEndDate = new Date(windowStartDate);
      windowEndDate.setDate(windowEndDate.getDate() - 1); // Start one day before the previous window

      // Safety check to prevent infinite loop
      if (windows.length > 100) break;
    }

    return windows.length > 0 ? windows : [sortedData];
  }, [chartData]);

  // Get the current window data
  const displayData = useMemo(() => {
    return windows[windowIndex] || chartData;
  }, [windows, windowIndex, chartData]);

  // Navigation handlers - left shows older data, right shows newer data
  const canGoLeft = windowIndex < windows.length - 1; // Can go to older data
  const canGoRight = windowIndex > 0; // Can go to newer data

  const handleLeft = () => {
    if (canGoLeft) setWindowIndex(windowIndex + 1); // Increase index = older data
  };

  const handleRight = () => {
    if (canGoRight) setWindowIndex(windowIndex - 1); // Decrease index = newer data
  };

  // Get date range of current window for display
  const windowDateRange = useMemo(() => {
    if (displayData.length === 0) return '';
    const realPoints = displayData.filter(d => !d.isPhantom);
    if (realPoints.length === 0) return '';
    const start = realPoints[0].fullDate;
    const end = realPoints[realPoints.length - 1].fullDate;
    return `${formatDateForDisplay(start)} - ${formatDateForDisplay(end)}`;
  }, [displayData]);

  // Determine interpretation based on trend (excluding phantom points)
  const interpretation = useMemo(() => {
    const realDataPoints = displayData.filter(d => !d.isPhantom);

    if (realDataPoints.length < 2) {
      return 'Current value: ' + biomarkerData.current.value + ' ' + unit;
    }

    const firstValue = realDataPoints[0].value;
    const lastValue = realDataPoints[realDataPoints.length - 1].value;
    const change = lastValue - firstValue;
    const pctChange = ((change / firstValue) * 100).toFixed(1);

    const direction = change > 0 ? 'increasing' : change < 0 ? 'decreasing' : 'stable';

    const changePrefix = change > 0 ? '+' : '';
    return labName + ' trending ' + direction + ' from ' + firstValue + ' to ' + lastValue + ' ' + unit + ' (' + changePrefix + pctChange + '% over ' + realDataPoints.length + ' measurements)';
  }, [displayData, biomarkerData, labName, unit]);

  // Compute treatment overlays with proper date matching
  const treatmentOverlays = useMemo(() => {
    if (!treatmentStages || treatmentStages.length === 0 || displayData.length === 0) {
      console.log('[' + labName + '] No treatment stages or chart data available');
      return { overlays: [], tickMarks: [], relevantStages: [] };
    }

    // Get lab data X-axis limits (only real data points, not phantom)
    const realDataPoints = displayData.filter(d => !d.isPhantom);
    if (realDataPoints.length === 0) {
      return { overlays: [], tickMarks: [], relevantStages: [] };
    }

    const labStartTime = new Date(realDataPoints[0].fullDate).getTime();
    const labEndTime = new Date(realDataPoints[realDataPoints.length - 1].fullDate).getTime();

    console.log('[' + labName + '] Lab data range: ' + realDataPoints[0].fullDate + ' to ' + realDataPoints[realDataPoints.length - 1].fullDate);

    // Filter treatments to only show relevant ones:
    // 1. The ONE most recent treatment that started before lab data (for context) - no ticker
    // 2. All treatments that started during or after lab data - with tickers

    const relevantStages: RelevantStage[] = [];
    let mostRecentPriorTreatment: TreatmentStage | null = null;
    let mostRecentPriorTime = -Infinity;

    treatmentStages.forEach((stage) => {
      if (!stage.start_date || !stage.end_date) return;

      const stageStart = new Date(stage.start_date).getTime();
      const stageEnd = new Date(stage.end_date).getTime();

      if (isNaN(stageStart) || isNaN(stageEnd)) return;

      // Check if treatment started during or after lab data range
      if (stageStart >= labStartTime) {
        // Treatment started during/after lab data - include it
        relevantStages.push({ ...stage, isContextOnly: false });
      } else if (stageStart < labStartTime && stageStart > mostRecentPriorTime) {
        // Treatment started before lab data - track the most recent one for context
        mostRecentPriorTreatment = stage;
        mostRecentPriorTime = stageStart;
      }
    });

    // Add the most recent prior treatment (if exists) for context, marked as context-only
    if (mostRecentPriorTreatment) {
      const priorStage: RelevantStage = {
        ...mostRecentPriorTreatment,
        isContextOnly: true
      };
      relevantStages.unshift(priorStage);
      console.log('[' + labName + '] Including prior treatment for context: ' + mostRecentPriorTreatment.label);
    }

    console.log('[' + labName + '] Filtered to ' + relevantStages.length + ' relevant treatments (from ' + treatmentStages.length + ' total)');
    console.log('[' + labName + '] Relevant treatments:', relevantStages.map(s => s.label + (s.isContextOnly ? ' (context)' : '')));

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

    // Only process relevant stages (filtered by lab data range)
    relevantStages.forEach((stage) => {
      // Validate stage dates
      if (!stage.start_date || !stage.end_date) {
        console.log('Stage missing dates:', stage);
        return;
      }

      const stageStart = new Date(stage.start_date).getTime();
      const stageEnd = new Date(stage.end_date).getTime();

      if (isNaN(stageStart) || isNaN(stageEnd)) {
        console.log('Stage invalid dates:', stage.start_date, stage.end_date);
        return;
      }

      // Check if stage overlaps with lab data
      const labStart = new Date(displayData[0].fullDate).getTime();
      const labEnd = new Date(displayData[displayData.length - 1].fullDate).getTime();

      // No overlap if stage ends before lab starts, or stage starts after lab ends
      if (stageEnd < labStart || stageStart > labEnd) {
        console.log('Stage no overlap with lab data');
        return;
      }

      // Find the best matching data points for x1 and x2
      // x1 should be the first data point that's on or after the stage start (or first available)
      let x1Idx = 0;
      for (let i = 0; i < displayData.length; i++) {
        const pointTime = new Date(displayData[i].fullDate).getTime();
        if (pointTime >= stageStart) {
          x1Idx = i;
          break;
        }
        // If we've gone past the stage start without finding a point, use the last checked point
        if (pointTime < stageStart && i === displayData.length - 1) {
          x1Idx = i;
        }
      }

      // x2 should be the last data point that's on or before the stage end (or last available)
      let x2Idx = displayData.length - 1;
      for (let i = displayData.length - 1; i >= 0; i--) {
        const pointTime = new Date(displayData[i].fullDate).getTime();
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
      if (x1Idx === x2Idx && displayData.length > 1) {
        if (x2Idx < displayData.length - 1) {
          x2Idx++;
        } else if (x1Idx > 0) {
          x1Idx--;
        }
      }

      const overlay = {
        x1: displayData[x1Idx].date,
        x2: displayData[x2Idx].date,
        fillColor: getTailwindColor(stage.color),
        strokeColor: getTailwindColor(stage.borderColor),
        label: stage.label
      };

      console.log('Overlay created for stage:', stage.label);
      overlays.push(overlay);

      // Add tick mark logic:
      // Show tickers for:
      // 1. Treatments that started during or after lab data range
      // 2. Context-only treatment (most recent prior treatment for context)
      const shouldShowTicker = stageStart >= labStartTime || stage.isContextOnly === true;

      if (shouldShowTicker) {
        const actualStartDate = formatDateForDisplay(stage.start_date);

        // Determine if this is a local therapy or systemic therapy
        // Local therapies (WBRT, surgery) don't have a line number prefix
        // Systemic therapies have a line number (e.g., "1 - Carboplatin")
        const isSystemicTherapy = /^\d+\s*-\s*/.test(stage.label);
        const tickLabel = isSystemicTherapy ? stage.label + ' Start' : stage.label;

        tickMarks.push({
          date: actualStartDate,
          label: tickLabel,
          color: getTailwindColor(stage.borderColor)
        });
        console.log('Adding tick mark for:', stage.label, 'at', actualStartDate);
      } else {
        console.log('Skipping tick mark for:', stage.label);
      }
    });

    console.log('Total overlays created:', overlays.length);
    console.log('Total tick marks created:', tickMarks.length);
    return { overlays, tickMarks, relevantStages };
  }, [treatmentStages, displayData, labName]);

  return (
    <div className="bg-white border border-gray-200 rounded-lg p-4">
      {/* Time Window Navigation */}
      {windows.length > 1 && (
        <div className="mb-4 flex items-center justify-center gap-4">
          <button
            onClick={handleLeft}
            disabled={!canGoLeft}
            className={`w-10 h-10 rounded-full flex items-center justify-center transition-all ${
              canGoLeft
                ? 'bg-blue-500 text-white hover:bg-blue-600 hover:scale-110 shadow-md hover:shadow-lg'
                : 'bg-gray-200 text-gray-400 cursor-not-allowed opacity-50'
            }`}
            title="Show earlier data"
          >
            <span className="text-xl">←</span>
          </button>

          <button
            onClick={handleRight}
            disabled={!canGoRight}
            className={`w-10 h-10 rounded-full flex items-center justify-center transition-all ${
              canGoRight
                ? 'bg-blue-500 text-white hover:bg-blue-600 hover:scale-110 shadow-md hover:shadow-lg'
                : 'bg-gray-200 text-gray-400 cursor-not-allowed opacity-50'
            }`}
            title="Show later data"
          >
            <span className="text-xl">→</span>
          </button>
        </div>
      )}

      {/* Stage Legend - show all treatments for full context */}
      {treatmentStages && treatmentStages.length > 0 && (
        <div className="mb-3 bg-gradient-to-r from-gray-50 to-slate-50 p-3 rounded-lg border border-gray-200">
          <div className="text-xs font-semibold text-gray-700 mb-2">
            Treatment Timeline:
            <span className="text-gray-500 font-normal ml-1">
              (showing all {treatmentStages.length} treatment{treatmentStages.length !== 1 ? 's' : ''})
            </span>
          </div>
          <div className="flex flex-wrap items-center gap-4 max-h-[120px] overflow-y-auto pr-2" style={{ scrollbarWidth: 'thin' }}>
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
                  return day + ' ' + month + ' ' + year;
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
                  dateRangeText = '(' + formattedStart + ')';
                } else {
                  // Show full range
                  dateRangeText = '(' + (formattedStart || '') + ' - ' + (formattedEnd || '') + ')';
                }
              }

              return (
                <div key={idx} className="flex items-center gap-1.5 text-xs">
                  <div className={'w-3 h-3 ' + stage.color + ' border-2 ' + stage.borderColor + ' rounded flex-shrink-0'}></div>
                  <span className={'font-medium ' + stage.textColor}>{stage.label}</span>
                  {showDateRange && (
                    <span className="text-gray-500 text-[10px]">{dateRangeText}</span>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      )}

      <ResponsiveContainer width="100%" height={320}>
        <LineChart data={displayData} margin={{ top: 45, right: 80, bottom: 60, left: 20 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />

          {/* Treatment start tick marks - vertical lines with enhanced visibility */}
          {treatmentOverlays.tickMarks.map((tick, idx) => {
            // If there are too many treatments, reduce label size and visibility to avoid clutter
            const hasManyTreatments = treatmentOverlays.tickMarks.length > 5;

            return (
              <ReferenceLine
                key={'tick-' + idx}
                x={tick.date}
                stroke={tick.color}
                strokeWidth={hasManyTreatments ? 2.5 : 4}
                strokeDasharray="8 4"
                label={{
                  value: tick.label,
                  position: 'top',
                  fontSize: hasManyTreatments ? 9 : 12,
                  fill: tick.color,
                  fontWeight: 'bold',
                  offset: 10,
                }}
                isFront={true}
              />
            );
          })}
          <XAxis
            dataKey="date"
            tick={(props: any) => {
              const { x, y, payload } = props;
              // Find the corresponding data point
              const dataPoint = displayData.find(d => d.date === payload.value);

              // Only show tick if this is a real data point (not phantom)
              if (!dataPoint || dataPoint.isPhantom) {
                return null;
              }

              return (
                <g transform={`translate(${x},${y})`}>
                  <text
                    x={0}
                    y={0}
                    dy={16}
                    textAnchor="end"
                    fill="#666"
                    fontSize={11}
                    transform="rotate(-45)"
                  >
                    {payload.value}
                  </text>
                </g>
              );
            }}
            interval={0}
            height={70}
          />
          <YAxis
            tick={{ fontSize: 12 }}
            label={{ value: labName + ' (' + unit + ')', angle: -90, position: 'insideLeft', fontSize: 12 }}
          />
          <Tooltip
            content={({ active, payload }) => {
              if (active && payload && payload.length) {
                const data = payload[0].payload;

                // Don't show tooltip for phantom data points
                if (data.isPhantom) {
                  return null;
                }

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
                    return 'Above upper limit (>' + normalRange.upper + ' ' + unit + ')';
                  } else if (status === 'Low') {
                    return 'Below lower limit (<' + normalRange.lower + ' ' + unit + ')';
                  } else {
                    return 'Within normal range (' + normalRange.lower + '-' + normalRange.upper + ' ' + unit + ')';
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
                        <p className={'font-bold text-sm ' + getStatusColor(data.status)}>
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
                value: 'Normal limit: ' + normalLimit,
                fontSize: 10,
                fill: '#ef4444',
                fontWeight: 'bold',
                position: 'insideBottomRight',
                offset: 5
              }}
            />
          )}
          <Line
            type="monotone"
            dataKey="value"
            stroke="#3b82f6"
            strokeWidth={2}
            dot={(props: any) => {
              // Don't render dots for phantom data points
              if (props.payload.isPhantom) {
                return null;
              }
              return (
                <circle
                  cx={props.cx}
                  cy={props.cy}
                  r={4}
                  fill="#3b82f6"
                  stroke="#fff"
                  strokeWidth={1}
                />
              );
            }}
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