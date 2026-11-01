#!/usr/bin/env python3
"""Generate repo-native macropad mechanical CAD and exploded-view media.

The KiCad PCB is the source of truth. This script reads its Edge.Cuts,
footprints, drilled pads, switch centers, Pico envelope, and mounting holes;
then generates a printable enclosure, switch plate, component proxies, and a
technical exploded assembly animation.
"""

from __future__ import annotations

import argparse
import math
import os
import re
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

os.environ.setdefault(
    "MPLCONFIGDIR", str(Path(tempfile.gettempdir()) / "rp2040-macropad-mpl")
)

import cadquery as cq
import matplotlib
import numpy as np
import trimesh
from PIL import Image

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d.art3d import Poly3DCollection


REPO_ROOT = Path(__file__).resolve().parents[2]
PCB_PATH = REPO_ROOT / "hardware" / "MacroPad.kicad_pcb"
MECHANICAL_DIR = Path(__file__).resolve().parent
STL_DIR = MECHANICAL_DIR / "stl"
STEP_DIR = MECHANICAL_DIR / "step"
IMAGE_DIR = REPO_ROOT / "docs" / "images"

PCB_THICKNESS_MM = 1.6
PLATE_THICKNESS_MM = 1.5
PLATE_CLEARANCE_MM = 5.0
CASE_FLOOR_MM = 2.4
PCB_UNDERSIDE_Z_MM = 6.0
PLATE_UNDERSIDE_Z_MM = PCB_UNDERSIDE_Z_MM + PCB_THICKNESS_MM + PLATE_CLEARANCE_MM
CASE_WALL_MM = 3.0
CASE_MARGIN_MM = 3.0
MX_PLATE_CUTOUT_MM = 14.0


@dataclass(frozen=True)
class Pad:
    x: float
    y: float
    drill_x: float
    drill_y: float


@dataclass(frozen=True)
class Footprint:
    library_name: str
    reference: str
    x: float
    y: float
    rotation_deg: float
    pads: tuple[Pad, ...]


@dataclass(frozen=True)
class BoardData:
    minimum_x: float
    minimum_y: float
    maximum_x: float
    maximum_y: float
    footprints: tuple[Footprint, ...]

    @property
    def width(self) -> float:
        return self.maximum_x - self.minimum_x

    @property
    def height(self) -> float:
        return self.maximum_y - self.minimum_y

    @property
    def center_x(self) -> float:
        return (self.minimum_x + self.maximum_x) / 2.0

    @property
    def center_y(self) -> float:
        return (self.minimum_y + self.maximum_y) / 2.0


def extract_blocks(text: str, prefix: str) -> list[str]:
    """Return balanced S-expression blocks while ignoring parentheses in strings."""
    blocks: list[str] = []
    cursor = 0
    while True:
        start = text.find(prefix, cursor)
        if start < 0:
            return blocks
        depth = 0
        quoted = False
        escaped = False
        for index in range(start, len(text)):
            character = text[index]
            if quoted:
                if escaped:
                    escaped = False
                elif character == "\\":
                    escaped = True
                elif character == '"':
                    quoted = False
                continue
            if character == '"':
                quoted = True
            elif character == "(":
                depth += 1
            elif character == ")":
                depth -= 1
                if depth == 0:
                    blocks.append(text[start : index + 1])
                    cursor = index + 1
                    break
        else:
            raise ValueError(f"unterminated KiCad block beginning with {prefix!r}")


def parse_at(block: str) -> tuple[float, float, float]:
    match = re.search(
        r"\(at\s+(-?[0-9.]+)\s+(-?[0-9.]+)(?:\s+(-?[0-9.]+))?\)", block
    )
    if not match:
        return 0.0, 0.0, 0.0
    return float(match.group(1)), float(match.group(2)), float(match.group(3) or 0.0)


