(() => {
  'use strict';

  const CATALOG_ENDPOINT = '/api/catalog';
  const CHECKOUT_HOST = 'buy.stripe.com';
  const CONTACT = 'contact@crownthrive.com';

  const lanes = Object.freeze({
    overview: {
      path: '/go-flipbooks',
      crumb: 'Go Flipbooks',
      title: 'Go Flipbooks by CrownThrive',
      description: 'Choose hosted Standard publishing, licensed static infrastructure, API-powered PRO operations, or hands-on managed publication services.',
      eyebrow: 'Go Flipbooks publishing infrastructure',
      hero: 'Pages that move.<br><em>Rights that stay yours.</em>',
      lede: 'Choose the publication operating lane that fits the source, the buyer, and the work: direct hosted publishing, licensed static infrastructure, API-powered PRO operations, or hands-on managed production.',
      primary: { label: 'Find your lane', href: '#lanes' },
      secondary: { label: 'Browse live offers', href: '/store?category=publishing' },
      proof: ['Four operating lanes', 'Live governed pricing', 'Customer-owned content', 'CrownThrive ecosystem integration'],
      visual: ['SOURCE', 'Authorized content', 'READER', 'Branded delivery', 'COMMERCE', 'Exact offers', 'EVIDENCE', 'Rights + readback', 'PUBLISH'],
      notice: 'Live catalog readback · CHLOM-scoped commerce · CrownThrive-operated delivery',
      outcomes: [
        ['01', 'Publish with purpose', 'Move books, guides, magazines, programs, catalogs, reports, and cultural archives into a focused digital destination.'],
        ['02', 'Connect reader to action', 'Route approved products, services, tickets, memberships, contacts, licensing, and next steps from the publication experience.'],
        ['03', 'Preserve rights and editions', 'Keep the source, customer authority, edition, publication, deployment, and license distinguishable through CHLOM.'],
        ['04', 'Measure what matters', 'Use CrownLytics-compatible events for approved reader, campaign, click, conversion, delivery, and lifecycle signals.'],
        ['05', 'Create media inventory', 'Eligible reader surfaces can support PentaAds house campaigns, sponsorship, and paid inventory without erasing editorial control.'],
        ['06', 'Expand through the flywheel', 'Connect publishing to CrownThriveU, CrownThrive Studios, Virality Music, Locticians, local media, events, affiliates, rewards, and licensing.']
      ],
      audiences: [
        ['AUTHORS & PUBLISHERS', 'Turn finished work into a durable destination', 'Launch editions, previews, series, catalogs, companion assets, and direct commercial pathways.', '/go-flipbooks/standard'],
        ['EDUCATORS & MINISTRIES', 'Deliver resources people can actually use', 'Publish curricula, workbooks, study tools, manuals, sermon resources, and family learning experiences.', '/go-flipbooks/standard'],
        ['AGENCIES & STUDIOS', 'Operate client publications without workflow sprawl', 'Choose self-hosted control, repeat automation, or managed delivery by client and scope.', '/go-flipbooks/static'],
        ['MEDIA & COMMUNITY BRANDS', 'Build editions, archives, and sponsor-ready inventory', 'Connect stories, local coverage, magazines, programs, advertisers, audiences, and archives.', '/go-flipbooks/pro'],
        ['INSTITUTIONS & ARCHIVES', 'Preserve control, provenance, and accessibility', 'Choose deployment custody, structured publication standards, and governed organizational access.', '/go-flipbooks/static'],
        ['FOUNDERS & COMMERCE TEAMS', 'Make proposals, catalogs, reports, and lookbooks work harder', 'Give product and service narratives a measurable path to inquiry, checkout, or relationship growth.', '/go-flipbooks/managed']
      ],
      workflow: [
        ['01', 'Choose the lane', 'Match the operating model to source readiness, custody, cadence, and automation.'],
        ['02', 'Select the offer', 'Use live provider-backed pricing or request written scope where no public checkout exists.'],
        ['03', 'Confirm authority', 'Bind the customer, source rights, destination, edition, and permitted use.'],
        ['04', 'Prepare the publication', 'Validate, remediate, configure, build, and quality-assure the approved asset.'],
        ['05', 'Publish and read back', 'Verify the destination and provider state instead of treating a request as success.'],
        ['06', 'Operate the lifecycle', 'Measure, update, license, monetize, archive, and expand without losing history.']
      ],
      faq: [
        ['Which lane should I choose?', 'Use Standard for ready content and direct hosted publishing; Static for licensed deployment custody; PRO for recurring API-powered operations; Managed Services for difficult sources or hands-on production.'],
        ['Does Go Flipbooks take ownership of my content?', 'No. The customer retains underlying content rights and grants only the permissions required for the purchased processing, hosting, display, delivery, or licensed deployment scope.'],
        ['Are the prices hardcoded on this website?', 'No. Active public offers are read from CrownThrive’s governed catalog. A page enters a visible hold state when live pricing cannot be verified.'],
        ['Can publications connect to the wider CrownThrive ecosystem?', 'Yes, when authorized. Go Flipbooks can connect with PentaGreen, PentaAds, CrownLytics, CrownRewards, affiliates, events, media, education, licensing, and other CrownThrive corridors.'],
        ['Does checkout mean the publication is already delivered?', 'No. Checkout, entitlement, intake, production, publication, provider readback, and delivery acceptance are separate states.'],
        ['Is anything physically shipped?', 'No physical item is implied by these Go Flipbooks marketplace pages. Any physical product would require its own explicit listing and fulfillment terms.']
      ],
      closing: ['Choose the right publication corridor', 'Make the next edition easier to launch—and easier to trust.', 'Start with the operating lane that matches the actual work. Expand only when the publication business requires it.', 'Find your lane', '#lanes']
    },

    standard: {
      path: '/go-flipbooks/standard',
      crumb: 'Standard',
      title: 'Go Flipbooks Standard | Hosted Interactive Publishing',
      description: 'Direct hosted publishing for authors, educators, ministries, founders, cultural organizations, and teams with substantially finished content.',
      eyebrow: 'Go Flipbooks Standard',
      hero: 'Publish the file you <em>already finished.</em>',
      lede: 'Standard is the direct hosted publishing lane for authors, educators, ministries, founders, beauty and wellness brands, event teams, local publishers, and organizations that already have the content—and need a credible digital destination built around it.',
      primary: { label: 'Choose a Standard offer', href: '#offers' },
      secondary: { label: 'Compare all lanes', href: '#comparison' },
      proof: ['Hosted interactive reader', 'Private source intake', 'No platform publication limit', 'Customer-owned content'],
      visual: ['UPLOAD', 'Authorized source', 'BUILD', 'Reader + actions', 'PUBLISH', 'Hosted destination', 'MEASURE', 'Reader signals', 'STANDARD'],
      notice: 'Standard is the direct hosted/static publishing lane · live offers verified from the CrownThrive catalog',
      outcomes: [
        ['01', 'Branded reader', 'Give the publication a focused destination designed for reading on desktop, tablet, and mobile.'],
        ['02', 'Secure intake', 'Receive the authorized source through a controlled customer and publication workspace.'],
        ['03', 'Conversion layer', 'Connect approved products, services, tickets, contact paths, licensing, or next steps.'],
        ['04', 'Reader measurement', 'Record approved reading, click, conversion, fulfillment, and lifecycle events through CrownLytics.'],
        ['05', 'PentaAds-ready surfaces', 'Register eligible inventory for house campaigns, sponsorship, or paid placements by scope.'],
        ['06', 'Expandable publication', 'Add editions, managed support, commerce, licensing, PRO, or related ecosystem corridors without erasing history.']
      ],
      audiences: [
        ['AUTHORS & IMPRINTS', 'Books, previews, companion guides', 'Launch one title or grow a catalog while preserving edition, rights, and delivery evidence.', '/store?q=Go%20Flipbooks%20Standard'],
        ['EDUCATORS & MINISTRIES', 'Curriculum, workbooks, study resources', 'Deliver training, sermon resources, manuals, family study, and institutional learning assets.', '/store?q=Go%20Flipbooks%20Standard'],
        ['FOUNDERS & BUSINESSES', 'Catalogs, proposals, reports', 'Turn services, products, impact evidence, and procurement materials into conversion surfaces.', '/store?q=Go%20Flipbooks%20Standard'],
        ['BEAUTY & WELLNESS', 'Lookbooks, methods, menus, education', 'Showcase collections, professionals, events, methods, and culturally aligned customer education.', 'mailto:contact@crownthrive.com?subject=Go%20Flipbooks%20Standard%20for%20Beauty%20and%20Wellness'],
        ['EVENT & COMMUNITY TEAMS', 'Programs, playbills, directories', 'Connect schedules, speakers, sponsors, tickets, vendors, resources, and archives.', 'mailto:contact@crownthrive.com?subject=Go%20Flipbooks%20Standard%20for%20Events'],
        ['LOCAL & INDEPENDENT MEDIA', 'Magazines, editions, newsletters', 'Publish issue-based stories, advertiser inventory, archives, subscriptions, and reader actions.', 'mailto:contact@crownthrive.com?subject=Go%20Flipbooks%20Standard%20for%20Media']
      ],
      workflow: [
        ['01', 'Choose production scope', 'Select the current Standard offer that matches the publications included in this order.'],
        ['02', 'Complete checkout', 'Stripe records the exact product, price, cadence, and customer.'],
        ['03', 'Activate intake', 'A scoped customer workspace opens for the authorized publication source.'],
        ['04', 'Confirm rights and instructions', 'Identify the source, edition, destination, calls to action, and permitted use.'],
        ['05', 'Build and review', 'CrownThrive validates, configures, tests, and presents the publication for approval.'],
        ['06', 'Publish and operate', 'The approved edition reaches its hosted reader and eligible measurement, commerce, and lifecycle routes.']
      ],
      faq: [
        ['Is Standard capped at 1, 5, or 25 publications forever?', 'No. Standard/static reader capacity has no arbitrary Go Flipbooks publication limit. The live offers describe the production or activation quantity included in that purchase—not a permanent platform ceiling.'],
        ['What should I have ready?', 'A substantially complete publication and authority to submit it. PDF is the fastest route; other supported sources can be reviewed.'],
        ['Does Standard include writing or major redesign?', 'Standard centers on producing and hosting ready source material. Extensive writing, redesign, remediation, migration, or custom production routes to Managed Services.'],
        ['Can I sell or promote from the reader?', 'Approved calls to action, products, services, licensing paths, PentaAds inventory, and CrownLytics measurement can be activated when supported by the purchased scope.'],
        ['Does CrownThrive own my publication?', 'No. The customer retains underlying rights. CHLOM records the exact permissions needed to process, host, display, deliver, and operate the purchased service.'],
        ['What is the monthly Standard offer?', 'The recurring Standard offer is an eligible managed-hosting and lifecycle-support add-on. It does not replace the applicable setup or publication-production entitlement.'],
        ['Can I upgrade later?', 'Yes. Additional production scope, managed support, PRO, and Managed Services can be added without rewriting the original edition history.']
      ],
      closing: ['Your finished file can do more', 'Give it a destination built to circulate.', 'Choose the current production scope, complete secure checkout, and enter the governed Go Flipbooks intake corridor.', 'Choose Standard', '#offers']
    },

    static: {
      path: '/go-flipbooks/static',
      crumb: 'Static / Self-Hosted',
      title: 'Go Flipbooks Static | Licensed Deployment Control',
      description: 'Licensed static-reader and self-hosted deployment control for agencies, institutions, archives, developers, and white-label operators.',
      eyebrow: 'Go Flipbooks Static / Self-Hosted',
      hero: 'Control the deployment. <em>License the infrastructure.</em>',
      lede: 'Static / Self-Hosted is for agencies, institutions, archives, developer teams, white-label operators, and organizations that need deployment custody—not merely a hosted publication. It separates customer content rights from software, source, deployment, redistribution, and client-use rights.',
      primary: { label: 'Request exact license scope', href: 'mailto:contact@crownthrive.com?subject=Go%20Flipbooks%20Static%20or%20Self-Hosted%20License' },
      secondary: { label: 'Compare all lanes', href: '#comparison' },
      proof: ['Licensed deployment custody', 'No platform publication limit', 'Exact entity and use scope', 'No implied source ownership'],
      visual: ['PACKAGE', 'Approved build', 'DEPLOY', 'Customer environment', 'CONTROL', 'Domain + runtime', 'EVIDENCE', 'License + version', 'STATIC'],
      notice: 'Static deployment rights require an exact CHLOM license · no public self-hosted checkout is manufactured',
      outcomes: [
        ['01', 'Deployment custody', 'Operate the licensed static reader in an approved customer or organizational environment.'],
        ['02', 'Domain control', 'Use authorized domains, hosting, security, delivery, and operational policies under the written scope.'],
        ['03', 'Versioned package', 'Bind the exact code or deployment package, version, integrity hash, documentation, and supported use.'],
        ['04', 'Entity-level rights', 'Define whether the license covers one organization, internal projects, client deployments, or an approved portfolio.'],
        ['05', 'Operational independence', 'Run eligible static publications without depending on a per-publication provider API slot.'],
        ['06', 'Governed expansion', 'Add support, updates, managed operations, white-label rights, client rights, or new versions only when explicitly licensed.']
      ],
      audiences: [
        ['AGENCIES', 'Deploy for authorized client work', 'Request client-use scope without assuming sublicense, resale, OEM, or white-label rights.', 'mailto:contact@crownthrive.com?subject=Agency%20Go%20Flipbooks%20Static%20License'],
        ['INSTITUTIONS', 'Control infrastructure and data posture', 'Align hosting, identity, accessibility, retention, security, and procurement requirements.', 'mailto:contact@crownthrive.com?subject=Institutional%20Go%20Flipbooks%20Static%20License'],
        ['ARCHIVES & LIBRARIES', 'Preserve durable access', 'Operate governed publication collections with version, provenance, and long-term custody controls.', 'mailto:contact@crownthrive.com?subject=Archive%20Go%20Flipbooks%20Static%20License'],
        ['DEVELOPER TEAMS', 'Integrate the reader into an approved stack', 'Receive exact deployment boundaries, interfaces, documentation, and release evidence.', 'mailto:contact@crownthrive.com?subject=Developer%20Go%20Flipbooks%20Static%20License'],
        ['WHITE-LABEL OPERATORS', 'Request brand and client rights explicitly', 'White-label, resale, multi-tenant, and client-operation rights are separate—not inherited from basic deployment rights.', 'mailto:contact@crownthrive.com?subject=White%20Label%20Go%20Flipbooks%20Scope'],
        ['CULTURAL ORGANIZATIONS', 'Keep identity and custody aligned', 'Preserve voice, provenance, community standards, and controlled long-term reuse.', 'mailto:contact@crownthrive.com?subject=Cultural%20Organization%20Go%20Flipbooks%20Static']
      ],
      workflow: [
        ['01', 'Describe the deployment', 'Identify the legal entity, environment, domains, audience, data posture, and intended use.'],
        ['02', 'Select the rights class', 'Separate internal use, client deployment, white-label, modification, and support requirements.'],
        ['03', 'Review technical fit', 'Confirm hosting, runtime, security, accessibility, integration, performance, and maintenance needs.'],
        ['04', 'Issue exact CHLOM scope', 'Bind the license to the entity, version, package, permitted deployments, restrictions, and evidence.'],
        ['05', 'Deliver and validate', 'Transfer the approved package and documentation, then verify the target deployment.'],
        ['06', 'Maintain by entitlement', 'Apply updates, support, migrations, and expanded rights only under an active matching entitlement.']
      ],
      faq: [
        ['Is Static the same as Standard?', 'No. Standard is a CrownThrive-hosted publication service. Static / Self-Hosted grants only the deployment rights expressly stated in an exact CHLOM license.'],
        ['Is there a publication limit?', 'The static reader itself is not governed by an arbitrary Go Flipbooks publication count. Practical infrastructure, performance, storage, accessibility, rights, and support boundaries still apply.'],
        ['Does a deployment license include source ownership?', 'No. Ownership remains with CrownThrive. Source access, modification, client deployment, white-label, resale, redistribution, and future-version rights must be expressly granted.'],
        ['Can an agency deploy for clients?', 'Only when the license includes client-deployment rights and defines the authorized legal entity, client relationship, portfolio boundary, and restrictions.'],
        ['Is there a public checkout?', 'Not currently. The website intentionally routes Static / Self-Hosted through written scope because the rights and technical boundary must be explicit before purchase.'],
        ['Can CrownThrive operate the deployment for us?', 'Yes. Managed Services can handle implementation, migration, updates, monitoring, and lifecycle operations under a separate scope.'],
        ['Can Static later connect to PRO?', 'Yes, when API-powered provider capabilities are required and paid PRO capacity is available. The two rails remain separately licensed and evidenced.']
      ],
      closing: ['Own the deployment decision', 'License exactly what the organization needs.', 'Define the entity, environment, rights, support, and operating boundary before infrastructure changes hands.', 'Request Static scope', 'mailto:contact@crownthrive.com?subject=Go%20Flipbooks%20Static%20or%20Self-Hosted%20License']
    },

    pro: {
      path: '/go-flipbooks/pro',
      crumb: 'PRO / API',
      title: 'Go Flipbooks PRO | API-Powered Managed Publishing',
      description: 'API-powered managed publication operations for publishers, agencies, media brands, institutions, and recurring editorial programs.',
      eyebrow: 'Go Flipbooks PRO / API',
      hero: 'Run publishing like <em>an operating system.</em>',
      lede: 'PRO is for publishers, agencies, media brands, institutions, and recurring editorial teams that need more than a hosted reader. It adds API-powered managed creation, configuration, publishing, lead capture, analytics, readback, and lifecycle operations while provider credentials stay server-side.',
      primary: { label: 'Activate the published PRO offer', href: '#offers' },
      secondary: { label: 'See the operating model', href: '#outcomes' },
      proof: ['API-powered operations', 'Server-side credentials', 'Provider readback required', 'Capacity controlled'],
      visual: ['CREATE', 'Source + identity', 'CONFIGURE', 'Reader + controls', 'PUBLISH', 'Approved state', 'RECONCILE', 'Readback + retry', 'PRO / API'],
      notice: 'PRO is the API-powered managed lane · provider capacity and entitlement are confirmed before activation',
      outcomes: [
        ['01', 'Programmatic creation', 'Create publications from authorized files or URLs through controlled server-side operations.'],
        ['02', 'Managed configuration', 'Apply approved metadata, navigation, viewer controls, header and footer structure, and primary calls to action.'],
        ['03', 'Governed lead capture', 'Configure lead fields, consent language, destinations, and webhook handoffs within the purchased scope.'],
        ['04', 'Analytics continuity', 'Connect approved tracking and CrownLytics events so publication behavior becomes operating evidence.'],
        ['05', 'Lifecycle operations', 'Create, replace, update, publish, unpublish, monitor, and reconcile approved publication states.'],
        ['06', 'Provider readback', 'Verify the business result after each consequential write; transport success alone never proves publication success.']
      ],
      audiences: [
        ['PUBLISHERS & IMPRINTS', 'Operate a growing catalog', 'Standardize edition intake, settings, delivery, measurement, and lifecycle work while preserving title-level evidence.', 'mailto:contact@crownthrive.com?subject=Publisher%20Go%20Flipbooks%20PRO'],
        ['AGENCIES & STUDIOS', 'Serve clients without workflow sprawl', 'Route authorized client publications through controlled identities, destinations, approvals, and readback.', 'mailto:contact@crownthrive.com?subject=Agency%20Go%20Flipbooks%20PRO'],
        ['MEDIA BRANDS', 'Keep recurring editions moving', 'Connect magazines, newsletters, programs, archives, advertiser surfaces, lead paths, and audience measurement.', 'mailto:contact@crownthrive.com?subject=Media%20Brand%20Go%20Flipbooks%20PRO'],
        ['INSTITUTIONS', 'Standardize departments and programs', 'Create repeatable publication operations for education, ministries, associations, impact reporting, and resources.', 'mailto:contact@crownthrive.com?subject=Institutional%20Go%20Flipbooks%20PRO'],
        ['COMMERCE TEAMS', 'Connect catalog content to action', 'Operate lookbooks, seasonal editions, calls to action, lead capture, campaigns, and reader inventory.', 'mailto:contact@crownthrive.com?subject=Commerce%20Go%20Flipbooks%20PRO'],
        ['CROWNTHRIVE ECOSYSTEM', 'Move assets through the flywheel', 'Connect publications with PentaGreen, PentaAds, CrownLytics, ThrivePush, CrownRewards, affiliates, media, and licensing.', '/commerce']
      ],
      workflow: [
        ['01', 'Qualify the operation', 'Confirm recurring volume, brands, teams, domains, data, lead, analytics, and lifecycle requirements.'],
        ['02', 'Activate implementation', 'Purchase the published implementation offer or execute a written custom scope.'],
        ['03', 'Bind provider capacity', 'Confirm current paid provider entitlement and available PRO slot before representing the lane as active.'],
        ['04', 'Configure the corridor', 'Establish controlled API operations, reader settings, destinations, leads, analytics, and authority.'],
        ['05', 'Canary and read back', 'Test create, update, publish, lead, analytics, and recovery behavior against actual provider state.'],
        ['06', 'Operate and reconcile', 'Monitor lifecycle activity, retry safely, preserve evidence, and manage capacity without displacing reservations.']
      ],
      faq: [
        ['What does API-powered mean for the buyer?', 'Authorized publication operations can be created, configured, updated, published, read back, and reconciled through controlled server-side workflows. Customers receive the managed outcome—not provider credentials or unrestricted internal access.'],
        ['Is PRO unlimited?', 'No. PRO is constrained by paid provider entitlement and available capacity. Existing persistent reservations are not displaced, and new activation is confirmed before a slot is represented as assigned.'],
        ['Does the current $297 checkout include a $29 monthly subscription?', 'The live CrownThrive catalog currently exposes the $297 implementation checkout. This page does not manufacture a recurring PRO charge. Any ongoing managed service must be separately published, entitled, or included in written scope.'],
        ['Can PRO capture leads?', 'Approved lead fields, consent, privacy language, destinations, and webhook handoffs can be configured when the customer has authority and the purchased scope supports them.'],
        ['Where are the provider credentials?', 'They remain server-side in restricted custody. The public website and customer experience do not expose them.'],
        ['What happens when an API operation fails?', 'The requested action, failure state, retry route, readback, and reconciliation evidence remain distinct. A response code alone is not treated as a completed business result.'],
        ['Should a one-time publication use PRO?', 'Usually not. Standard is the lighter route for ready direct publications. PRO is justified when publishing is a recurring operation with automation, lead, analytics, or lifecycle requirements.']
      ],
      closing: ['Stop rebuilding the publishing workflow', 'Implement the operating corridor once.', 'Use PRO when publication creation, configuration, leads, analytics, readback, and lifecycle management are recurring work.', 'Activate PRO', '#offers']
    },

    managed: {
      path: '/go-flipbooks/managed',
      crumb: 'Managed Services',
      title: 'Go Flipbooks Managed Services | Done-for-You Publishing',
      description: 'Done-for-you source preparation, remediation, migration, publication production, configuration, and launch support.',
      eyebrow: 'Go Flipbooks Managed Services',
      hero: 'Bring the source. <em>Bring the deadline.</em>',
      lede: 'Managed Services is for authors, publishers, agencies, institutions, ministries, media teams, and businesses that need CrownThrive to prepare, repair, migrate, configure, produce, or launch the publication directly.',
      primary: { label: 'Choose a managed scope', href: '#offers' },
      secondary: { label: 'Request custom scope', href: 'mailto:contact@crownthrive.com?subject=Custom%20Go%20Flipbooks%20Managed%20Scope' },
      proof: ['Done-for-you production', 'Secure source handling', 'Explicit acceptance criteria', 'Evidence-bound delivery'],
      visual: ['REVIEW', 'Source + constraints', 'REPAIR', 'Structure + quality', 'PRODUCE', 'Reader + assets', 'DELIVER', 'Readback + evidence', 'MANAGED'],
      notice: 'Managed Services is the hands-on production lane · exact work remains bound to source, scope, and acceptance',
      outcomes: [
        ['01', 'Source preparation', 'Review unsupported, image-heavy, fragmented, inconsistent, or technically difficult source material.'],
        ['02', 'Remediation', 'Repair structure, sequencing, readability, accessibility, metadata, links, and publication-ready output by scope.'],
        ['03', 'Migration', 'Assess and move legacy publications, libraries, destinations, domains, links, and version history.'],
        ['04', 'Catalog production', 'Coordinate page-heavy, multi-title, recurring, commerce-ready, or institutional publication work.'],
        ['05', 'Custom delivery', 'Configure approved domains, readers, downloads, calls to action, lead paths, and related integrations.'],
        ['06', 'Launch and acceptance', 'Verify the destination, preserve evidence, and close the work against explicit acceptance criteria.']
      ],
      audiences: [
        ['AUTHORS & ESTATES', 'Recover and package the work', 'Prepare manuscripts, archives, legacy PDFs, image collections, companion materials, and editions.', 'mailto:contact@crownthrive.com?subject=Author%20Managed%20Publication'],
        ['PUBLISHERS & AGENCIES', 'Move complex catalogs', 'Coordinate multi-title production, migrations, client requirements, release sequencing, and destinations.', 'mailto:contact@crownthrive.com?subject=Publisher%20Managed%20Catalog'],
        ['EDUCATION & MINISTRY', 'Prepare usable learning assets', 'Remediate workbooks, curricula, guides, sermon resources, manuals, and family material.', 'mailto:contact@crownthrive.com?subject=Education%20or%20Ministry%20Managed%20Publishing'],
        ['EVENT & MEDIA TEAMS', 'Hit the launch window', 'Produce programs, playbills, magazines, sponsor packages, press kits, and archives against a deadline.', 'mailto:contact@crownthrive.com?subject=Event%20or%20Media%20Managed%20Publishing'],
        ['BUSINESSES & INSTITUTIONS', 'Package evidence and opportunity', 'Prepare impact reports, proposals, catalogs, procurement packages, investor material, and resources.', 'mailto:contact@crownthrive.com?subject=Institutional%20Managed%20Publishing'],
        ['CULTURAL & COMMUNITY BRANDS', 'Preserve identity while scaling', 'Build publication experiences that respect voice, audience, rights, context, and long-term reuse.', 'mailto:contact@crownthrive.com?subject=Cultural%20Go%20Flipbooks%20Managed%20Publishing']
      ],
      workflow: [
        ['01', 'Choose or request scope', 'Select a published package or submit a larger program for PentaGreen routing.'],
        ['02', 'Confirm the job', 'Define the source, result, deadline, revisions, destinations, integrations, and acceptance criteria.'],
        ['03', 'Transfer securely', 'Provide the best available authorized files and required access through restricted intake.'],
        ['04', 'Prepare and produce', 'Execute the approved remediation, migration, design, configuration, or production work.'],
        ['05', 'Review against scope', 'Compare the deliverable with the agreed acceptance criteria and correct scoped defects.'],
        ['06', 'Launch and close', 'Verify the destination, preserve delivery evidence, and route ongoing needs to Standard, Static, or PRO.']
      ],
      faq: [
        ['Does buying a package guarantee every requested feature?', 'No. The package activates a managed production corridor at the published scope. Exact features, source condition, revisions, domains, integrations, deadlines, and acceptance criteria are confirmed during intake.'],
        ['What files can I bring?', 'PDF, EPUB, DOCX, PPTX, ZIP, common images, and related source materials can be reviewed. Better originals reduce avoidable remediation, but difficult sources are the reason this lane exists.'],
        ['Can CrownThrive migrate an existing publication library?', 'Yes, by scope. Migration begins with inventory, rights, source availability, destinations, links, domains, version history, and current provider-state review.'],
        ['Do page ranges include unlimited revisions?', 'No. Page ranges guide package selection. Revision rounds, redesign, content changes, data entry, integrations, and expanded deliverables remain subject to confirmed scope and change control.'],
        ['Can Managed Services lead into Standard, Static, or PRO?', 'Yes. Once the source and operating model are ready, the result can route to Standard hosted delivery, a licensed Static deployment, or recurring PRO operations.'],
        ['What is the Major Update product?', 'It is a separate active Go Flipbooks service for substantial content, layout, or functionality changes. It appears with the managed offers when provider checkout is active.'],
        ['What if the project exceeds the largest public package?', 'Request custom scope. PentaGreen routes the program based on volume, complexity, deadlines, destinations, integrations, and operating requirements rather than forcing it into a smaller package.']
      ],
      closing: ['The difficult source can still move', 'Turn complexity into a defined production job.', 'Choose a published managed scope or describe the larger program once. CrownThrive will route the work to the correct production corridor.', 'Choose Managed Services', '#offers']
    }
  });

  const laneCards = [
    {
      key: 'standard', index: '01', label: 'DIRECT HOSTED', title: 'Standard',
      copy: 'For substantially ready content that needs a hosted interactive reader, delivery, commerce, and measurement path.',
      bullets: ['Authors, educators, ministries, founders', 'No arbitrary platform publication limit', 'Live setup and managed-support offers'],
      href: '/go-flipbooks/standard'
    },
    {
      key: 'static', index: '02', label: 'LICENSED CONTROL', title: 'Static / Self-Hosted',
      copy: 'For teams that need approved deployment custody, infrastructure control, or client and white-label rights by exact scope.',
      bullets: ['Agencies, institutions, archives, developers', 'Entity-, version-, and use-bound licensing', 'No public license manufactured without scope'],
      href: '/go-flipbooks/static'
    },
    {
      key: 'pro', index: '03', label: 'API-POWERED', title: 'PRO',
      copy: 'For recurring publication programs that need controlled API operations, leads, analytics, readback, and lifecycle management.',
      bullets: ['Publishers, agencies, media, institutions', 'Provider credentials remain server-side', 'Paid capacity and slot availability required'],
      href: '/go-flipbooks/pro'
    },
    {
      key: 'managed', index: '04', label: 'DONE FOR YOU', title: 'Managed Services',
      copy: 'For difficult sources, remediation, migration, custom configuration, deadline-driven production, and direct execution.',
      bullets: ['Authors, publishers, agencies, institutions', 'Defined source, scope, changes, and acceptance', 'Published packages plus custom routing'],
      href: '/go-flipbooks/managed'
    }
  ];

  const fitOptions = [
    ['standard', 'A finished publication', 'I need a credible hosted reader and direct publication path.', 'Go Flipbooks Standard', 'A substantially ready publication needs secure intake, hosted production, and a usable reader destination.', '/go-flipbooks/standard'],
    ['static', 'Deployment custody', 'My organization needs to host or integrate the reader itself.', 'Go Flipbooks Static / Self-Hosted', 'You need an exact entity-, version-, deployment-, and use-bound infrastructure license.', '/go-flipbooks/static'],
    ['pro', 'Recurring publication operations', 'We publish repeatedly or across clients, brands, or departments.', 'Go Flipbooks PRO / API', 'The work benefits from controlled API creation, configuration, publishing, leads, analytics, readback, and lifecycle operations.', '/go-flipbooks/pro'],
    ['managed', 'A difficult source or deadline', 'The content needs repair, migration, production, or hands-on execution.', 'Go Flipbooks Managed Services', 'CrownThrive should directly prepare, remediate, configure, produce, and verify the publication under a defined scope.', '/go-flipbooks/managed'],
    ['standard', 'A small publication catalog', 'We have several ready publications but do not need API operations.', 'Go Flipbooks Standard', 'Use Standard production scope for ready titles; the platform itself has no arbitrary publication ceiling.', '/go-flipbooks/standard'],
    ['pro', 'Leads and analytics are core', 'Publication behavior must feed growth and operating decisions.', 'Go Flipbooks PRO / API', 'PRO is the stronger fit when governed lead capture, analytics, campaign actions, and recurring lifecycle work are central.', '/go-flipbooks/pro']
  ];

  const comparisonRows = [
    ['Ready source to hosted interactive reader', 'Best fit', 'Supported by licensed deployment', 'Included', 'Done for you'],
    ['Platform publication-count ceiling', 'No arbitrary limit', 'No arbitrary limit', 'Provider capacity controlled', 'Depends on selected rail'],
    ['Customer controls hosting environment', 'No', 'Best fit', 'Provider-managed', 'By project scope'],
    ['API create, update, publish, and readback', 'Not core', 'Customer integration only', 'Best fit', 'By project scope'],
    ['Lead and analytics configuration', 'Optional by scope', 'Customer-operated', 'Managed', 'By project scope'],
    ['Source remediation and migration', 'Limited', 'Not included by default', 'Not included by default', 'Best fit'],
    ['Ongoing lifecycle operations', 'Managed add-on', 'Separate support entitlement', 'Managed by scope', 'By agreement'],
    ['Public checkout', 'Active offers', 'Written scope required', 'Active implementation offer', 'Active packages'],
    ['Best for', 'Direct launches and ready catalogs', 'Infrastructure and deployment custody', 'Recurring publication programs', 'Difficult production and direct execution']
  ];

  const offerLabels = {
    standard: {
      '2900|one_time|': ['Standard Launch', 'One-publication production activation', ['One eligible publication in this order', 'Hosted interactive reader', 'Secure customer intake', 'CHLOM edition and delivery evidence'], 'Launch one publication'],
      '4900|recurring|month': ['Standard Managed', 'Monthly hosting and lifecycle add-on', ['Managed hosting', 'Approved publication updates', 'Availability monitoring', 'Matching setup entitlement required'], 'Add managed support'],
      '9900|one_time|': ['Standard Studio', 'Up to five-publication production activation', ['Up to five eligible publications in this order', 'Reusable publication settings', 'Hosted delivery', 'One authorized organization scope'], 'Choose Studio'],
      '24900|one_time|': ['Standard Commerce', 'Up to twenty-five-publication production activation', ['Up to twenty-five eligible publications in this order', 'Commerce-ready reader settings', 'PentaAds inventory readiness', 'CrownLytics measurement readiness'], 'Choose Commerce']
    },
    pro: {
      '29700|one_time|': ['PRO Implementation', 'API-powered managed publication implementation', ['Customer and entitlement binding', 'Controlled publication operations', 'Reader, lead, and analytics configuration', 'Provider readback and lifecycle route'], 'Activate PRO']
    },
    managed: {
      '10000|one_time|': ['Essential Service', 'Focused managed publication scope', ['Secure source intake', 'Scope and source review', 'Direct production routing', 'Delivery evidence'], 'Book Essential'],
      '20000|one_time|': ['Growth Service', 'Expanded managed production scope', ['Larger publication scope', 'Production coordination', 'Quality and delivery review', 'Acceptance checklist'], 'Book Growth'],
      '30000|one_time|': ['Commerce Service', 'Managed commerce-ready publication scope', ['Catalog and conversion configuration', 'PentaAds surface planning', 'Governed production', 'Launch and delivery evidence'], 'Book Commerce'],
      '50000|one_time|': ['Full Managed Service', 'Broad complex-publication scope', ['Complex catalog or migration routing', 'Managed configuration', 'Acceptance and defect closure', 'Full evidence package'], 'Book Full Managed'],
      '20000|major-update|': ['Major Update', 'Substantial content, layout, or functionality update', ['Existing Go Flipbooks publication', 'Major approved changes', 'Lifecycle-safe update path', 'Provider and delivery readback'], 'Book Major Update']
    }
  };

  const routeAliases = new Map([
    ['/go-flipbooks', 'overview'],
    ['/go-flipbooks/', 'overview'],
    ['/marketplace/go-flipbooks', 'overview'],
    ['/marketplace/go-flipbooks/', 'overview'],
    ['/go-flipbooks/standard', 'standard'],
    ['/go-flipbooks/standard/', 'standard'],
    ['/go-flipbooks/static', 'static'],
    ['/go-flipbooks/static/', 'static'],
    ['/go-flipbooks/self-hosted', 'static'],
    ['/go-flipbooks/self-hosted/', 'static'],
    ['/go-flipbooks/pro', 'pro'],
    ['/go-flipbooks/pro/', 'pro'],
    ['/go-flipbooks/api', 'pro'],
    ['/go-flipbooks/api/', 'pro'],
    ['/go-flipbooks/managed', 'managed'],
    ['/go-flipbooks/managed/', 'managed'],
    ['/go-flipbooks/managed-services', 'managed'],
    ['/go-flipbooks/managed-services/', 'managed']
  ]);

  let currentLane = routeAliases.get(location.pathname) || 'overview';
  let catalogProducts = [];
  let publishingProducts = [];

  function qs(selector, root = document) {
    return root.querySelector(selector);
  }

  function qsa(selector, root = document) {
    return [...root.querySelectorAll(selector)];
  }

  function escapeHtml(value) {
    return String(value ?? '').replace(/[&<>"']/g, (character) => ({
      '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#039;'
    }[character]));
  }

  function safeHref(value) {
    const raw = String(value || '').trim();
    if (!raw) return null;
    if (raw.startsWith('#')) return raw;
    if (raw.startsWith('/') && !raw.startsWith('//')) return raw;
    if (/^mailto:[^\s@]+@[^\s@]+/i.test(raw)) return raw;
    try {
      const url = new URL(raw);
      if (url.protocol === 'https:' && url.hostname === CHECKOUT_HOST) return url.href;
    } catch {
      return null;
    }
    return null;
  }

  function formatMoney(amountMinor, currency = 'USD') {
    const amount = Number(amountMinor || 0) / 100;
    try {
      return new Intl.NumberFormat('en-US', {
        style: 'currency',
        currency: String(currency || 'USD').toUpperCase(),
        maximumFractionDigits: amount % 1 ? 2 : 0
      }).format(amount);
    } catch {
      return `$${amount.toFixed(amount % 1 ? 2 : 0)}`;
    }
  }

  function cadence(offer) {
    if (offer.billing_type === 'recurring') {
      if (offer.recurring_interval === 'month') return 'per month';
      if (offer.recurring_interval === 'year') return 'per year';
      return offer.recurring_interval ? `per ${offer.recurring_interval}` : 'subscription';
    }
    return 'one time';
  }

  function offerSignature(offer) {
    return [
      Number(offer?.amount_minor || 0),
      String(offer?.billing_type || 'one_time'),
      String(offer?.recurring_interval || '')
    ].join('|');
  }

  function normalizeOffer(offer) {
    const href = safeHref(offer?.checkout_url);
    if (!href || !href.startsWith('https://buy.stripe.com/')) return null;
    return {
      amount_minor: Number(offer?.amount_minor || 0),
      currency: String(offer?.currency || 'USD').toUpperCase(),
      billing_type: String(offer?.billing_type || 'one_time'),
      recurring_interval: offer?.recurring_interval || null,
      checkout_url: href,
      provider_price_id: offer?.provider_price_id || null,
      provider_payment_link_id: offer?.provider_payment_link_id || null
    };
  }

  function normalizeProduct(product) {
    const seen = new Set();
    const offers = (Array.isArray(product?.offers) ? product.offers : [])
      .map(normalizeOffer)
      .filter(Boolean)
      .filter((offer) => {
        const signature = offerSignature(offer);
        if (seen.has(signature)) return false;
        seen.add(signature);
        return true;
      })
      .sort((a, b) => a.amount_minor - b.amount_minor || cadence(a).localeCompare(cadence(b)));

    return {
      name: String(product?.name || ''),
      summary: String(product?.summary || product?.subtitle || ''),
      provider_product_id: product?.provider_product_id || product?.catalog_key || null,
      public_state: product?.public_state || null,
      checkout_state: product?.checkout_state || null,
      offers
    };
  }

  function setText(selector, value) {
    const node = qs(selector);
    if (node) node.textContent = String(value ?? '');
  }

  function setHtml(selector, value) {
    const node = qs(selector);
    if (node) node.innerHTML = value;
  }

  function setLink(selector, link) {
    const node = qs(selector);
    if (!node || !link) return;
    node.textContent = link.label;
    node.setAttribute('href', link.href);
  }

  function renderBase() {
    const config = lanes[currentLane];
    document.body.dataset.gfLane = currentLane;
    document.title = config.title;

    const canonical = qs('link[rel="canonical"]');
    if (canonical) canonical.href = new URL(config.path, location.origin).href;
    const description = qs('meta[name="description"]');
    if (description) description.content = config.description;
    const ogTitle = qs('meta[property="og:title"]');
    if (ogTitle) ogTitle.content = config.title;
    const ogDescription = qs('meta[property="og:description"]');
    if (ogDescription) ogDescription.content = config.description;
    const ogUrl = qs('meta[property="og:url"]');
    if (ogUrl) ogUrl.content = new URL(config.path, location.origin).href;

    setText('#crumb-current', config.crumb);
    setText('#hero-eyebrow', config.eyebrow);
    setHtml('#hero-title', config.hero);
    setText('#hero-lede', config.lede);
    setLink('#hero-primary', config.primary);
    setLink('#hero-secondary', config.secondary);
    setText('#notice-copy', config.notice);

    const proof = qs('#hero-proof');
    if (proof) proof.innerHTML = config.proof.map((item) => `<span>${escapeHtml(item)}</span>`).join('');

    const visual = config.visual;
    setText('#orbit-a-title', visual[0]); setText('#orbit-a-copy', visual[1]);
    setText('#orbit-b-title', visual[2]); setText('#orbit-b-copy', visual[3]);
    setText('#orbit-c-title', visual[4]); setText('#orbit-c-copy', visual[5]);
    setText('#orbit-d-title', visual[6]); setText('#orbit-d-copy', visual[7]);
    setText('#visual-core-label', visual[8]);

    qsa('[data-lane-link]').forEach((link) => {
      if (link.dataset.laneLink === currentLane || (currentLane === 'overview' && link.dataset.laneLink === 'overview')) {
        link.setAttribute('aria-current', 'page');
      } else {
        link.removeAttribute('aria-current');
      }
    });

    const headerCta = qs('#header-cta');
    if (headerCta) {
      if (currentLane === 'static') {
        headerCta.textContent = 'Request license scope';
        headerCta.href = 'mailto:contact@crownthrive.com?subject=Go%20Flipbooks%20Static%20or%20Self-Hosted%20License';
      } else if (currentLane === 'overview') {
        headerCta.textContent = 'See live offers';
        headerCta.href = '#offers';
      } else {
        headerCta.textContent = currentLane === 'managed' ? 'Choose a package' : `Choose ${currentLane === 'pro' ? 'PRO' : 'Standard'}`;
        headerCta.href = '#offers';
      }
    }

    renderLaneCards();
    renderOutcomes(config);
    renderFitGuide();
    renderAudiences(config);
    renderWorkflow(config);
    renderComparison();
    renderFaq(config);
    renderClosing(config);
    renderSticky(config);
  }

  function renderLaneCards() {
    const root = qs('#lane-cards');
    if (!root) return;
    root.innerHTML = laneCards.map((card) => `
      <article class="lane-card${currentLane === card.key ? ' is-current' : ''}" data-lane="${escapeHtml(card.key)}">
        <span class="lane-card-index">${escapeHtml(card.index)}</span>
        <span class="lane-card-badge">${escapeHtml(card.label)}</span>
        <h3>${escapeHtml(card.title)}</h3>
        <p>${escapeHtml(card.copy)}</p>
        <ul>${card.bullets.map((item) => `<li>${escapeHtml(item)}</li>`).join('')}</ul>
        <a href="${escapeHtml(card.href)}">${currentLane === card.key ? 'You are viewing this lane' : `Explore ${escapeHtml(card.title)}`} →</a>
      </article>
    `).join('');

    if (currentLane !== 'overview') {
      setText('#lanes-eyebrow', 'Your lane in context');
      setText('#lanes-title', 'Move between operating models without losing the publication history.');
      setText('#lanes-copy', 'Use Standard, Static, PRO, or Managed only where it is the correct operational fit. A higher-complexity lane is not automatically a better lane.');
    }
  }

  function renderOutcomes(config) {
    const root = qs('#outcome-grid');
    if (!root) return;
    root.innerHTML = config.outcomes.map(([index, title, copy]) => `
      <article class="outcome-card"><span>${escapeHtml(index)}</span><h3>${escapeHtml(title)}</h3><p>${escapeHtml(copy)}</p></article>
    `).join('');
    if (currentLane !== 'overview') {
      setText('#outcomes-eyebrow', `${config.crumb} outcomes`);
      setText('#outcomes-title', `What ${config.crumb} changes for the buyer.`);
      setText('#outcomes-copy', 'The page focuses on outcomes, operational boundaries, and the next action appropriate to this lane.');
    }
  }

  function renderFitGuide() {
    const root = qs('#fit-options');
    if (!root) return;
    root.innerHTML = fitOptions.map(([key, title, copy], index) => `
      <button class="fit-option" type="button" data-fit="${escapeHtml(key)}" data-fit-index="${index}" aria-pressed="${index === 0 ? 'true' : 'false'}">
        <strong>${escapeHtml(title)}</strong><small>${escapeHtml(copy)}</small>
      </button>
    `).join('');
    root.addEventListener('click', (event) => {
      const button = event.target.closest('[data-fit-index]');
      if (!button) return;
      const option = fitOptions[Number(button.dataset.fitIndex)];
      if (!option) return;
      qsa('[data-fit-index]', root).forEach((candidate) => candidate.setAttribute('aria-pressed', String(candidate === button)));
      setText('#fit-title', option[3]);
      setText('#fit-copy', option[4]);
      const link = qs('#fit-link');
      if (link) {
        link.textContent = `Explore ${option[3].replace('Go Flipbooks ', '')}`;
        link.href = option[5];
      }
    });

    const relevant = fitOptions.findIndex((option) => option[0] === (currentLane === 'overview' ? 'standard' : currentLane));
    const selected = qsa('[data-fit-index]', root)[Math.max(relevant, 0)];
    selected?.click();
  }

  function renderAudiences(config) {
    const root = qs('#audience-grid');
    if (!root) return;
    root.innerHTML = config.audiences.map(([label, title, copy, href]) => `
      <article class="audience-card">
        <span>${escapeHtml(label)}</span><h3>${escapeHtml(title)}</h3><p>${escapeHtml(copy)}</p>
        <a href="${escapeHtml(safeHref(href) || '/go-flipbooks')}">Follow this route →</a>
      </article>
    `).join('');
    if (currentLane !== 'overview') {
      setText('#audiences-eyebrow', `${config.crumb} audiences`);
      setText('#audiences-title', `Who gets the most value from ${config.crumb}.`);
      setText('#audiences-copy', 'The same platform serves different sectors, but the message and operating outcome remain specific to the buyer.');
    }
  }

  function renderWorkflow(config) {
    const root = qs('#workflow-grid');
    if (!root) return;
    root.innerHTML = config.workflow.map(([index, title, copy]) => `
      <article class="workflow-card"><span>${escapeHtml(index)}</span><h3>${escapeHtml(title)}</h3><p>${escapeHtml(copy)}</p></article>
    `).join('');
    if (currentLane !== 'overview') {
      setText('#workflow-eyebrow', `${config.crumb} workflow`);
      setText('#workflow-title', `How ${config.crumb} moves from decision to verified outcome.`);
      setText('#workflow-copy', 'Payment and intent never replace authority, execution, provider readback, or delivery acceptance.');
    }
  }

  function renderComparison() {
    const root = qs('#comparison-body');
    if (!root) return;
    root.innerHTML = comparisonRows.map((row) => `
      <tr>${row.map((cell) => {
        const best = /best fit|active offers|active implementation|active packages|no arbitrary limit/i.test(cell);
        const limited = /no$|limited|not core|not included|written scope|required/i.test(cell);
        return `<td class="${best ? 'best' : limited ? 'limited' : ''}">${escapeHtml(cell)}</td>`;
      }).join('')}</tr>
    `).join('');
  }

  function renderFaq(config) {
    const root = qs('#faq-list');
    if (!root) return;
    root.innerHTML = config.faq.map(([question, answer], index) => `
      <details class="faq"${index === 0 ? ' open' : ''}><summary>${escapeHtml(question)}</summary><div class="faq-answer">${escapeHtml(answer)}</div></details>
    `).join('');
    if (currentLane !== 'overview') {
      setText('#faq-eyebrow', `${config.crumb} FAQ`);
      setText('#faq-title', `Clear boundaries for ${config.crumb}.`);
      setText('#faq-copy', 'These answers reflect the current lane and live catalog posture.');
    }
  }

  function renderClosing(config) {
    const [eyebrow, title, copy, label, href] = config.closing;
    setText('#closing-eyebrow', eyebrow);
    setText('#closing-title', title);
    setText('#closing-copy', copy);
    const primary = qs('#closing-primary');
    if (primary) { primary.textContent = label; primary.href = href; }
    const secondary = qs('#closing-secondary');
    if (secondary) {
      secondary.textContent = currentLane === 'overview' ? 'Request custom scope' : 'Ask a scope question';
      secondary.href = `mailto:${CONTACT}?subject=${encodeURIComponent(`Go Flipbooks ${config.crumb} Scope`)}`;
    }
  }

  function renderSticky(config) {
    setText('#sticky-kicker', config.eyebrow);
    setText('#sticky-title', currentLane === 'overview' ? 'Choose your publishing lane' : config.crumb);
    const link = qs('#sticky-link');
    if (!link) return;
    if (currentLane === 'static') {
      link.textContent = 'Request scope';
      link.href = config.primary.href;
    } else if (currentLane === 'overview') {
      link.textContent = 'Find your fit';
      link.href = '#lanes';
    } else {
      link.textContent = currentLane === 'managed' ? 'Choose a package' : `Choose ${currentLane === 'pro' ? 'PRO' : 'Standard'}`;
      link.href = '#offers';
    }
  }

  function publishingCatalog(products) {
    return products.filter((product) =>
      /^Go Flipbooks\b/i.test(product.name) ||
      /^Go-Flipbook\b/i.test(product.name)
    );
  }

  function productForLane(key) {
    if (key === 'standard') return publishingProducts.find((product) => product.name === 'Go Flipbooks Standard') || null;
    if (key === 'pro') return publishingProducts.find((product) => product.name === 'Go Flipbooks PRO') || null;
    if (key === 'managed') return publishingProducts.find((product) => product.name === 'Go Flipbooks Managed Services') || null;
    return null;
  }

  function majorUpdateProduct() {
    return publishingProducts.find((product) => /Major Update/i.test(product.name)) || null;
  }

  async function loadCatalog() {
    const response = await fetch(CATALOG_ENDPOINT, { cache: 'no-store', headers: { accept: 'application/json' } });
    if (!response.ok) throw new Error(`catalog_${response.status}`);
    const payload = await response.json();
    if (payload?.status !== 'LIVE' || !Array.isArray(payload.products)) throw new Error('catalog_not_live');

    catalogProducts = payload.products.map(normalizeProduct);
    publishingProducts = publishingCatalog(catalogProducts);
    const offerCount = publishingProducts.reduce((total, product) => total + product.offers.length, 0);

    setText('#metric-products', publishingProducts.length);
    setText('#metric-offers', offerCount);
    setText('#live-signal-copy', `${publishingProducts.length} products · ${offerCount} checkouts`);

    renderOffers();
  }

  function status(message, ok = true) {
    const root = qs('#catalog-status');
    if (!root) return;
    root.classList.toggle('is-hold', !ok);
    const strong = qs('strong', root);
    const small = qs('small', root);
    if (strong) strong.textContent = message;
    if (small) small.textContent = ok ? 'Live provider readback' : 'No pass state manufactured';
  }

  function inferOfferContent(key, product, offer) {
    let signature = offerSignature(offer);
    if (product?.name && /Major Update/i.test(product.name)) signature = `${offer.amount_minor}|major-update|`;
    const mapped = offerLabels[key]?.[signature];
    if (mapped) return mapped;

    const defaultName = key === 'pro' ? 'PRO Implementation' : key === 'managed' ? 'Managed Service' : 'Standard Offer';
    return [
      defaultName,
      product?.summary || `${lanes[key]?.crumb || 'Go Flipbooks'} active marketplace offer`,
      ['Active provider product', 'Active provider price', 'Active Stripe Payment Link', 'CHLOM and PentaGreen boundaries'],
      `Choose ${defaultName}`
    ];
  }

  function createOfferCard(key, product, offer, index, total) {
    const [name, summary, features, cta] = inferOfferContent(key, product, offer);
    const article = document.createElement('article');
    article.className = `offer-card${index === Math.min(2, total - 1) ? ' is-featured' : ''}`;

    if (article.classList.contains('is-featured')) {
      const badge = document.createElement('span');
      badge.className = 'offer-card-badge';
      badge.textContent = key === 'pro' ? 'API-powered implementation' : key === 'managed' ? 'Popular managed scope' : 'Strong catalog fit';
      article.append(badge);
    }

    const kicker = document.createElement('small');
    kicker.textContent = `${lanes[key].crumb.toUpperCase()} · LIVE OFFER`;

    const heading = document.createElement('h3');
    heading.textContent = name;

    const description = document.createElement('p');
    description.textContent = summary;

    const price = document.createElement('div');
    price.className = 'offer-price';
    price.append(document.createTextNode(formatMoney(offer.amount_minor, offer.currency)));
    const cadenceNode = document.createElement('span');
    cadenceNode.textContent = cadence(offer);
    price.append(cadenceNode);

    const list = document.createElement('ul');
    for (const feature of features) {
      const item = document.createElement('li');
      item.textContent = feature;
      list.append(item);
    }

    const checkout = document.createElement('a');
    checkout.className = `button ${article.classList.contains('is-featured') ? 'button-primary' : 'button-secondary'}`;
    checkout.href = offer.checkout_url;
    checkout.target = '_blank';
    checkout.rel = 'noopener nofollow noreferrer';
    checkout.textContent = cta;
    checkout.setAttribute('aria-label', `${cta} for ${formatMoney(offer.amount_minor, offer.currency)} ${cadence(offer)}`);

    const fineprint = document.createElement('p');
    fineprint.className = 'fineprint';
    fineprint.textContent = key === 'standard'
      ? 'The quantity describes this production order, not a permanent Standard platform limit.'
      : key === 'pro'
        ? 'Provider capacity is confirmed before assignment. No recurring charge is implied unless separately published or scoped.'
        : 'Final deliverables, revisions, integrations, and acceptance criteria are confirmed during managed intake.';

    article.append(kicker, heading, description, price, list, checkout, fineprint);
    return article;
  }

  function renderStaticScope(root) {
    root.className = 'offer-grid is-empty';
    root.innerHTML = '';
    const article = document.createElement('article');
    article.className = 'scope-card';

    const copy = document.createElement('div');
    const kicker = document.createElement('p');
    kicker.className = 'eyebrow';
    kicker.textContent = 'WRITTEN LICENSE SCOPE REQUIRED';
    const title = document.createElement('h3');
    title.textContent = 'Static deployment is not a generic checkout.';
    const description = document.createElement('p');
    description.textContent = 'The legal entity, environment, source or package access, domains, internal or client use, modification, support, white-label, resale, and version boundaries must be explicit before a license is issued.';
    const list = document.createElement('ul');
    ['No arbitrary publication-count ceiling', 'CHLOM entity and version binding', 'Deployment and client rights stated separately', 'Source ownership never implied'].forEach((text) => {
      const item = document.createElement('li');
      item.textContent = text;
      list.append(item);
    });
    copy.append(kicker, title, description, list);

    const link = document.createElement('a');
    link.className = 'button button-primary';
    link.href = `mailto:${CONTACT}?subject=${encodeURIComponent('Go Flipbooks Static or Self-Hosted License')}`;
    link.textContent = 'Request exact license scope';

    article.append(copy, link);
    root.append(article);
    status('No public Static checkout published · written scope required', true);
    setText('#offers-title', 'License the exact deployment—not a vague bundle of rights.');
    setText('#offers-copy', 'The absence of a generic checkout is intentional. Static and self-hosted rights require exact entity, environment, version, use, and support boundaries.');
    setText('#offer-boundary', 'No source ownership, modification, client deployment, sublicense, resale, OEM, white-label, redistribution, or future-version right is granted unless the written CHLOM license states it.');
  }

  function renderOverviewOffers(root) {
    root.className = 'offer-grid';
    root.innerHTML = '';

    const keys = ['standard', 'pro', 'managed'];
    for (const key of keys) {
      const product = productForLane(key);
      if (!product || !product.offers.length) continue;
      const article = document.createElement('article');
      article.className = 'offer-card';

      const kicker = document.createElement('small');
      kicker.textContent = `${lanes[key].crumb.toUpperCase()} · ${product.offers.length} ACTIVE OPTION${product.offers.length === 1 ? '' : 'S'}`;

      const title = document.createElement('h3');
      title.textContent = lanes[key].crumb;

      const description = document.createElement('p');
      description.textContent = lanes[key].lede;

      const amounts = product.offers.map((offer) => offer.amount_minor);
      const price = document.createElement('div');
      price.className = 'offer-price';
      price.append(document.createTextNode(`From ${formatMoney(Math.min(...amounts), product.offers[0].currency)}`));
      const sub = document.createElement('span');
      sub.textContent = `${product.offers.length} verified checkout option${product.offers.length === 1 ? '' : 's'}`;
      price.append(sub);

      const list = document.createElement('ul');
      laneCards.find((card) => card.key === key)?.bullets.forEach((feature) => {
        const item = document.createElement('li');
        item.textContent = feature;
        list.append(item);
      });

      const link = document.createElement('a');
      link.className = 'button button-secondary';
      link.href = lanes[key].path;
      link.textContent = `Explore ${lanes[key].crumb}`;

      article.append(kicker, title, description, price, list, link);
      root.append(article);
    }

    const staticArticle = document.createElement('article');
    staticArticle.className = 'offer-card';
    staticArticle.innerHTML = `
      <small>STATIC / SELF-HOSTED · WRITTEN SCOPE</small>
      <h3>Licensed deployment control</h3>
      <p>For organizations that need infrastructure custody, internal deployment, approved client use, or a separately licensed white-label route.</p>
      <div class="offer-price">Scoped<span>No generic rights bundle</span></div>
      <ul><li>No arbitrary publication-count ceiling</li><li>Exact legal entity and version</li><li>Deployment rights separated from ownership</li><li>Support and updates by entitlement</li></ul>
      <a class="button button-secondary" href="/go-flipbooks/static">Explore Static / Self-Hosted</a>
    `;
    root.append(staticArticle);

    status(`${publishingProducts.length} active Go Flipbooks products · ${publishingProducts.reduce((sum, product) => sum + product.offers.length, 0)} checkout options`, true);
  }

  function renderOffers() {
    const root = qs('#offer-grid');
    if (!root) return;

    if (currentLane === 'overview') {
      renderOverviewOffers(root);
      return;
    }
    if (currentLane === 'static') {
      renderStaticScope(root);
      return;
    }

    const products = [];
    const primary = productForLane(currentLane);
    if (primary) products.push(primary);
    if (currentLane === 'managed') {
      const update = majorUpdateProduct();
      if (update) products.push(update);
    }

    const entries = products.flatMap((product) => product.offers.map((offer) => ({ product, offer })));
    root.className = `offer-grid${entries.length === 1 ? ' is-single' : ''}`;
    root.innerHTML = '';
    entries.forEach(({ product, offer }, index) => root.append(createOfferCard(currentLane, product, offer, index, entries.length)));

    if (!entries.length) {
      throw new Error(`${currentLane}_offers_missing`);
    }

    status(`${entries.length} active ${lanes[currentLane].crumb} checkout option${entries.length === 1 ? '' : 's'} verified`, true);
    setText('#offers-eyebrow', `Live ${lanes[currentLane].crumb} offers`);
    setText('#offers-title', currentLane === 'pro'
      ? 'Activate the published implementation—then bind capacity.'
      : currentLane === 'managed'
        ? 'Buy the production scope that matches the job.'
        : 'Choose the production scope included in this order.');
    setText('#offer-boundary', currentLane === 'standard'
      ? 'Standard/static reader capacity has no arbitrary platform publication limit. The offer quantities describe the publication-production work included in that order. Customer authority, source quality, CHLOM rights, fulfillment, and acceptance remain separate.'
      : currentLane === 'pro'
        ? 'The current catalog exposes a one-time PRO implementation offer. Provider-backed capacity, paid entitlement, exact publications, domains, integrations, ongoing service, and reserved slots are confirmed before activation.'
        : 'Managed packages activate a production corridor. Source condition, page volume, revisions, design, accessibility, domains, integrations, deadlines, and acceptance criteria can require revised or custom scope.');
  }

  function renderCatalogHold(error) {
    setText('#metric-products', 'HOLD');
    setText('#metric-offers', 'HOLD');
    setText('#live-signal-copy', 'Catalog readback unavailable');
    const root = qs('#offer-grid');
    if (root) {
      root.className = 'offer-grid is-empty';
      root.innerHTML = '';
      const article = document.createElement('article');
      article.className = 'scope-card';
      const copy = document.createElement('div');
      const kicker = document.createElement('p');
      kicker.className = 'eyebrow';
      kicker.textContent = 'LIVE PRICING HOLD';
      const title = document.createElement('h3');
      title.textContent = 'No checkout is being guessed.';
      const description = document.createElement('p');
      description.textContent = 'The live CrownThrive catalog could not be verified. The product education remains available, but the website will not substitute stale or invented pricing.';
      copy.append(kicker, title, description);
      const link = document.createElement('a');
      link.className = 'button button-secondary';
      link.href = `mailto:${CONTACT}?subject=${encodeURIComponent(`Go Flipbooks ${lanes[currentLane].crumb} Catalog Readback`)}`;
      link.textContent = 'Contact CrownThrive';
      article.append(copy, link);
      root.append(article);
    }
    status(`Live catalog hold: ${String(error?.message || error)}`, false);
  }

  function setupMenu() {
    const button = qs('[data-menu-button]');
    const nav = qs('[data-mobile-nav]');
    if (!button || !nav) return;
    button.addEventListener('click', () => {
      const open = button.getAttribute('aria-expanded') !== 'true';
      button.setAttribute('aria-expanded', String(open));
      nav.classList.toggle('open', open);
    });
    nav.addEventListener('click', (event) => {
      if (!event.target.closest('a')) return;
      button.setAttribute('aria-expanded', 'false');
      nav.classList.remove('open');
    });
  }

  function setupYear() {
    qsa('[data-year]').forEach((node) => { node.textContent = String(new Date().getFullYear()); });
  }

  function setupPlanQuery() {
    const plan = new URLSearchParams(location.search).get('plan');
    if (!plan || currentLane === 'overview') return;
    window.setTimeout(() => {
      const match = qsa('.offer-card').find((card) => card.textContent.toLowerCase().includes(plan.toLowerCase()));
      if (match) {
        match.scrollIntoView({ behavior: matchMedia('(prefers-reduced-motion: reduce)').matches ? 'auto' : 'smooth', block: 'center' });
        match.classList.add('is-featured');
      }
    }, 600);
  }

  renderBase();
  setupMenu();
  setupYear();
  loadCatalog()
    .then(setupPlanQuery)
    .catch(renderCatalogHold);
})();
