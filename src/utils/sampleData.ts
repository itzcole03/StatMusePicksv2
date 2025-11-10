import { ProjectionData } from '../types';

export function getSampleData(): ProjectionData {
  return {
    data: [
      {
        id: '1',
        type: 'projection',
        attributes: {
          stat_type: 'Points',
          line_score: 25.5,
          start_time: new Date(Date.now() + 3600000).toISOString(),
          status: 'pre_game'
        },
        relationships: {
          new_player: { data: { id: 'p1' } },
          league: { data: { id: 'l1' } },
          game: { data: { id: 'g1' } }
        }
      },
      {
        id: '2',
        type: 'projection',
        attributes: {
          stat_type: 'Rebounds',
          line_score: 10.5,
          start_time: new Date(Date.now() + 7200000).toISOString(),
          status: 'pre_game'
        },
        relationships: {
          new_player: { data: { id: 'p2' } },
          league: { data: { id: 'l1' } },
          game: { data: { id: 'g1' } }
        }
      },
      {
        id: '3',
        type: 'projection',
        attributes: {
          stat_type: 'Passing Yards',
          line_score: 275.5,
          start_time: new Date(Date.now() + 10800000).toISOString(),
          status: 'pre_game'
        },
        relationships: {
          new_player: { data: { id: 'p3' } },
          league: { data: { id: 'l2' } },
          game: { data: { id: 'g2' } }
        }
      }
    ],
    included: [
      {
        id: 'p1',
        type: 'new_player',
        attributes: {
          name: 'LeBron James',
          team: 'Los Angeles Lakers',
          position: 'SF'
        }
      },
      {
        id: 'p2',
        type: 'new_player',
        attributes: {
          name: 'Anthony Davis',
          team: 'Los Angeles Lakers',
          position: 'PF'
        }
      },
      {
        id: 'p3',
        type: 'new_player',
        attributes: {
          name: 'Patrick Mahomes',
          team: 'Kansas City Chiefs',
          position: 'QB'
        }
      },
      {
        id: 'l1',
        type: 'league',
        attributes: {
          name: 'NBA'
        }
      },
      {
        id: 'l2',
        type: 'league',
        attributes: {
          name: 'NFL'
        }
      },
      {
        id: 'g1',
        type: 'game',
        attributes: {
          home_team: 'Los Angeles Lakers',
          away_team: 'Boston Celtics'
        }
      },
      {
        id: 'g2',
        type: 'game',
        attributes: {
          home_team: 'Kansas City Chiefs',
          away_team: 'Buffalo Bills'
        }
      }
    ]
  };
}
