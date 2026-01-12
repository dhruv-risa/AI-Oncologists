import { Users, TrendingUp, AlertCircle, CheckCircle } from 'lucide-react';

const metrics = [
  {
    label: 'Total Patients',
    value: '1,247',
    change: '+12%',
    trend: 'up',
    icon: Users,
    color: 'blue',
  },
  {
    label: 'Active Treatments',
    value: '892',
    change: '+8%',
    trend: 'up',
    icon: TrendingUp,
    color: 'green',
  },
  {
    label: 'Critical Cases',
    value: '34',
    change: '-5%',
    trend: 'down',
    icon: AlertCircle,
    color: 'red',
  },
  {
    label: 'Remission',
    value: '423',
    change: '+15%',
    trend: 'up',
    icon: CheckCircle,
    color: 'emerald',
  },
];

export function MetricsGrid() {
  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
      {metrics.map((metric) => {
        const Icon = metric.icon;
        const isPositive = metric.trend === 'up';
        
        return (
          <div
            key={metric.label}
            className="bg-white rounded-lg p-6 shadow-sm border border-gray-200"
          >
            <div className="flex items-start justify-between">
              <div className="flex-1">
                <p className="text-sm text-gray-600 mb-1">{metric.label}</p>
                <p className="text-gray-900 mb-2">{metric.value}</p>
                <span
                  className={`text-sm ${
                    isPositive ? 'text-green-600' : 'text-red-600'
                  }`}
                >
                  {metric.change} from last month
                </span>
              </div>
              <div
                className={`p-3 rounded-lg bg-${metric.color}-50`}
              >
                <Icon className={`w-5 h-5 text-${metric.color}-600`} />
              </div>
            </div>
          </div>
        );
      })}
    </div>
  );
}
