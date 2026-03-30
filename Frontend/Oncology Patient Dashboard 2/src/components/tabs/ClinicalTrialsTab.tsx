import { useState, useEffect, useRef } from 'react';
import { FlaskConical, CheckCircle, XCircle, HelpCircle, Phone, Mail, MapPin, ExternalLink, RefreshCw, AlertCircle, Database, Search, ClipboardCheck, User, Stethoscope, X, Loader2, Send, Copy, Check } from 'lucide-react';
import { usePatient } from '../../contexts/PatientContext';
import { useHospital } from '../../contexts/HospitalContext';
import { apiService, ClinicalTrial, CriterionResult, ClinicalTrialsResponse, CriterionResolutionPayload } from '../../services/api';

// ── Review Modal ──────────────────────────────────────────────────────────
function ReviewModal({
    type,
    trialId,
    criteria,
    onSave,
    onClose,
    saving,
}: {
    type: 'patient' | 'clinician';
    trialId: string;
    criteria: CriterionResult[];
    onSave: (resolutions: CriterionResolutionPayload[]) => Promise<void>;
    onClose: () => void;
    saving: boolean;
}) {
    const [resolutions, setResolutions] = useState<Map<string, boolean>>(new Map());

    const toggle = (criterionType: string, criterionNumber: number, value: boolean) => {
        const key = `${criterionType}-${criterionNumber}`;
        setResolutions(prev => {
            const next = new Map(prev);
            next.get(key) === value ? next.delete(key) : next.set(key, value);
            return next;
        });
    };

    const handleSave = async () => {
        const payloads: CriterionResolutionPayload[] = [];
        resolutions.forEach((resolved_met, key) => {
            const [criterion_type, num] = key.split('-');
            payloads.push({
                criterion_number: parseInt(num),
                criterion_type: criterion_type as 'inclusion' | 'exclusion',
                resolved_met,
                resolved_by: type,
            });
        });
        await onSave(payloads);
    };

    const isPatient = type === 'patient';

    return (
        <div className="fixed inset-0 z-50 flex items-center justify-center">
            <div className="absolute inset-0 bg-black/20" onClick={onClose} />
            <div className={`relative bg-white rounded-lg w-[720px] max-h-[80vh] flex flex-col shadow-lg border ${isPatient ? 'border-blue-300' : 'border-red-300'}`}>
                {/* Header */}
                <div className={`px-3.5 py-2.5 flex items-center justify-between rounded-t-lg ${isPatient ? 'bg-blue-50 border-b border-blue-300' : 'bg-red-50 border-b border-red-300'}`}>
                    <div className="flex items-center gap-2">
                        <ClipboardCheck className={`w-3.5 h-3.5 ${isPatient ? 'text-blue-600' : 'text-red-600'}`} />
                        <span className={`text-xs font-semibold ${isPatient ? 'text-blue-900' : 'text-red-900'}`}>
                            {isPatient ? 'Patient Review' : 'Clinician Review'}
                        </span>
                        <span className="text-[10px] text-gray-400">{trialId}</span>
                    </div>
                    <button onClick={onClose} className="bg-transparent border-none cursor-pointer text-gray-400 p-0.5">
                        <X className="w-3.5 h-3.5" />
                    </button>
                </div>

                {/* Checklist */}
                <div className="flex-1 overflow-y-auto px-3.5 py-2">
                    {criteria.length === 0 ? (
                        <p className="text-center text-[11px] text-gray-400 py-5">All items reviewed</p>
                    ) : (
                        criteria.map((criterion, idx) => {
                            const key = `${criterion.criterion_type}-${criterion.criterion_number}`;
                            const resolved = resolutions.get(key);

                            return (
                                <div key={idx} className="flex items-start gap-2 py-1.5 border-b border-gray-100 last:border-b-0">
                                    <p className="flex-1 text-[11px] text-gray-700 leading-snug m-0 pt-0.5">
                                        {criterion.criterion_text}
                                    </p>
                                    <div className="flex gap-0.5 shrink-0">
                                        <button
                                            onClick={() => toggle(criterion.criterion_type, criterion.criterion_number, true)}
                                            className={`px-2 py-0.5 rounded text-[10px] font-semibold cursor-pointer border-none transition-all ${resolved === true ? 'bg-green-600 text-white' : 'bg-gray-100 text-gray-400'}`}
                                        >Yes</button>
                                        <button
                                            onClick={() => toggle(criterion.criterion_type, criterion.criterion_number, false)}
                                            className={`px-2 py-0.5 rounded text-[10px] font-semibold cursor-pointer border-none transition-all ${resolved === false ? 'bg-red-600 text-white' : 'bg-gray-100 text-gray-400'}`}
                                        >No</button>
                                    </div>
                                </div>
                            );
                        })
                    )}
                </div>

                {/* Footer */}
                <div className={`px-3.5 py-2 flex items-center justify-between rounded-b-lg ${isPatient ? 'bg-blue-50 border-t border-blue-300' : 'bg-red-50 border-t border-red-300'}`}>
                    <span className="text-[10px] text-gray-400">{resolutions.size}/{criteria.length}</span>
                    <button
                        onClick={handleSave}
                        disabled={resolutions.size === 0 || saving}
                        className={`px-3 py-1 text-[11px] font-semibold text-white rounded-md border-none flex items-center gap-1 ${(resolutions.size === 0 || saving) ? 'bg-gray-300 cursor-not-allowed' : isPatient ? 'bg-blue-600 cursor-pointer' : 'bg-red-700 cursor-pointer'}`}
                    >
                        {saving && <Loader2 className="w-2.5 h-2.5 animate-spin" />}
                        {saving ? 'Saving...' : 'Save'}
                    </button>
                </div>
            </div>
        </div>
    );
}

