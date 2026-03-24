import { useState, useEffect } from 'react';
import { apiService, PatientReviewData, CriterionResolutionPayload } from '../services/api';

interface PatientReviewPageProps {
    token: string;
}

type PageState = 'loading' | 'ready' | 'submitting' | 'completed' | 'already_completed' | 'error';

export default function PatientReviewPage({ token }: PatientReviewPageProps) {
    const [pageState, setPageState] = useState<PageState>('loading');
    const [reviewData, setReviewData] = useState<PatientReviewData | null>(null);
    const [responses, setResponses] = useState<Map<string, boolean>>(new Map());
    const [errorMessage, setErrorMessage] = useState('');

    useEffect(() => {
        loadReviewData();
    }, [token]);

    const loadReviewData = async () => {
        try {
            const data = await apiService.getPatientReview(token);
            setReviewData(data);
            if (data.status === 'completed') {
                setPageState('already_completed');
            } else {
                setPageState('ready');
            }
        } catch (err: any) {
            setErrorMessage(err?.message || 'This review link is invalid or has expired.');
            setPageState('error');
        }
    };

    const toggleResponse = (criterionKey: string, value: boolean) => {
        setResponses(prev => {
            const next = new Map(prev);
            if (next.get(criterionKey) === value) {
                next.delete(criterionKey);
            } else {
                next.set(criterionKey, value);
            }
            return next;
        });
    };

    const allAnswered = reviewData?.criteria
        ? reviewData.criteria.every(c => responses.has(`${c.criterion_type}-${c.criterion_number}`))
        : false;

    const handleSubmit = async () => {
        if (!reviewData?.criteria || !allAnswered) return;
        setPageState('submitting');
        try {
            const resolutions: CriterionResolutionPayload[] = reviewData.criteria.map(c => ({
                criterion_number: c.criterion_number,
                criterion_type: c.criterion_type,
                resolved_met: responses.get(`${c.criterion_type}-${c.criterion_number}`) ?? false,
                resolved_by: 'patient',
            }));
            await apiService.submitPatientReview(token, resolutions);
            setPageState('completed');
        } catch (err: any) {
            setErrorMessage(err?.message || 'Failed to submit responses. Please try again.');
            setPageState('ready');
        }
    };

    // ── Loading State ──
    if (pageState === 'loading') {
        return (
            <div className="min-h-screen bg-gradient-to-br from-blue-50 to-indigo-50 flex items-center justify-center">
                <div className="text-center">
                    <div className="w-12 h-12 border-4 border-blue-200 border-t-blue-600 rounded-full animate-spin mx-auto mb-4" />
                    <p className="text-gray-600">Loading your review...</p>
                </div>
            </div>
        );
    }

    // ── Error State ──
    if (pageState === 'error') {
        return (
            <div className="min-h-screen bg-gradient-to-br from-red-50 to-orange-50 flex items-center justify-center p-4">
                <div className="bg-white rounded-2xl shadow-lg max-w-md w-full p-8 text-center">
                    <div className="w-16 h-16 bg-red-100 rounded-full flex items-center justify-center mx-auto mb-4">
                        <svg className="w-8 h-8 text-red-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                        </svg>
                    </div>
                    <h2 className="text-xl font-semibold text-gray-900 mb-2">Link Not Found</h2>
                    <p className="text-gray-600">{errorMessage}</p>
                </div>
            </div>
        );
    }

    // ── Already Completed State ──
    if (pageState === 'already_completed') {
        return (
            <div className="min-h-screen bg-gradient-to-br from-green-50 to-emerald-50 flex items-center justify-center p-4">
                <div className="bg-white rounded-2xl shadow-lg max-w-md w-full p-8 text-center">
                    <div className="w-16 h-16 bg-green-100 rounded-full flex items-center justify-center mx-auto mb-4">
                        <svg className="w-8 h-8 text-green-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                        </svg>
                    </div>
                    <h2 className="text-xl font-semibold text-gray-900 mb-2">Already Submitted</h2>
                    <p className="text-gray-600">{reviewData?.message || 'You have already submitted your responses. Thank you!'}</p>
                </div>
            </div>
        );
    }

    // ── Completed State (just submitted) ──
    if (pageState === 'completed') {
        return (
            <div className="min-h-screen bg-gradient-to-br from-green-50 to-emerald-50 flex items-center justify-center p-4">
                <div className="bg-white rounded-2xl shadow-lg max-w-md w-full p-8 text-center">
                    <div className="w-16 h-16 bg-green-100 rounded-full flex items-center justify-center mx-auto mb-4">
                        <svg className="w-8 h-8 text-green-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                        </svg>
                    </div>
                    <h2 className="text-xl font-semibold text-gray-900 mb-2">Thank You!</h2>
                    <p className="text-gray-600 mb-4">
                        Your responses have been submitted successfully. Your care team will review the updated eligibility assessment.
                    </p>
                    <p className="text-sm text-gray-400">You can close this page now.</p>
                </div>
            </div>
        );
    }

    // ── Ready State (main form) ──
    const criteria = reviewData?.criteria || [];
    const answeredCount = responses.size;

    return (
        <div className="min-h-screen bg-gradient-to-br from-blue-50 to-indigo-50 py-8 px-4">
            <div className="max-w-2xl mx-auto">
                {/* Header */}
                <div className="bg-white rounded-2xl shadow-lg p-6 mb-6">
                    <div className="flex items-center gap-3 mb-4">
                        <div className="w-10 h-10 bg-blue-600 rounded-xl flex items-center justify-center">
                            <svg className="w-5 h-5 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                            </svg>
                        </div>
                        <div>
                            <h1 className="text-xl font-bold text-gray-900">Clinical Trial Eligibility Review</h1>
                            <p className="text-sm text-gray-500">{reviewData?.trial_title}</p>
                        </div>
                    </div>
                    <div className="bg-blue-50 rounded-xl p-4">
                        <p className="text-sm text-blue-800">
                            {reviewData?.patient_first_name ? (
                                <>Hi <span className="font-semibold">{reviewData.patient_first_name}</span>, your</>
                            ) : (
                                <>Your</>
                            )}{' '}
                            care team is evaluating your eligibility for a clinical trial.
                            Please answer the following questions to help determine if this trial may be right for you.
                        </p>
                    </div>
                </div>

                {/* Questions */}
                <div className="space-y-4 mb-6">
                    {criteria.map((c, idx) => {
                        const key = `${c.criterion_type}-${c.criterion_number}`;
                        const answer = responses.get(key);
                        return (
                            <div key={key} className="bg-white rounded-xl shadow-sm border border-gray-100 p-5">
                                <div className="flex items-start gap-3 mb-3">
                                    <span className="flex-shrink-0 w-7 h-7 rounded-full bg-blue-100 text-blue-700 flex items-center justify-center text-sm font-semibold">
                                        {idx + 1}
                                    </span>
                                    <p className="text-gray-800 text-sm leading-relaxed pt-0.5">{c.criterion_text}</p>
                                </div>
                                <div className="flex gap-3 ml-10">
                                    <button
                                        onClick={() => toggleResponse(key, true)}
                                        className={`flex-1 py-2.5 rounded-lg text-sm font-medium transition-all ${
                                            answer === true
                                                ? 'bg-green-600 text-white shadow-sm'
                                                : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
                                        }`}
                                    >
                                        Yes
                                    </button>
                                    <button
                                        onClick={() => toggleResponse(key, false)}
                                        className={`flex-1 py-2.5 rounded-lg text-sm font-medium transition-all ${
                                            answer === false
                                                ? 'bg-red-500 text-white shadow-sm'
                                                : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
                                        }`}
                                    >
                                        No
                                    </button>
                                </div>
                            </div>
                        );
                    })}
                </div>

                {/* Submit */}
                <div className="bg-white rounded-2xl shadow-lg p-6">
                    <div className="flex items-center justify-between mb-4">
                        <span className="text-sm text-gray-500">
                            {answeredCount}/{criteria.length} questions answered
                        </span>
                        <div className="h-2 flex-1 mx-4 bg-gray-100 rounded-full overflow-hidden">
                            <div
                                className="h-full bg-blue-600 rounded-full transition-all duration-300"
                                style={{ width: `${criteria.length > 0 ? (answeredCount / criteria.length) * 100 : 0}%` }}
                            />
                        </div>
                    </div>
                    <button
                        onClick={handleSubmit}
                        disabled={!allAnswered || pageState === 'submitting'}
                        className={`w-full py-3 rounded-xl text-sm font-semibold transition-all ${
                            allAnswered
                                ? 'bg-blue-600 text-white hover:bg-blue-700 shadow-md'
                                : 'bg-gray-200 text-gray-400 cursor-not-allowed'
                        }`}
                    >
                        {pageState === 'submitting' ? (
                            <span className="flex items-center justify-center gap-2">
                                <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                                Submitting...
                            </span>
                        ) : (
                            'Submit Responses'
                        )}
                    </button>
                    {errorMessage && pageState === 'ready' && (
                        <p className="text-red-500 text-sm text-center mt-3">{errorMessage}</p>
                    )}
                </div>

                {/* Footer */}
                <p className="text-center text-xs text-gray-400 mt-6">
                    RISA OneView Clinical Trial Matching System
                </p>
            </div>
        </div>
    );
}