def parse_pads(footprint_block: str) -> tuple[Pad, ...]:
    pads: list[Pad] = []
    for pad_block in extract_blocks(footprint_block, "(pad "):
        drill = re.search(
            r"\(drill(?:\s+oval)?\s+([0-9.]+)(?:\s+([0-9.]+))?\)", pad_block
        )
        if not drill:
            continue
        local_x, local_y, _ = parse_at(pad_block)
        drill_x = float(drill.group(1))
        drill_y = float(drill.group(2) or drill.group(1))
        pads.append(Pad(local_x, local_y, drill_x, drill_y))
    return tuple(pads)


def parse_board(path: Path) -> BoardData:
    text = path.read_text(encoding="utf-8")
    edge_rect = None
    for rectangle in extract_blocks(text, "(gr_rect"):
        if '(layer "Edge.Cuts")' in rectangle:
            edge_rect = rectangle
            break
    if edge_rect is None:
        raise ValueError("no rectangular Edge.Cuts outline found")

    start = re.search(r"\(start\s+(-?[0-9.]+)\s+(-?[0-9.]+)\)", edge_rect)
    end = re.search(r"\(end\s+(-?[0-9.]+)\s+(-?[0-9.]+)\)", edge_rect)
    if not start or not end:
        raise ValueError("could not parse Edge.Cuts rectangle")
    x_values = (float(start.group(1)), float(end.group(1)))
    y_values = (float(start.group(2)), float(end.group(2)))

    footprints: list[Footprint] = []
    for block in extract_blocks(text, "(footprint "):
        name = re.match(r'\(footprint\s+"([^"]+)"', block)
        reference = re.search(r'\(property\s+"Reference"\s+"([^"]+)"', block)
        if not name or not reference:
            continue
        x_pos, y_pos, rotation = parse_at(block)
        footprints.append(
            Footprint(
                name.group(1),
                reference.group(1),
                x_pos,
                y_pos,
                rotation,
                parse_pads(block),
            )
        )

    return BoardData(
        min(x_values),
        min(y_values),
        max(x_values),
        max(y_values),
        tuple(footprints),
    )


def board_xy(board: BoardData, x_pos: float, y_pos: float) -> tuple[float, float]:
    """Convert KiCad coordinates to centered CAD coordinates with Y pointing up."""
    return x_pos - board.center_x, board.center_y - y_pos


def pad_board_position(footprint: Footprint, pad: Pad) -> tuple[float, float]:
    radians = math.radians(footprint.rotation_deg)
    rotated_x = pad.x * math.cos(radians) - pad.y * math.sin(radians)
    rotated_y = pad.x * math.sin(radians) + pad.y * math.cos(radians)
    return footprint.x + rotated_x, footprint.y + rotated_y


def by_reference(board: BoardData, reference: str) -> Footprint:
    for footprint in board.footprints:
        if footprint.reference == reference:
            return footprint
    raise ValueError(f"missing footprint {reference}")


def switch_centers(board: BoardData) -> list[tuple[str, float, float]]:
    centers: list[tuple[str, float, float]] = []
    for reference in ("SW1", "SW2", "SW3", "SW4"):
        footprint = by_reference(board, reference)
        center_pad = max(footprint.pads, key=lambda pad: pad.drill_x * pad.drill_y)
        global_x, global_y = pad_board_position(footprint, center_pad)
        local_x, local_y = board_xy(board, global_x, global_y)
        centers.append((reference, local_x, local_y))
    return centers


def mounting_centers(board: BoardData) -> list[tuple[float, float]]:
    return [
        board_xy(board, by_reference(board, reference).x, by_reference(board, reference).y)
        for reference in ("H1", "H2", "H3", "H4")
    ]


