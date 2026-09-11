export const CIE_PACKETS = [
  {
    id: 'foundation', slug: 'cie-foundation-workbook', title: 'CIE Foundation Workbook',
    subtitle: 'Define the imprint before you scale the expression.', kind: 'workbook', pages: 6,
    description: 'A practical workbook for identity, audience, voice, goals, cultural commitments and non-negotiable guardrails.',
    sections: [
      ['Start with the imprint', ['Write one sentence describing what the organization is.', 'Name the audience relationship, not just demographics.', 'Describe the voice in observable terms.', 'List three things the brand will not become to chase growth.']],
      ['Identity depth test', ['What should remain recognizable if the logo disappears?', 'Which promises are institutional versus campaign-specific?', 'What does the audience trust you to understand without explanation?', 'Where does founder intuition currently substitute for documentation?']],
      ['Voice envelope', ['Write three sentences that are unmistakably on-imprint.', 'Write three sentences that are technically polished but culturally wrong.', 'Define acceptable variation by website, social, email, support and product UI.', 'Document words, tropes or tones that require review.']],
      ['Goals and guardrails', ['List current commercial and community goals.', 'For each goal, identify the pressure it can place on identity.', 'Attach at least one guardrail to each high-pressure goal.', 'Decide who can approve a guardrail exception.']],
      ['Route map', ['List every channel where the imprint appears.', 'Mark which channels are human-authored, agency-authored or AI-assisted.', 'Identify where rights, provenance or attribution must travel.', 'Name the evidence you need back from each route.']],
      ['Take-home decision', ['If more than three channels rely on unwritten founder judgment, formalize the imprint.', 'If AI or outside partners publish in your name, make context machine-usable.', 'If monetization changes the voice, separate performance evidence from cultural authority.', 'Next: run the CIE Live Lab and compare the result with this workbook.']]
    ]
  },
  {
    id: 'drift', slug: 'cie-drift-audit-packet', title: 'CIE Drift Audit Packet',
    subtitle: 'Find where the organization is becoming different versions of itself.', kind: 'workbook', pages: 6,
    description: 'A channel-by-channel diagnostic packet for tone, promise, representation, claims, rights and attribution drift.',
    sections: [
      ['Inventory the surfaces', ['List website, social, email, ads, product UI, support, events, media, press and partner surfaces.', 'Name the owner of each surface.', 'Mark where external agencies or creators publish.', 'Mark where AI generates or edits customer-facing work.']],
      ['Compare the promises', ['Copy the primary promise from each channel.', 'Circle promises that contradict or outrun the institutional promise.', 'Flag channels that optimize for a different customer than the stated audience.', 'Record which promise is canonical.']],
      ['Compare the voice', ['Rate each channel: restrained, conversational, promotional, editorial, instructional or transactional.', 'Flag tone changes that are intentional versus accidental.', 'Identify slang, urgency or trend language that only appears under performance pressure.', 'Document acceptable voice ranges.']],
      ['Rights and attribution', ['Find assets that travel without creator attribution.', 'Find licensed material with unclear downstream use.', 'Find sponsor or affiliate material that looks editorial.', 'Mark every route requiring CHLOM-compatible rights context.']],
      ['Risk disposition', ['HOLD: identity or rights contradiction that should stop release.', 'WARN: incomplete context that can continue only as draft/review.', 'PASS: expression varies by job while preserving the imprint.', 'Record the exact reason for every HOLD or WARN.']],
      ['Remediation sprint', ['Fix the highest-risk channel first.', 'Create one shared imprint object for all owners.', 'Re-run failing assets after remediation.', 'Archive the before/after evidence instead of deleting the failure.']]
    ]
  },
  {
    id: 'ai', slug: 'cie-ai-agent-readiness-packet', title: 'CIE AI + Agent Readiness Packet',
    subtitle: 'Give automation an imprint instead of another pile of prompts.', kind: 'guide', pages: 6,
    description: 'A readiness test for AI writers, agents, support systems and automated product experiences.',
    sections: [
      ['Automation inventory', ['List every AI tool or agent that can create customer-facing output.', 'Separate suggestion-only systems from autonomous publishing systems.', 'Document who owns the final cultural decision.', 'Record which systems can mutate data, spend money or publish.']],
      ['Context contract', ['Identity: what the system represents.', 'Audience: who the system is serving in this task.', 'Voice: observable style boundaries.', 'Guardrails: what the system cannot improvise.']],
      ['Claim discipline', ['Define which claims require sources.', 'Define which claims require human review.', 'Ban fabricated citations and unsupported numeric claims.', 'Separate commentary, inference and verified fact.']],
      ['Tool boundaries', ['Planning authority is not provider-write authority.', 'Content generation is not legal clearance.', 'Recommendation is not payment authority.', 'Every consequential action needs the correct downstream permission.']],
      ['Conformance test', ['Run the same request across three channels.', 'Check whether the identity remains stable while format changes.', 'Introduce a tempting trend or sponsor request and observe whether guardrails hold.', 'Log failures as training evidence.']],
      ['Production decision', ['PASS when outputs preserve identity and explicit boundaries.', 'WARN when context is incomplete but no irreversible action occurs.', 'HOLD when the system invents rights, claims, authority or identity.', 'Use the CIE public audit API for repeatable tests.']]
    ]
  },
  {
    id: 'media', slug: 'cie-media-sponsor-boundary-packet', title: 'CIE Media + Sponsor Boundary Packet',
    subtitle: 'Monetize the channel without selling the voice.', kind: 'workbook', pages: 6,
    description: 'Editorial, sponsor, attribution and distribution checks for media networks, podcasts, newsletters and streaming brands.',
    sections: [
      ['Name the authorities', ['Who owns editorial judgment?', 'Who owns sponsor commitments?', 'Who can approve product claims?', 'Who can approve rights and syndication?']],
      ['Editorial imprint', ['Define the network voice.', 'Define the difference between host voice and institutional voice.', 'List claims that must be sourced.', 'Document what a sponsor can never dictate.']],
      ['Sponsor boundary', ['Separate ad copy from editorial copy.', 'Require visible sponsorship disclosure.', 'Prohibit sponsor approval of unrelated editorial conclusions.', 'Record product-claim evidence separately from cultural fit.']],
      ['Format projections', ['Streaming can be visual and paced differently.', 'Podcast can be conversational without losing source discipline.', 'Social can compress without erasing provenance.', 'Newsletter can convert without becoming an ad sheet.']],
      ['Distribution route', ['Attach rights and attribution before syndication.', 'Attach CIE identity context before PentaAds planning.', 'Return CrownLytics evidence after distribution.', 'Never let performance metrics silently rewrite editorial authority.']],
      ['Failure drill', ['Test a sponsor demanding a favorable editorial conclusion.', 'Expected disposition: HOLD.', 'Remediation: separate sponsor message, restore editorial authority, retain disclosure and evidence.', 'Re-run before release.']]
    ]
  },
  {
    id: 'multibrand', slug: 'cie-multibrand-map-packet', title: 'CIE Multi-Brand Map Packet',
    subtitle: 'Build distinct child voices without creating brand soup.', kind: 'workbook', pages: 6,
    description: 'A parent-child imprint mapping packet for incubators, portfolios, studios, corridors and multi-brand operators.',
    sections: [
      ['Map the parent', ['Write the institutional narrative that every child should reinforce.', 'Define parent-level commitments.', 'Define parent-level prohibited drift.', 'Name the evidence the parent needs back.']],
      ['Map each child', ['State the child job.', 'State the child audience.', 'State the child voice.', 'State what it inherits and what it may vary.']],
      ['Classify expressions', ['Institutional: official voice and policy.', 'Corridor: major business/community lane.', 'Platform: technology/operating product.', 'Media/channel and brand/campaign: distribution and activation layers.']],
      ['Collision test', ['Find two brands making the same promise.', 'Find two brands competing for the same audience without a routing reason.', 'Find child language that contradicts the parent.', 'Find platform copy that has become culturally generic.']],
      ['Shared services', ['Define which identity context can be shared.', 'Keep analytics shared without flattening voice.', 'Keep commerce shared without forcing one sales style.', 'Keep AI context scoped to the active imprint.']],
      ['Portfolio release rule', ['A child may differ by job, audience and format.', 'A child may not silently rewrite parent commitments.', 'Record exceptions as explicit decisions.', 'Revisit the map whenever a new brand, channel or license enters the ecosystem.']]
    ]
  },
  {
    id: 'rights', slug: 'cie-rights-routing-packet', title: 'CIE Rights + Routing Packet',
    subtitle: 'Keep cultural context and legal permission connected without confusing them.', kind: 'guide', pages: 6,
    description: 'A practical handoff packet for CIE identity context and CHLOM-compatible rights/provenance evidence.',
    sections: [
      ['Two different questions', ['CIE asks: is this expression coherent with the imprint?', 'Rights asks: are we authorized to use, adapt, distribute or monetize it?', 'A yes to one is not automatically a yes to the other.', 'Both contexts should travel when the route needs them.']],
      ['Provenance checklist', ['Who created the asset?', 'What source or edition is authoritative?', 'What transformations occurred?', 'What attribution must remain visible?']],
      ['Permission checklist', ['What use is allowed?', 'Which channels are allowed?', 'Is adaptation allowed?', 'Is commercial use allowed?']],
      ['Cultural constraint checklist', ['What cannot be reframed?', 'What community context must remain?', 'What claims require evidence?', 'What language or imagery needs review?']],
      ['Handoff object', ['Asset ID and source reference.', 'CIE imprint ID and active guardrails.', 'Rights/provenance reference.', 'Destination, channel and evidence expectations.']],
      ['Release rule', ['HOLD if permission is missing for the requested use.', 'HOLD if the requested expression violates a non-negotiable imprint rule.', 'WARN if context is incomplete but no irreversible distribution occurs.', 'PASS only when both required contexts are sufficient for the route.']]
    ]
  },
  {
    id: 'pentaads', slug: 'cie-pentaads-placement-packet', title: 'CIE to PentaAds Placement Packet',
    subtitle: 'Let placement optimize inside the imprint, not rewrite it.', kind: 'guide', pages: 6,
    description: 'A provider-neutral advertising planning packet for identity, audience, creative constraints, safety, rights and measurement.',
    sections: [
      ['Campaign intent', ['State the business objective.', 'State the audience relationship.', 'State what the campaign must not imply.', 'State the evidence that matters after the campaign.']],
      ['Creative context', ['Attach the CIE imprint ID.', 'Attach channel-specific voice boundaries.', 'Attach required attribution/disclosure.', 'Attach prohibited claims and representations.']],
      ['Inventory constraints', ['List allowed channels.', 'List excluded channels.', 'List sensitive adjacency concerns.', 'Keep provider choice separate from identity authority.']],
      ['Rights state', ['Attach rights context when creative or audience use requires it.', 'Do not infer rights from file possession.', 'Do not infer sponsor permission from a media buy.', 'Keep evidence references durable.']],
      ['Measurement', ['Impression and click are operational evidence.', 'Conversion and qualified action are business evidence.', 'Neither automatically becomes cultural authority.', 'Feed verified learning into the Thrive Flywheel.']],
      ['Authority boundary', ['CIE can plan.', 'PentaAds execution requires separate provider authority.', 'The public demo cannot spend money.', 'A valid placement plan is not proof that media was purchased.']]
    ]
  },
  {
    id: 'readiness', slug: 'cie-implementation-readiness-packet', title: 'CIE Implementation Readiness Packet',
    subtitle: 'Decide whether you need Operator, Studio, Agency, Institutional or Enterprise.', kind: 'workbook', pages: 6,
    description: 'A buyer-side implementation assessment that maps identity complexity to the appropriate CIE scope.',
    sections: [
      ['Count the complexity', ['How many brands or programs?', 'How many public channels?', 'How many people or vendors publish?', 'How many AI systems create customer-facing work?']],
      ['Count the authority edges', ['Do you license content or brand assets?', 'Do sponsors influence public work?', 'Do affiliates or resellers speak for you?', 'Do outside agencies execute campaigns?']],
      ['Count the evidence needs', ['Do you need auditability?', 'Do you need API/MCP integration?', 'Do you need advertising context?', 'Do you need multi-team conformance?']],
      ['Typical fit', ['Operator: one bounded brand/site.', 'Studio: multi-brand/site or API/MCP + PentaAds needs.', 'Agency: repeatable client implementations.', 'Institutional: program and multi-team deployment.', 'Enterprise: multi-environment, managed integration or OEM eligibility.']],
      ['Implementation gates', ['Name the canonical imprint owner.', 'Name the first three channels to govern.', 'Name the first failure scenarios to test.', 'Name the evidence destination.']],
      ['Take-home plan', ['Run the CIE Live Lab.', 'Run at least one failing asset in the Failure Lab.', 'Download the packet matching your highest-risk lane.', 'Choose the commercial tier only after the scope is explicit.']]
    ]
  }
];

export function packetById(id) {
  const key = String(id || '').trim().toLowerCase();
  return CIE_PACKETS.find((packet) => packet.id === key || packet.slug === key) || null;
}

export function publicPacket(packet) {
  return {
    id: packet.id,
    slug: packet.slug,
    title: packet.title,
    subtitle: packet.subtitle,
    kind: packet.kind,
    page_count: packet.pages,
    description: packet.description,
    pdf_url: `https://crown-thrive-os.vercel.app/api/cie-packet?id=${encodeURIComponent(packet.id)}`,
    cover_url: `https://crown-thrive-os.vercel.app/api/cie-packet-cover?id=${encodeURIComponent(packet.id)}`,
    go_flipbooks_reader: `https://go-flipbooks.vercel.app/reader/${packet.slug}`,
    source: 'CrownThrive CIE Website 2.0'
  };
}
