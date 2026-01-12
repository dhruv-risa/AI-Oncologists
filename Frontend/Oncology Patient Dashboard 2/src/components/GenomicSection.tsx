import { Dna } from 'lucide-react';
import { SectionCard } from './SectionCard';
import { DataRow } from './DataRow';
import { AIInterpretation } from './AIInterpretation';

export function GenomicSection() {
  return (
    <SectionCard title="Genomic & Molecular Testing" icon={Dna}>
      <div className="space-y-4">
        <AIInterpretation
          title="AI Genomic Analysis"
          content="EGFR Exon 19 deletion is a highly actionable mutation with excellent response rates to EGFR tyrosine kinase inhibitors. First-line osimertinib is recommended based on FLAURA trial data showing superior PFS and OS. The high PD-L1 TPS of 75% indicates robust immune activation, though EGFR-mutant tumors typically respond better to targeted therapy than immunotherapy. The intermediate TMB (8 mut/Mb) and MSS status are consistent with EGFR-mutant biology. Recent ctDNA detection (VAF 12.3%) suggests minimal residual disease, warranting close monitoring during treatment."
          variant="info"
        />

        <div>
          <h4 className="text-sm text-gray-700 mb-3">Driver Mutations</h4>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-x-8 gap-y-4">
            <DataRow label="EGFR Mutation" value="Exon 19 deletion (L747_P753delinsS)" highlight actionable />
            <DataRow label="ALK Rearrangement" value="Negative" />
            <DataRow label="ROS1 Rearrangement" value="Negative" />
            <DataRow label="KRAS Mutation" value="Negative" />
            <DataRow label="BRAF Mutation" value="Negative" />
            <DataRow label="MET Exon 14 Skipping" value="Negative" />
            <DataRow label="RET Rearrangement" value="Negative" />
            <DataRow label="HER2 Mutation" value="Negative" />
            <DataRow label="NTRK Fusion" value="Negative" />
          </div>
        </div>

        <div>
          <h4 className="text-sm text-gray-700 mb-3">Biomarkers & Additional Testing</h4>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-x-8 gap-y-4">
            <DataRow label="PD-L1 Expression" value="75% (TPS)" highlight />
            <DataRow label="TMB" value="8 mutations/Mb (Intermediate)" />
            <DataRow label="MSI Status" value="MSS (Microsatellite Stable)" />
            <DataRow label="DNA Repair Genes" value="No pathogenic mutations detected" />
            <DataRow label="ctDNA (Latest)" value="EGFR Ex19del detected (VAF 12.3%)" highlight />
            <DataRow label="Testing Date" value="November 28, 2024" />
          </div>
        </div>

        <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
          <h4 className="text-sm text-blue-900 mb-2">Actionable Mutation Summary</h4>
          <p className="text-sm text-blue-800">
            <strong>EGFR Exon 19 deletion detected</strong> - FDA-approved targeted therapies available (Osimertinib, Erlotinib, Afatinib). High PD-L1 expression (75%) also supports immunotherapy consideration.
          </p>
        </div>
      </div>
    </SectionCard>
  );
}