def pico_center_and_size(board: BoardData) -> tuple[float, float, float, float]:
    pico = by_reference(board, "A1")
    pad_positions = [pad_board_position(pico, pad) for pad in pico.pads]
    minimum_x = min(position[0] for position in pad_positions)
    maximum_x = max(position[0] for position in pad_positions)
    minimum_y = min(position[1] for position in pad_positions)
    maximum_y = max(position[1] for position in pad_positions)
    center_x, center_y = board_xy(
        board, (minimum_x + maximum_x) / 2.0, (minimum_y + maximum_y) / 2.0
    )
    return center_x, center_y, maximum_x - minimum_x + 4.0, maximum_y - minimum_y + 4.0


def cylinder(
    radius: float,
    height: float,
    center: tuple[float, float, float],
    direction: tuple[float, float, float] = (0.0, 0.0, 1.0),
) -> cq.Workplane:
    direction_vector = cq.Vector(*direction)
    center_vector = cq.Vector(*center)
    start = center_vector - direction_vector.multiply(height / 2.0)
    solid = cq.Solid.makeCylinder(radius, height, start, direction_vector)
    return cq.Workplane("XY").newObject([solid])


def box(
    length: float,
    width: float,
    height: float,
    center: tuple[float, float, float],
) -> cq.Workplane:
    return cq.Workplane("XY").box(length, width, height).translate(center)


def build_pcb(board: BoardData) -> cq.Workplane:
    part = box(board.width, board.height, PCB_THICKNESS_MM, (0.0, 0.0, PCB_THICKNESS_MM / 2.0))
    holes: set[tuple[float, float, float]] = set()
    for footprint in board.footprints:
        for pad in footprint.pads:
            global_x, global_y = pad_board_position(footprint, pad)
            local_x, local_y = board_xy(board, global_x, global_y)
            diameter = max(pad.drill_x, pad.drill_y)
            holes.add((round(local_x, 4), round(local_y, 4), round(diameter, 4)))
    for x_pos, y_pos, diameter in sorted(holes):
        part = part.cut(cylinder(diameter / 2.0, 4.0, (x_pos, y_pos, 1.0)))
    return part.clean()


def build_bottom_enclosure(board: BoardData) -> cq.Workplane:
    outer_width = board.width + 2.0 * CASE_MARGIN_MM
    outer_height = board.height + 2.0 * CASE_MARGIN_MM
    case_height = PLATE_UNDERSIDE_Z_MM
    inner_width = board.width + 1.0
    inner_height = board.height + 1.0

    outer = box(outer_width, outer_height, case_height, (0.0, 0.0, case_height / 2.0))
    outer = outer.edges("|Z").fillet(4.0)
    cavity_height = case_height - CASE_FLOOR_MM + 1.0
    cavity = box(
        inner_width,
        inner_height,
        cavity_height,
        (0.0, 0.0, CASE_FLOOR_MM + cavity_height / 2.0),
    )
    part = outer.cut(cavity)

    for x_pos, y_pos in mounting_centers(board):
        post = cylinder(
            3.5,
            PCB_UNDERSIDE_Z_MM - CASE_FLOOR_MM,
            (x_pos, y_pos, (PCB_UNDERSIDE_Z_MM + CASE_FLOOR_MM) / 2.0),
        )
        part = part.union(post)
        part = part.cut(cylinder(1.1, PCB_UNDERSIDE_Z_MM + 2.0, (x_pos, y_pos, PCB_UNDERSIDE_Z_MM / 2.0)))
    return part.clean()


