import { FileText, Download, User, AlertTriangle, CheckCircle } from 'lucide-react';
import { ImageWithFallback } from './figma/ImageWithFallback';
import { PatientData } from '../services/api';

interface PatientHeaderProps {
  patient: PatientData;
}

export function PatientHeader({ patient }: PatientHeaderProps) {
  // Extract data using exact backend keys with optional chaining
  const name = patient.demographics?.["Patient Name"] || "Unknown";
  const mrn = patient.demographics?.["MRN"] || "Unknown";
  const dob = patient.demographics?.["Date of Birth"] || "Unknown";
  const age = patient.demographics?.["Age"] || "Unknown";
  const gender = patient.demographics?.["Gender"] || "Unknown";
  const height = patient.demographics?.["Height"] || "Unknown";
  const weight = patient.demographics?.["Weight"] || "Unknown";
  const oncologist = patient.demographics?.["Primary Oncologist"] || "Unknown";
  const lastVisit = patient.demographics?.["Last Visit"] || "Unknown";

  return (
    <header className="bg-white">
      {/* Patient Demographics Bar */}
      <div className="bg-gradient-to-r from-slate-800 to-slate-900 border-b border-slate-700">
        <div className="max-w-[1600px] mx-auto px-6 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-6">
              {/* Patient Photo */}
              <div className="w-16 h-16 rounded-full overflow-hidden border-2 border-slate-600 bg-slate-700 flex-shrink-0">
                <ImageWithFallback
                  src="https://images.unsplash.com/photo-1758685848602-09e52ef9c7d3?crop=entropy&cs=tinysrgb&fit=max&fm=jpg&ixid=M3w3Nzg4Nzd8MHwxfHNlYXJjaHwxfHxtYXR1cmUlMjB3b21hbiUyMHBvcnRyYWl0JTIwcHJvZmVzc2lvbmFsfGVufDF8fHx8MTc2NjA2OTc4OHww&ixlib=rb-4.1.0&q=80&w=1080"
                  alt="Patient photo"
                  className="w-full h-full object-cover"
                />
              </div>
              <div>
                <h1 className="text-white text-xl mb-0.5">{name}</h1>
                <p className="text-slate-300 text-sm">
                  MRN: {mrn} • DOB: {dob} ({age} years) • {gender} • Height: {height} • Weight: {weight}
                </p>
              </div>
            </div>
            <div className="flex items-center gap-4">
              <div className="text-right">
                <p className="text-slate-400 text-xs">Primary Oncologist</p>
                <p className="text-white text-sm">{oncologist}</p>
              </div>
              <div className="text-right">
                <p className="text-slate-400 text-xs">Last Visit</p>
                <p className="text-white text-sm">{lastVisit}</p>
              </div>
            </div>
          </div>
        </div>
      </div>
    </header>
  );
}