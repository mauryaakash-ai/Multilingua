"""Local quality overrides; leaves the upstream MuseTalk checkout unchanged."""

import os
import runpy
import sys
from pathlib import Path

sys.path.insert(0, str(Path.cwd()))
import cv2
import musetalk.utils.blending as blending
import numpy as np
import torch
from musetalk.utils.face_parsing import FaceParsing
from PIL import Image

original_parse = FaceParsing.__call__


def parse(self, image, size=(512, 512), mode="raw"):
    if mode != "mouth":
        return original_parse(self, image, size, mode)
    # Limit replacement to lips and nearby skin; retain the original beard/jaw.
    with torch.no_grad():
        tensor = self.preprocess(image.resize(size, Image.BILINEAR)).unsqueeze(0)
        tensor = tensor.to(next(self.net.parameters()).device)
        labels = self.net(tensor)[0].squeeze(0).argmax(0).cpu().numpy()
    mask = np.isin(labels, [11, 12, 13]).astype(np.uint8) * 255
    if not mask.any():
        raise RuntimeError("Mouth segmentation failed; refusing an unverified blend")
    mask = cv2.dilate(mask, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (31, 31)))
    return Image.fromarray(mask)


FaceParsing.__call__ = parse

original_blend = blending.get_image


def blend(image, face, face_box, **kwargs):
    # Mild local detail enhancement, never sharpen the entire source image.
    softened = cv2.GaussianBlur(face, (0, 0), 1.0)
    face = cv2.addWeighted(face, 1.3, softened, -0.3, 0)
    return original_blend(image, face, face_box, **kwargs)


blending.get_image = blend
# Preserve the first encoded video before upstream re-encodes it during muxing.
import shutil

original_remove = os.remove


def remove(path, *args, **kwargs):
    path_obj = Path(path)
    if path_obj.name == "temp_video_audio.mp4":
        shutil.copyfile(path_obj, path_obj.parent / "detail.mp4")
    return original_remove(path, *args, **kwargs)


os.remove = remove
runpy.run_module("scripts.inference", run_name="__main__")
