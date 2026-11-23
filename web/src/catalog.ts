import savedEvidence from '../../artifacts/scenarios.json';
import type { AnalysisResponse } from './types';

/** These are complete Python-generated results, never browser recalculations. */
export const scenarioCatalog = savedEvidence as unknown as Record<string, AnalysisResponse>;

export const catalogEntries = [
  {
    id: 'case_default', label: 'Case baseline',
    description: 'The original case assumptions, valuing additional useful output. Start here, then test what changes the decision.',
  },
  {
    id: 'same_work_savings', label: 'Same work, less time',
    description: 'The same quantum evidence, but value comes from completing a fixed workload sooner. This separates time saved from demand for more output.',
  },
  {
    id: 'low_commercial_value', label: 'Low commercial value',
    description: 'A more conservative buyer captures less value from each productive hour. The hardware gain remains; the financial case changes.',
  },
  {
    id: 'demand_backlog', label: 'Demand backlog',
    description: 'More customer demand can fill recovered capacity. Compare the resulting calibration bookings and contract economics with the baseline.',
  },
  {
    id: 'time_reduction_reading', label: '“70% faster” means 70% less time',
    description: 'An alternative reading of the calibration claim under higher customer demand. It preserves the distinction between a speed increase and a duration reduction.',
  },
  {
    id: 'replacement_already_due', label: 'Control replacement already due',
    description: 'A new control-system purchase was already required. The model can therefore count avoided procurement cost instead of treating the installed system as a new saving.',
  },
  {
    id: 'no_fixed_overhead', label: 'No fixed shot overhead',
    description: 'Initialization and readout overhead are set to zero. Longer optimized gates now take a larger share of the full cycle, testing the throughput claim.',
  },
  {
    id: 'control_only_noise', label: 'Reported errors are control-only',
    description: 'A separate saved experiment treats the reported gate errors as control errors and adds the documented Pauli-twirled relaxation model.',
  },
].filter((entry) => entry.id in scenarioCatalog);
