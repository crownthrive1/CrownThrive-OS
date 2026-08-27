-- Authority-reducing rollback for D3 Founder Production Approval Window v1.
-- Evidence is preserved. The window is revoked rather than deleted.

select penta_runtime.revoke_d3_founder_approval_window_v1(
  'ct.d3.founder-production-window.20260827.v1',
  'Rollback of migration 20260827170000; preserve directive, window, receipt, and release history while stopping new or pending approval consumption.',
  '1ff979329aa37668db86a02aca948ccabfcaee07ef09c256f20224e40213b5e4',
  'ct.rollback.d3-founder-production-window-v1'
);
