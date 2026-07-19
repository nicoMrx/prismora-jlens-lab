# Human Visualizer i18n inventory

This checklist scopes PR #1's final i18n pass. It intentionally covers the global shell, navigation, Human Visualizer, Understand card, and Build Week judge path only. Other laboratory panel internals remain scheduled for a follow-up PR.

## Global shell

- Header subtitle: `app.subtitle`
- Language selector label: `app.language`
- Refresh button: `app.refresh`
- Health badge online/offline copy: `control plane` / `plan de contrôle`, `app.offline`
- Security banner: `shell.securityLead`, `shell.securityText`
- Navigation: `nav.dashboard`, `nav.experiments`, `nav.registry`, `nav.campaign`, `nav.fleet`, `nav.runs`, `nav.inspector`, `nav.visualizer`, `nav.baseline`, `nav.causal`, `nav.compare`, `nav.claims`

## Human Visualizer static UI

- Panel title, description and badge: `visual.title`, `visual.description`, `visual.badge`
- Source card: `visual.choose`, `visual.obsA`, `visual.obsB`, `visual.swap`, `visual.compareArchived`, `understand.demo`
- Probe folder path: `visual.probeSummary`, `visual.probeHelp`, `visual.loadProbe`, `visual.compareLocal`
- Controls: `visual.controls`, `visual.lens`, `visual.positions`, `visual.scope.prompt`, `visual.scope.generated`, `visual.scope.all`, `visual.metric`, `visual.metric.strict`, `visual.metric.top1`, `visual.metric.jaccard`, `visual.redraw`
- Understand card: `understand.badge`, `understand.empty`, `understand.errorTitle`, `understand.retry`
- Output cards and chart sections: `visual.output`, `visual.outputEmpty`, `visual.where`, `visual.whereHelp`, `visual.selectedCell`, `visual.clickMap`, `visual.trajectory`, `visual.trajectoryHelp`, `visual.factual`, `visual.noComparison`, `visual.ruleLead`, `visual.ruleText`

## Human Visualizer dynamic UI

- Status/error messages: `status.comparisonLoaded`, `status.demoLoaded`, `status.loadingArtifacts`, `status.probeResults`, `error.noRuns`, `error.sameRuns`, `error.noLens`, `error.demoUnavailable`, `error.localLoadFirst`, `error.localDifferent`
- Summary cards: `visual.strictFirst`, `visual.top1First`, `visual.declaredLayers`, `visual.generatedOutputs`, `visual.alignedTokens`, `visual.sharedLayers`, `visual.none`, `visual.identical`, `visual.different`
- Charts/cells/tables: `visual.layer`, `visual.alignedTokensArrow`, `visual.declaredLayer`, `visual.cellRate`, `visual.strictLegend`, `visual.top1Legend`, `visual.heatLegend`, `visual.metricStrictLabel`, `visual.metricJaccardLabel`, `visual.cellMissing`, `visual.prompt`, `visual.generated`, `visual.rank`, `visual.state`, `visual.same`, `visual.missing`
- Factual reading: `visual.noStrict`, `visual.firstDiff`, `visual.declaredCoincides`, `visual.beforeDeclared`, `visual.afterDeclared`, `visual.declaredNoVisible`, `visual.noDeclared`, `visual.surfaceSame`, `visual.surfaceDifferent`, `visual.maxRow`, `visual.caution`
- Intervention display: `visual.syntheticIntervention`, `visual.noIntervention`
