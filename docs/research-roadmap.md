# Make a changed room explainable

[中文](research-roadmap.zh-CN.md) · [Practical uses](use-cases.md) · [Current evidence](validation.md)

A short missing wall can join several rooms. An outer-wall gap can make the interior disappear into the excluded background. Improving this behavior would be valuable to anyone building a drawing review or spatial analysis tool: a model update should come with an explanation of which spaces changed and why they need review.

The current release work adds a way to inspect region changes. The training and annotation work below is a proposed research program, not a completed experiment or an accuracy claim. The published [validation snapshot](validation.md) remains the source of measured recognition results.

## What the change report can establish

For aligned instance maps, comparison describes unchanged or reshaped regions, splits, merges, many-to-many reorganization, and regions that appear or disappear. It also tracks pixels moving between regions and label 0. Region numbers are identifiers; renumbering alone should not be treated as a geometry change.

These events help locate a regression. They do not establish which version is correct. Label 0 includes walls, exterior, and filtered space, so transfer to background is evidence to inspect, not an automatic diagnosis of exterior leakage. Likewise, an overlap-based split is not proof that a true room was split. The current rule counts every positive pixel overlap without a tolerance; a small boundary movement can therefore create a split or reorganization event. The report records the overlap and alignment policy. Human truth is needed to call a change an error.

This is the first useful layer of instance stability: explain how regions correspond between two results. Persistent IDs across a document's edit history, registration of shifted drawings, and automatic repair remain separate problems.

## The difficult part is deciding what should connect

| Problem | Evidence needed | How to test it |
| --- | --- | --- |
| Thin walls disappear | Wall masks at usable resolution and reviewed gap cases | Measure fine-wall recall alongside room merges and lost interiors |
| A gap is a door, an exterior opening, or a missed wall | Explicit opening labels and an agreed room-boundary policy | Score false closures and missed barriers separately; preserve the distinction between room partition and traversability |
| An open exterior loses indoor space | An independently supplied or predicted footprint, with its source recorded | Compare automatic, assisted, and truth-footprint diagnostic conditions separately |
| Small input changes rearrange instances | Registered paired inputs and reviewed region correspondence | Track splits, merges, background transfer, and many-to-many changes alongside accuracy |

[CubiCasa5K](https://arxiv.org/abs/1904.01920) provides dense floor-plan annotations and a multi-task research setting. Its labels still need an explicit mapping to the task here. In our existing loader, structural Wall includes annotated opening structures. A structural wall mask, a barrier used to delimit a room, and a traversable doorway are different targets. Define all three before training a loss to preserve their connections.

For footprints, record whether the source is an independent annotation, a prediction, or user input. A footprint derived from test room truth belongs only in an oracle diagnostic. It must not enter the automatic result unnoticed. A footprint also bounds the working area; it cannot recover all missing internal walls.

## A testable hypothesis: soft-clDice for wall continuity

Shit et al.'s [clDice, CVPR 2021](https://arxiv.org/abs/2003.07311), compares masks and their skeletons and proposes a differentiable soft-clDice loss for tubular networks. Its experiments concern structures such as vessels, neurons, and roads.

**Our hypothesis:** adding soft-clDice to the wall baseline may reduce gaps that merge or erase regions. This has not been tested here. It could also encourage unwanted connections across real openings, and an imperfect wall network is not covered by a blanket topology guarantee. Room instances, opening errors, and annotated connectivity must decide whether the adaptation helps.

The proposed ablation changes one training factor:

| Arm | Objective | Fixed across arms |
| --- | --- | --- |
| Baseline | BCE + Dice | Model, data, resolution, augmentations, padding policy, optimizer, learning-rate schedule, batch size, update count, paired seeds, and downstream partitioning |
| Candidate | BCE + Dice + a weighted soft-clDice term | The same settings; declare the loss weight and skeletonization iterations before final evaluation |

Use the same predetermined validation search budget and checkpoint-selection rule. Count every attempted run. Equal optimizer updates do not mean equal compute: record training time and peak memory because the extra loss costs work. Check valid-pixel handling around padding and crop boundaries before interpreting connectivity. The private legacy model has unknown training exposure and budget, so it can be a contextual reference, not the equal-budget control.

## Freeze the experiment before reading its answer

1. Freeze label definitions, training/validation groups, candidate settings, seed list, selection rule, and acceptance criteria. Keep all crops and augmentations from a source drawing together; inspect near duplicates as well as exact duplicates.
2. Reserve a new holdout that has not guided prior fixes. The existing published test sample has already informed development and cannot provide a fresh final answer. Use validation alone to select loss weights, thresholds, and cleanup.
3. Evaluate both trained arms through the same frozen region stage in original coordinates. For region-stage changes, add a same-wall control. Report footprints or separators as assisted inputs when supplied; keep truth-input diagnostics separate.
4. Preserve failed cases, paired per-drawing results, runtimes, and the configuration of every run. Report paired uncertainty by drawing group and variation across seeds. Keep data, annotations, and research weights private; publish the protocol and aggregate findings.

## Ask three different questions of the result

| Evidence | Question | Limit |
| --- | --- | --- |
| Pixel IoU, precision/recall, and skeleton coverage | Are wall pixels and fine structures recovered? | Coverage does not prove correct paths or room separation |
| Region PQ/F1 and split/merge analysis | Are the intended spaces preserved? | Matching rules and background policy affect the scores |
| Reviewed graph junctions, edges, loops, and connectivity pairs | Do the required wall connections exist without spurious joins? | This requires graph-level truth that current evaluations do not contain |

For additional split/merge evaluation, scikit-image's [variation-of-information API](https://scikit-image.org/docs/stable/api/skimage.metrics.html#skimage.metrics.variation_of_information) and [official example](https://scikit-image.org/docs/stable/auto_examples/segmentation/plot_metrics.html) distinguish oversegmentation from undersegmentation. With truth first and prediction second, the outputs are `H(prediction | truth)` for splitting and `H(truth | prediction)` for merging. Smaller is better. This is a proposed evaluation addition, not a metric already measured in the validation table.

Declare which pixels enter that calculation. Ignoring truth label 0 omits false positive regions in truth background, so separately retain background-transfer counts and review them. Comparing two predictions measures disagreement; it becomes error measurement only when one side is independent truth. Test ID permutations and known split/merge counterexamples before using a new score.

## Decide whether to adopt the change

Before running the holdout, record the minimum useful instance improvement, tolerated pixel-quality change, limits on false closures and lost interiors, and compute budget. Use those requirements to decide:

- **Go:** held-out evidence meets the predefined requirements, with uncertainty and seed variation reported. Explain which failure modes improved and where the result applies.
- **No-go:** improved overlap or skeleton coverage comes with unacceptable room merges, disappearing interiors, false closures, or cost. Keep the existing default and publish the failed hypothesis.
- **Inconclusive:** the uncertainty is too wide or the required annotations are missing. Report that limitation and gather the evidence needed for the next decision.

The lasting technical value will come from consistent annotation definitions, verified connectivity, and diagnostics that connect a model change to an affected space. A named loss function is a starting point; a result another developer can inspect and trust is the useful outcome.
