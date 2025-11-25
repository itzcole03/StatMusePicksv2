// Use centralized test mocks (registers vi.mock for services)
import '../../tests/testUtils/mockServices';

import { render, screen, fireEvent } from '@testing-library/react';
import React from 'react';
import AnalysisSection from '../AnalysisSection';
import { ParsedProjection, Settings } from '../../types';


describe('AnalysisSection rolling averages display', () => {
  it('renders rolling averages chips when external context includes them', async () => {
    const projections: ParsedProjection[] = [
      { id: 'p1', player: 'Test Player', team: 'TST', position: 'PG', league: 'NBA', stat: 'points', line: 20, startTime: '', status: 'SCHEDULED' },
    ];
    const settings: Settings = { aiProvider: 'local', llmEndpoint: '', llmModel: '' };

    render(<AnalysisSection projections={projections} settings={settings} />);

    try {
      // Wait for the external contexts banner and then the details toggle to appear
      await screen.findByText(/External StatMuse data was fetched/i, undefined, { timeout: 3000 });
      const showBtn = await screen.findByText(/Show details/i, undefined, { timeout: 2000 }).catch(() => null);
      if (showBtn) fireEvent.click(showBtn);

      // Check for rolling averages chip text after details are shown
      const chip = await screen.findByText(/last_3_avg: 21.00/i, undefined, { timeout: 2000 }).catch(() => null);
      expect(chip).not.toBeNull();
    } catch (err) {
      // Dump DOM to aid debugging of flaky render failures
      console.error('Debug DOM snapshot:');
      // Dump DOM using testing library helper
      screen.debug();
      throw err;
    }
  });
});
