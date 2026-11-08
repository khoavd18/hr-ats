# Computer Vision Metrics

## Definitions

| Metric | Meaning | Watch out |
|---|---|---|
| IoU | Overlap ÷ union of predicted and true region | A prediction counts as a true positive only above the IoU threshold |
| Precision | TP ÷ (TP + FP) at a confidence threshold | Depends on the threshold |
| Recall | TP ÷ (TP + FN) at a confidence threshold | Depends on the threshold and on max detections per image |
| AP (per class) | Area under the precision–recall curve | Interpolation differs: VOC 11-point, VOC 2010+ all-points, COCO 101-point |
| mAP50 | Mean AP over classes at IoU 0.50 | Lenient on localization |
| mAP50-95 | Mean AP over IoU 0.50:0.05:0.95 (COCO "AP") | Rewards tight boxes; usually much lower than mAP50 |
| AP small/medium/large | COCO AP by absolute object area (< 32², < 96², ≥ 96² pixels) | Uses original image size, not the training size |
| Top-1 accuracy | Share of images whose highest-scoring class is correct (classification) | Misleading with class imbalance; add balanced accuracy and per-class recall |
| Mask mAP, mIoU | Segmentation versions of AP and IoU | mIoU averages over classes; state whether background is included |

## Evaluator differences

- Different tools give different numbers for the same predictions (interpolation, max detections, crowd handling, IoU computed on pixel-inclusive or exclusive coordinates). Never compare a number from one evaluator with a number from another.
- Many framework `val` commands use a very low confidence threshold (for example 0.001) for mAP. That is correct for mAP and wrong for describing deployed behaviour.
- Rectangular or letterboxed validation images, image size and NMS IoU all change the score. Record them.

## Threshold selection

```
On validation predictions, for each candidate confidence threshold t:
    compute precision(t), recall(t), F1(t) per class and overall
Choose t by the stated rule, e.g. "max F1", or "highest precision with recall ≥ R" (R is UNKNOWN until the owner sets it)
Freeze t, then report precision/recall/F1 at t on test
```

## Bootstrap interval over images

```python
import numpy as np

def bootstrap_ci(image_ids, metric_fn, n=1000, seed=0, alpha=0.05):
    """metric_fn(list_of_image_ids) -> float. Resample whole images, never individual boxes."""
    rng = np.random.default_rng(seed)
    ids = np.asarray(image_ids)
    stats = [metric_fn(rng.choice(ids, size=len(ids), replace=True)) for _ in range(n)]
    return np.quantile(stats, [alpha / 2, 1 - alpha / 2])
```

For two models, draw the same resample for both and take the interval of the difference (paired bootstrap). If it contains 0, the data do not show a difference.

## Error taxonomy for detection

| Type | Definition | Usual fix |
|---|---|---|
| Localization | Right class, IoU between ~0.1 and the threshold | Box quality, image size, label consistency |
| Classification | Overlaps a different-class object | Class definitions, more boundary examples |
| Duplicate | Second detection on an already matched object | NMS settings |
| Background | No object nearby | Hard negatives, threshold |
| Missed | Object with no detection | Small objects: larger input size or tiling; occlusion: more examples |
| Label error | Prediction is right, annotation is wrong | Fix the label in a new dataset version; report how many |

## Same evaluator, different defaults

Ultralytics validates a `.pt` checkpoint with rectangular batches (`rect=True`) but switches to square letterbox for static-shape exports (ONNX, TensorRT, OpenVINO). PyTorch and exported scores then differ even when the export is perfect. For a fair comparison, run every variant with `rect=False`, the same `imgsz`, batch size, `conf` and `iou`, and report those settings. Scores from training logs are not comparable with these.
