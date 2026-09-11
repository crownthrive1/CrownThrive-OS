-- Persona Template Studio Skill v1
-- Founder-controlled candidate-template workflow. Existing production renderers remain unchanged
-- until the exact tested candidate receives explicit founder acceptance.

insert into penta_runtime.skill_contracts_v1(
  skill_key,owner_component_key,version,purpose,allowed_actions,prohibited_actions,
  authority_ceiling,autonomy_ceiling,requires_independent_verifier,fail_closed,status,metadata
) values (
  'ct.skill.persona-template-studio.v1',
  'penta.skills',
  '1.0.0',
  'Develop, compare, founder-test, revise, and safely promote persona communication templates without changing the current production template before explicit founder acceptance.',
  array[
    'template.snapshot_current','template.hash_current','template.candidate_create',
    'template.candidate_render','template.candidate_compare','template.founder_test_queue',
    'template.inbox_readback','template.feedback_capture','template.candidate_revise',
    'template.approval_record','template.promote_after_approval','template.post_promotion_readback'
  ]::text[],
  array[
    'template.production_mutate_before_founder_acceptance','template.mass_send_candidate',
    'template.auto_accept','template.overwrite_history','template.remove_ai_disclosure',
    'template.weaken_suppression','template.weaken_unsubscribe','template.weaken_recipient_safety',
    'template.change_provider_pacing','template.expand_authority','template.claim_human_identity'
  ]::text[],
  'D2','A2',true,true,'active',
  jsonb_build_object(
    'workflow',jsonb_build_array(
      'SNAPSHOT_PRODUCTION','BUILD_CANDIDATE','RENDER_AND_DIFF','FOUNDER_ONLY_TEST',
      'GMAIL_INBOX_READBACK','WAIT_FOR_FOUNDER_FEEDBACK','REVISE_OR_ACCEPT',
      'EXPLICIT_APPROVAL_GATE','PROMOTE_EXACT_CANDIDATE','PRODUCTION_READBACK_AND_ROLLBACK_CANARY'
    ),
    'production_freeze_until_explicit_acceptance',true,
    'ambiguous_founder_feedback','HOLD_FOR_CLARIFICATION',
    'test_delivery_policy','founder_test_lane_only',
    'test_transport','PentaMarketer -> PentaMail -> governed provider -> Gmail readback',
    'candidate_transport_authority',false,
    'production_transport_owner','PentaMail',
    'persona_control_plane','PentaMarketer',
    'template_history_append_only',true,
    'candidate_versioning','immutable candidate hash + predecessor production hash',
    'promotion_requirements',jsonb_build_array(
      'explicit_founder_acceptance','candidate_hash_matches_tested_candidate',
      'recipient_safety_preserved','suppression_and_unsubscribe_preserved',
      'AI_assisted_disclosure_preserved','provider_readback','rollback_canary'
    ),
    'default_first_persona','ct.persona.locticians.member-success.avery.v1',
    'current_production_renderer','crm.penta_marketer_locticians_v3_render_v1(uuid)',
    'current_production_version','3.0.0',
    'founder_acceptance_required_for_style_or_renderer_changes',true,
    'source_reason','Founder-directed persona template development workflow 2026-09-01'
  )
)
on conflict(skill_key) do update set
  version=excluded.version,purpose=excluded.purpose,allowed_actions=excluded.allowed_actions,
  prohibited_actions=excluded.prohibited_actions,authority_ceiling=excluded.authority_ceiling,
  autonomy_ceiling=excluded.autonomy_ceiling,requires_independent_verifier=excluded.requires_independent_verifier,
  fail_closed=excluded.fail_closed,status=excluded.status,metadata=excluded.metadata,updated_at=now();
