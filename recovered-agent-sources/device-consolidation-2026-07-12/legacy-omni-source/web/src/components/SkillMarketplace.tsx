import { useState, useEffect, useMemo } from 'react';
import type { FC } from 'react';
import { Search, Package, Check, Filter, AlertTriangle } from 'lucide-react';

type Skill = {
  name: string;
  description?: string | null;
  enabled: boolean;
  category?: string | null;
};

const SkillCard: FC<{ skill: Skill }> = ({ skill }) => (
  <div
    className="bg-zinc-900 rounded-xl p-4 flex flex-col justify-between h-full cursor-pointer border border-transparent hover:border-cyan-400 transition-colors duration-200 group"
    onClick={() => (window.location.href = '/skills')}
  >
    <div>
      <div className="flex justify-between items-start">
        <h3 className="font-bold text-lg text-zinc-100 group-hover:text-cyan-400">{skill.name}</h3>
        <div
          className={`w-3 h-3 rounded-full mt-1 ${
            skill.enabled ? 'bg-green-500' : 'bg-zinc-600'
          }`}
          title={skill.enabled ? 'Enabled' : 'Disabled'}
        />
      </div>
      <p className="text-zinc-400 text-sm mt-2 line-clamp-2">
        {skill.description || 'No description available.'}
      </p>
    </div>
    {skill.category && (
      <div className="mt-4">
        <span className="inline-block bg-zinc-800 text-cyan-400 text-xs font-medium px-2 py-1 rounded-full">
          {skill.category}
        </span>
      </div>
    )}
  </div>
);

const LoadingSkeleton: FC = () => (
  <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
    {Array.from({ length: 12 }).map((_, i) => (
      <div key={i} className="bg-zinc-900 rounded-xl p-4 animate-pulse h-36">
        <div className="h-4 bg-zinc-800 rounded w-3/4 mb-4"></div>
        <div className="h-3 bg-zinc-800 rounded w-full mb-2"></div>
        <div className="h-3 bg-zinc-800 rounded w-5/6"></div>
        <div className="h-4 bg-zinc-800 rounded w-1/4 mt-4"></div>
      </div>
    ))}
  </div>
);

const ErrorDisplay: FC<{ onRetry: () => void }> = ({ onRetry }) => (
    <div className="bg-zinc-900 border border-red-500/30 rounded-xl p-6 text-center text-zinc-300">
        <AlertTriangle className="mx-auto h-12 w-12 text-red-500" />
        <h3 className="mt-4 text-lg font-semibold text-white">Failed to load skills</h3>
        <p className="mt-2 text-sm text-zinc-400">
            There was a problem fetching the skill data. Please try again.
        </p>
        <div className="mt-6">
            <button
                onClick={onRetry}
                className="inline-flex items-center px-4 py-2 border border-transparent text-sm font-medium rounded-md shadow-sm text-white bg-cyan-600 hover:bg-cyan-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-offset-zinc-950 focus:ring-cyan-500"
            >
                Retry
            </button>
        </div>
    </div>
);


const SkillMarketplace: FC = () => {
  const [skills, setSkills] = useState<Skill[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);
  const [searchTerm, setSearchTerm] = useState('');
  const [selectedCategory, setSelectedCategory] = useState<string | null>(null);

  const fetchSkills = async () => {
    setLoading(true);
    setError(null);
    try {
      const token = (window as any).__HERMES_SESSION_TOKEN__ as string;
      const response = await fetch('/api/skills', {
        headers: {
          Authorization: `Bearer ${token}`,
        },
      });
      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }
      const data = await response.json();
      setSkills(data);
    } catch (e) {
      setError(e as Error);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchSkills();
  }, []);

  const categories = useMemo(() => {
    const uniqueCategories = new Set(
      skills.map(skill => skill.category).filter(Boolean) as string[]
    );
    return ['All', ...Array.from(uniqueCategories).sort()];
  }, [skills]);

  const filteredSkills = useMemo(() => {
    return skills.filter(skill => {
      const matchesCategory =
        !selectedCategory || selectedCategory === 'All' || skill.category === selectedCategory;
      const matchesSearch =
        searchTerm.trim() === '' ||
        skill.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
        (skill.description &&
          skill.description.toLowerCase().includes(searchTerm.toLowerCase()));
      return matchesCategory && matchesSearch;
    });
  }, [skills, searchTerm, selectedCategory]);

  const stats = useMemo(() => ({
    total: skills.length,
    enabled: skills.filter(s => s.enabled).length,
    categories: categories.length - 1, // Exclude 'All'
  }), [skills, categories]);


  return (
    <div className="bg-zinc-950 text-white min-h-screen p-4 sm:p-6 lg:p-8">
      <div className="max-w-7xl mx-auto">
        <header className="mb-8">
          <h1 className="text-3xl font-bold tracking-tight text-white sm:text-4xl">Skill Marketplace</h1>
          <p className="mt-2 text-lg text-zinc-400">Browse and manage available agent skills.</p>
          <div className="mt-6 grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-4 text-center">
            <div className="bg-zinc-900 p-4 rounded-xl">
              <Package className="mx-auto h-6 w-6 text-cyan-400" />
              <p className="mt-2 text-2xl font-bold">{loading ? '...' : stats.total}</p>
              <p className="text-sm text-zinc-400">Total Skills</p>
            </div>
            <div className="bg-zinc-900 p-4 rounded-xl">
              <Check className="mx-auto h-6 w-6 text-green-500" />
              <p className="mt-2 text-2xl font-bold">{loading ? '...' : stats.enabled}</p>
              <p className="text-sm text-zinc-400">Enabled</p>
            </div>
             <div className="bg-zinc-900 p-4 rounded-xl">
              <Filter className="mx-auto h-6 w-6 text-cyan-400" />
              <p className="mt-2 text-2xl font-bold">{loading ? '...' : stats.categories}</p>
              <p className="text-sm text-zinc-400">Categories</p>
            </div>
          </div>
        </header>

        <div className="mb-6 sticky top-0 bg-zinc-950 py-4 z-10">
          <div className="relative">
            <input
              type="text"
              placeholder="Search skills by name or description..."
              value={searchTerm}
              onChange={e => setSearchTerm(e.target.value)}
              className="w-full bg-zinc-900 border border-zinc-700 rounded-lg pl-10 pr-4 py-2 text-white focus:ring-cyan-500 focus:border-cyan-500"
            />
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-5 w-5 text-zinc-400" />
          </div>
          <div className="mt-4 flex flex-wrap gap-2">
            {categories.map(category => (
              <button
                key={category}
                onClick={() => setSelectedCategory(category)}
                className={`px-3 py-1 text-sm font-medium rounded-full transition-colors ${
                  selectedCategory === category
                    ? 'bg-cyan-400 text-zinc-950'
                    : 'bg-zinc-800 text-zinc-300 hover:bg-zinc-700'
                }`}
              >
                {category}
              </button>
            ))}
          </div>
        </div>

        <main>
          {loading ? (
            <LoadingSkeleton />
          ) : error ? (
            <ErrorDisplay onRetry={fetchSkills} />
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
              {filteredSkills.map(skill => (
                <SkillCard key={skill.name} skill={skill} />
              ))}
            </div>
          )}
           { !loading && !error && filteredSkills.length === 0 && (
             <div className="text-center py-16">
                 <h3 className="text-lg font-semibold text-white">No skills found</h3>
                 <p className="mt-1 text-sm text-zinc-400">
                     Try adjusting your search or filter criteria.
                 </p>
             </div>
           )}
        </main>
      </div>
    </div>
  );
};

export default SkillMarketplace;