def build_switch_plate(board: BoardData) -> cq.Workplane:
    outer_width = board.width + 2.0 * CASE_MARGIN_MM
    outer_height = board.height + 2.0 * CASE_MARGIN_MM
    part = box(
        outer_width,
        outer_height,
        PLATE_THICKNESS_MM,
        (0.0, 0.0, PLATE_THICKNESS_MM / 2.0),
    )
    part = part.edges("|Z").fillet(4.0)

    for _, x_pos, y_pos in switch_centers(board):
        cutout = box(
            MX_PLATE_CUTOUT_MM,
            MX_PLATE_CUTOUT_MM,
            PLATE_THICKNESS_MM + 2.0,
            (x_pos, y_pos, PLATE_THICKNESS_MM / 2.0),
        )
        part = part.cut(cutout)

    pico_x, pico_y, pico_width, pico_height = pico_center_and_size(board)
    pico_access = box(
        pico_width,
        pico_height,
        PLATE_THICKNESS_MM + 2.0,
        (pico_x, pico_y, PLATE_THICKNESS_MM / 2.0),
    )
    part = part.cut(pico_access)

    for x_pos, y_pos in mounting_centers(board):
        part = part.cut(cylinder(1.1, PLATE_THICKNESS_MM + 2.0, (x_pos, y_pos, PLATE_THICKNESS_MM / 2.0)))
    return part.clean()


def build_switch_proxy() -> cq.Workplane:
    lower = box(15.6, 15.6, 5.0, (0.0, 0.0, 2.5))
    upper = box(15.6, 15.6, 5.5, (0.0, 0.0, 7.75))
    stem_vertical = box(1.3, 4.1, 3.0, (0.0, 0.0, 12.0))
    stem_horizontal = box(4.1, 1.3, 3.0, (0.0, 0.0, 12.0))
    center_peg = cylinder(1.9, 5.0, (0.0, 0.0, -1.5))
    pin_one = cylinder(0.65, 5.0, (2.54, -5.08, -1.5))
    pin_two = cylinder(0.65, 5.0, (-3.81, -2.54, -1.5))
    return lower.union(upper).union(stem_vertical).union(stem_horizontal).union(center_peg).union(pin_one).union(pin_two).clean()


def build_keycap_proxy() -> cq.Workplane:
    return (
        cq.Workplane("XY")
        .rect(18.0, 18.0)
        .workplane(offset=8.0)
        .rect(16.0, 16.0)
        .loft(combine=True)
        .clean()
    )


def build_diode_proxy() -> cq.Workplane:
    lead = cylinder(0.28, 7.62, (0.0, 0.0, 1.0), (1.0, 0.0, 0.0))
    body = cylinder(1.0, 4.0, (0.0, 0.0, 1.0), (1.0, 0.0, 0.0))
    return lead.union(body).clean()


def build_pico_proxy() -> cq.Workplane:
    board = box(21.0, 51.0, 1.0, (0.0, 0.0, 0.5))
    left_header = box(2.2, 48.5, 2.4, (-8.89, 0.0, 1.8))
    right_header = box(2.2, 48.5, 2.4, (8.89, 0.0, 1.8))
    processor = box(7.0, 7.0, 1.2, (0.0, 2.0, 1.6))
    usb = box(8.0, 6.0, 3.0, (0.0, 25.0, 2.0))
    return board.union(left_header).union(right_header).union(processor).union(usb).clean()


def export_part(shape: cq.Workplane, name: str, require_single_body: bool = True) -> None:
    STL_DIR.mkdir(parents=True, exist_ok=True)
    STEP_DIR.mkdir(parents=True, exist_ok=True)
    stl_path = STL_DIR / f"{name}.stl"
    step_path = STEP_DIR / f"{name}.step"
    solid = shape.val()
    if not solid.isValid():
        raise RuntimeError(f"{name}: OpenCascade geometry is invalid")
    solid.exportStl(
        str(stl_path),
        tolerance=0.08,
        angularTolerance=0.08,
        ascii=False,
        relative=True,
        parallel=True,
    )
    cq.exporters.export(shape, str(step_path))

    mesh = trimesh.load_mesh(stl_path, process=True)
    if not isinstance(mesh, trimesh.Trimesh) or not mesh.is_watertight or not mesh.is_winding_consistent:
        raise RuntimeError(f"{name}: exported STL is not a watertight, consistently wound mesh")
    if require_single_body and mesh.body_count != 1:
        raise RuntimeError(f"{name}: expected one printable body, found {mesh.body_count}")
    dimensions = mesh.extents
    print(
        f"  {stl_path.relative_to(REPO_ROOT)}: "
        f"{dimensions[0]:.1f} x {dimensions[1]:.1f} x {dimensions[2]:.1f} mm"
    )


