import { CancerTypeChart } from './CancerTypeChart';
import { AgeDistributionChart } from './AgeDistributionChart';
import { TreatmentStageChart } from './TreatmentStageChart';
import { OutcomesChart } from './OutcomesChart';

export function ChartsSection() {
  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-8">
      <CancerTypeChart />
      <AgeDistributionChart />
      <TreatmentStageChart />
      <OutcomesChart />
    </div>
  );
}
