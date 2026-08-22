-- Read-only verification for the CrownThrive Commercial Release Factory v2.
-- This script returns sanitized counts and never returns credentials, customer records,
-- Vault bodies, private storage paths, or protected policy bodies.

select public.commercial_release_factory_status_v2() as factory_status;

select
  (select count(*)
   from integration_control.product_release_packages p
   join integration_control.governed_releases gr on gr.release_id=p.governed_release_id
   where p.source_system='commercial_sites_candidate_4'
     and (gr.content_sha256 is distinct from p.package_sha256
          or gr.exact_version_ref is distinct from p.exact_version_ref
          or gr.required_certification_dimensions is distinct from p.required_dimensions)) as package_release_binding_mismatches,
  (select count(*)
   from integration_control.product_release_packages p
   join lateral jsonb_array_elements_text(p.required_dimensions) rd(dimension_key) on true
   join integration_control.product_release_package_gates g on g.package_id=p.package_id and g.dimension_key=rd.dimension_key
   where p.source_system='commercial_sites_candidate_4'
     and (g.content_sha256 is distinct from p.package_sha256 or g.exact_version_ref is distinct from p.exact_version_ref)) as canonical_gate_binding_mismatches,
  (select count(*)
   from integration_control.product_release_packages p
   join lateral jsonb_array_elements_text(p.required_dimensions) rd(dimension_key) on true
   join integration_control.governed_release_certifications c on c.release_id=p.governed_release_id and c.dimension_key=rd.dimension_key
   where p.source_system='commercial_sites_candidate_4'
     and (c.content_sha256 is distinct from p.package_sha256 or c.exact_version_ref is distinct from p.exact_version_ref)) as canonical_certification_binding_mismatches;

select run_id,run_state,product_count,package_count,pass_gate_count,hold_gate_count,
       accepted_count,published_count,input_sha256,output_sha256,started_at,completed_at
from integration_control.product_release_package_runs
where source_system='commercial_sites_candidate_4'
order by started_at desc
limit 10;
