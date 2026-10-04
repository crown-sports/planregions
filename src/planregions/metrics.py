import numpy as np
from scipy.optimize import linear_sum_assignment


def region_metrics(predicted: np.ndarray, target: np.ndarray, threshold: float = 0.5) -> dict:
    """Instance IoU matching independent of the arbitrary region numbering."""
    if predicted.shape != target.shape or predicted.ndim != 2:
        raise ValueError("instance maps must share the same 2D shape")
    if not 0 < threshold <= 1 or min(predicted.min(), target.min()) < 0:
        raise ValueError("nonnegative instance labels and threshold in (0, 1] required")
    if not np.issubdtype(predicted.dtype, np.integer) or not np.issubdtype(
        target.dtype, np.integer
    ):
        raise ValueError("instance maps must contain integers")
    # Count all intersections in one pass rather than scanning the image for
    # every region pair. Background still contributes to each instance's area.
    pred_all, pred_inverse = np.unique(predicted, return_inverse=True)
    true_all, true_inverse = np.unique(target, return_inverse=True)
    intersections = np.bincount(
        pred_inverse.ravel() * len(true_all) + true_inverse.ravel(),
        minlength=len(pred_all) * len(true_all),
    ).reshape(len(pred_all), len(true_all))
    pred_foreground, true_foreground = pred_all != 0, true_all != 0
    pred_ids, true_ids = pred_all[pred_foreground], true_all[true_foreground]
    shared = intersections[np.ix_(pred_foreground, true_foreground)]
    union = (
        intersections.sum(axis=1)[pred_foreground, None]
        + intersections.sum(axis=0)[None, true_foreground]
        - shared
    )
    scores = np.divide(shared, union, out=np.zeros(shared.shape, np.float64), where=union > 0)
    # Qualified-match count dominates; IoU across all assigned pairs breaks ties.
    reward = (scores >= threshold) * (min(scores.shape, default=0) + 1) + scores
    rows, cols = linear_sum_assignment(-reward)
    matched = scores[rows, cols]
    matched = matched[matched >= threshold]
    tp = len(matched)
    fp, fn = len(pred_ids) - tp, len(true_ids) - tp
    denominator = tp + 0.5 * fp + 0.5 * fn
    foreground_union = int(((predicted > 0) | (target > 0)).sum())
    return {
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "iou_threshold": threshold,
        "matched_mean_iou": float(matched.mean()) if tp else None,
        "instance_f1": tp / denominator if denominator else 1.0,
        "panoptic_quality": float(matched.sum() / denominator) if denominator else 1.0,
        "foreground_iou": float(((predicted > 0) & (target > 0)).sum() / foreground_union)
        if foreground_union
        else 1.0,
    }