def transformed_mesh(path: Path, translations: Iterable[tuple[float, float, float]]) -> trimesh.Trimesh:
    source = trimesh.load_mesh(path, process=True)
    meshes: list[trimesh.Trimesh] = []
    for translation in translations:
        instance = source.copy()
        instance.apply_translation(translation)
        meshes.append(instance)
    return trimesh.util.concatenate(meshes)


def component_meshes(board: BoardData) -> dict[str, trimesh.Trimesh]:
    switch_positions = [(x_pos, y_pos, 0.0) for _, x_pos, y_pos in switch_centers(board)]
    keycap_positions = [(x_pos, y_pos, 0.0) for _, x_pos, y_pos in switch_centers(board)]

    diode_positions: list[tuple[float, float, float]] = []
    for reference in ("D1", "D2", "D3", "D4"):
        diode = by_reference(board, reference)
        pad_positions = [pad_board_position(diode, pad) for pad in diode.pads]
        center_x = sum(position[0] for position in pad_positions) / len(pad_positions)
        center_y = sum(position[1] for position in pad_positions) / len(pad_positions)
        local_x, local_y = board_xy(board, center_x, center_y)
        diode_positions.append((local_x, local_y, 0.0))

    pico_x, pico_y, _, _ = pico_center_and_size(board)
    return {
        "case": trimesh.load_mesh(STL_DIR / "bottom_enclosure.stl", process=True),
        "pcb": trimesh.load_mesh(STL_DIR / "pcb_from_kicad.stl", process=True),
        "diodes": transformed_mesh(STL_DIR / "diode_proxy.stl", diode_positions),
        "pico": transformed_mesh(STL_DIR / "pico_proxy.stl", [(pico_x, pico_y, 0.0)]),
        "plate": trimesh.load_mesh(STL_DIR / "switch_plate.stl", process=True),
        "switches": transformed_mesh(STL_DIR / "mx_switch_proxy.stl", switch_positions),
        "keycaps": transformed_mesh(STL_DIR / "keycap_proxy.stl", keycap_positions),
    }


