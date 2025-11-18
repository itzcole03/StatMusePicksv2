import os
import json
from glob import glob

AUDIT_DIR = os.path.join(os.path.dirname(__file__), '..', 'backend', 'ingest_audit')


def find_latest_audit():
    pattern = os.path.join(AUDIT_DIR, 'games_raw_*.json')
    files = glob(pattern)
    if not files:
        return None
    files.sort(key=os.path.getmtime, reverse=True)
    return files[0]


def load_audit(path):
    recs = []
    with open(path, 'r', encoding='utf-8') as fh:
        for ln in fh:
            ln = ln.strip()
            if not ln:
                continue
            try:
                recs.append(json.loads(ln))
            except Exception:
                continue
    return recs


def write_repaired(path, records):
    try:
        with open(path, 'w', encoding='utf-8') as fh:
            for r in records:
                fh.write(json.dumps(r, ensure_ascii=False) + '\n')
        return True
    except Exception as e:
        print('Failed to write repaired file:', e)
        return False


def main():
    path = find_latest_audit()
    if not path:
        print('No audit file found')
        return
    recs = load_audit(path)
    print(f'Loaded {len(recs)} records from {path}')

    try:
        from backend.services.data_ingestion_service import detect_outlier_values
        from backend.services import nba_stats_client
    except Exception as e:
        print('Failed to import required backend modules:', e)
        return

    outlier_idxs = detect_outlier_values(recs, field='value', z_thresh=3.0)
    print(f'Found {len(outlier_idxs)} outlier indices')
    if not outlier_idxs:
        return

    # Build id -> name mapping using nba_stats_client.fetch_all_players()
    players = nba_stats_client.fetch_all_players() or []
    id_to_name = {int(p.get('id')): p.get('full_name') for p in players if p.get('id')}

    repaired = False
    repaired_idxs = []
    for i in outlier_idxs:
        r = recs[i]
        if not r.get('player_name'):
            pid = r.get('player_nba_id') or r.get('Player_ID') or r.get('player_id')
            try:
                if pid is not None:
                    pid = int(pid)
                    name = id_to_name.get(pid)
                    if not name:
                        # try alternative: find in fetch_all_players by string id match
                        for p in players:
                            if int(p.get('id')) == pid:
                                name = p.get('full_name')
                                break
                    if name:
                        r['player_name'] = name
                        repaired = True
                        repaired_idxs.append(i)
                    else:
                        # try nba client resolver that can consult league logs
                        try:
                            name2 = nba_stats_client.get_player_name_by_id(pid)
                            if name2:
                                r['player_name'] = name2
                                repaired = True
                                repaired_idxs.append(i)
                        except Exception:
                            pass
            except Exception:
                continue

    if not repaired:
        print('No missing names could be backfilled (nba_api may be unavailable)')
    else:
        # write repaired file alongside original
        base = os.path.basename(path)
        repaired_path = os.path.join(os.path.dirname(path), base.replace('.json', '_repaired.json'))
        ok = write_repaired(repaired_path, recs)
        if ok:
            print(f'Wrote repaired audit to {repaired_path} (repaired {len(repaired_idxs)} records)')
        else:
            print('Failed to write repaired audit file')

        # Re-run ingestion for the repaired subset only
        subset = [recs[i] for i in repaired_idxs]
        if subset:
            try:
                from backend.services.data_ingestion_service import normalize_raw_game, update_player_stats
                normalized = [normalize_raw_game(r) for r in subset]
                inserted = update_player_stats(normalized)
                print(f'update_player_stats inserted {inserted} rows for repaired subset')
            except Exception as e:
                print('Failed to run ingestion for repaired subset:', e)


if __name__ == '__main__':
    main()
