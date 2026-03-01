import { useState, useEffect, useRef } from 'react';
import { FlaskConical, CheckCircle, XCircle, HelpCircle, Phone, Mail, MapPin, ExternalLink, RefreshCw, AlertCircle, Database, Search, ClipboardCheck, User, Stethoscope, X, Loader2 } from 'lucide-react';
import { usePatient } from '../../contexts/PatientContext';
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

    // Patient = purple-indigo tones, Clinician = violet-purple tones
    const colors = isPatient
        ? { border: '#c7d2fe', headerBg: '#eef2ff', headerText: '#3730a3', accent: '#4f46e5', light: '#e0e7ff' }
        : { border: '#ddd6fe', headerBg: '#f5f3ff', headerText: '#5b21b6', accent: '#7c3aed', light: '#ede9fe' };

    return (
        <div style={{ position: 'fixed', inset: 0, zIndex: 50, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
            <div style={{ position: 'absolute', inset: 0, backgroundColor: 'rgba(0,0,0,0.2)' }} onClick={onClose} />
            <div style={{
                position: 'relative', backgroundColor: '#fff', borderRadius: 10, width: 720, maxHeight: '80vh',
                display: 'flex', flexDirection: 'column', border: `1.5px solid ${colors.border}`,
                boxShadow: '0 8px 30px rgba(0,0,0,0.12)',
            }}>
                {/* Header */}
                <div style={{
                    padding: '10px 14px', display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                    backgroundColor: colors.headerBg, borderBottom: `1px solid ${colors.border}`,
                    borderRadius: '10px 10px 0 0',
                }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                        <ClipboardCheck style={{ width: 14, height: 14, color: colors.accent }} />
                        <span style={{ fontSize: 12, fontWeight: 600, color: colors.headerText }}>
                            {isPatient ? 'Patient Review' : 'Clinician Review'}
                        </span>
                        <span style={{ fontSize: 10, color: '#9ca3af' }}>{trialId}</span>
                    </div>
                    <button onClick={onClose} style={{ background: 'none', border: 'none', cursor: 'pointer', color: '#9ca3af', padding: 2 }}>
                        <X style={{ width: 14, height: 14 }} />
                    </button>
                </div>

                {/* Checklist */}
                <div style={{ flex: 1, overflowY: 'auto', padding: '8px 14px' }}>
                    {criteria.length === 0 ? (
                        <p style={{ textAlign: 'center', fontSize: 11, color: '#9ca3af', padding: '20px 0' }}>All items reviewed</p>
                    ) : (
                        criteria.map((criterion, idx) => {
                            const key = `${criterion.criterion_type}-${criterion.criterion_number}`;
                            const resolved = resolutions.get(key);

                            return (
                                <div key={idx} style={{
                                    display: 'flex', alignItems: 'flex-start', gap: 8, padding: '6px 0',
                                    borderBottom: idx < criteria.length - 1 ? '1px solid #f3f4f6' : 'none',
                                }}>
                                    <p style={{ flex: 1, fontSize: 11, color: '#374151', lineHeight: 1.4, margin: 0, paddingTop: 2 }}>
                                        {criterion.criterion_text}
                                    </p>
                                    <div style={{ display: 'flex', gap: 3, flexShrink: 0 }}>
                                        <button
                                            onClick={() => toggle(criterion.criterion_type, criterion.criterion_number, true)}
                                            style={{
                                                padding: '2px 7px', borderRadius: 4, fontSize: 10, fontWeight: 600, cursor: 'pointer',
                                                border: 'none', transition: 'all 0.15s',
                                                backgroundColor: resolved === true ? '#059669' : '#f3f4f6',
                                                color: resolved === true ? '#fff' : '#9ca3af',
                                            }}
                                        >Yes</button>
                                        <button
                                            onClick={() => toggle(criterion.criterion_type, criterion.criterion_number, false)}
                                            style={{
                                                padding: '2px 7px', borderRadius: 4, fontSize: 10, fontWeight: 600, cursor: 'pointer',
                                                border: 'none', transition: 'all 0.15s',
                                                backgroundColor: resolved === false ? '#dc2626' : '#f3f4f6',
                                                color: resolved === false ? '#fff' : '#9ca3af',
                                            }}
                                        >No</button>
                                    </div>
                                </div>
                            );
                        })
                    )}
                </div>

                {/* Footer */}
                <div style={{
                    padding: '8px 14px', display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                    backgroundColor: colors.headerBg, borderTop: `1px solid ${colors.border}`,
                    borderRadius: '0 0 10px 10px',
                }}>
                    <span style={{ fontSize: 10, color: '#9ca3af' }}>{resolutions.size}/{criteria.length}</span>
                    <button
                        onClick={handleSave}
                        disabled={resolutions.size === 0 || saving}
                        style={{
                            padding: '4px 12px', fontSize: 11, fontWeight: 600, color: '#fff', borderRadius: 5,
                            backgroundColor: (resolutions.size === 0 || saving) ? '#d1d5db' : colors.accent,
                            border: 'none', cursor: (resolutions.size === 0 || saving) ? 'not-allowed' : 'pointer',
                            display: 'flex', alignItems: 'center', gap: 4,
                        }}
                    >
                        {saving && <Loader2 style={{ width: 10, height: 10 }} className="animate-spin" />}
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
    const colors = { border: '#fde68a', headerBg: '#fffbeb', headerText: '#92400e', accent: '#d97706', light: '#fef3c7' };

    return (
        <div style={{ position: 'fixed', inset: 0, zIndex: 50, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
            <div style={{ position: 'absolute', inset: 0, backgroundColor: 'rgba(0,0,0,0.2)' }} onClick={onClose} />
            <div style={{
                position: 'relative', backgroundColor: '#fff', borderRadius: 10, width: 840, maxHeight: '80vh',
                display: 'flex', flexDirection: 'column', border: `1.5px solid ${colors.border}`,
                boxShadow: '0 8px 30px rgba(0,0,0,0.12)',
            }}>
                {/* Header */}
                <div style={{
                    padding: '10px 14px', display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                    backgroundColor: colors.headerBg, borderBottom: `1px solid ${colors.border}`,
                    borderRadius: '10px 10px 0 0',
                }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                        <HelpCircle style={{ width: 14, height: 14, color: colors.accent }} />
                        <span style={{ fontSize: 12, fontWeight: 600, color: colors.headerText }}>
                            Needs Testing
                        </span>
                        <span style={{ fontSize: 10, color: '#9ca3af' }}>{trialId}</span>
                    </div>
                    <button onClick={onClose} style={{ background: 'none', border: 'none', cursor: 'pointer', color: '#9ca3af', padding: 2 }}>
                        <X style={{ width: 14, height: 14 }} />
                    </button>
                </div>

                {/* Criteria + Suggested Tests */}
                <div style={{ flex: 1, overflowY: 'auto', padding: '8px 14px' }}>
                    {criteria.length === 0 ? (
                        <p style={{ textAlign: 'center', fontSize: 11, color: '#9ca3af', padding: '20px 0' }}>No testing criteria</p>
                    ) : (
                        criteria.map((criterion, idx) => (
                            <div key={idx} style={{
                                display: 'flex', alignItems: 'flex-start', gap: 10, padding: '6px 0',
                                borderBottom: idx < criteria.length - 1 ? '1px solid #f3f4f6' : 'none',
                            }}>
                                <p style={{ flex: 1, fontSize: 11, color: '#374151', lineHeight: 1.4, margin: 0, paddingTop: 2 }}>
                                    {criterion.criterion_text}
                                </p>
                                <span style={{
                                    flexShrink: 0, fontSize: 10, fontWeight: 600, color: colors.accent,
                                    backgroundColor: colors.light, padding: '2px 8px', borderRadius: 4, whiteSpace: 'nowrap',
                                }}>
                                    {(criterion as any).suggested_test || 'Clinical Assessment'}
                                </span>
                            </div>
                        ))
                    )}
                </div>

                {/* Footer */}
                <div style={{
                    padding: '8px 14px', display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                    backgroundColor: colors.headerBg, borderTop: `1px solid ${colors.border}`,
                    borderRadius: '0 0 10px 10px',
                }}>
                    <span style={{ fontSize: 10, color: '#9ca3af' }}>{criteria.length} criteria need testing</span>
                    <button
                        onClick={onClose}
                        style={{
                            padding: '4px 12px', fontSize: 11, fontWeight: 600, color: '#fff', borderRadius: 5,
                            backgroundColor: colors.accent, border: 'none', cursor: 'pointer',
                        }}
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

    // Search/filter state
    const [filterText, setFilterText] = useState('');

    // ── Data fetching ─────────────────────────────────────────────────
    const fetchCachedTrials = async () => {
        if (!currentPatient?.mrn) return false;

        try {
            const response = await apiService.getCachedEligibleTrialsForPatient(currentPatient.mrn);
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
                            inclusion: { met: inclusionMet, not_met: inclusionNotMet, unknown: inclusionUnknown, consent_needed: inclusionConsent, total: inclusion.length },
                            exclusion: { clear: exclusionClear, violated: exclusionViolated, unknown: exclusionUnknown, consent_needed: exclusionConsent, total: exclusion.length }
                        },
                        criteria_results: { inclusion, exclusion },
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

        if (useCached && !forceRealTime) {
            const hasCached = await fetchCachedTrials();
            if (hasCached) { setLoading(false); return; }
        }

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
        if (currentPatient?.mrn) fetchTrials();
    }, [currentPatient?.mrn]);

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

    const getPercentageColor = (pct: number) => {
        if (pct >= 80) return 'text-emerald-600';
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
                currentPatient.mrn, reviewModal.trialNctId, payloads
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
            const response = await apiService.refreshTrialEligibility(currentPatient.mrn, nctId);
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
                    <thead className={type === 'inclusion' ? 'bg-emerald-50' : 'bg-red-50'}>
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
                                            <div className="bg-green-50 border border-green-200 rounded px-2 py-1.5 max-w-xs">
                                                <div className="inline-flex items-center gap-1 text-[10px] font-semibold text-green-700 uppercase tracking-wide mb-0.5">
                                                    <ClipboardCheck className="w-3 h-3" />
                                                    Patient Can Answer
                                                </div>
                                                <p className="text-xs text-gray-700 leading-snug">
                                                    {criterion.criterion_text || 'Ask the patient directly'}
                                                </p>
                                            </div>
                                        ) : needsReview && reviewType === 'clinician' ? (
                                            <div className="bg-blue-50 border border-blue-200 rounded px-2 py-1.5 max-w-xs">
                                                <div className="inline-flex items-center gap-1 text-[10px] font-semibold text-blue-700 uppercase tracking-wide mb-0.5">
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
                                            <ClipboardCheck className="w-4 h-4 text-green-500 mx-auto" title="Patient Can Answer" />
                                        ) : needsReview && reviewType === 'clinician' ? (
                                            <ClipboardCheck className="w-4 h-4 text-blue-500 mx-auto" title="Clinician Review" />
                                        ) : needsReview && (reviewType === 'testing' || !reviewType) ? (
                                            <FlaskConical className="w-4 h-4 text-purple-500 mx-auto" title="Testing Needed" />
                                        ) : isResolved ? (
                                            type === 'exclusion' ? (
                                                criterion.met === true
                                                    ? <XCircle className="w-4 h-4 text-red-500 mx-auto" title="Excluded" />
                                                    : <CheckCircle className="w-4 h-4 text-emerald-600 mx-auto" title="Clear" />
                                            ) : (
                                                criterion.met === true
                                                    ? <CheckCircle className="w-4 h-4 text-emerald-600 mx-auto" title="Met" />
                                                    : <XCircle className="w-4 h-4 text-red-500 mx-auto" title="Not met" />
                                            )
                                        ) : type === 'exclusion' ? (
                                            criterion.met === false
                                                ? <CheckCircle className="w-4 h-4 text-emerald-600 mx-auto" title="Clear" />
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

            {/* Loading */}
            {loading && (
                <div className="flex flex-col items-center justify-center py-16">
                    <div className="w-16 h-16 border-4 border-violet-200 border-t-violet-600 rounded-full animate-spin mb-4"></div>
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

            {/* Empty */}
            {!loading && !error && trials.length === 0 && (
                <div className="text-center py-12 bg-gray-50 rounded-lg border border-gray-200">
                    <FlaskConical className="w-12 h-12 text-gray-400 mx-auto mb-3" />
                    <p className="text-gray-600 font-medium">No matching clinical trials found</p>
                    <p className="text-gray-400 text-sm mt-1">Try refreshing or check back later</p>
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
                        <div className="bg-gradient-to-r from-violet-50 to-purple-50 border border-violet-200 rounded-lg px-4 py-3 flex-shrink-0">
                            <p className="text-violet-800 font-medium text-sm">
                                {trials.length} trial{trials.length !== 1 ? 's' : ''} analyzed
                            </p>
                        </div>
                        <div className="relative flex-1 max-w-md">
                            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
                            <input
                                type="text"
                                placeholder="Search by NCT ID, title, phase, or eligibility..."
                                value={filterText}
                                onChange={e => setFilterText(e.target.value)}
                                className="w-full pl-9 pr-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-violet-300 focus:border-violet-400"
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
                            <div key={trial.nct_id} ref={el => { if (el) trialRefs.current.set(trial.nct_id, el); }} className={`border-2 rounded-xl overflow-hidden transition-colors relative ${highlightedTrial === trial.nct_id ? 'border-violet-400 ring-2 ring-violet-200' : 'border-gray-200 hover:border-violet-300'}`}>
                                {/* Refreshing overlay */}
                                {refreshingTrials.has(trial.nct_id) && (
                                    <div className="absolute inset-0 bg-white/70 z-10 flex flex-col items-center justify-center rounded-xl">
                                        <Loader2 className="w-8 h-8 text-violet-600 animate-spin mb-2" />
                                        <p className="text-sm text-violet-700 font-medium">Re-analyzing eligibility...</p>
                                        <p className="text-xs text-gray-500 mt-1">This may take 1-3 minutes</p>
                                    </div>
                                )}
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
                                                className="p-2 rounded-lg text-gray-300 hover:text-violet-600 hover:bg-violet-50 transition-colors disabled:opacity-50"
                                                title="Re-run eligibility analysis"
                                            >
                                                <RefreshCw className={`w-4 h-4 ${refreshingTrials.has(trial.nct_id) ? 'animate-spin' : ''}`} />
                                            </button>
                                        </div>
                                    </div>

                                    {/* Criteria Summary Bar */}
                                    <div className="mt-4 flex items-center gap-3 text-sm flex-wrap">
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

                                        {/* Patient Review Needed */}
                                        {rc.patient > 0 && (
                                            <button
                                                onClick={(e) => { e.stopPropagation(); setReviewModal({ type: 'patient', trialNctId: trial.nct_id }); }}
                                                className="flex items-center gap-1 text-violet-600 hover:text-violet-800 hover:underline cursor-pointer"
                                            >
                                                <ClipboardCheck className="w-3.5 h-3.5" />
                                                <span>{rc.patient} Patient Review Needed</span>
                                            </button>
                                        )}

                                        {/* Clinician Review Needed */}
                                        {rc.clinician > 0 && (
                                            <button
                                                onClick={(e) => { e.stopPropagation(); setReviewModal({ type: 'clinician', trialNctId: trial.nct_id }); }}
                                                className="flex items-center gap-1 text-violet-600 hover:text-violet-800 hover:underline cursor-pointer"
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
                                                    <CheckCircle className="w-5 h-5 text-emerald-600" />
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
        </div>
    );
}
