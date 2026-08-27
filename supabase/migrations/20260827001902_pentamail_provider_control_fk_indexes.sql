-- Cover provider-control foreign keys reported by the post-deployment advisor.

create index if not exists penta_mail_provider_control_incident_idx
  on integration_control.penta_mail_provider_control_v1(active_incident_id);

create index if not exists penta_mail_provider_events_incident_idx
  on integration_control.penta_mail_provider_events_v1(incident_id);

create index if not exists penta_mail_trigger_probation_incident_idx
  on integration_control.penta_mail_trigger_probation_v1(active_incident_id);
