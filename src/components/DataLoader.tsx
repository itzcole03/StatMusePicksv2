import { useEffect, useRef, useState } from 'react';
import { Info, TestTube } from 'lucide-react';
import { getSampleData } from '../utils/sampleData';
import { saveBatch, clearDB, countAll, rebuildPlayersIndex } from '../services/indexedDBService';

export default function DataLoader() {
  const [dataInput, setDataInput] = useState('');
  const [status, setStatus] = useState<{ message: string; type: 'error' | 'success' | 'info' } | null>(null);
  const [progress, setProgress] = useState(0);
  const [parsedCount, setParsedCount] = useState(0);
  const workerRef = useRef<Worker | null>(null);

  useEffect(() => {
    return () => {
      if (workerRef.current) {
        workerRef.current.terminate();
        workerRef.current = null;
      }
    };
  }, []);

  const handleLoadSample = () => {
    const sampleData = getSampleData();
    const str = JSON.stringify(sampleData, null, 2);
    setDataInput(str);
    // feed to parser for consistent path
    handleLoadDataWithString(str);
  };

  const handleLoadData = () => {
    if (!dataInput.trim()) {
      setStatus({ message: 'Please paste JSON data or load sample data first.', type: 'error' });
      return;
    }
    handleLoadDataWithString(dataInput);
  };

  const handleLoadDataWithString = (raw: string) => {
    setStatus({ message: 'Parsing and saving data...', type: 'info' });
    setProgress(0);
    setParsedCount(0);

    if (workerRef.current) {
      workerRef.current.terminate();
      workerRef.current = null;
    }

    const worker = new Worker(new URL('../workers/parser.worker.ts', import.meta.url), { type: 'module' });
    workerRef.current = worker;

    worker.onmessage = async (ev) => {
      const msg = ev.data as any;
      if (msg.type === 'chunk') {
        const chunk = msg.chunk as any[];
        try {
          await saveBatch(chunk);
          setParsedCount((p) => p + chunk.length);
          setProgress(msg.progress ?? 0);
        } catch (err) {
          console.error('saveBatch error', err);
          setStatus({ message: 'Error saving data. See console.', type: 'error' });
        }
      } else if (msg.type === 'done') {
        const total = await countAll();
        setStatus({ message: `Data parsed and saved (${total} items).`, type: 'success' });
        setProgress(1);
        worker.terminate();
        workerRef.current = null;
        try {
          // notify app that DB was updated
          window.dispatchEvent(new CustomEvent('db-updated', { detail: { total } }));
        } catch (e) {
          // ignore
        }
      } else if (msg.type === 'error') {
        setStatus({ message: `Parse error: ${msg.message}`, type: 'error' });
        worker.terminate();
        workerRef.current = null;
      }
    };

    worker.postMessage(raw);
  };

  const handleClear = async () => {
    await clearDB();
    setStatus({ message: 'Stored data cleared.', type: 'success' });
    setProgress(0);
    setParsedCount(0);
  };

  const handleRebuildIndex = async () => {
    setStatus({ message: 'Rebuilding player index...', type: 'info' });
    try {
      const res = await rebuildPlayersIndex();
      setStatus({ message: `Rebuilt player index: ${res.players} players, ${res.mappings} mappings.`, type: 'success' });
    } catch (e) {
      console.error('rebuildPlayersIndex error', e);
      setStatus({ message: 'Failed to rebuild player index.', type: 'error' });
    }
  };

  const statusColors = {
    error: 'text-red-500',
    success: 'text-green-500',
    info: 'text-blue-500'
  };

  return (
    <div className="bg-gray-50 dark:bg-gray-800 rounded-xl p-6 mb-6 shadow-sm">
      <h2 className="text-xl font-semibold mb-4">Load Projections Data</h2>

      <div className="bg-blue-50 dark:bg-blue-900/20 border border-blue-200 dark:border-blue-800 rounded-lg p-4 mb-4">
        <h3 className="font-semibold text-blue-900 dark:text-blue-100 mb-2 flex items-center gap-2">
          <Info className="w-5 h-5" />
          How to get live PrizePicks data:
        </h3>
        <ol className="text-sm text-blue-800 dark:text-blue-200 space-y-1 ml-6 list-decimal">
          <li>
            Open{' '}
            <a
              href="https://partner-api.prizepicks.com/projections"
              target="_blank"
              rel="noopener noreferrer"
              className="underline hover:text-blue-600"
            >
              partner-api.prizepicks.com/projections
            </a>{' '}
            in a new tab
          </li>
          <li>Copy all the JSON data (Ctrl+A, Ctrl+C)</li>
          <li>Paste it into the text area below</li>
          <li>Click "Load Data"</li>
        </ol>
        <p className="text-xs text-blue-700 dark:text-blue-300 mt-2">
          💡 Tip: Use the sample data button below to see how the app works
        </p>
      </div>

      <div className="flex gap-3 mb-4">
        <button
          onClick={handleLoadSample}
          className="px-6 py-2 bg-green-600 hover:bg-green-700 text-white font-medium rounded-lg transition-colors flex items-center gap-2"
        >
          <TestTube className="w-5 h-5" />
          Try Sample Data
        </button>
        <button
          onClick={handleClear}
          className="px-4 py-2 bg-red-600 hover:bg-red-700 text-white font-medium rounded-lg transition-colors"
        >
          Clear Stored Data
        </button>
        <button
          onClick={handleRebuildIndex}
          className="px-4 py-2 bg-yellow-600 hover:bg-yellow-700 text-white font-medium rounded-lg transition-colors"
        >
          Rebuild Player Index
        </button>
      </div>

      <textarea
        value={dataInput}
        onChange={(e) => setDataInput(e.target.value)}
        className="w-full px-4 py-3 text-base border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 focus:ring-2 focus:ring-[#5D5CDE] focus:border-transparent font-mono text-sm"
        rows={8}
        placeholder='{"data": [...], "included": [...]}'
      />

      <div className="flex gap-3 mt-4">
        <button
          onClick={handleLoadData}
          className="px-6 py-2 bg-[#5D5CDE] hover:bg-[#4a49c9] text-white font-medium rounded-lg transition-colors"
        >
          Load Data
        </button>
      </div>

      {progress > 0 && (
        <div className="mt-3">
          <div className="w-full bg-gray-200 dark:bg-gray-700 rounded-full h-2 overflow-hidden">
            <div style={{ width: `${Math.round(progress * 100)}%` }} className="h-2 bg-[#5D5CDE]" />
          </div>
          <div className="text-sm mt-1">Saved: {parsedCount}</div>
        </div>
      )}

      {status && (
        <div className={`mt-3 text-sm ${statusColors[status.type]}`}>
          {status.message}
        </div>
      )}
    </div>
  );
}