def render_media(board: BoardData, create_animation: bool) -> None:
    meshes = component_meshes(board)
    colors = {
        "case": "#35445c",
        "pcb": "#b51f36",
        "diodes": "#f0b44d",
        "pico": "#3ca48d",
        "plate": "#b9c4d2",
        "switches": "#272e3a",
        "keycaps": "#edf2f7",
    }
    assembled_z = {
        "case": 0.0,
        "pcb": PCB_UNDERSIDE_Z_MM,
        "diodes": PCB_UNDERSIDE_Z_MM + PCB_THICKNESS_MM,
        "pico": PCB_UNDERSIDE_Z_MM + PCB_THICKNESS_MM,
        "plate": PLATE_UNDERSIDE_Z_MM,
        "switches": PCB_UNDERSIDE_Z_MM + PCB_THICKNESS_MM,
        "keycaps": PCB_UNDERSIDE_Z_MM + PCB_THICKNESS_MM + 13.5,
    }
    exploded_extra_z = {
        "case": 0.0,
        "pcb": 19.0,
        "diodes": 19.0,
        "pico": 19.0,
        "plate": 48.0,
        "switches": 72.0,
        "keycaps": 93.0,
    }

    fig = plt.figure(figsize=(12.8, 7.2), dpi=100, facecolor="#08111f")
    ax = fig.add_subplot(111, projection="3d", facecolor="#08111f")
    ax.set_proj_type("ortho")
    ax.view_init(elev=24.0, azim=-48.0)
    ax.set_xlim(-60.0, 60.0)
    ax.set_ylim(-73.0, 73.0)
    ax.set_zlim(0.0, 125.0)
    ax.set_box_aspect((1.15, 1.5, 1.55))
    ax.set_axis_off()

    collections: dict[str, Poly3DCollection] = {}
    base_triangles: dict[str, np.ndarray] = {}
    for name, mesh in meshes.items():
        triangles = np.asarray(mesh.triangles)
        base_triangles[name] = triangles
        collection = Poly3DCollection(
            triangles,
            facecolor=colors[name],
            edgecolor="#d7e5f5" if name in {"plate", "keycaps"} else "#111a28",
            linewidth=0.08,
            alpha=0.98,
        )
        ax.add_collection3d(collection)
        collections[name] = collection

    for x_pos, y_pos in mounting_centers(board):
        ax.plot(
            [x_pos, x_pos],
            [y_pos, y_pos],
            [0.0, 116.0],
            color="#4fd1ff",
            linewidth=0.8,
            linestyle="--",
            alpha=0.5,
        )

    fig.text(
        0.055,
        0.92,
        "RP2040 2×2 MACROPAD",
        color="#f4f8ff",
        fontsize=22,
        fontweight="bold",
    )
    fig.text(
        0.055,
        0.875,
        "EXPLODED ASSEMBLY  •  PCB-DERIVED PARAMETRIC CAD",
        color="#58d5ff",
        fontsize=10,
        fontweight="bold",
    )
    legend = [
        ("05", "1u KEYCAPS", colors["keycaps"]),
        ("04", "MX SWITCHES", colors["switches"]),
        ("03", "1.5 mm SWITCH PLATE", colors["plate"]),
        ("02", "PCB + DIODES + PICO", colors["pcb"]),
        ("01", "BOTTOM ENCLOSURE", colors["case"]),
    ]
    for index, (number, label, color) in enumerate(legend):
        y_pos = 0.72 - index * 0.065
        fig.text(0.065, y_pos, number, color="#58d5ff", fontsize=10, fontweight="bold")
        fig.text(0.10, y_pos, "■", color=color, fontsize=12)
        fig.text(0.122, y_pos, label, color="#d8e2ef", fontsize=9)
    fig.text(
        0.055,
        0.315,
        "NO STABILIZERS",
        color="#f0b44d",
        fontsize=10,
        fontweight="bold",
    )
    fig.text(
        0.055,
        0.285,
        "All four keys are 1u MX footprints.",
        color="#aebdce",
        fontsize=8.5,
    )
    status_text = fig.text(0.055, 0.11, "", color="#58d5ff", fontsize=10, fontweight="bold")
    fig.text(
        0.055,
        0.055,
        "SOURCE  hardware/MacroPad.kicad_pcb  •  58 × 97 mm  •  M2 ALIGNMENT GUIDES",
        color="#71859d",
        fontsize=8,
    )

    def draw(separation: float, output_path: Path) -> None:
        for name, collection in collections.items():
            z_offset = assembled_z[name] + exploded_extra_z[name] * separation
            translation = np.array([0.0, 0.0, z_offset])
            collection.set_verts(base_triangles[name] + translation)
        if separation > 0.67:
            status_text.set_text("EXPLODED • FOLLOW LAYERS 01 → 05")
        elif separation > 0.08:
            status_text.set_text("ALIGNING M2 HOLES + MX SWITCH PINS")
        else:
            status_text.set_text("ASSEMBLED STACK")
        fig.savefig(output_path, facecolor=fig.get_facecolor(), bbox_inches=None)

    IMAGE_DIR.mkdir(parents=True, exist_ok=True)
    preview_path = IMAGE_DIR / "macropad-exploded-assembly.png"
    draw(1.0, preview_path)
    print(f"  {preview_path.relative_to(REPO_ROOT)}")

    if not create_animation:
        plt.close(fig)
        return

    def smoothstep(value: float) -> float:
        return value * value * (3.0 - 2.0 * value)

    separations = [1.0] * 10
    separations += [1.0 - smoothstep(index / 31.0) for index in range(32)]
    separations += [0.0] * 12
    separations += [smoothstep(index / 31.0) for index in range(32)]

    with tempfile.TemporaryDirectory(prefix="macropad-assembly-") as temporary:
        frame_directory = Path(temporary)
        for index, separation in enumerate(separations):
            draw(separation, frame_directory / f"frame-{index:03d}.png")

        ffmpeg = shutil.which("ffmpeg")
        if ffmpeg is None:
            raise RuntimeError("ffmpeg is required to encode the MP4 animation")
        video_path = IMAGE_DIR / "macropad-exploded-assembly.mp4"
        subprocess.run(
            [
                ffmpeg,
                "-y",
                "-loglevel",
                "error",
                "-framerate",
                "24",
                "-i",
                str(frame_directory / "frame-%03d.png"),
                "-c:v",
                "libx264",
                "-crf",
                "20",
                "-pix_fmt",
                "yuv420p",
                "-movflags",
                "+faststart",
                str(video_path),
            ],
            check=True,
        )

        gif_frames: list[Image.Image] = []
        for index in range(0, len(separations), 2):
            with Image.open(frame_directory / f"frame-{index:03d}.png") as image:
                gif_frames.append(image.resize((960, 540), Image.Resampling.LANCZOS).convert("P", palette=Image.Palette.ADAPTIVE))
        gif_path = IMAGE_DIR / "macropad-exploded-assembly.gif"
        gif_frames[0].save(
            gif_path,
            save_all=True,
            append_images=gif_frames[1:],
            duration=84,
            loop=0,
            optimize=True,
        )
        print(f"  {video_path.relative_to(REPO_ROOT)}")
        print(f"  {gif_path.relative_to(REPO_ROOT)}")

    plt.close(fig)


