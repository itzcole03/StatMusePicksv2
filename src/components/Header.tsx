import { Settings } from 'lucide-react';

interface HeaderProps {
  onOpenSettings: () => void;
}

export default function Header({ onOpenSettings }: HeaderProps) {
  return (
    <div className="mb-8 flex justify-between items-start">
      <div>
        <h1 className="text-4xl font-bold mb-2 bg-gradient-to-r from-[#5D5CDE] to-purple-600 bg-clip-text text-transparent">
          PrizePicks Analyzer
        </h1>
        <p className="text-gray-600 dark:text-gray-400 text-lg">
          AI-powered analysis using real-time data to find the best over/under picks
        </p>
      </div>
      <button
        onClick={onOpenSettings}
        className="px-4 py-2 bg-gray-200 dark:bg-gray-700 hover:bg-gray-300 dark:hover:bg-gray-600 text-gray-800 dark:text-gray-200 font-medium rounded-lg transition-colors flex items-center gap-2"
      >
        <Settings className="w-5 h-5" />
        Settings
      </button>
    </div>
  );
}