// ── Testing Modal (Bucket 3 — read-only) ─────────────────────────────────
function TestingModal({
    trialId,
    criteria,
    onClose,
}: {
    trialId: string;
    criteria: CriterionResult[];
    onClose: () => void;
}) {
    return (
        <div className="fixed inset-0 z-50 flex items-center justify-center">
            <div className="absolute inset-0 bg-black/20" onClick={onClose} />
            <div className="relative bg-white rounded-lg w-[840px] max-h-[80vh] flex flex-col shadow-lg border border-amber-200">
                {/* Header */}
                <div className="px-3.5 py-2.5 flex items-center justify-between bg-amber-50 border-b border-amber-200 rounded-t-lg">
                    <div className="flex items-center gap-2">
                        <HelpCircle className="w-3.5 h-3.5 text-amber-600" />
                        <span className="text-xs font-semibold text-amber-800">
                            Needs Testing
                        </span>
                        <span className="text-[10px] text-gray-400">{trialId}</span>
                    </div>
                    <button onClick={onClose} className="bg-transparent border-none cursor-pointer text-gray-400 p-0.5">
                        <X className="w-3.5 h-3.5" />
                    </button>
                </div>

                {/* Criteria + Suggested Tests */}
                <div className="flex-1 overflow-y-auto px-3.5 py-2">
                    {criteria.length === 0 ? (
                        <p className="text-center text-[11px] text-gray-400 py-5">No testing criteria</p>
                    ) : (
                        criteria.map((criterion, idx) => (
                            <div key={idx} className="flex items-start gap-2.5 py-1.5 border-b border-gray-100 last:border-b-0">
                                <p className="flex-1 text-[11px] text-gray-700 leading-snug m-0 pt-0.5">
                                    {criterion.criterion_text}
                                </p>
                                <span className="shrink-0 text-[10px] font-semibold text-amber-600 bg-amber-100 px-2 py-0.5 rounded whitespace-nowrap">
                                    {(criterion as any).suggested_test || 'Clinical Assessment'}
                                </span>
                            </div>
                        ))
                    )}
                </div>

                {/* Footer */}
                <div className="px-3.5 py-2 flex items-center justify-between bg-amber-50 border-t border-amber-200 rounded-b-lg">
                    <span className="text-[10px] text-gray-400">{criteria.length} criteria need testing</span>
                    <button
                        onClick={onClose}
                        className="px-3 py-1 text-[11px] font-semibold text-white rounded-md border-none cursor-pointer bg-amber-600"
                    >
                        Close
                    </button>
                </div>
            </div>
        </div>
    );
}

