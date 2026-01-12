import { Stethoscope } from 'lucide-react';
import { SectionCard } from './SectionCard';
import { DataRow } from './DataRow';

export function DiagnosisSection() {
  return (
    <SectionCard title="Primary Diagnosis" icon={Stethoscope}>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-x-8 gap-y-4">
        <DataRow label="Primary Diagnosis" value="Non-Small Cell Lung Cancer (NSCLC)" />
        <DataRow label="Histologic Type" value="Adenocarcinoma" />
        <DataRow label="Diagnosis Date" value="March 12, 2023" />
        <DataRow label="Initial TNM Stage" value="T2aN1M0 (Stage IIB)" />
        <DataRow label="Current TNM Stage" value="T2aN2M1a (Stage IVA)" highlight />
        <DataRow label="Metastatic Status" value="Yes - Active metastases" highlight />
        <DataRow label="Metastatic Sites" value="Contralateral lung, pleural nodules" highlight />
        <DataRow label="Recurrence Status" value="Progressive disease after initial treatment" />
      </div>
    </SectionCard>
  );
}
