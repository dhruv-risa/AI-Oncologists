import { useState, useEffect } from 'react';
import { FlaskConical, CheckCircle, XCircle, HelpCircle, Phone, Mail, MapPin, ExternalLink, RefreshCw, AlertCircle, Database, Search } from 'lucide-react';
import { usePatient } from '../../contexts/PatientContext';
import { apiService, ClinicalTrial, CriterionResult, ClinicalTrialsResponse } from '../../services/api';

export function ClinicalTrialsTab() {
    const { currentPatient } = usePatient();
    const [trials, setTrials] = useState<ClinicalTrial[]>([]);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [searchQueries, setSearchQueries] = useState<string[]>([]);
    const [expandedTrials, setExpandedTrials] = useState<Set<string>>(new Set());
    const [useCached, setUseCached] = useState(true);
    const [cachedCount, setCachedCount] = useState<number>(0);

    // Try to fetch cached eligibility data first
    const fetchCachedTrials = async () => {
        if (!currentPatient?.mrn) return false;

        try {
            const response = await apiService.getCachedEligibleTrialsForPatient(currentPatient.mrn);
            if (response.success && response.trials && response.trials.length > 0) {
                // Transform cached data to match ClinicalTrial interface
                const transformedTrials = response.trials.map((t: any) => {
                    // Use full criteria_results if available, otherwise fall back to key_matching/exclusion
                    const inclusion = t.criteria_results?.inclusion ||
                        t.key_matching_criteria?.map((c: string, i: number) => ({
                            criterion_number: i + 1,
                            criterion_text: c,
                            patient_value: '',
                            met: true,
                            confidence: 'high',
                            explanation: '',
                            criterion_type: 'inclusion' as const
                        })) || [];

                    const exclusion = t.criteria_results?.exclusion ||
                        t.key_exclusion_reasons?.map((c: string, i: number) => ({
                            criterion_number: i + 1,
                            criterion_text: c,
                            patient_value: '',
                            met: true,
                            confidence: 'high',
                            explanation: '',
                            criterion_type: 'exclusion' as const
                        })) || [];

                    // Calculate inclusion/exclusion stats from criteria
                    const inclusionMet = inclusion.filter((c: any) => c.met === true).length;
                    const inclusionNotMet = inclusion.filter((c: any) => c.met === false).length;
                    const inclusionUnknown = inclusion.filter((c: any) => c.met === null).length;
                    const exclusionClear = exclusion.filter((c: any) => c.met === false).length;
                    const exclusionViolated = exclusion.filter((c: any) => c.met === true).length;
                    const exclusionUnknown = exclusion.filter((c: any) => c.met === null).length;

                    return {
                        nct_id: t.trial_nct_id,
                        title: t.title || 'Unknown Trial',
                        phase: t.phase || 'N/A',
                        status: t.trial_status || 'Unknown',
                        study_type: 'Interventional',
                        brief_summary: '',
                        eligibility: {
                            status: t.eligibility_status === 'LIKELY_ELIGIBLE' ? 'LIKELY_ELIGIBLE' :
                                    t.eligibility_status === 'POTENTIALLY_ELIGIBLE' ? 'POTENTIALLY_ELIGIBLE' :
                                    t.eligibility_status === 'NOT_ELIGIBLE' ? 'NOT_ELIGIBLE' :
                                    t.eligibility_status === 'Likely Eligible' ? 'LIKELY_ELIGIBLE' :
                                    t.eligibility_status === 'Potentially Eligible' ? 'POTENTIALLY_ELIGIBLE' : 'NOT_ELIGIBLE',
                            status_reason: '',
                            percentage: t.eligibility_percentage || 0,
                            inclusion: { met: inclusionMet, not_met: inclusionNotMet, unknown: inclusionUnknown, total: inclusion.length },
                            exclusion: { clear: exclusionClear, violated: exclusionViolated, unknown: exclusionUnknown, total: exclusion.length }
                        },
                        criteria_results: {
                            inclusion,
                            exclusion
                        },
                        contact: {},
                        locations: []
                    };
                });
                setTrials(transformedTrials);
                setCachedCount(response.total);
                setSearchQueries(['Saved eligibility analysis']);
                return true;
            }
            return false;
        } catch (err) {
            console.log('No cached data available, will use real-time search');
            return false;
        }
    };

    const fetchTrials = async (forceRealTime = false) => {
        if (!currentPatient?.mrn) return;

        setLoading(true);
        setError(null);

        // Try cached data first unless forcing real-time
        if (useCached && !forceRealTime) {
            const hasCached = await fetchCachedTrials();
            if (hasCached) {
                setLoading(false);
                return;
            }
        }

        // Fall back to real-time search
        try {
            const response: ClinicalTrialsResponse = await apiService.getClinicalTrials(currentPatient.mrn);
            if (response.success) {
                setTrials(response.trials || []);
                setSearchQueries(response.search_queries || []);
            } else {
                setError(response.error || 'Failed to fetch clinical trials');
            }
        } catch (err) {
            setError(err instanceof Error ? err.message : 'Failed to fetch clinical trials');
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        if (currentPatient?.mrn) {
            fetchTrials();
        }
    }, [currentPatient?.mrn]);

    const toggleTrialExpanded = (nctId: string) => {
        setExpandedTrials(prev => {
            const next = new Set(prev);
            if (next.has(nctId)) {
                next.delete(nctId);
            } else {
                next.add(nctId);
            }
            return next;
        });
    };

    const getStatusIcon = (met: boolean | null) => {
        if (met === true) return <CheckCircle className="w-4 h-4 text-emerald-600" />;
        if (met === false) return <XCircle className="w-4 h-4 text-red-500" />;
        return <HelpCircle className="w-4 h-4 text-amber-500" />;
    };

    const getStatusBadge = (status: string) => {
        const colors: Record<string, string> = {
            'LIKELY_ELIGIBLE': 'bg-emerald-100 text-emerald-800 border-emerald-300',
            'POTENTIALLY_ELIGIBLE': 'bg-amber-100 text-amber-800 border-amber-300',
            'NOT_ELIGIBLE': 'bg-red-100 text-red-800 border-red-300'
        };
        const labels: Record<string, string> = {
            'LIKELY_ELIGIBLE': 'Likely Eligible',
            'POTENTIALLY_ELIGIBLE': 'Potentially Eligible',
            'NOT_ELIGIBLE': 'Not Eligible'
        };
        return (
            <span className={`px-3 py-1 rounded-full text-xs font-medium border ${colors[status] || 'bg-gray-100 text-gray-800'}`}>
                {labels[status] || status}
            </span>
        );
    };

    const getPercentageColor = (percentage: number) => {
        if (percentage >= 80) return 'text-emerald-600';
        if (percentage >= 60) return 'text-amber-600';
        return 'text-red-500';
    };

    const renderCriteriaTable = (criteria: CriterionResult[], type: 'inclusion' | 'exclusion') => {
        if (!criteria || criteria.length === 0) {
            return (
                <div className="text-center py-4 text-gray-500 text-sm">
                    No {type} criteria found
                </div>
            );
        }

        return (
            <div className="overflow-hidden rounded-lg border border-gray-200">
                <table className="w-full text-sm">
                    <thead className={type === 'inclusion' ? 'bg-emerald-50' : 'bg-red-50'}>
                        <tr>
                            <th className="px-3 py-2 text-left font-medium text-gray-700 w-1/2">Criterion</th>
                            <th className="px-3 py-2 text-left font-medium text-gray-700 w-1/3">Patient Value</th>
                            <th className="px-3 py-2 text-center font-medium text-gray-700 w-16">Status</th>
                        </tr>
                    </thead>
                    <tbody className="divide-y divide-gray-100">
                        {criteria.map((criterion, idx) => (
                            <tr key={idx} className="hover:bg-gray-50 transition-colors">
                                <td className="px-3 py-2 text-gray-800">
                                    <span className="line-clamp-2" title={criterion.explanation}>
                                        {criterion.criterion_text}
                                    </span>
                                </td>
                                <td className="px-3 py-2 text-gray-600">
                                    <span className="line-clamp-2">{criterion.patient_value || '-'}</span>
                                </td>
                                <td className="px-3 py-2 text-center">
                                    {type === 'exclusion' ? (
                                        // For exclusion: met=false is good (patient doesn't have it)
                                        criterion.met === false ? (
                                            <CheckCircle className="w-4 h-4 text-emerald-600 mx-auto" title="Patient does not have this condition ✓" />
                                        ) : criterion.met === true ? (
                                            <XCircle className="w-4 h-4 text-red-500 mx-auto" title="Patient has this exclusion condition ✗" />
                                        ) : (
                                            <HelpCircle className="w-4 h-4 text-amber-500 mx-auto" title="Unknown" />
                                        )
                                    ) : (
                                        getStatusIcon(criterion.met)
                                    )}
                                </td>
                            </tr>
                        ))}
                    </tbody>
                </table>
            </div>
        );
    };

    // Show loading state
    if (!currentPatient) {
        return (
            <div className="bg-white border border-t-0 border-gray-200 rounded-b-lg shadow-sm p-6">
                <div className="text-center text-gray-500 py-8">
                    No patient data available
                </div>
            </div>
        );
    }

    return (
        <div className="bg-white border border-t-0 border-gray-200 rounded-b-lg shadow-sm p-6">
            {/* Header */}
            <div className="flex items-center justify-between mb-6">
                <div className="flex items-center gap-3">
                    <div className="w-10 h-10 bg-gradient-to-br from-violet-500 to-purple-600 rounded-xl flex items-center justify-center">
                        <FlaskConical className="w-5 h-5 text-white" />
                    </div>
                    <div>
                        <h2 className="text-lg font-semibold text-gray-900">Clinical Trials</h2>
                        {searchQueries.length > 0 && (
                            <p className="text-sm text-gray-500">
                                {searchQueries[0] === 'Saved eligibility analysis' ? (
                                    <span className="flex items-center gap-1">
                                        <Database className="w-3 h-3" />
                                        {cachedCount} trials analyzed for eligibility
                                    </span>
                                ) : (
                                    <>Searching: {searchQueries.map(q => `"${q}"`).join(', ')}</>
                                )}
                            </p>
                        )}
                    </div>
                </div>
                <div className="flex items-center gap-2">
                    {cachedCount > 0 && (
                        <button
                            onClick={() => fetchTrials(true)}
                            disabled={loading}
                            className="flex items-center gap-2 px-4 py-2 bg-white border border-violet-300 text-violet-700 rounded-lg hover:bg-violet-50 transition-colors disabled:opacity-50"
                        >
                            <Search className="w-4 h-4" />
                            Search New Trials
                        </button>
                    )}
                    <button
                        onClick={() => fetchTrials()}
                        disabled={loading}
                        className="flex items-center gap-2 px-4 py-2 bg-violet-600 text-white rounded-lg hover:bg-violet-700 transition-colors disabled:opacity-50"
                    >
                        <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
                        {loading ? 'Searching...' : 'Refresh'}
                    </button>
                </div>
            </div>

            {/* Loading State */}
            {loading && (
                <div className="flex flex-col items-center justify-center py-16">
                    <div className="w-16 h-16 border-4 border-violet-200 border-t-violet-600 rounded-full animate-spin mb-4"></div>
                    <p className="text-gray-600">Searching for matching clinical trials...</p>
                    <p className="text-sm text-gray-400 mt-2">Analyzing eligibility criteria for each trial</p>
                </div>
            )}

            {/* Error State */}
            {error && !loading && (
                <div className="flex items-center gap-3 p-4 bg-red-50 border border-red-200 rounded-lg mb-6">
                    <AlertCircle className="w-5 h-5 text-red-500" />
                    <p className="text-red-700">{error}</p>
                </div>
            )}

            {/* No Trials Found */}
            {!loading && !error && trials.length === 0 && (
                <div className="text-center py-12 bg-gray-50 rounded-lg border border-gray-200">
                    <FlaskConical className="w-12 h-12 text-gray-400 mx-auto mb-3" />
                    <p className="text-gray-600 font-medium">No matching clinical trials found</p>
                    <p className="text-gray-400 text-sm mt-1">Try refreshing or check back later</p>
                </div>
            )}

            {/* Trials List */}
            {!loading && trials.length > 0 && (
                <div className="space-y-6">
                    {/* Summary */}
                    <div className="bg-gradient-to-r from-violet-50 to-purple-50 border border-violet-200 rounded-lg p-4">
                        <p className="text-violet-800 font-medium">
                            {searchQueries[0] === 'Saved eligibility analysis'
                                ? `Found ${trials.length} potentially matching clinical trial${trials.length !== 1 ? 's' : ''} for this patient`
                                : `Found ${trials.length} clinical trial${trials.length !== 1 ? 's' : ''} matching ${searchQueries.length > 0 ? searchQueries.map(q => `"${q}"`).join(' or ') : 'patient criteria'}`
                            }
                        </p>
                    </div>

                    {/* Trial Cards */}
                    {trials.map((trial) => (
                        <div
                            key={trial.nct_id}
                            className="border-2 border-gray-200 rounded-xl overflow-hidden hover:border-violet-300 transition-colors"
                        >
                            {/* Trial Header */}
                            <div
                                className="p-5 cursor-pointer bg-gradient-to-r from-gray-50 to-white hover:from-violet-50 hover:to-white transition-colors"
                                onClick={() => toggleTrialExpanded(trial.nct_id)}
                            >
                                <div className="flex items-start justify-between gap-4">
                                    <div className="flex-1">
                                        <div className="flex items-center gap-3 mb-2">
                                            <a
                                                href={`https://clinicaltrials.gov/study/${trial.nct_id}`}
                                                target="_blank"
                                                rel="noopener noreferrer"
                                                onClick={(e) => e.stopPropagation()}
                                                className="text-violet-600 font-mono font-medium hover:underline flex items-center gap-1"
                                            >
                                                {trial.nct_id}
                                                <ExternalLink className="w-3 h-3" />
                                            </a>
                                            <span className="px-2 py-0.5 bg-blue-100 text-blue-700 rounded text-xs font-medium">
                                                {trial.phase || 'N/A'}
                                            </span>
                                            <span className="px-2 py-0.5 bg-green-100 text-green-700 rounded text-xs font-medium">
                                                {trial.status}
                                            </span>
                                        </div>
                                        <h3 className="text-gray-900 font-medium line-clamp-2">{trial.title}</h3>
                                    </div>

                                    {/* Eligibility Score */}
                                    <div className="flex flex-col items-end gap-2">
                                        <div className="text-right">
                                            <span className={`text-2xl font-bold ${getPercentageColor(trial.eligibility.percentage)}`}>
                                                {trial.eligibility.percentage}%
                                            </span>
                                            <p className="text-xs text-gray-500">Match</p>
                                        </div>
                                        {getStatusBadge(trial.eligibility.status)}
                                    </div>
                                </div>

                                {/* Criteria Summary Bar */}
                                <div className="mt-4 flex items-center gap-4 text-sm">
                                    <div className="flex items-center gap-1.5">
                                        <CheckCircle className="w-4 h-4 text-emerald-600" />
                                        <span className="text-gray-600">
                                            Inclusion: {trial.eligibility.inclusion.met}/{trial.eligibility.inclusion.total}
                                        </span>
                                    </div>
                                    <div className="flex items-center gap-1.5">
                                        <CheckCircle className="w-4 h-4 text-emerald-600" />
                                        <span className="text-gray-600">
                                            Exclusion Clear: {trial.eligibility.exclusion.clear}/{trial.eligibility.exclusion.total}
                                        </span>
                                    </div>
                                    {(trial.eligibility.inclusion.unknown > 0 || trial.eligibility.exclusion.unknown > 0) && (
                                        <div className="flex items-center gap-1.5">
                                            <HelpCircle className="w-4 h-4 text-amber-500" />
                                            <span className="text-amber-600">
                                                {trial.eligibility.inclusion.unknown + trial.eligibility.exclusion.unknown} Unknown
                                            </span>
                                        </div>
                                    )}
                                </div>
                            </div>

                            {/* Expanded Content */}
                            {expandedTrials.has(trial.nct_id) && (
                                <div className="border-t border-gray-200 bg-white p-5">
                                    {/* Two Column Criteria Layout */}
                                    <div className="grid grid-cols-2 gap-6 mb-6">
                                        {/* Inclusion Criteria */}
                                        <div>
                                            <div className="flex items-center gap-2 mb-3">
                                                <CheckCircle className="w-5 h-5 text-emerald-600" />
                                                <h4 className="font-medium text-gray-900">Inclusion Criteria</h4>
                                                <span className="text-sm text-gray-500">
                                                    ({trial.eligibility.inclusion.met}/{trial.eligibility.inclusion.total} met)
                                                </span>
                                            </div>
                                            {renderCriteriaTable(trial.criteria_results.inclusion, 'inclusion')}
                                        </div>

                                        {/* Exclusion Criteria */}
                                        <div>
                                            <div className="flex items-center gap-2 mb-3">
                                                <XCircle className="w-5 h-5 text-red-500" />
                                                <h4 className="font-medium text-gray-900">Exclusion Criteria</h4>
                                                <span className="text-sm text-gray-500">
                                                    ({trial.eligibility.exclusion.clear}/{trial.eligibility.exclusion.total} clear)
                                                </span>
                                            </div>
                                            {renderCriteriaTable(trial.criteria_results.exclusion, 'exclusion')}
                                        </div>
                                    </div>

                                    {/* Contact & Location */}
                                    <div className="grid grid-cols-2 gap-6 pt-4 border-t border-gray-200">
                                        {/* Contact Info */}
                                        {trial.contact && (trial.contact.name || trial.contact.phone || trial.contact.email) && (
                                            <div className="bg-blue-50 rounded-lg p-4">
                                                <h4 className="font-medium text-gray-900 mb-3 flex items-center gap-2">
                                                    <Phone className="w-4 h-4 text-blue-600" />
                                                    Contact Information
                                                </h4>
                                                <div className="space-y-2 text-sm">
                                                    {trial.contact.name && (
                                                        <p className="text-gray-700">{trial.contact.name}</p>
                                                    )}
                                                    {trial.contact.phone && (
                                                        <p className="flex items-center gap-2 text-gray-600">
                                                            <Phone className="w-3 h-3" />
                                                            <a href={`tel:${trial.contact.phone}`} className="hover:text-blue-600">
                                                                {trial.contact.phone}
                                                            </a>
                                                        </p>
                                                    )}
                                                    {trial.contact.email && (
                                                        <p className="flex items-center gap-2 text-gray-600">
                                                            <Mail className="w-3 h-3" />
                                                            <a href={`mailto:${trial.contact.email}`} className="hover:text-blue-600">
                                                                {trial.contact.email}
                                                            </a>
                                                        </p>
                                                    )}
                                                </div>
                                            </div>
                                        )}

                                        {/* Locations */}
                                        {trial.locations && trial.locations.length > 0 && (
                                            <div className="bg-green-50 rounded-lg p-4">
                                                <h4 className="font-medium text-gray-900 mb-3 flex items-center gap-2">
                                                    <MapPin className="w-4 h-4 text-green-600" />
                                                    Study Locations
                                                </h4>
                                                <div className="space-y-2 text-sm">
                                                    {trial.locations.slice(0, 3).map((loc, idx) => (
                                                        <p key={idx} className="text-gray-700">
                                                            {loc.facility && <span className="font-medium">{loc.facility}</span>}
                                                            {loc.city && <span className="text-gray-500"> - {loc.city}</span>}
                                                            {loc.state && <span className="text-gray-500">, {loc.state}</span>}
                                                        </p>
                                                    ))}
                                                    {trial.locations.length > 3 && (
                                                        <p className="text-gray-500 italic">
                                                            +{trial.locations.length - 3} more locations
                                                        </p>
                                                    )}
                                                </div>
                                            </div>
                                        )}
                                    </div>

                                    {/* Brief Summary */}
                                    {trial.brief_summary && (
                                        <div className="mt-4 pt-4 border-t border-gray-200">
                                            <h4 className="font-medium text-gray-900 mb-2">Brief Summary</h4>
                                            <p className="text-sm text-gray-600 leading-relaxed">{trial.brief_summary}</p>
                                        </div>
                                    )}
                                </div>
                            )}
                        </div>
                    ))}
                </div>
            )}
        </div>
    );
}
