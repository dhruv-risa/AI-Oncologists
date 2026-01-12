import { useEffect, useState } from 'react';
import { Loader2 } from 'lucide-react';

interface LoadingModalProps {
  open: boolean;
  title?: string;
}

const loadingSteps = [
  "Connecting to FHIR API...",
  "Fetching medical records...",
  "Retrieving patient documents...",
  "Extracting demographics data...",
  "Analyzing diagnosis information...",
  "Processing treatment history...",
  "Compiling lab results...",
  "Gathering genomic data...",
  "Organizing pathology reports...",
  "Finalizing patient profile...",
  "Almost there...",
];

export function LoadingModal({ open, title = "Fetching Patient Data" }: LoadingModalProps) {
  const [currentStep, setCurrentStep] = useState(0);

  useEffect(() => {
    if (!open) {
      setCurrentStep(0);
      return;
    }

    // Text change animation
    const textInterval = setInterval(() => {
      setCurrentStep((prev) => (prev + 1) % loadingSteps.length);
    }, 2500); // Change text every 2.5 seconds

    return () => {
      clearInterval(textInterval);
    };
  }, [open]);

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-[100] flex items-center justify-center p-4">
      {/* Backdrop with blur */}
      <div
        className="fixed inset-0 bg-black/60 backdrop-blur-md transition-all duration-300"
        onClick={(e) => e.preventDefault()}
      />

      {/* Modal Content */}
      <div className="relative z-[101] bg-white rounded-2xl shadow-2xl max-w-lg w-full overflow-hidden">
        {/* Header with gradient */}
        <div className="bg-gradient-to-r from-blue-600 to-blue-700 px-8 py-6">
          <h3 className="text-2xl font-bold text-white text-center">{title}</h3>
        </div>

        {/* Content */}
        <div className="px-8 py-10 flex flex-col items-center">
          {/* Animated spinner - centered */}
          <div className="mb-10">
            <Loader2 className="w-20 h-20 text-blue-600 animate-spin" />
          </div>

          {/* Dynamic status text */}
          <div className="mb-10 min-h-[32px] flex items-center justify-center w-full">
            <p className="text-base font-medium text-gray-700 text-center transition-all duration-500">
              {loadingSteps[currentStep]}
            </p>
          </div>

          {/* Info message */}
          <div className="w-full p-4 bg-blue-50 rounded-lg border border-blue-200">
            <p className="text-sm text-gray-600 text-center leading-relaxed">
              This process may take <span className="font-semibold text-blue-700">3-5 minutes</span> depending on the amount of patient data.
            </p>
            <p className="text-xs text-gray-500 text-center mt-2">Please do not close this window.</p>
          </div>
        </div>
      </div>
    </div>
  );
}
