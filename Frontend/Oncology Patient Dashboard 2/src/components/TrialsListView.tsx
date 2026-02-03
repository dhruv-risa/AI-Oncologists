import { useState, useEffect } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from './ui/card';
import { Button } from './ui/button';
import { Input } from './ui/input';
import { Badge } from './ui/badge';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from './ui/select';
import { apiService, CachedTrial, SyncStatusResponse } from '../services/api';
import { Search, RefreshCw, ChevronLeft, ChevronRight, Beaker, Users, Building2, Calendar, AlertCircle } from 'lucide-react';

interface TrialsListViewProps {
  onSelectTrial: (nctId: string) => void;
  onBackToPatients: () => void;
}

export function TrialsListView({ onSelectTrial, onBackToPatients }: TrialsListViewProps) {
  const [trials, setTrials] = useState<CachedTrial[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [statusFilter, setStatusFilter] = useState<string>('all');
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [total, setTotal] = useState(0);
  const [syncStatus, setSyncStatus] = useState<SyncStatusResponse | null>(null);
  const [syncing, setSyncing] = useState(false);

  const limit = 20;

  const fetchTrials = async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await apiService.listTrials({
        status: statusFilter === 'all' ? undefined : statusFilter,
        page,
        limit,
      });
      setTrials(response.trials);
      setTotalPages(response.total_pages);
      setTotal(response.total);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to fetch trials');
    } finally {
      setLoading(false);
    }
  };

  const fetchSyncStatus = async () => {
    try {
      const status = await apiService.getSyncStatus();
      setSyncStatus(status);
    } catch (err) {
      console.error('Failed to fetch sync status:', err);
    }
  };

  useEffect(() => {
    fetchTrials();
    fetchSyncStatus();
  }, [page, statusFilter]);

  const handleSync = async () => {
    setSyncing(true);
    try {
      await apiService.fullSync({ background: false, maxTrialsPerQuery: 30, limitTrials: 50 });
      await fetchTrials();
      await fetchSyncStatus();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Sync failed');
    } finally {
      setSyncing(false);
    }
  };

  const filteredTrials = trials.filter(trial =>
    trial.title.toLowerCase().includes(searchQuery.toLowerCase()) ||
    trial.nct_id.toLowerCase().includes(searchQuery.toLowerCase()) ||
    trial.conditions?.some(c => c.toLowerCase().includes(searchQuery.toLowerCase()))
  );

  const getPhaseColor = (phase: string) => {
    if (phase.includes('1')) return 'bg-yellow-100 text-yellow-800';
    if (phase.includes('2')) return 'bg-blue-100 text-blue-800';
    if (phase.includes('3')) return 'bg-green-100 text-green-800';
    if (phase.includes('4')) return 'bg-purple-100 text-purple-800';
    return 'bg-gray-100 text-gray-800';
  };

  const getStatusColor = (status: string) => {
    if (status === 'RECRUITING') return 'bg-green-100 text-green-800';
    if (status === 'ACTIVE_NOT_RECRUITING') return 'bg-yellow-100 text-yellow-800';
    if (status === 'COMPLETED') return 'bg-gray-100 text-gray-800';
    return 'bg-gray-100 text-gray-800';
  };

  return (
    <div className="min-h-screen bg-gray-50 p-6 overflow-x-hidden">
      <div className="max-w-7xl mx-auto overflow-hidden">
        {/* Header */}
        <div className="flex items-center justify-between mb-6">
          <div className="flex items-center gap-4">
            <Button variant="ghost" onClick={onBackToPatients} className="p-2">
              <ChevronLeft className="h-5 w-5" />
            </Button>
            <div>
              <h1 className="text-2xl font-bold text-gray-900">Clinical Trials</h1>
              <p className="text-sm text-gray-500">
                {total} trials available | Find eligible patients for each trial
              </p>
            </div>
          </div>
          <Button
            onClick={handleSync}
            disabled={syncing}
            className="flex items-center gap-2"
          >
            <RefreshCw className={`h-4 w-4 ${syncing ? 'animate-spin' : ''}`} />
            {syncing ? 'Syncing...' : 'Sync Trials'}
          </Button>
        </div>

        {/* Sync Status */}
        {syncStatus && (
          <Card className="mb-6 bg-blue-50 border-blue-200">
            <CardContent className="py-4">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-6">
                  <div className="flex items-center gap-2">
                    <Beaker className="h-4 w-4 text-blue-600" />
                    <span className="text-sm font-medium">{syncStatus.trials_in_cache} Trials Available</span>
                  </div>
                  {syncStatus.last_trials_sync && (
                    <div className="text-sm text-gray-600">
                      Last sync: {new Date(syncStatus.last_trials_sync.sync_date).toLocaleString()}
                    </div>
                  )}
                </div>
                {!syncStatus.trials_in_cache && (
                  <div className="flex items-center gap-2 text-amber-600">
                    <AlertCircle className="h-4 w-4" />
                    <span className="text-sm">No trials available. Click "Sync Trials" to fetch from ClinicalTrials.gov</span>
                  </div>
                )}
              </div>
            </CardContent>
          </Card>
        )}

        {/* Filters */}
        <div className="flex gap-4 mb-6">
          <div className="relative flex-1 max-w-md">
            <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-gray-400" />
            <Input
              placeholder="Search trials by title, NCT ID, or condition..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="pl-10"
            />
          </div>
          <Select value={statusFilter} onValueChange={setStatusFilter}>
            <SelectTrigger className="w-[200px]">
              <SelectValue placeholder="Filter by status" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All Statuses</SelectItem>
              <SelectItem value="RECRUITING">Recruiting</SelectItem>
              <SelectItem value="ACTIVE_NOT_RECRUITING">Active, Not Recruiting</SelectItem>
              <SelectItem value="COMPLETED">Completed</SelectItem>
            </SelectContent>
          </Select>
        </div>

        {/* Error State */}
        {error && (
          <Card className="mb-6 border-red-200 bg-red-50">
            <CardContent className="py-4">
              <p className="text-red-600">{error}</p>
            </CardContent>
          </Card>
        )}

        {/* Trials Grid */}
        {loading ? (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {[1, 2, 3, 4].map((i) => (
              <Card key={i} className="animate-pulse">
                <CardHeader>
                  <div className="h-4 bg-gray-200 rounded w-1/4 mb-2"></div>
                  <div className="h-6 bg-gray-200 rounded w-3/4"></div>
                </CardHeader>
                <CardContent>
                  <div className="h-4 bg-gray-200 rounded w-full mb-2"></div>
                  <div className="h-4 bg-gray-200 rounded w-2/3"></div>
                </CardContent>
              </Card>
            ))}
          </div>
        ) : filteredTrials.length === 0 ? (
          <Card className="text-center py-12">
            <CardContent>
              <Beaker className="h-12 w-12 mx-auto text-gray-400 mb-4" />
              <h3 className="text-lg font-medium text-gray-900 mb-2">No Trials Found</h3>
              <p className="text-gray-500 mb-4">
                {total === 0
                  ? 'No trials available. Click "Sync Trials" to fetch from ClinicalTrials.gov.'
                  : 'No trials match your search criteria.'}
              </p>
              {total === 0 && (
                <Button onClick={handleSync} disabled={syncing}>
                  <RefreshCw className={`h-4 w-4 mr-2 ${syncing ? 'animate-spin' : ''}`} />
                  Sync Trials Now
                </Button>
              )}
            </CardContent>
          </Card>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {filteredTrials.map((trial) => (
              <Card
                key={trial.nct_id}
                className="hover:shadow-lg transition-shadow cursor-pointer"
                onClick={() => onSelectTrial(trial.nct_id)}
              >
                <CardHeader className="pb-2">
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-sm font-mono text-blue-600">{trial.nct_id}</span>
                    <div className="flex gap-2">
                      <Badge className={getPhaseColor(trial.phase || 'N/A')}>
                        {trial.phase || 'N/A'}
                      </Badge>
                      <Badge className={getStatusColor(trial.status)}>
                        {trial.status?.replace(/_/g, ' ') || 'Unknown'}
                      </Badge>
                    </div>
                  </div>
                  <CardTitle className="text-base line-clamp-2">{trial.title}</CardTitle>
                </CardHeader>
                <CardContent>
                  <p className="text-sm text-gray-600 line-clamp-2 mb-4">
                    {trial.brief_summary || 'No summary available'}
                  </p>

                  {/* Eligible Patients Badge */}
                  {(trial as any).eligible_patient_count > 0 && (
                    <div className="mb-3 inline-flex items-center gap-2 px-3 py-1.5 bg-green-100 text-green-800 rounded-full text-sm font-medium">
                      <Users className="h-4 w-4" />
                      {(trial as any).eligible_patient_count} eligible patient{(trial as any).eligible_patient_count !== 1 ? 's' : ''}
                    </div>
                  )}

                  <div className="flex items-center gap-4 text-sm text-gray-500">
                    {trial.sponsor && (
                      <div className="flex items-center gap-1">
                        <Building2 className="h-4 w-4" />
                        <span className="truncate max-w-[150px]">{trial.sponsor}</span>
                      </div>
                    )}
                    {trial.enrollment > 0 && (
                      <div className="flex items-center gap-1">
                        <Users className="h-4 w-4" />
                        <span>{trial.enrollment} target</span>
                      </div>
                    )}
                    {trial.start_date && (
                      <div className="flex items-center gap-1">
                        <Calendar className="h-4 w-4" />
                        <span>{trial.start_date}</span>
                      </div>
                    )}
                  </div>
                  {trial.conditions && trial.conditions.length > 0 && (
                    <div className="mt-3 flex flex-wrap gap-1">
                      {trial.conditions.slice(0, 3).map((condition, idx) => (
                        <Badge key={idx} variant="outline" className="text-xs">
                          {condition}
                        </Badge>
                      ))}
                      {trial.conditions.length > 3 && (
                        <Badge variant="outline" className="text-xs">
                          +{trial.conditions.length - 3} more
                        </Badge>
                      )}
                    </div>
                  )}
                </CardContent>
              </Card>
            ))}
          </div>
        )}

        {/* Pagination */}
        {totalPages > 1 && (
          <div className="flex items-center justify-center gap-4 mt-6">
            <Button
              variant="outline"
              onClick={() => setPage((p) => Math.max(1, p - 1))}
              disabled={page === 1}
            >
              <ChevronLeft className="h-4 w-4" />
              Previous
            </Button>
            <span className="text-sm text-gray-600">
              Page {page} of {totalPages}
            </span>
            <Button
              variant="outline"
              onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
              disabled={page === totalPages}
            >
              Next
              <ChevronRight className="h-4 w-4" />
            </Button>
          </div>
        )}
      </div>
    </div>
  );
}
