import { useEffect, useState } from "react";
import { Settings } from "../types";
import { fetchBatchPlayerContext } from "../services/nbaService";

type DemoResult = { player?: string; error?: string; fetchedAt?: string };

export default function BatchContextDemo() {
  const [results, setResults] = useState<DemoResult[]>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    async function run() {
      setLoading(true);
      const requests = [
        { player: "LeBron James", stat: "points", limit: 5 },
        { player: "Stephen Curry", stat: "points", limit: 5 },
      ];
      const settings: Settings = {
        aiProvider: "local",
        llmEndpoint: "",
        llmModel: "",
      };

      const res = await fetchBatchPlayerContext(requests, settings);
      setResults(
        res.map((r: any) => ({
          player: r.player || r.player_name || r.player,
          error: r.error,
          fetchedAt: r.fetchedAt,
        }))
      );
      setLoading(false);
    }

    run();
  }, []);

  return (
    <div className="p-4">
      <h3 className="text-lg font-medium">Batch Player Context Demo</h3>
      {loading && <div>Loading...</div>}
      <ul>
        {results.map((r, i) => (
          <li key={i} className="py-2">
            <strong>{r.player}</strong>:{" "}
            {r.error ? (
              <span className="text-red-600">{r.error}</span>
            ) : (
              <span>fetched at {r.fetchedAt}</span>
            )}
          </li>
        ))}
      </ul>
    </div>
  );
}
