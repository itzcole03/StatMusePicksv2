interface StatsSectionProps {
  totalProjections: number;
  totalPlayers: number;
  totalLeagues: number;
}

export default function StatsSection({
  totalProjections,
  totalPlayers,
  totalLeagues,
}: StatsSectionProps) {
  return (
    <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
      <div className="bg-gradient-to-br from-blue-500 to-blue-600 rounded-xl p-6 text-white shadow-lg">
        <div className="text-sm opacity-90 mb-1">Total Projections</div>
        <div className="text-3xl font-bold">{totalProjections}</div>
      </div>
      <div className="bg-gradient-to-br from-purple-500 to-purple-600 rounded-xl p-6 text-white shadow-lg">
        <div className="text-sm opacity-90 mb-1">Players</div>
        <div className="text-3xl font-bold">{totalPlayers}</div>
      </div>
      <div className="bg-gradient-to-br from-pink-500 to-pink-600 rounded-xl p-6 text-white shadow-lg">
        <div className="text-sm opacity-90 mb-1">Leagues</div>
        <div className="text-3xl font-bold">{totalLeagues}</div>
      </div>
    </div>
  );
}