def validate_source(board: BoardData) -> None:
    if not math.isclose(board.width, 58.0, abs_tol=0.01) or not math.isclose(board.height, 97.0, abs_tol=0.01):
        raise RuntimeError(
            f"unexpected board size {board.width:.2f} x {board.height:.2f} mm"
        )
    switches = switch_centers(board)
    x_positions = sorted({round(center[1], 2) for center in switches})
    y_positions = sorted({round(center[2], 2) for center in switches})
    if len(x_positions) != 2 or len(y_positions) != 2:
        raise RuntimeError("switches no longer form a 2x2 grid")
    if not math.isclose(x_positions[1] - x_positions[0], 19.05, abs_tol=0.01):
        raise RuntimeError("unexpected horizontal switch pitch")
    if not math.isclose(y_positions[1] - y_positions[0], 19.05, abs_tol=0.01):
        raise RuntimeError("unexpected vertical switch pitch")
    if len(mounting_centers(board)) != 4:
        raise RuntimeError("expected four M2 mounting holes")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--skip-animation",
        action="store_true",
        help="generate CAD and the exploded PNG without encoding MP4/GIF",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    board = parse_board(PCB_PATH)
    validate_source(board)
    print(
        f"Parsed {PCB_PATH.relative_to(REPO_ROOT)}: "
        f"{board.width:.1f} x {board.height:.1f} mm, "
        f"{len(board.footprints)} footprints"
    )

    parts = {
        "bottom_enclosure": (build_bottom_enclosure(board), True),
        "switch_plate": (build_switch_plate(board), True),
        "pcb_from_kicad": (build_pcb(board), True),
        "mx_switch_proxy": (build_switch_proxy(), True),
        "keycap_proxy": (build_keycap_proxy(), True),
        "diode_proxy": (build_diode_proxy(), True),
        "pico_proxy": (build_pico_proxy(), True),
    }
    print("Exporting CAD:")
    for name, (shape, single_body) in parts.items():
        export_part(shape, name, require_single_body=single_body)

    print("Rendering assembly media:")
    render_media(board, create_animation=not args.skip_animation)
    print("Generation complete.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
