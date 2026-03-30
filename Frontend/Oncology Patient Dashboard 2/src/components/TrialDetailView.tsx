import { useState, useEffect } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from './ui/card';
import { Button } from './ui/button';
import { Badge } from './ui/badge';
import { Progress } from './ui/progress';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from './ui/select';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from './ui/table';
import {
  apiService,
  CachedTrial,
  PatientEligibility,
  EligibilityStats,
} from '../services/api';
import {
  ChevronLeft,
  ChevronRight,
  Users,
  Building2,
  Calendar,
  ExternalLink,
  CheckCircle2,
  XCircle,
  AlertCircle,
  RefreshCw,
} from 'lucide-react';
import { useHospital } from '../contexts/HospitalContext';

interface TrialDetailViewProps {
  nctId: string;
  onBack: () => void;
  onSelectPatient?: (mrn: string, trialNctId?: string) => void;
}

export function TrialDetailView({ nctId, onBack, onSelectPatient }: TrialDetailViewProps) {
  const { selectedHospital } = useHospital();
  const [trial, setTrial] = useState<CachedTrial | null>(null);
  const [patients, setPatients] = useState<PatientEligibility[]>([]);
  const [stats, setStats] = useState<EligibilityStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadingPatients, setLoadingPatients] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [statusFilter, setStatusFilter] = useState<string>('all');
  const [page, setPage] = useState(1);
  const [computing, setComputing] = useState(false);

  const limit = 20;

  const fetchTrialDetails = async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await apiService.getTrialDetails(nctId, selectedHospital);
      setTrial(response.trial);
      setStats(response.eligibility_stats);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to fetch trial details');
    } finally {
      setLoading(false);
    }
  };

  const fetchPatients = async () => {
    setLoadingPatients(true);
    try {
      const response = await apiService.getEligiblePatientsForTrial(nctId, {
        eligibilityStatus: statusFilter === 'all' ? undefined : statusFilter,
        page,
        limit,
      });
      setPatients(response.patients);
      setStats(response.eligibility_stats);
    } catch (err) {
      console.error('Failed to fetch patients:', err);
    } finally {
      setLoadingPatients(false);
    }
  };

  useEffect(() => {
    fetchTrialDetails();
  }, [nctId]);

  useEffect(() => {
    if (trial) {
      fetchPatients();
    }
  }, [trial, statusFilter, page]);

  const handleComputeEligibility = async () => {
    setComputing(true);
    setError(null);
    try {
      await apiService.computeEligibility({ background: false, trialNctId: nctId });
      await fetchPatients();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to compute eligibility');
    } finally {
      setComputing(false);
    }
  };

  const getStatusIcon = (status: string) => {
    if (status === 'LIKELY_ELIGIBLE' || status === 'Likely Eligible') return <CheckCircle2 className="h-4 w-4 text-green-500" />;
    if (status === 'POTENTIALLY_ELIGIBLE' || status === 'Potentially Eligible') return <AlertCircle className="h-4 w-4 text-yellow-500" />;
    return <XCircle className="h-4 w-4 text-red-500" />;
  };

  const getStatusColor = (status: string) => {
    if (status === 'LIKELY_ELIGIBLE' || status === 'Likely Eligible') return 'bg-green-100 text-green-700';
    if (status === 'POTENTIALLY_ELIGIBLE' || status === 'Potentially Eligible') return 'bg-amber-100 text-amber-800';
    return 'bg-red-100 text-red-800';
  };

  const formatStatus = (status: string) => {
    const statusMap: Record<string, string> = {
      'LIKELY_ELIGIBLE': 'Likely Eligible',
      'POTENTIALLY_ELIGIBLE': 'Potentially Eligible',
      'NOT_ELIGIBLE': 'Not Eligible'
    };
    return statusMap[status] || status;
  };

  const getPhaseColor = (phase: string) => {
    if (phase?.includes('1')) return 'bg-amber-100 text-amber-800';
    if (phase?.includes('2')) return 'bg-blue-100 text-blue-700';
    if (phase?.includes('3')) return 'bg-green-100 text-green-700';
    if (phase?.includes('4')) return 'bg-purple-100 text-purple-700';
    return 'bg-gray-100 text-gray-700';
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-50 p-6 flex items-center justify-center">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600"></div>
      </div>
    );
  }

  if (error || !trial) {
    return (
      <div className="min-h-screen bg-gray-50 p-6">
        <div className="max-w-7xl mx-auto">
          <Button variant="ghost" onClick={onBack} className="mb-4">
            <ChevronLeft className="h-5 w-5 mr-2" />
            Back to Trials
          </Button>
          <Card className="border-red-200 bg-red-50">
            <CardContent className="py-8 text-center">
              <p className="text-red-600">{error || 'Trial not found'}</p>
            </CardContent>
          </Card>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50 p-6 overflow-x-hidden">
      <div className="max-w-7xl mx-auto overflow-hidden">
        {/* Header */}
        <div className="flex items-start gap-4 mb-6">
          <Button variant="ghost" onClick={onBack} className="p-2 mt-1">
            <ChevronLeft className="h-5 w-5" />
          </Button>
          <div className="flex-1">
            <div className="flex items-center gap-3 mb-2">
              <a
                href={`https://clinicaltrials.gov/study/${nctId}`}
                target="_blank"
                rel="noopener noreferrer"
                className="text-blue-600 hover:underline font-mono flex items-center gap-1"
              >
                {nctId}
                <ExternalLink className="h-3 w-3" />
              </a>
              {trial.phase && trial.phase !== 'N/A' && trial.phase !== 'NA' && (
                <Badge className={getPhaseColor(trial.phase)}>{trial.phase}</Badge>
              )}
              <Badge className="bg-green-100 text-green-700">{trial.status?.replace(/_/g, ' ')}</Badge>
            </div>
            <h1 className="text-xl font-bold text-gray-900">{trial.title}</h1>
          </div>
        </div>

        {/* Trial Info Cards */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
          <Card className="border border-gray-200 shadow-sm">
            <CardContent className="pt-4">
              <div className="flex items-center gap-3">
                <div className="bg-blue-100 p-2 rounded-lg">
                  <Building2 className="h-5 w-5 text-blue-600" />
                </div>
                <div>
                  <p className="text-xs text-gray-500 mb-1">Sponsor</p>
                  <p className="font-medium">{trial.sponsor || 'Not specified'}</p>
                </div>
              </div>
            </CardContent>
          </Card>
          <Card className="border border-gray-200 shadow-sm">
            <CardContent className="pt-4">
              <div className="flex items-center gap-3">
                <div className="bg-blue-100 p-2 rounded-lg">
                  <Users className="h-5 w-5 text-blue-600" />
                </div>
                <div>
                  <p className="text-xs text-gray-500 mb-1">Target Enrollment</p>
                  <p className="font-medium">{trial.enrollment || 'Not specified'}</p>
                </div>
              </div>
            </CardContent>
          </Card>
          <Card className="border border-gray-200 shadow-sm">
            <CardContent className="pt-4">
              <div className="flex items-center gap-3">
                <div className="bg-blue-100 p-2 rounded-lg">
                  <Calendar className="h-5 w-5 text-blue-600" />
                </div>
                <div>
                  <p className="text-xs text-gray-500 mb-1">Start Date</p>
                  <p className="font-medium">{trial.start_date || 'Not specified'}</p>
                </div>
              </div>
            </CardContent>
          </Card>
        </div>

        {/* Summary */}
        {trial.brief_summary && (
          <Card className="mb-6">
            <CardHeader>
              <CardTitle className="text-lg">Study Summary</CardTitle>
            </CardHeader>
            <CardContent>
              <p className="text-gray-700">{trial.brief_summary}</p>
            </CardContent>
          </Card>
        )}

        {/* Eligibility Stats */}
        <Card className="mb-6">
          <CardHeader className="flex flex-row items-center justify-between">
            <CardTitle className="text-lg">Eligible Patients</CardTitle>
            <Button
              variant="outline"
              size="sm"
              onClick={handleComputeEligibility}
              disabled={computing}
            >
              <RefreshCw className={`h-4 w-4 mr-2 ${computing ? 'animate-spin' : ''}`} />
              {computing ? 'Computing...' : 'Recompute Eligibility'}
            </Button>
          </CardHeader>
          <CardContent>
            {stats && stats.total > 0 ? (
              <div className="grid grid-cols-4 gap-4 mb-6">
                <div className="text-center p-4 bg-gray-50 rounded-lg">
                  <p className="text-2xl font-bold">{stats.total}</p>
                  <p className="text-xs text-gray-500">Total Analyzed</p>
                </div>
                <div className="text-center p-4 bg-green-50 rounded-lg border border-green-200">
                  <p className="text-2xl font-bold text-green-600">
                    {stats['LIKELY_ELIGIBLE'] || stats['Likely Eligible'] || 0}
                  </p>
                  <p className="text-xs text-gray-500">Likely Eligible</p>
                </div>
                <div className="text-center p-4 bg-amber-50 rounded-lg border border-amber-200">
                  <p className="text-2xl font-bold text-amber-600">
                    {stats['POTENTIALLY_ELIGIBLE'] || stats['Potentially Eligible'] || 0}
                  </p>
                  <p className="text-xs text-gray-500">Potentially Eligible</p>
                </div>
                <div className="text-center p-4 bg-red-50 rounded-lg border border-red-200">
                  <p className="text-2xl font-bold text-red-600">
                    {stats['NOT_ELIGIBLE'] || stats['Not Eligible'] || 0}
                  </p>
                  <p className="text-xs text-gray-500">Not Eligible</p>
                </div>
              </div>
            ) : (
              <div className="text-center py-8 text-gray-500">
                <Users className="h-12 w-12 mx-auto mb-4 text-gray-400" />
                <p>No eligibility data computed yet.</p>
                <p className="text-sm">Click "Recompute Eligibility" to analyze patients.</p>
              </div>
            )}

            {/* Filter */}
            {stats && stats.total > 0 && (
              <div className="flex justify-between items-center mb-4">
                <Select value={statusFilter} onValueChange={setStatusFilter}>
                  <SelectTrigger className="w-[200px]">
                    <SelectValue placeholder="Filter by eligibility" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="all">All Patients</SelectItem>
                    <SelectItem value="LIKELY_ELIGIBLE">Likely Eligible</SelectItem>
                    <SelectItem value="POTENTIALLY_ELIGIBLE">Potentially Eligible</SelectItem>
                    <SelectItem value="NOT_ELIGIBLE">Not Eligible</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            )}

            {/* Patients Table */}
            {loadingPatients ? (
              <div className="flex justify-center py-8">
                <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
              </div>
            ) : patients.length > 0 ? (
              <div className="overflow-hidden rounded-lg border border-gray-200">
              <Table>
                <TableHeader className="bg-gray-50">
                  <TableRow>
                    <TableHead>Patient</TableHead>
                    <TableHead>Cancer Type</TableHead>
                    <TableHead>Stage</TableHead>
                    <TableHead>Eligibility</TableHead>
                    <TableHead className="text-right">Match Score</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {patients.map((patient) => (
                    <TableRow
                      key={patient.id}
                      className={onSelectPatient ? 'cursor-pointer hover:bg-gray-50' : ''}
                      onClick={() => onSelectPatient?.(patient.patient_mrn, nctId)}
                    >
                      <TableCell>
                        <div>
                          <p className="font-medium">{patient.patient_summary?.name || 'Unknown'}</p>
                          <p className="text-sm text-gray-500">
                            MRN: {patient.patient_mrn} | {patient.patient_summary?.age} | {patient.patient_summary?.gender}
                          </p>
                        </div>
                      </TableCell>
                      <TableCell>{patient.patient_summary?.cancer_type || 'N/A'}</TableCell>
                      <TableCell>{patient.patient_summary?.stage || 'N/A'}</TableCell>
                      <TableCell>
                        <div className="flex items-center gap-2">
                          {getStatusIcon(patient.eligibility_status)}
                          <Badge className={getStatusColor(patient.eligibility_status)}>
                            {formatStatus(patient.eligibility_status)}
                          </Badge>
                        </div>
                      </TableCell>
                      <TableCell className="text-right">
                        <div className="flex items-center justify-end gap-2">
                          <Progress value={patient.eligibility_percentage} className="w-20 h-2" />
                          <span className="text-sm font-medium w-12 text-right">
                            {patient.eligibility_percentage}%
                          </span>
                        </div>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
              </div>
            ) : stats && stats.total > 0 ? (
              <p className="text-center py-4 text-gray-500">
                No patients match the selected filter.
              </p>
            ) : null}
          </CardContent>
        </Card>

        {/* Conditions */}
        {trial.conditions && trial.conditions.length > 0 && (
          <Card className="mb-6">
            <CardHeader>
              <CardTitle className="text-lg">Conditions</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="flex flex-wrap gap-2">
                {trial.conditions.map((condition, idx) => (
                  <Badge key={idx} variant="outline">
                    {condition}
                  </Badge>
                ))}
              </div>
            </CardContent>
          </Card>
        )}

        {/* Eligibility Criteria */}
        {trial.eligibility_criteria && (
          <Card className="overflow-hidden">
            <CardHeader>
              <CardTitle className="text-lg">Eligibility Criteria</CardTitle>
            </CardHeader>
            <CardContent>
              {(() => {
                // Parse criteria into inclusion and exclusion sections
                const text = trial.eligibility_criteria || '';
                const exclusionMatch = text.match(/exclusion\s*criteria[:\s]*/i);
                let inclusionText = text;
                let exclusionText = '';

                if (exclusionMatch) {
                  const splitIndex = text.toLowerCase().indexOf(exclusionMatch[0].toLowerCase());
                  inclusionText = text.substring(0, splitIndex);
                  exclusionText = text.substring(splitIndex + exclusionMatch[0].length);
                }

                // Clean up inclusion text
                inclusionText = inclusionText.replace(/inclusion\s*criteria[:\s]*/i, '').trim();

                // Parse bullet points
                const parseItems = (text: string) => {
                  return text
                    .split(/\n\s*[\*\-•]\s*|\n\s*\d+[\.\)]\s*/)
                    .map(item => item.trim())
                    .filter(item => item.length > 10);
                };

                const inclusionItems = parseItems(inclusionText);
                const exclusionItems = parseItems(exclusionText);

                return (
                  <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                    {/* Inclusion Criteria */}
                    <div>
                      <div className="flex items-center gap-2 mb-3">
                        <CheckCircle2 className="h-5 w-5 text-green-600" />
                        <h4 className="font-semibold text-gray-900">Inclusion Criteria</h4>
                        <span className="text-sm text-gray-500">({inclusionItems.length} criteria)</span>
                      </div>
                      <div className="bg-green-50 rounded-lg border border-green-200 overflow-hidden">
                        {inclusionItems.length > 0 ? (
                          <div className="divide-y divide-green-100">
                            {inclusionItems.map((item, idx) => (
                              <div key={idx} className="p-3 text-sm text-gray-700 hover:bg-green-100 transition-colors">
                                <span className="font-medium text-green-700 mr-2">{idx + 1}.</span>
                                <span className="break-words">{item}</span>
                              </div>
                            ))}
                          </div>
                        ) : (
                          <div className="p-4 text-center text-gray-500 text-sm">
                            No inclusion criteria specified
                          </div>
                        )}
                      </div>
                    </div>

                    {/* Exclusion Criteria */}
                    <div>
                      <div className="flex items-center gap-2 mb-3">
                        <XCircle className="h-5 w-5 text-red-500" />
                        <h4 className="font-semibold text-gray-900">Exclusion Criteria</h4>
                        <span className="text-sm text-gray-500">({exclusionItems.length} criteria)</span>
                      </div>
                      <div className="bg-red-50 rounded-lg border border-red-200 overflow-hidden">
                        {exclusionItems.length > 0 ? (
                          <div className="divide-y divide-red-100">
                            {exclusionItems.map((item, idx) => (
                              <div key={idx} className="p-3 text-sm text-gray-700 hover:bg-red-100 transition-colors">
                                <span className="font-medium text-red-700 mr-2">{idx + 1}.</span>
                                <span className="break-words">{item}</span>
                              </div>
                            ))}
                          </div>
                        ) : (
                          <div className="p-4 text-center text-gray-500 text-sm">
                            No exclusion criteria specified
                          </div>
                        )}
                      </div>
                    </div>
                  </div>
                );
              })()}
            </CardContent>
          </Card>
        )}
      </div>
    </div>
  );
}
