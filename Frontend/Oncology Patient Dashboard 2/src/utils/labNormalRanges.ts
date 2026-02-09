/**
 * Predefined normal ranges for all lab biomarkers
 * Based on standard clinical reference ranges from medical literature and laboratory guidelines
 */

export interface NormalRange {
  upper: number;
  lower: number;
  unit: string;
  source: string;
}

export const PREDEFINED_NORMAL_LIMITS: Record<string, NormalRange> = {
  // ===== TUMOR MARKERS =====
  'CEA': {
    upper: 3.0,
    lower: 0,
    unit: 'ng/mL',
    source: 'ASCO Guidelines - <3.0 for non-smokers, <5.0 for smokers'
  },
  'NSE': {
    upper: 16.3,
    lower: 0,
    unit: 'ng/mL',
    source: 'Clinical Chemistry Reference - Primary marker for SCLC'
  },
  'proGRP': {
    upper: 63,
    lower: 0,
    unit: 'pg/mL',
    source: 'Clinical Guidelines - Superior specificity for SCLC (>90%)'
  },
  'CYFRA 21-1': {
    upper: 3.3,
    lower: 0,
    unit: 'ng/mL',
    source: 'NACB Guidelines - Primary marker for squamous cell carcinoma'
  },

  // ===== COMPLETE BLOOD COUNT (CBC) =====
  'WBC': {
    upper: 11.0,
    lower: 4.5,
    unit: '10^3/μL',
    source: 'Clinical Laboratory Standards - Adult reference range'
  },
  'Hemoglobin': {
    upper: 17.5,
    lower: 12.0,
    unit: 'g/dL',
    source: 'WHO Guidelines - Female: 12.0-16.0, Male: 13.5-17.5'
  },
  'Platelets': {
    upper: 400,
    lower: 150,
    unit: '10^3/μL',
    source: 'Hematology Standards - Normal platelet count'
  },
  'ANC': {
    upper: 7.0,
    lower: 1.5,
    unit: '10^3/μL',
    source: 'NCCN Guidelines - <1.5 = neutropenia, <0.5 = severe'
  },

  // ===== METABOLIC PANEL =====
  'Creatinine': {
    upper: 1.3,
    lower: 0.6,
    unit: 'mg/dL',
    source: 'KDIGO Guidelines - Female: 0.6-1.1, Male: 0.7-1.3'
  },
  'ALT': {
    upper: 40,
    lower: 7,
    unit: 'U/L',
    source: 'AASLD Guidelines - Elevated >40 indicates hepatic injury'
  },
  'AST': {
    upper: 40,
    lower: 8,
    unit: 'U/L',
    source: 'AASLD Guidelines - Elevated >40 indicates hepatocellular damage'
  },
  'Total Bilirubin': {
    upper: 1.2,
    lower: 0.1,
    unit: 'mg/dL',
    source: 'Clinical Chemistry Standards - >1.2 indicates hyperbilirubinemia'
  },

  // ===== ADDITIONAL MARKERS =====
  'RBC': {
    upper: 5.9,
    lower: 4.2,
    unit: '10^6/μL',
    source: 'Hematology Standards - Female: 4.2-5.4, Male: 4.7-5.9'
  },
  'Hematocrit': {
    upper: 52,
    lower: 36,
    unit: '%',
    source: 'Clinical Lab Standards - Female: 36-46%, Male: 41-52%'
  },
  'Albumin': {
    upper: 5.5,
    lower: 3.5,
    unit: 'g/dL',
    source: 'Clinical Guidelines - <3.5 indicates hypoalbuminemia'
  },
  'Alkaline Phosphatase': {
    upper: 120,
    lower: 30,
    unit: 'U/L',
    source: 'Clinical Chemistry - Elevated in bone mets or cholestasis'
  },
  'LDH': {
    upper: 250,
    lower: 140,
    unit: 'U/L',
    source: 'Clinical Standards - Elevated in tumor burden/hemolysis'
  },
};

/**
 * Calculate lab status based on predefined normal ranges
 * @param labName - Name of the biomarker (e.g., 'CEA', 'WBC')
 * @param value - The lab value to evaluate
 * @returns 'High', 'Low', or 'Normal'
 */
export function calculateLabStatus(labName: string, value: any): 'High' | 'Low' | 'Normal' | null {
  // Check if value is valid
  if (value === null || value === undefined || value === 'NA' || value === 'N/A' || value === '') {
    return null;
  }

  // Convert value to number
  const numValue = typeof value === 'number' ? value : parseFloat(value);
  if (isNaN(numValue)) {
    return null;
  }

  // Get predefined normal range
  const normalRange = PREDEFINED_NORMAL_LIMITS[labName];
  if (!normalRange) {
    console.warn(`[calculateLabStatus] No predefined normal range found for: ${labName}`);
    return null;
  }

  // Calculate status based on normal range
  if (numValue > normalRange.upper) {
    return 'High';
  } else if (numValue < normalRange.lower) {
    return 'Low';
  } else {
    return 'Normal';
  }
}

/**
 * Get the appropriate normal limit to display on chart based on current status
 * @param labName - Name of the biomarker
 * @param status - Current calculated status
 * @returns The normal limit to show (upper for High, lower for Low)
 */
export function getNormalLimitForChart(labName: string, status: 'High' | 'Low' | 'Normal' | null): number | null {
  const normalRange = PREDEFINED_NORMAL_LIMITS[labName];
  if (!normalRange) {
    return null;
  }

  // For High status, show upper limit as the threshold
  if (status === 'High') {
    return normalRange.upper;
  }

  // For Low status, show lower limit as the threshold
  if (status === 'Low') {
    return normalRange.lower;
  }

  // For Normal status, show upper limit by default
  return normalRange.upper;
}
