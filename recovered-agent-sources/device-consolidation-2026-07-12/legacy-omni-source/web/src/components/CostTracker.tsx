import { useEffect, useState } from 'react';
import type { FC } from 'react';
import { DollarSign, Zap, TrendingUp, Activity } from 'lucide-react';

// Type definitions for the API response
interface DailyUsage {
  date: string;
  input_tokens: number;
  output_tokens: number;
  cost: number;
}

interface AnalyticsData {
  daily: DailyUsage[];
  totals: {
    total_sessions: number;
    total_input: number;
    total_output: number;
    total_estimated_cost: number;
  };
}

const CostTracker: FC = () => {
  const [data, setData] = useState<AnalyticsData | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  const fetchData = async () => {
    try {
      const token = (window as unknown as Record<string, unknown>).__HERMES_SESSION_TOKEN__ as string;
      if (!token) {
        throw new Error('Authentication token not found.');
      }

      const response = await fetch('/api/analytics/usage', {
        headers: {
          Authorization: `Bearer ${token}`,
        },
      });

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      const result: AnalyticsData = await response.json();
      setData(result);
    } catch (e) {
      if (e instanceof Error) {
        setError(e.message);
      } else {
        setError('An unknown error occurred.');
      }
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
    const intervalId = setInterval(fetchData, 60000); // Refresh every 60 seconds

    return () => clearInterval(intervalId);
  }, []);

  if (loading) {
    return <div className="p-4 bg-zinc-950 text-white/50">Loading...</div>;
  }

  if (error) {
    return <div className="p-4 bg-zinc-950 text-red-500">Error: {error}</div>;
  }

  if (!data || data.totals.total_sessions === 0) {
    return (
      <div className="p-4 bg-zinc-950 text-white/50 rounded-lg border border-white/5">
        No data yet.
      </div>
    );
  }

  const { totals, daily } = data;
  const totalTokens = totals.total_input + totals.total_output;

  const maxDailyTokens = Math.max(...daily.map(d => d.input_tokens + d.output_tokens), 1);

  return (
    <div className="p-4 bg-zinc-950 text-white rounded-lg border border-white/5 font-sans">
      <div className="flex justify-between items-center mb-4">
        <h3 className="text-lg font-semibold text-cyan-400">Usage Analytics</h3>
        <Activity className="w-5 h-5 text-cyan-400" />
      </div>

      <div className="grid grid-cols-2 gap-4 text-sm">
        <div className="flex items-center space-x-2">
          <DollarSign className="w-4 h-4 text-white/50" />
          <div>
            <div className="text-white/70">Cost</div>
            <div className="font-semibold text-lg">${totals.total_estimated_cost.toFixed(4)}</div>
          </div>
        </div>

        <div className="flex items-center space-x-2">
          <Zap className="w-4 h-4 text-white/50" />
          <div>
            <div className="text-white/70">Tokens</div>
            <div className="font-semibold text-lg">{totalTokens.toLocaleString()}</div>
          </div>
        </div>
        
        <div className="flex items-center space-x-2 col-span-2">
          <TrendingUp className="w-4 h-4 text-white/50" />
          <div>
            <div className="text-white/70">Sessions</div>
            <div className="font-semibold text-lg">{totals.total_sessions.toLocaleString()}</div>
          </div>
        </div>
      </div>

      <div className="mt-4 pt-4 border-t border-white/5">
        <div className="text-sm text-white/70 mb-2">Daily Activity</div>
        {daily.length > 0 ? (
          <div className="flex items-end h-16 space-x-1">
            {daily.slice(-30).map((day, index) => (
              <div
                key={index}
                className="flex-1 bg-cyan-400/50 hover:bg-cyan-400 rounded-t-sm"
                style={{ height: `${((day.input_tokens + day.output_tokens) / maxDailyTokens) * 100}%` }}
                title={`Date: ${day.date}\nTokens: ${(day.input_tokens + day.output_tokens).toLocaleString()}\nCost: $${day.cost.toFixed(4)}`}
              />
            ))}
          </div>
        ) : (
           <div className="text-center text-sm text-white/30">No daily data available.</div>
        )}
      </div>
    </div>
  );
};

export default CostTracker;