// ── Main Component ────────────────────────────────────────────────────────
export function ClinicalTrialsTab({ focusTrialId }: { focusTrialId?: string } = {}) {
    const { currentPatient } = usePatient();
    const { selectedHospital } = useHospital();
    const [trials, setTrials] = useState<ClinicalTrial[]>([]);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [searchQueries, setSearchQueries] = useState<string[]>([]);
    const [expandedTrials, setExpandedTrials] = useState<Set<string>>(new Set());
    const [highlightedTrial, setHighlightedTrial] = useState<string | undefined>(focusTrialId);
    const trialRefs = useRef<Map<string, HTMLDivElement>>(new Map());
    const [useCached, setUseCached] = useState(true);
    const [cachedCount, setCachedCount] = useState<number>(0);

    // Review modal state
    const [reviewModal, setReviewModal] = useState<{
        type: 'patient' | 'clinician';
        trialNctId: string;
    } | null>(null);
    const [saving, setSaving] = useState(false);

    // Testing modal state (Bucket 3)
    const [testingModal, setTestingModal] = useState<string | null>(null);

    // Per-trial refresh state
    const [refreshingTrials, setRefreshingTrials] = useState<Set<string>>(new Set());

    // Patient review link modal state
    const [linkModal, setLinkModal] = useState<{ nctId: string; url: string } | null>(null);
    const [sendingLink, setSendingLink] = useState(false);
    const [copied, setCopied] = useState(false);

    // Search/filter state
    const [filterText, setFilterText] = useState('');

    // Computation progress state (progressive loading)
    const [computationStatus, setComputationStatus] = useState<
        'not_started' | 'computing' | 'completed' | 'stale' | 'error' | null
    >(null);
    const [progress, setProgress] = useState({ total: 0, completed: 0, eligible: 0, error: 0 });
    const pollingRef = useRef<ReturnType<typeof setInterval> | null>(null);
    const prevCompletedRef = useRef<number>(0);
    const computationStartRef = useRef<number | null>(null);

    // ── Data fetching ─────────────────────────────────────────────────
    const fetchCachedTrials = async () => {
        if (!currentPatient?.mrn) return false;

        try {
            const response = await apiService.getCachedEligibleTrialsForPatient(currentPatient.mrn, undefined, selectedHospital);
            if (response.success && response.trials && response.trials.length > 0) {
                const transformedTrials = response.trials.map((t: any) => {
                    const inclusion = t.criteria_results?.inclusion ||
                        t.key_matching_criteria?.map((c: string, i: number) => ({
                            criterion_number: i + 1, criterion_text: c, patient_value: '',
                            met: true, confidence: 'high', explanation: '', criterion_type: 'inclusion' as const
                        })) || [];

                    const exclusion = t.criteria_results?.exclusion ||
                        t.key_exclusion_reasons?.map((c: string, i: number) => ({
                            criterion_number: i + 1, criterion_text: c, patient_value: '',
                            met: true, confidence: 'high', explanation: '', criterion_type: 'exclusion' as const
                        })) || [];

                    const inclusionMet = inclusion.filter((c: any) => c.met === true).length;
                    const inclusionNotMet = inclusion.filter((c: any) => c.met === false).length;
                    const inclusionUnknown = inclusion.filter((c: any) => c.met === null).length;
                    const inclusionConsent = inclusion.filter((c: any) => c.consent_needed === true).length;
                    const exclusionClear = exclusion.filter((c: any) => c.met === false).length;
                    const exclusionViolated = exclusion.filter((c: any) => c.met === true).length;
                    const exclusionUnknown = exclusion.filter((c: any) => c.met === null).length;
                    const exclusionConsent = exclusion.filter((c: any) => c.consent_needed === true).length;

                    return {
                        nct_id: t.trial_nct_id,
                        title: t.title || 'Unknown Trial',
                        phase: t.phase,
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
                            inclusion: { met: inclusionMet, not_met: inclusionNotMet, unknown: inclusionUnknown, consent_needed: inclusionConsent, total: inclusion.length },
                            exclusion: { clear: exclusionClear, violated: exclusionViolated, unknown: exclusionUnknown, consent_needed: exclusionConsent, total: exclusion.length }
                        },
                        criteria_results: { inclusion, exclusion },
                        contact: {},
                        locations: []
                    };
                });
                // Sort: LIKELY_ELIGIBLE first, then POTENTIALLY_ELIGIBLE, then NOT_ELIGIBLE; within each group by percentage desc
                const statusOrder: Record<string, number> = { 'LIKELY_ELIGIBLE': 0, 'POTENTIALLY_ELIGIBLE': 1, 'NOT_ELIGIBLE': 2 };
                transformedTrials.sort((a: any, b: any) => {
                    const aOrder = statusOrder[a.eligibility.status] ?? 2;
                    const bOrder = statusOrder[b.eligibility.status] ?? 2;
                    if (aOrder !== bOrder) return aOrder - bOrder;
                    return (b.eligibility.percentage || 0) - (a.eligibility.percentage || 0);
                });
                // Merge new trials into existing list to avoid flash/jump on re-render
                setTrials(prev => {
                    if (prev.length === 0) return transformedTrials;
                    const existingMap = new Map(prev.map(t => [t.nct_id, t]));
                    const merged = transformedTrials.map((t: any) => {
                        const existing = existingMap.get(t.nct_id);
                        // Update data but preserve identity if unchanged
                        if (existing && existing.eligibility.percentage === t.eligibility.percentage
                            && existing.eligibility.status === t.eligibility.status) {
                            return existing;
                        }
                        return t;
                    });
                    return merged;
                });
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

    // ── Polling for progressive loading ──────────────────────────────
    const stopPolling = () => {
        if (pollingRef.current) {
            clearInterval(pollingRef.current);
            pollingRef.current = null;
        }
    };

    const pollProgress = async () => {
        if (!currentPatient?.mrn) return;
        try {
            const resp = await apiService.getEligibilityProgress(currentPatient.mrn);
            if (!resp.success) return;

            setComputationStatus(resp.status);
            setProgress({
                total: resp.trials_total,
                completed: resp.trials_completed,
                eligible: resp.trials_eligible,
                error: resp.trials_error,
            });

            // If new trials completed since last poll, refetch results
            if (resp.trials_completed > prevCompletedRef.current) {
                prevCompletedRef.current = resp.trials_completed;
                await fetchCachedTrials();
            }

            // Stop polling on terminal states
            if (resp.status === 'completed' || resp.status === 'error' || resp.status === 'not_started') {
                stopPolling();
            }
        } catch {
            // Don't stop polling on transient network errors
        }
    };

    const startPolling = () => {
        stopPolling();
        prevCompletedRef.current = 0;
        computationStartRef.current = Date.now();
        pollProgress(); // Immediate first poll
        pollingRef.current = setInterval(pollProgress, 10000); // 10s interval
    };

    const fetchTrials = async (forceRealTime = false) => {
        if (!currentPatient?.mrn) return;
        setLoading(true);
        setError(null);

        if (useCached && !forceRealTime) {
            const hasCached = await fetchCachedTrials();

            // Check computation status regardless
            try {
                const resp = await apiService.getEligibilityProgress(currentPatient.mrn);
                setComputationStatus(resp.status);
                setProgress({
                    total: resp.trials_total,
                    completed: resp.trials_completed,
                    eligible: resp.trials_eligible,
                    error: resp.trials_error,
                });
                if (resp.status === 'computing') {
                    prevCompletedRef.current = resp.trials_completed;
                    startPolling();
                }
            } catch {
                // Non-fatal
            }

            if (hasCached) { setLoading(false); return; }
        }

        try {
            const response: ClinicalTrialsResponse = await apiService.getClinicalTrials(currentPatient.mrn, selectedHospital);
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
        if (currentPatient?.mrn) fetchTrials();
        return () => stopPolling();
    }, [currentPatient?.mrn, selectedHospital]);

    // Auto-expand and scroll to a specific trial when navigated from trial detail view
    useEffect(() => {
        if (focusTrialId && trials.length > 0 && !loading) {
            setHighlightedTrial(focusTrialId);
            setExpandedTrials(prev => new Set(prev).add(focusTrialId));
            setTimeout(() => {
                const el = trialRefs.current.get(focusTrialId);
                if (el) el.scrollIntoView({ behavior: 'smooth', block: 'start' });
            }, 150);
        }
    }, [focusTrialId, trials, loading]);

    // ── Helpers ────────────────────────────────────────────────────────
    const toggleTrialExpanded = (nctId: string) => {
        setExpandedTrials(prev => {
            const next = new Set(prev);
            next.has(nctId) ? next.delete(nctId) : next.add(nctId);
            // Highlight the trial being expanded, clear if collapsing
            setHighlightedTrial(next.has(nctId) ? nctId : undefined);
            return next;
        });
    };

    const getStatusIcon = (met: boolean | null) => {
        if (met === true) return <CheckCircle className="w-4 h-4 text-green-600" />;
        if (met === false) return <XCircle className="w-4 h-4 text-red-500" />;
        return <HelpCircle className="w-4 h-4 text-amber-500" />;
    };

    const getStatusBadge = (status: string) => {
        const colors: Record<string, string> = {
            'LIKELY_ELIGIBLE': 'bg-green-100 text-green-700 border-green-300',
            'POTENTIALLY_ELIGIBLE': 'bg-amber-100 text-amber-800 border-amber-300',
            'NOT_ELIGIBLE': 'bg-red-100 text-red-800 border-red-300'
        };
        const labels: Record<string, string> = {
            'LIKELY_ELIGIBLE': 'Likely Eligible',
            'POTENTIALLY_ELIGIBLE': 'Potentially Eligible',
            'NOT_ELIGIBLE': 'Not Eligible'
        };
        return (
            <span className={`px-3 py-1 rounded-lg text-xs font-medium border ${colors[status] || 'bg-gray-100 text-gray-800'}`}>
                {labels[status] || status}
            </span>
        );
    };

    const getPercentageColor = (pct: number) => {
        if (pct >= 80) return 'text-green-600';
        if (pct >= 60) return 'text-amber-600';
        return 'text-red-500';
    };

    const getReviewCounts = (trial: ClinicalTrial) => {
        const all = [...(trial.criteria_results?.inclusion || []), ...(trial.criteria_results?.exclusion || [])];
        // Include both unknowns (met=null) and consent items in review counts
        const reviewable = all.filter((c: any) => c.met === null || c.consent_needed);
        return {
            patient: reviewable.filter((c: any) => c.review_type === 'patient').length,
            clinician: reviewable.filter((c: any) => c.review_type === 'clinician').length,
            testing: all.filter((c: any) => c.met === null && (c.review_type === 'testing' || !c.review_type)).length,
        };
    };

    // ── Review modal ──────────────────────────────────────────────────
    const getModalCriteria = (): CriterionResult[] => {
        if (!reviewModal) return [];
        const trial = trials.find(t => t.nct_id === reviewModal.trialNctId);
        if (!trial) return [];
        return [
            ...(trial.criteria_results?.inclusion || []),
            ...(trial.criteria_results?.exclusion || [])
        ].filter((c: any) => (c.met === null || c.consent_needed) && c.review_type === reviewModal.type);
    };

    const handleSaveResolutions = async (payloads: CriterionResolutionPayload[]) => {
        if (!currentPatient?.mrn || !reviewModal) return;
        setSaving(true);
        try {
            const response = await apiService.resolveCriteria(
                currentPatient.mrn, reviewModal.trialNctId, payloads, selectedHospital
            );
            if (response.success) {
                setTrials(prev => prev.map(t => {
                    if (t.nct_id !== reviewModal.trialNctId) return t;
                    const inc = response.criteria_results.inclusion || [];
                    const exc = response.criteria_results.exclusion || [];
                    return {
                        ...t,
                        eligibility: {
                            status: response.updated_eligibility.status,
                            status_reason: response.updated_eligibility.status_reason || '',
                            percentage: response.updated_eligibility.percentage,
                            inclusion: {
                                met: inc.filter((c: any) => c.met === true).length,
                                not_met: inc.filter((c: any) => c.met === false).length,
                                unknown: inc.filter((c: any) => c.met === null).length,
                                consent_needed: inc.filter((c: any) => c.consent_needed === true).length,
                                total: inc.length
                            },
                            exclusion: {
                                clear: exc.filter((c: any) => c.met === false).length,
                                violated: exc.filter((c: any) => c.met === true && !c.consent_needed).length,
                                unknown: exc.filter((c: any) => c.met === null).length,
                                consent_needed: exc.filter((c: any) => c.consent_needed === true).length,
                                total: exc.length
                            },
                        },
                        criteria_results: response.criteria_results,
                    };
                }));
                setReviewModal(null);
            }
        } catch (err) {
            console.error('Failed to save resolutions:', err);
        } finally {
            setSaving(false);
        }
    };

    // ── Send patient review link ──────────────────────────────────────
    const handleSendToPatient = async (nctId: string) => {
        if (!currentPatient?.mrn) return;
        setSendingLink(true);
        try {
            const response = await apiService.sendPatientReview(currentPatient.mrn, nctId, selectedHospital);
            if (response.success && response.review_url) {
                setLinkModal({ nctId, url: response.review_url });
                setCopied(false);
            } else {
                alert(response.message || 'No patient-review criteria to send.');
            }
        } catch (err) {
            console.error('Failed to generate review link:', err);
            alert('Failed to generate review link.');
        } finally {
            setSendingLink(false);
        }
    };

    const handleCopyLink = async () => {
        if (!linkModal) return;
        try {
            await navigator.clipboard.writeText(linkModal.url);
            setCopied(true);
            setTimeout(() => setCopied(false), 2000);
        } catch {
            // Fallback for older browsers
            const input = document.createElement('input');
            input.value = linkModal.url;
            document.body.appendChild(input);
            input.select();
            document.execCommand('copy');
            document.body.removeChild(input);
            setCopied(true);
            setTimeout(() => setCopied(false), 2000);
        }
    };

    // ── Testing modal criteria helper ──────────────────────────────────
    const getTestingCriteria = (): CriterionResult[] => {
        if (!testingModal) return [];
        const trial = trials.find(t => t.nct_id === testingModal);
        if (!trial) return [];
        return [
            ...(trial.criteria_results?.inclusion || []),
            ...(trial.criteria_results?.exclusion || [])
        ].filter((c: any) => c.met === null && (c.review_type === 'testing' || !c.review_type));
    };

    // ── Per-trial refresh handler ────────────────────────────────────
    const handleRefreshTrial = async (nctId: string) => {
        if (!currentPatient?.mrn) return;
        setRefreshingTrials(prev => new Set(prev).add(nctId));
        try {
            const response = await apiService.refreshTrialEligibility(currentPatient.mrn, nctId, selectedHospital);
            if (response.success) {
                setTrials(prev => prev.map(t => {
                    if (t.nct_id !== nctId) return t;
                    const inc = response.criteria_results.inclusion || [];
                    const exc = response.criteria_results.exclusion || [];
                    return {
                        ...t,
                        eligibility: {
                            status: response.updated_eligibility.status,
                            status_reason: response.updated_eligibility.status_reason || '',
                            percentage: response.updated_eligibility.percentage,
                            inclusion: {
                                met: inc.filter((c: any) => c.met === true).length,
                                not_met: inc.filter((c: any) => c.met === false).length,
                                unknown: inc.filter((c: any) => c.met === null).length,
                                consent_needed: inc.filter((c: any) => c.consent_needed === true).length,
                                total: inc.length
                            },
                            exclusion: {
                                clear: exc.filter((c: any) => c.met === false).length,
                                violated: exc.filter((c: any) => c.met === true && !c.consent_needed).length,
                                unknown: exc.filter((c: any) => c.met === null).length,
                                consent_needed: exc.filter((c: any) => c.consent_needed === true).length,
                                total: exc.length
                            },
                        },
                        criteria_results: response.criteria_results,
                    };
                }));
            }
        } catch (err) {
            console.error('Failed to refresh trial:', err);
        } finally {
            setRefreshingTrials(prev => {
                const next = new Set(prev);
                next.delete(nctId);
                return next;
            });
        }
    };

    // ── Criteria table ────────────────────────────────────────────────
    const renderCriteriaTable = (criteria: CriterionResult[], type: 'inclusion' | 'exclusion') => {
        if (!criteria || criteria.length === 0) {
            return <div className="text-center py-4 text-gray-500 text-sm">No {type} criteria found</div>;
        }

        return (
            <div className="overflow-hidden rounded-lg border border-gray-200">
                <table className="w-full text-sm">
                    <thead className={type === 'inclusion' ? 'bg-green-50' : 'bg-red-50'}>
                        <tr>
                            <th className="px-3 py-2 text-left font-medium text-gray-700" style={{width: '45%'}}>Criterion</th>
                            <th className="px-3 py-2 text-left font-medium text-gray-700" style={{width: '40%'}}>Patient Value</th>
                            <th className="px-3 py-2 text-center font-medium text-gray-700" style={{width: '15%'}}>Status</th>
                        </tr>
                    </thead>
                    <tbody className="divide-y divide-gray-100">
                        {criteria.map((criterion, idx) => {
                            const isResolved = (criterion as any).manually_resolved;
                            const resolvedBy = (criterion as any).resolved_by;
                            const reviewType = (criterion as any).review_type;
                            const isConsent = (criterion as any).consent_needed;
                            const needsReview = (criterion.met === null || isConsent) && !isResolved;

                            return (
                                <tr key={idx} className="hover:bg-gray-50 transition-colors">
                                    <td className="px-3 py-2 text-gray-800">
                                        <span className="line-clamp-2" title={criterion.explanation}>
                                            {criterion.criterion_text}
                                        </span>
                                    </td>
                                    <td className="px-3 py-2 text-gray-600">
                                        {isResolved ? (
                                            <span className="inline-flex items-center gap-1 text-xs font-medium text-blue-600">
                                                <ClipboardCheck className="w-3 h-3" />
                                                {resolvedBy === 'patient' ? 'Patient Reviewed' : 'Clinician Reviewed'}
                                            </span>
                                        ) : needsReview && reviewType === 'patient' ? (
                                            <div className="rounded px-2 py-1.5 max-w-xs bg-blue-50 border border-blue-300">
                                                <div className="inline-flex items-center gap-1 text-[10px] font-semibold uppercase tracking-wide mb-0.5 text-blue-900">
                                                    <ClipboardCheck className="w-3 h-3" />
                                                    Patient Can Answer
                                                </div>
                                                <p className="text-xs text-gray-700 leading-snug">
                                                    {criterion.criterion_text || 'Ask the patient directly'}
                                                </p>
                                            </div>
                                        ) : needsReview && reviewType === 'clinician' ? (
                                            <div className="rounded px-2 py-1.5 max-w-xs bg-red-50 border border-red-300">
                                                <div className="inline-flex items-center gap-1 text-[10px] font-semibold uppercase tracking-wide mb-0.5 text-red-900">
                                                    <ClipboardCheck className="w-3 h-3" />
                                                    Clinician Review
                                                </div>
                                                <p className="text-xs text-gray-700 leading-snug">
                                                    {(criterion as any).clinician_action && (criterion as any).clinician_action !== 'None' && (criterion as any).clinician_action !== 'null'
                                                        ? (criterion as any).clinician_action
                                                        : `Patient has: ${criterion.patient_value}. Needs clinical assessment.`}
                                                </p>
                                            </div>
                                        ) : needsReview && (reviewType === 'testing' || !reviewType) ? (
                                            <div className="bg-purple-50 border border-purple-200 rounded px-2 py-1.5 max-w-xs">
                                                <div className="inline-flex items-center gap-1 text-[10px] font-semibold text-purple-700 uppercase tracking-wide mb-0.5">
                                                    <FlaskConical className="w-3 h-3" />
                                                    Testing Needed
                                                </div>
                                                <p className="text-xs text-gray-700 leading-snug">
                                                    {(criterion as any).suggested_test && (criterion as any).suggested_test !== 'None' && (criterion as any).suggested_test !== 'null'
                                                        ? (criterion as any).suggested_test
                                                        : 'Specific test to be determined'}
                                                </p>
                                            </div>
                                        ) : (
                                            <span className="line-clamp-2">{criterion.patient_value || '-'}</span>
                                        )}
                                    </td>
                                    <td className="px-3 py-2 text-center">
                                        {needsReview && reviewType === 'patient' ? (
                                            <ClipboardCheck className="w-4 h-4 mx-auto text-blue-600" title="Patient Can Answer" />
                                        ) : needsReview && reviewType === 'clinician' ? (
                                            <ClipboardCheck className="w-4 h-4 mx-auto text-red-700" title="Clinician Review" />
                                        ) : needsReview && (reviewType === 'testing' || !reviewType) ? (
                                            <FlaskConical className="w-4 h-4 text-purple-500 mx-auto" title="Testing Needed" />
                                        ) : isResolved ? (
                                            type === 'exclusion' ? (
                                                criterion.met === true
                                                    ? <XCircle className="w-4 h-4 text-red-500 mx-auto" title="Excluded" />
                                                    : <CheckCircle className="w-4 h-4 text-green-600 mx-auto" title="Clear" />
                                            ) : (
                                                criterion.met === true
                                                    ? <CheckCircle className="w-4 h-4 text-green-600 mx-auto" title="Met" />
                                                    : <XCircle className="w-4 h-4 text-red-500 mx-auto" title="Not met" />
                                            )
                                        ) : type === 'exclusion' ? (
                                            criterion.met === false
                                                ? <CheckCircle className="w-4 h-4 text-green-600 mx-auto" title="Clear" />
                                                : criterion.met === true
                                                ? <XCircle className="w-4 h-4 text-red-500 mx-auto" title="Violated" />
                                                : <HelpCircle className="w-4 h-4 text-amber-500 mx-auto" title="Unknown" />
                                        ) : (
                                            getStatusIcon(criterion.met)
                                        )}
                                    </td>
                                </tr>
                            );
                        })}
                    </tbody>
                </table>
            </div>
        );
    };

    // ── Render ─────────────────────────────────────────────────────────
    if (!currentPatient) {
        return (
            <div className="bg-white border border-t-0 border-gray-200 rounded-b-lg shadow-sm p-6">
                <div className="text-center text-gray-500 py-8">No patient data available</div>
            </div>
        );
    }

    return (
        <div className="bg-white border border-t-0 border-gray-200 rounded-b-lg shadow-sm p-6">
            {/* Header */}
            <div className="flex items-center justify-between mb-6">
                <div className="flex items-center gap-3">
                    <div className="w-10 h-10 bg-blue-100 p-2 rounded-lg flex items-center justify-center">
                        <FlaskConical className="w-5 h-5 text-blue-600" />
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
                            className="flex flex-row items-center gap-2 px-4 py-2 bg-white border border-gray-300 text-gray-700 rounded-lg hover:bg-gray-50 transition-colors disabled:opacity-50 whitespace-nowrap"
                        >
                            <Search className="w-4 h-4 flex-shrink-0" />
                            <span>Search New Trials</span>
                        </button>
                    )}
                    <button
                        onClick={() => fetchTrials()}
                        disabled={loading}
                        className="flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors disabled:opacity-50"
                    >
                        <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
                        {loading ? 'Searching...' : 'Refresh'}
                    </button>
                </div>
            </div>

            {/* Loading */}
            {loading && (
                <div className="flex flex-col items-center justify-center py-16">
                    <div className="w-16 h-16 border-4 border-blue-200 border-t-blue-600 rounded-full animate-spin mb-4"></div>
                    <p className="text-gray-600">Searching for matching clinical trials...</p>
                    <p className="text-sm text-gray-400 mt-2">Analyzing eligibility criteria for each trial</p>
                </div>
            )}

            {/* Error */}
            {error && !loading && (
                <div className="flex items-center gap-3 p-4 bg-red-50 border border-red-200 rounded-lg mb-6">
                    <AlertCircle className="w-5 h-5 text-red-500" />
                    <p className="text-red-700">{error}</p>
                </div>
            )}

            {/* Computation Progress Banner */}
            {computationStatus === 'computing' && (
                <div className="mb-4 bg-gradient-to-r from-blue-50 to-indigo-50 border border-blue-200 rounded-lg p-4">
                    <div className="flex items-center justify-between mb-2">
                        <div className="flex items-center gap-2">
                            <Loader2 className="w-4 h-4 text-blue-600 animate-spin" />
                            <span className="text-sm font-medium text-blue-800">
                                Analyzing eligibility for clinical trials...
                            </span>
                        </div>
                        <span className="text-sm font-mono text-blue-600">
                            {progress.completed}/{progress.total}
                        </span>
                    </div>
                    <div className="w-full bg-blue-100 rounded-full h-2">
                        <div
                            className="bg-blue-600 h-2 rounded-full transition-all duration-500 ease-out"
                            style={{ width: `${progress.total > 0 ? (progress.completed / progress.total) * 100 : 0}%` }}
                        />
                    </div>
                    <div className="flex items-center justify-between mt-2 text-xs text-blue-600">
                        <span>{trials.filter(t => t.eligibility.status === 'LIKELY_ELIGIBLE' || t.eligibility.status === 'POTENTIALLY_ELIGIBLE').length} eligible trial{trials.filter(t => t.eligibility.status === 'LIKELY_ELIGIBLE' || t.eligibility.status === 'POTENTIALLY_ELIGIBLE').length !== 1 ? 's' : ''} found so far</span>
                        <span>
                            {(() => {
                                const elapsed = computationStartRef.current ? (Date.now() - computationStartRef.current) / 1000 : 0;
                                const secPerTrial = progress.completed > 0 && elapsed > 0 ? elapsed / progress.completed : 10;
                                const remaining = Math.max(1, Math.ceil(((progress.total - progress.completed) * secPerTrial) / 60));
                                return `~${remaining} min remaining`;
                            })()}
                        </span>
                    </div>
                </div>
            )}

            {computationStatus === 'stale' && (
                <div className="mb-4 bg-amber-50 border border-amber-200 rounded-lg p-4 flex items-center justify-between">
                    <div className="flex items-center gap-2">
                        <AlertCircle className="w-4 h-4 text-amber-600" />
                        <span className="text-sm text-amber-800">
                            A previous analysis was interrupted. Results may be incomplete ({progress.completed}/{progress.total} trials analyzed).
                        </span>
                    </div>
                    <button
                        onClick={() => {
                            apiService.computeEligibility({ patientMrn: currentPatient?.mrn, background: true });
                            setComputationStatus('computing');
                            startPolling();
                        }}
                        className="px-3 py-1.5 text-sm font-medium text-amber-700 bg-amber-100 border border-amber-300 rounded-lg hover:bg-amber-200 transition-colors"
                    >
                        Resume Analysis
                    </button>
                </div>
            )}

            {computationStatus === 'error' && (
                <div className="mb-4 bg-red-50 border border-red-200 rounded-lg p-4 flex items-center justify-between">
                    <div className="flex items-center gap-2">
                        <AlertCircle className="w-4 h-4 text-red-500" />
                        <span className="text-sm text-red-700">
                            Eligibility analysis encountered an error. Partial results shown below.
                        </span>
                    </div>
                    <button
                        onClick={() => {
                            apiService.computeEligibility({ patientMrn: currentPatient?.mrn, background: true });
                            setComputationStatus('computing');
                            startPolling();
                        }}
                        className="px-3 py-1.5 text-sm font-medium text-red-700 bg-red-100 border border-red-300 rounded-lg hover:bg-red-200 transition-colors"
                    >
                        Retry Analysis
                    </button>
                </div>
            )}

            {/* Empty */}
            {!loading && !error && trials.length === 0 && (
                <div className="text-center py-12 bg-gray-50 rounded-lg border border-gray-200">
                    <FlaskConical className="w-12 h-12 text-gray-400 mx-auto mb-3" />
                    {computationStatus === 'computing' ? (
                        <>
                            <p className="text-gray-600 font-medium">Analyzing clinical trials...</p>
                            <p className="text-gray-400 text-sm mt-1">
                                Results will appear here as they are computed.
                                {progress.completed > 0 && ` ${progress.completed} trials analyzed so far.`}
                            </p>
                        </>
                    ) : (
                        <>
                            <p className="text-gray-600 font-medium">No matching clinical trials found</p>
                            <p className="text-gray-400 text-sm mt-1">Try refreshing or check back later</p>
                        </>
                    )}
                </div>
            )}

            {/* Trials List */}
            {!loading && trials.length > 0 && (() => {
                const query = filterText.toLowerCase().trim();
                const filteredTrials = query
                    ? trials.filter(t =>
                        t.nct_id.toLowerCase().includes(query) ||
                        t.title.toLowerCase().includes(query) ||
                        (t.phase || '').toLowerCase().includes(query) ||
                        t.eligibility.status.toLowerCase().replace(/_/g, ' ').includes(query) ||
                        (query === 'likely' && t.eligibility.status === 'LIKELY_ELIGIBLE') ||
                        (query === 'potential' && t.eligibility.status === 'POTENTIALLY_ELIGIBLE') ||
                        (query === 'not eligible' && t.eligibility.status === 'NOT_ELIGIBLE')
                    )
                    : trials;

                return (
                <div className="space-y-4">
                    {/* Summary + Search */}
                    <div className="flex items-center justify-between gap-4">
                        <div className="bg-blue-50 border border-blue-200 rounded-lg px-4 py-3 flex-shrink-0">
                            <p className="text-blue-800 font-medium text-sm">
                                {trials.length} trial{trials.length !== 1 ? 's' : ''} analyzed
                                {computationStatus === 'computing' && progress.total > 0 && (
                                    <span className="text-blue-500 font-normal ml-1">
                                        (analyzing {progress.total - progress.completed} more...)
                                    </span>
                                )}
                            </p>
                        </div>
                        <div className="relative flex-1 max-w-md">
                            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400 pointer-events-none" />
                            <input
                                type="text"
                                placeholder="Search by NCT ID, title, phase, or eligibility..."
                                value={filterText}
                                onChange={e => setFilterText(e.target.value)}
                                className="w-full pl-10 pr-10 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-300 focus:border-blue-400"
                            />
                            {filterText && (
                                <button
                                    onClick={() => setFilterText('')}
                                    className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600"
                                >
                                    <X className="w-3.5 h-3.5" />
                                </button>
                            )}
                        </div>
                    </div>

                    {/* Filter result count */}
                    {query && (
                        <p className="text-sm text-gray-500">
                            Showing {filteredTrials.length} of {trials.length} trials
                        </p>
                    )}

                    {/* No results */}
                    {filteredTrials.length === 0 && (
                        <div className="text-center py-8 text-gray-500 text-sm">
                            No trials match "{filterText}"
                        </div>
                    )}

                    {filteredTrials.map((trial) => {
                        const rc = getReviewCounts(trial);
                        return (
                            <div key={trial.nct_id} ref={el => { if (el) trialRefs.current.set(trial.nct_id, el); }} className={`border-2 rounded-lg overflow-hidden transition-colors relative ${highlightedTrial === trial.nct_id ? 'border-blue-400 ring-2 ring-blue-200' : 'border-gray-200 hover:border-blue-300'}`}>
                                {/* Refreshing overlay */}
                                {refreshingTrials.has(trial.nct_id) && (
                                    <div className="absolute inset-0 bg-white/70 z-10 flex flex-col items-center justify-center rounded-xl">
                                        <Loader2 className="w-8 h-8 text-blue-600 animate-spin mb-2" />
                                        <p className="text-sm text-blue-700 font-medium">Re-analyzing eligibility...</p>
                                        <p className="text-xs text-gray-500 mt-1">This may take 1-3 minutes</p>
                                    </div>
                                )}
                                {/* Trial Header */}
                                <div
                                    className="p-5 cursor-pointer bg-gradient-to-r from-gray-50 to-white hover:from-blue-50 hover:to-white transition-colors"
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
                                                    className="text-blue-600 font-mono font-medium hover:underline flex items-center gap-1"
                                                >
                                                    {trial.nct_id}
                                                    <ExternalLink className="w-3 h-3" />
                                                </a>
                                                {trial.phase && trial.phase !== 'N/A' && trial.phase !== 'NA' && (
                                                    <span className="px-2 py-0.5 bg-blue-100 text-blue-700 rounded text-xs font-medium">
                                                        {trial.phase}
                                                    </span>
                                                )}
                                                <span className="px-2 py-0.5 bg-green-100 text-green-700 rounded text-xs font-medium">
                                                    {trial.status}
                                                </span>
                                            </div>
                                            <h3 className="text-gray-900 font-medium line-clamp-2">{trial.title}</h3>
                                        </div>
                                        <div className="flex items-center gap-3 flex-shrink-0" style={{ width: 180 }}>
                                            <div className="flex flex-col items-center gap-1 flex-1">
                                                <span className={`text-2xl font-bold ${getPercentageColor(trial.eligibility.percentage)}`}>
                                                    {trial.eligibility.percentage}%
                                                </span>
                                                <p className="text-xs text-gray-500">Match</p>
                                                {getStatusBadge(trial.eligibility.status)}
                                            </div>
                                            <button
                                                onClick={(e) => { e.stopPropagation(); handleRefreshTrial(trial.nct_id); }}
                                                disabled={refreshingTrials.has(trial.nct_id)}
                                                className="p-2 rounded-lg text-gray-300 hover:text-blue-600 hover:bg-blue-50 transition-colors disabled:opacity-50"
                                                title="Re-run eligibility analysis"
                                            >
                                                <RefreshCw className={`w-4 h-4 ${refreshingTrials.has(trial.nct_id) ? 'animate-spin' : ''}`} />
                                            </button>
                                        </div>
                                    </div>

                                    {/* Criteria Summary Bar */}
                                    <div className="mt-4 flex items-center gap-3 text-sm flex-wrap">
                                        <div className="flex items-center gap-1.5">
                                            <CheckCircle className="w-4 h-4 text-green-600" />
                                            <span className="text-gray-600">
                                                Inclusion: {trial.eligibility.inclusion.met}/{trial.eligibility.inclusion.total}
                                            </span>
                                        </div>
                                        <div className="flex items-center gap-1.5">
                                            <CheckCircle className="w-4 h-4 text-green-600" />
                                            <span className="text-gray-600">
                                                Exclusion Clear: {trial.eligibility.exclusion.clear}/{trial.eligibility.exclusion.total}
                                            </span>
                                        </div>

                                        {/* Patient Review Needed */}
                                        {rc.patient > 0 && (
                                            <div className="flex items-center gap-2">
                                                <button
                                                    onClick={(e) => { e.stopPropagation(); setReviewModal({ type: 'patient', trialNctId: trial.nct_id }); }}
                                                    className="flex items-center gap-1 hover:underline cursor-pointer text-blue-600"
                                                >
                                                    <ClipboardCheck className="w-3.5 h-3.5" />
                                                    <span>{rc.patient} Patient Review Needed</span>
                                                </button>
                                                <button
                                                    onClick={(e) => { e.stopPropagation(); handleSendToPatient(trial.nct_id); }}
                                                    className="flex items-center gap-1 px-2 py-0.5 rounded text-xs font-medium hover:opacity-80 cursor-pointer bg-blue-100 text-blue-600"
                                                    title="Generate a shareable link for the patient"
                                                    disabled={sendingLink}
                                                >
                                                    <Send className="w-3 h-3" />
                                                    <span>Send to Patient</span>
                                                </button>
                                            </div>
                                        )}

                                        {/* Clinician Review Needed */}
                                        {rc.clinician > 0 && (
                                            <button
                                                onClick={(e) => { e.stopPropagation(); setReviewModal({ type: 'clinician', trialNctId: trial.nct_id }); }}
                                                className="flex items-center gap-1 hover:underline cursor-pointer text-red-700"
                                            >
                                                <ClipboardCheck className="w-3.5 h-3.5" />
                                                <span>{rc.clinician} Clinician Review Needed</span>
                                            </button>
                                        )}

                                        {/* Needs Testing */}
                                        {rc.testing > 0 && (
                                            <button
                                                onClick={(e) => { e.stopPropagation(); setTestingModal(trial.nct_id); }}
                                                className="flex items-center gap-1 text-amber-600 hover:text-amber-800 hover:underline cursor-pointer"
                                            >
                                                <HelpCircle className="w-3.5 h-3.5" />
                                                <span>{rc.testing} Needs Testing</span>
                                            </button>
                                        )}
                                    </div>
                                </div>

                                {/* Expanded Content */}
                                {expandedTrials.has(trial.nct_id) && (
                                    <div className="border-t border-gray-200 bg-white p-5">
                                        <div className="grid grid-cols-2 gap-6 mb-6">
                                            <div>
                                                <div className="flex items-center gap-2 mb-3">
                                                    <CheckCircle className="w-5 h-5 text-green-600" />
                                                    <h4 className="font-medium text-gray-900">Inclusion Criteria</h4>
                                                    <span className="text-sm text-gray-500">
                                                        ({trial.eligibility.inclusion.met}/{trial.eligibility.inclusion.total} met)
                                                    </span>
                                                </div>
                                                {renderCriteriaTable(trial.criteria_results.inclusion, 'inclusion')}
                                            </div>
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

                                        <div className="grid grid-cols-2 gap-6 pt-4 border-t border-gray-200">
                                            {trial.contact && (trial.contact.name || trial.contact.phone || trial.contact.email) && (
                                                <div className="bg-blue-50 rounded-lg p-4">
                                                    <h4 className="font-medium text-gray-900 mb-3 flex items-center gap-2">
                                                        <Phone className="w-4 h-4 text-blue-600" />
                                                        Contact Information
                                                    </h4>
                                                    <div className="space-y-2 text-sm">
                                                        {trial.contact.name && <p className="text-gray-700">{trial.contact.name}</p>}
                                                        {trial.contact.phone && (
                                                            <p className="flex items-center gap-2 text-gray-600">
                                                                <Phone className="w-3 h-3" />
                                                                <a href={`tel:${trial.contact.phone}`} className="hover:text-blue-600">{trial.contact.phone}</a>
                                                            </p>
                                                        )}
                                                        {trial.contact.email && (
                                                            <p className="flex items-center gap-2 text-gray-600">
                                                                <Mail className="w-3 h-3" />
                                                                <a href={`mailto:${trial.contact.email}`} className="hover:text-blue-600">{trial.contact.email}</a>
                                                            </p>
                                                        )}
                                                    </div>
                                                </div>
                                            )}
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
                                                            <p className="text-gray-500 italic">+{trial.locations.length - 3} more locations</p>
                                                        )}
                                                    </div>
                                                </div>
                                            )}
                                        </div>

                                        {trial.brief_summary && (
                                            <div className="mt-4 pt-4 border-t border-gray-200">
                                                <h4 className="font-medium text-gray-900 mb-2">Brief Summary</h4>
                                                <p className="text-sm text-gray-600 leading-relaxed">{trial.brief_summary}</p>
                                            </div>
                                        )}
                                    </div>
                                )}
                            </div>
                        );
                    })}
                </div>
                );
            })()}

            {/* Review Modal */}
            {reviewModal && (
                <ReviewModal
                    type={reviewModal.type}
                    trialId={reviewModal.trialNctId}
                    criteria={getModalCriteria()}
                    onSave={handleSaveResolutions}
                    onClose={() => setReviewModal(null)}
                    saving={saving}
                />
            )}

            {/* Testing Modal (Bucket 3 — read-only) */}
            {testingModal && (
                <TestingModal
                    trialId={testingModal}
                    criteria={getTestingCriteria()}
                    onClose={() => setTestingModal(null)}
                />
            )}

            {/* Patient Review Link Modal */}
            {linkModal && (
                <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50" onClick={() => setLinkModal(null)}>
                    <div className="bg-white rounded-lg shadow-lg max-w-lg w-full mx-4 p-6" onClick={e => e.stopPropagation()}>
                        <div className="flex items-center justify-between mb-4">
                            <div className="flex items-center gap-2">
                                <div className="w-8 h-8 rounded-full flex items-center justify-center bg-blue-100">
                                    <Send className="w-4 h-4 text-blue-600" />
                                </div>
                                <h3 className="text-lg font-semibold text-gray-900">Patient Review Link</h3>
                            </div>
                            <button onClick={() => setLinkModal(null)} className="text-gray-400 hover:text-gray-600">
                                <X className="w-5 h-5" />
                            </button>
                        </div>

                        <p className="text-sm text-gray-600 mb-4">
                            Share this link with the patient to collect their responses for trial <span className="font-medium">{linkModal.nctId}</span>.
                            Their answers will automatically update the eligibility assessment.
                        </p>

                        <div className="flex items-center gap-2 mb-4">
                            <input
                                type="text"
                                readOnly
                                value={linkModal.url}
                                className="flex-1 px-3 py-2 bg-gray-50 border border-gray-200 rounded-lg text-sm text-gray-700 font-mono"
                                onClick={e => (e.target as HTMLInputElement).select()}
                            />
                            <button
                                onClick={handleCopyLink}
                                className={`flex items-center gap-1.5 px-4 py-2 rounded-lg text-sm font-medium text-white transition-colors ${copied ? 'bg-green-600' : 'bg-blue-600'}`}
                            >
                                {copied ? <Check className="w-4 h-4" /> : <Copy className="w-4 h-4" />}
                                {copied ? 'Copied!' : 'Copy Link'}
                            </button>
                        </div>

                        <div className="bg-blue-50 border border-blue-100 rounded-lg p-3">
                            <p className="text-xs text-blue-700">
                                The patient will see a simple mobile-friendly page with Yes/No questions about their eligibility criteria.
                                Once submitted, the trial eligibility will be recalculated automatically.
                            </p>
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
}
