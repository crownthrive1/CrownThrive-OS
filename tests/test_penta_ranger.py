import datetime as dt
import unittest
from scripts.penta_ranger import RangerState, CHECK_INTERVAL, REMEDIATION_WINDOW, ESCALATION_WINDOW
class FakeGH:
    repo='crownthrive1/CrownThrive-OS'
    def paginate(self,path): return []
class RangerTests(unittest.TestCase):
    def test_new_head_is_due_and_carries_sla(self):
        state=RangerState(FakeGH(),586); now=dt.datetime(2026,8,27,18,0,tzinfo=dt.timezone.utc); d=state.decision('a'*40,now=now)
        self.assertTrue(d.due); self.assertEqual(d.reason,'head_changed'); self.assertEqual(dt.datetime.fromisoformat(d.next_check_at.replace('Z','+00:00'))-now,CHECK_INTERVAL); self.assertEqual(dt.datetime.fromisoformat(d.remediation_deadline_at.replace('Z','+00:00'))-now,REMEDIATION_WINDOW); self.assertEqual(dt.datetime.fromisoformat(d.escalation_at.replace('Z','+00:00'))-now,ESCALATION_WINDOW); self.assertFalse(d.escalation_due)
    def test_same_head_before_next_check_is_not_due(self):
        state=RangerState(FakeGH(),586); now=dt.datetime(2026,8,27,18,0,tzinfo=dt.timezone.utc); state.state.update({'head_sha':'a'*40,'first_seen_at':'2026-08-27T18:00:00Z','next_check_at':'2026-08-27T18:10:00Z'}); d=state.decision('a'*40,now=now+dt.timedelta(minutes=5)); self.assertFalse(d.due); self.assertEqual(d.reason,'not_due')
    def test_escalation_becomes_due_without_terminal_authority(self):
        state=RangerState(FakeGH(),586); state.state.update({'head_sha':'a'*40,'first_seen_at':'2026-08-27T18:00:00Z','next_check_at':'2026-08-27T18:10:00Z'}); d=state.decision('a'*40,now=dt.datetime(2026,8,27,19,1,tzinfo=dt.timezone.utc)); self.assertTrue(d.due); self.assertTrue(d.escalation_due)
if __name__=='__main__': unittest.main()
